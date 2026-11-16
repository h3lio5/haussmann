"""The feasibility memo: its sections, how ledger facts become its inputs, and who writes it."""

import datetime as dt
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import cast

from haussmann.buildkit.build import Built, Cache, Sentence, build, fill, listing
from haussmann.buildkit.targets import Input, Target, targets
from haussmann.buildkit.writer import Ask, prose_author
from haussmann.coretypes.values import Quantity, Value, normalize
from haussmann.engine.workload import ISSUE, OPEN, RequiredFact, Workload
from haussmann.flow.journal import Json
from haussmann.flow.runner import Runner
from haussmann.ledger.ledger import Fact, Ledger
from haussmann.llmkit.client import LLMClient, Message, Request, Response
from haussmann.review.proposal import Proposal, checked
from haussmann.verify.settle import EXPERT, Settled, groups, settled

ANSWER_MAX_TOKENS = 800

_SENTENCES = {
    "type": "object",
    "properties": {"sentences": {"type": "array", "items": {"type": "string"}}},
    "required": ["sentences"],
    "additionalProperties": False,
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


def _reason(reason: str, workload: Workload) -> str:
    language = workload.language
    expired = _EXPIRED.fullmatch(reason)
    if expired is not None:
        date = language.format_date(dt.date.fromisoformat(expired.group(2)))
        return language.expired.format(months=expired.group(1), date=date)
    return language.reasons.get(reason, reason)


def _canonical(value: Value) -> str:
    if isinstance(value, Quantity):
        return f"{value.amount.normalize():f} {value.unit}"
    return value.isoformat() if isinstance(value, dt.date) else value


def printed(fact: Fact, workload: Workload) -> str:
    attribute = workload.schema[fact.key.attribute]
    value = normalize(fact.value, attribute) or fact.value
    return workload.language.format_value(value, attribute)


def _sources(facts: Sequence[Fact]) -> tuple[tuple[str, str | None], ...]:
    found = {(c.doc_id, c.locator) for fact in facts for c in fact.citations}
    return tuple(sorted(found, key=lambda place: (place[0], place[1] or "")))


def _where(fact: Fact) -> str:
    places = [f"{doc_id} {locator}" if locator else doc_id for doc_id, locator in _sources([fact])]
    return ", ".join(places)


def _issue(label: str, result: Settled, ledger: Ledger, workload: Workload) -> str:
    """One entry of the points to resolve: the values in dispute, the rule applied, the flags."""
    wording = workload.deliverable
    parts: list[str] = []
    flags = list(result.reasons)
    if result.conflict is not None:
        sides = [ledger.fact(fact_id) for fact_id in result.conflict.fact_ids]
        stated = wording.separator.join(
            f"{printed(side, workload)} ({_where(side)})" for side in sides
        )
        parts.append(wording.stated.format(values=stated))
        rule = flags.pop(0)
        if result.fact is None:
            parts.append(wording.undecided)
        else:
            kept = printed(result.fact, workload)
            parts.append(wording.kept.format(value=kept, reason=_reason(rule, workload)))
    parts.extend(_reason(flag, workload) for flag in flags)
    return wording.issue.format(label=label, parts=wording.separator.join(parts))


def bind(workload: Workload, ledger: Ledger, asked: Sequence[RequiredFact]) -> tuple[Bound, ...]:
    """The inputs of the memo, read from a verified ledger.

    A settled fact gives one input for its section. A disagreement or a flag gives one more,
    for the points to resolve. A required fact with nothing settled gives an open question.
    A value an expert set is a decision already made: it is not a point to resolve, and
    only a date rule can flag it.
    """
    schema = workload.schema
    bound: list[Bound] = []
    for required in asked:
        key = required.key
        name = f"{key.subject}.{key.attribute}"
        result = settled(ledger, key, schema)
        if result.fact is not None and result.fact.method == EXPERT:
            flags = result.reasons[1:] if result.conflict is not None else result.reasons
            result = replace(result, supporting=(result.fact,), conflict=None, reasons=flags)
        flagged = result.conflict is not None or bool(result.reasons)
        if result.fact is None and result.conflict is None:
            text = workload.deliverable.open_question.format(label=required.text)
            bound.append(Bound(Input(f"{name}#open", OPEN, text, "open"), required.text))
            continue
        if flagged:
            text = _issue(required.text, result, ledger, workload)
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
        item = Input(name, key.attribute, printed(result.fact, workload), digest, flagged)
        bound.append(Bound(item, required.text, sources))
    return tuple(bound)


def prompt(
    workload: Workload, target: Target, labels: Mapping[str, str], reasons: Sequence[str]
) -> str:
    texts = workload.prompts
    lines = [
        texts.writer_section.format(title=target.section.title),
        texts.writer_guidance.format(guidance=target.section.guidance),
        texts.writer_facts,
    ]
    for item in target.inputs:
        flag = texts.writer_flagged if item.flagged else ""
        lines.append(f'- {{{item.name}}} = "{item.text}" : {labels[item.name]}{flag}')
    if reasons:
        lines.append(texts.writer_refused)
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
    workload: Workload,
    client: LLMClient,
    model: str,
    sample: int,
    labels: Mapping[str, str],
    responses: list[Response],
) -> Ask:
    """One model call per draft. Every response is appended to `responses`."""

    async def ask(target: Target, reasons: Sequence[str]) -> Sequence[str]:
        messages = (
            Message("system", workload.prompts.writer),
            Message("user", prompt(workload, target, labels, reasons)),
        )
        request = Request(model, messages, ANSWER_MAX_TOKENS, 0.0, sample, _SENTENCES)
        response = await client.complete(request, sample=sample)
        responses.append(response)
        return read_sentences(response.text)

    return ask


async def write_memo(
    workload: Workload,
    ledger: Ledger,
    asked: Sequence[RequiredFact],
    client: LLMClient,
    model: str,
    cache: Cache,
    sample: int = 0,
    bound: Sequence[Bound] | None = None,
) -> Memo:
    """Build every section of the memo; sections whose inputs are unchanged come from `cache`.

    `bound` replaces the inputs read from the ledger, for a build after an edit.
    """
    bound = tuple(bound) if bound is not None else bind(workload, ledger, asked)
    labels = {item.input.name: item.label for item in bound}
    refusals: list[Refusal] = []
    responses: list[Response] = []

    def refused(target: Target, draft: int, reasons: Sequence[str]) -> None:
        refusals.append(Refusal(target.section.id, draft, tuple(reasons)))

    dropped: list[str] = []
    ask = memo_ask(workload, client, model, sample, labels, responses)
    authors = {
        "prose": prose_author(
            ask,
            lambda item: labels[item.name],
            refused,
            lambda target, sentences: dropped.extend(sentences),
        ),
        "listing": listing,
    }
    built = await build(memo_targets(workload, bound, model), authors, cache)
    return Memo(built, bound, tuple(refusals), tuple(responses), tuple(dropped))


def memo_targets(workload: Workload, bound: Sequence[Bound], model: str) -> tuple[Target, ...]:
    environment = {"prompt": workload.prompts.writer_version, "model": model}
    return targets(workload.deliverable.spec, [item.input for item in bound], environment)


def _stored(memo: Memo) -> Json:
    return {
        "built": [
            {
                "section_id": built.section_id,
                "hash": built.hash,
                "sentences": [{"text": s.text, "uses": list(s.uses)} for s in built.sentences],
            }
            for built in memo.built
        ],
        "refusals": [
            {"section_id": r.section_id, "draft": r.draft, "reasons": list(r.reasons)}
            for r in memo.refusals
        ],
        "dropped": list(memo.dropped),
    }


def _loaded(stored: Json, bound: tuple[Bound, ...]) -> Memo:
    data = cast("dict[str, list[dict[str, object]]]", stored)
    built = tuple(
        Built(
            cast(str, section["section_id"]),
            cast(str, section["hash"]),
            tuple(
                Sentence(cast(str, s["text"]), tuple(cast("list[str]", s["uses"])))
                for s in cast("list[dict[str, object]]", section["sentences"])
            ),
            True,
        )
        for section in data["built"]
    )
    refusals = tuple(
        Refusal(
            cast(str, r["section_id"]),
            cast(int, r["draft"]),
            tuple(cast("list[str]", r["reasons"])),
        )
        for r in data["refusals"]
    )
    return Memo(built, bound, refusals, (), tuple(cast("list[str]", data["dropped"])))


async def memo_step(
    workload: Workload,
    runner: Runner,
    asked: Sequence[RequiredFact],
    model: str,
    cache: Cache,
    sample: int = 0,
    bound: Sequence[Bound] | None = None,
) -> Memo:
    """Write the memo from the run's ledger as one step of `runner`.

    The step is named after the hashes of its sections, so a memo whose inputs changed is a
    new step; the sections that did not change send the requests they sent before, which the
    run has already paid for. A memo an earlier process finished is returned as it was stored,
    with every section marked reused and no responses.
    """
    inputs = tuple(bound) if bound is not None else bind(workload, runner.ledger, asked)
    hashes = "\n".join(target.hash for target in memo_targets(workload, inputs, model))
    written: list[Memo] = []

    async def step(ledger: Ledger, client: LLMClient) -> Json:
        memo = await write_memo(workload, ledger, asked, client, model, cache, sample, inputs)
        written.append(memo)
        return _stored(memo)

    stored = await runner.step(f"memo:{hashlib.sha256(hashes.encode()).hexdigest()[:16]}", step)
    return written[0] if written else _loaded(stored, inputs)


def revise_prompt(
    workload: Workload, target: Target, labels: Mapping[str, str], current: Built, comment: str
) -> str:
    texts = workload.prompts
    lines = [prompt(workload, target, labels, ()), "", texts.revise_current]
    lines.extend(f"- {sentence.text}" for sentence in current.sentences)
    lines += ["", texts.revise_comment, comment]
    return "\n".join(lines)


async def revise_step(
    workload: Workload,
    runner: Runner,
    memo: Memo,
    section_id: str,
    comment: str,
    model: str,
    sample: int = 0,
) -> Proposal:
    """Ask the model for a rewrite of one section in answer to a reviewer's comment.

    One call, as a step of `runner`. The draft is checked by the rules every section is
    written under; a draft that breaks one is returned as a refused proposal with the
    reasons. Nothing in the memo changes until the proposal is accepted.
    """
    labels = {item.input.name: item.label for item in memo.bound}
    inputs = [item.input for item in memo.bound]
    every = memo_targets(workload, memo.bound, model)
    target = next(t for t in every if t.section.id == section_id)
    current = next(built for built in memo.built if built.section_id == section_id)
    asked = revise_prompt(workload, target, labels, current, comment)
    request = Request(
        model,
        (Message("system", workload.prompts.revise), Message("user", asked)),
        ANSWER_MAX_TOKENS,
        0.0,
        sample,
        _SENTENCES,
    )
    digest = hashlib.sha256(
        f"{workload.prompts.revise_version}\n{current.hash}\n{asked}".encode()
    ).hexdigest()

    async def step(ledger: Ledger, client: LLMClient) -> Json:
        response = await client.complete(request, sample=sample)
        return list(read_sentences(response.text))

    drafted = await runner.step(f"revise:{section_id}:{digest[:16]}", step)
    of_section = [item for item in inputs if item.name in {i.name for i in target.inputs}]
    return checked(current, cast("list[str]", drafted), of_section)


def render(workload: Workload, memo: Memo, as_of: dt.date) -> str:
    """The memo as Markdown. Every value is printed from an input, never from a draft."""
    wording = workload.deliverable
    inputs = {item.input.name: item.input for item in memo.bound}
    titles = {section.id: section for section in wording.spec.sections}
    date = workload.language.format_date(as_of)
    lines = [f"# {wording.title}", "", wording.review_date.format(date=date)]
    for built in memo.built:
        section = titles[built.section_id]
        lines += ["", f"## {section.title}", ""]
        filled = [fill(sentence, inputs, wording.flag_mark) for sentence in built.sentences]
        if not filled:
            lines.append(wording.nothing)
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
