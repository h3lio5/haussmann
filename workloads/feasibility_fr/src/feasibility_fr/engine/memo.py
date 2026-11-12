"""The feasibility memo: its sections, how ledger facts become its inputs, and who writes it."""

import datetime as dt
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from feasibility_fr.engine.spec import RequiredFact
from feasibility_fr.french import format_date, format_value
from haussmann.buildkit.build import Built, Cache, build, fill, listing
from haussmann.buildkit.spec import Section, Spec
from haussmann.buildkit.targets import Input, Target, targets
from haussmann.buildkit.writer import Ask, prose_author
from haussmann.coretypes.values import Quantity, Schema, Value, normalize
from haussmann.ledger.ledger import Fact, Ledger
from haussmann.llmkit.client import LLMClient, Message, Request, Response
from haussmann.verify.settle import Settled, groups, settled

ISSUE = "issue"
OPEN = "open"
PROMPT_VERSION = "2"
ANSWER_MAX_TOKENS = 800
FLAG_MARK = " (à vérifier, voir « Points à résoudre »)"
NOTHING = "Aucun élément."

MEMO = Spec(
    "feasibility_memo",
    "1",
    (
        Section(
            "site",
            "Le site et sa propriété",
            "prose",
            ("parcel_ref", "land_area", "owner", "zone"),
            "Situer le terrain : sa référence, sa contenance, son propriétaire, son zonage.",
        ),
        Section(
            "rules",
            "Règles d'urbanisme",
            "prose",
            (
                "max_height",
                "max_levels",
                "footprint_limit",
                "street_setback",
                "planning_certificate_date",
            ),
            "Énoncer les règles applicables au terrain, puis le certificat d'urbanisme.",
        ),
        Section(
            "risks",
            "Risques et études",
            "prose",
            ("flood_risk", "soil_study", "pollution_study"),
            "Dire ce que le dossier établit sur les risques et les études disponibles.",
        ),
        Section(
            "occupancy",
            "Occupation et revenus",
            "prose",
            ("occupancy", "annual_rent", "lease_end"),
            "Présenter chaque occupation avec son loyer et son échéance, puis le total.",
        ),
        Section(
            "areas",
            "Surfaces",
            "prose",
            ("floor_area",),
            "Donner les surfaces par partie, puis le total.",
        ),
        Section(
            "price",
            "Prix",
            "prose",
            ("asking_price",),
            "Donner le prix par lot, puis le total.",
        ),
        Section("issues", "Points à résoudre", "listing", (ISSUE,)),
        Section("open", "Questions ouvertes", "listing", (OPEN,)),
    ),
)

INSTRUCTIONS = """\
Vous rédigez une section d'une note de faisabilité immobilière destinée à un professionnel.

Règles :
- Chaque fait vous est donné par un nom entre accolades, avec sa valeur. Là où la valeur doit \
apparaître, écrivez le nom entre accolades, par exemple {site.zone}. N'écrivez jamais la \
valeur vous-même.
- N'écrivez aucun chiffre, ni en chiffres ni en lettres, et ne reformulez pas une valeur \
avec vos mots : écrivez son nom entre accolades.
- Utilisez chaque fait une fois. Écrivez une phrase courte par fait, ou une phrase pour deux \
faits liés, et rien d'autre.
- N'ajoutez aucune information qui ne figure pas dans les faits : ni commentaire, ni \
précision, ni source, ni conséquence. Une section qui n'a qu'un fait tient en une phrase.
- Un fait marqué « signalé » s'écrit comme les autres. Ne le commentez pas : la mention de \
vérification est ajoutée automatiquement après sa valeur.
- Ton neutre. Pas d'introduction, pas de conclusion, pas d'avis.

Répondez en JSON : {"sentences": ["...", "..."]}.
"""

_SENTENCES = {
    "type": "object",
    "properties": {"sentences": {"type": "array", "items": {"type": "string"}}},
    "required": ["sentences"],
    "additionalProperties": False,
}

_RULES_FR: Mapping[str, str] = {
    "recomputed from its parts": "valeur recalculée à partir de ses composantes",
    "higher-authority source": "source de plus forte autorité",
    "later source": "source la plus récente",
    "ended before the review date": "échéance dépassée à la date de revue",
}
_EXPIRED = re.compile(r"valid for (\d+) months, expired on (\d{4}-\d{2}-\d{2})")


@dataclass(frozen=True, slots=True)
class Bound:
    """An input of the memo with what a reviewer needs to trace it: its label and sources."""

    input: Input
    label: str
    citations: tuple[tuple[str, str | None], ...] = ()


@dataclass(frozen=True, slots=True)
class Refusal:
    section_id: str
    draft: int
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Memo:
    """`refusals` lists every refused draft; a section with two wrote the plain list.

    `dropped` lists the sentences left out of drafts because they named no fact.
    """

    built: tuple[Built, ...]
    bound: tuple[Bound, ...]
    refusals: tuple[Refusal, ...]
    responses: tuple[Response, ...]
    dropped: tuple[str, ...] = ()


def _reason(reason: str) -> str:
    expired = _EXPIRED.fullmatch(reason)
    if expired is not None:
        date = format_date(dt.date.fromisoformat(expired.group(2)))
        return f"valable {expired.group(1)} mois, expiré le {date}"
    return _RULES_FR.get(reason, reason)


def _canonical(value: Value) -> str:
    if isinstance(value, Quantity):
        return f"{value.amount.normalize():f} {value.unit}"
    return value.isoformat() if isinstance(value, dt.date) else value


def _printed(fact: Fact, schema: Schema) -> str:
    attribute = schema[fact.key.attribute]
    return format_value(normalize(fact.value, attribute) or fact.value, attribute)


def _sources(facts: Sequence[Fact]) -> tuple[tuple[str, str | None], ...]:
    found = {(c.doc_id, c.locator) for fact in facts for c in fact.citations}
    return tuple(sorted(found, key=lambda place: (place[0], place[1] or "")))


def _where(fact: Fact) -> str:
    places = [f"{doc_id} {locator}" if locator else doc_id for doc_id, locator in _sources([fact])]
    return ", ".join(places)


def _issue(label: str, result: Settled, ledger: Ledger, schema: Schema) -> str:
    """One entry of the points to resolve: the values in dispute, the rule applied, the flags."""
    parts: list[str] = []
    flags = list(result.reasons)
    if result.conflict is not None:
        sides = [ledger.fact(fact_id) for fact_id in result.conflict.fact_ids]
        stated = " ; ".join(f"{_printed(side, schema)} ({_where(side)})" for side in sides)
        parts.append(f"les documents donnent {stated}")
        rule = flags.pop(0)
        if result.fact is None:
            parts.append("non tranché, à arbitrer par le relecteur")
        else:
            parts.append(f"valeur retenue : {_printed(result.fact, schema)} ({_reason(rule)})")
    parts.extend(_reason(flag) for flag in flags)
    return f"{label} : {' ; '.join(parts)}."


def bind(ledger: Ledger, asked: Sequence[RequiredFact], schema: Schema) -> tuple[Bound, ...]:
    """The inputs of the memo, read from a verified ledger.

    A settled fact gives one input for its section. A disagreement or a flag gives one more,
    for the points to resolve. A required fact with nothing settled gives an open question.
    """
    bound: list[Bound] = []
    for required in asked:
        key = required.key
        name = f"{key.subject}.{key.attribute}"
        result = settled(ledger, key, schema)
        flagged = result.conflict is not None or bool(result.reasons)
        if result.fact is None and result.conflict is None:
            text = f"{required.text} : aucun document ne l'établit."
            bound.append(Bound(Input(f"{name}#open", OPEN, text, "open"), required.text))
            continue
        if flagged:
            text = _issue(required.text, result, ledger, schema)
            sources = _sources(result.supporting)
            bound.append(Bound(Input(f"{name}#issue", ISSUE, text, text), required.text, sources))
        if result.fact is None:
            continue
        stating = result.supporting if result.conflict else groups(result.supporting, schema)[0]
        sources = _sources(stating)
        value = normalize(result.fact.value, schema[key.attribute]) or result.fact.value
        digest = json.dumps(
            [_canonical(value), sorted(result.reasons), sources], ensure_ascii=False
        )
        item = Input(name, key.attribute, _printed(result.fact, schema), digest, flagged)
        bound.append(Bound(item, required.text, sources))
    return tuple(bound)


def prompt(target: Target, labels: Mapping[str, str], reasons: Sequence[str]) -> str:
    lines = [
        f"Section : {target.section.title}",
        f"Consigne : {target.section.guidance}",
        "Faits :",
    ]
    for item in target.inputs:
        flag = " (signalé)" if item.flagged else ""
        lines.append(f'- {{{item.name}}} = "{item.text}" : {labels[item.name]}{flag}')
    if reasons:
        lines.append("\nVotre brouillon précédent a été refusé pour ces raisons :")
        lines.extend(f"- {reason}" for reason in reasons)
    return "\n".join(lines)


def read_sentences(text: str) -> list[str]:
    """The sentences of a model's answer; none when the answer is not the JSON asked for."""
    try:
        answer: object = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(answer, dict):
        return []
    sentences = cast("dict[str, object]", answer).get("sentences")
    if not isinstance(sentences, list):
        return []
    return [s for s in cast("list[object]", sentences) if isinstance(s, str)]


def memo_ask(
    client: LLMClient,
    model: str,
    sample: int,
    labels: Mapping[str, str],
    responses: list[Response],
) -> Ask:
    """One model call per draft. Every response is appended to `responses`."""

    async def ask(target: Target, reasons: Sequence[str]) -> Sequence[str]:
        messages = (
            Message("system", INSTRUCTIONS),
            Message("user", prompt(target, labels, reasons)),
        )
        request = Request(model, messages, ANSWER_MAX_TOKENS, 0.0, sample, _SENTENCES)
        response = await client.complete(request, sample=sample)
        responses.append(response)
        return read_sentences(response.text)

    return ask


async def write_memo(
    ledger: Ledger,
    asked: Sequence[RequiredFact],
    schema: Schema,
    client: LLMClient,
    model: str,
    cache: Cache,
    sample: int = 0,
    bound: Sequence[Bound] | None = None,
) -> Memo:
    """Build every section of the memo; sections whose inputs are unchanged come from `cache`.

    `bound` replaces the inputs read from the ledger, for a build after an edit.
    """
    bound = tuple(bound) if bound is not None else bind(ledger, asked, schema)
    labels = {item.input.name: item.label for item in bound}
    refusals: list[Refusal] = []
    responses: list[Response] = []

    def refused(target: Target, draft: int, reasons: Sequence[str]) -> None:
        refusals.append(Refusal(target.section.id, draft, tuple(reasons)))

    dropped: list[str] = []
    ask = memo_ask(client, model, sample, labels, responses)
    authors = {
        "prose": prose_author(
            ask,
            lambda item: labels[item.name],
            refused,
            lambda target, sentences: dropped.extend(sentences),
        ),
        "listing": listing,
    }
    environment = {"prompt": PROMPT_VERSION, "model": model}
    made = targets(MEMO, [item.input for item in bound], environment)
    built = await build(made, authors, cache)
    return Memo(built, bound, tuple(refusals), tuple(responses), tuple(dropped))


def render(memo: Memo, as_of: dt.date) -> str:
    """The memo as Markdown. Every value is printed from an input, never from a draft."""
    inputs = {item.input.name: item.input for item in memo.bound}
    titles = {section.id: section for section in MEMO.sections}
    lines = ["# Note de faisabilité", "", f"Date de revue : {format_date(as_of)}"]
    for built in memo.built:
        section = titles[built.section_id]
        lines += ["", f"## {section.title}", ""]
        filled = [fill(sentence, inputs, FLAG_MARK) for sentence in built.sentences]
        if not filled:
            lines.append(NOTHING)
        elif section.kind == "listing":
            lines.extend(f"- {entry}" for entry in filled)
        else:
            lines.append(" ".join(filled))
    return "\n".join(lines) + "\n"


def record(memo: Memo) -> dict[str, object]:
    """What a reviewer follows: section, sentence, the inputs it uses, their sources."""
    return {
        "sections": [
            {
                "id": built.section_id,
                "hash": built.hash,
                "sentences": [{"text": s.text, "uses": list(s.uses)} for s in built.sentences],
            }
            for built in memo.built
        ],
        "inputs": {
            item.input.name: {
                "text": item.input.text,
                "flagged": item.input.flagged,
                "citations": [list(citation) for citation in item.citations],
            }
            for item in memo.bound
        },
    }
