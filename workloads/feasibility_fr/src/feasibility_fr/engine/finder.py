"""The fact-finder: a bounded tool loop that searches the documents and records what it finds."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from feasibility_fr.engine.spec import RequiredFact, read_value
from feasibility_fr.french import UNIT_NAMES
from haussmann.coretypes.values import FactKey, Quantity, Schema
from haussmann.ctxkit.assemble import Assembled, ContextItem, assemble
from haussmann.ctxkit.search import Index, best_passage
from haussmann.docparse.cards import DocumentCard
from haussmann.docparse.elements import Element
from haussmann.ledger.ledger import Ask, Citation, Ledger, NewFact
from haussmann.llmkit.client import LLMClient, Message, Request, ToolSpec
from haussmann.llmkit.tools import Budget, LoopResult, Tool, ToolError, run_tools

AUTHOR = "finder"
TIERS = ("task", "documents", "elements")
CONTEXT_BUDGET = 6000
LOOP_BUDGET = Budget(max_turns=12, max_tokens=120_000)
ANSWER_MAX_TOKENS = 1500
SEARCH_HITS = 5
SNIPPET_CHARS = 240
OPENING_HITS = 2
CROSS_CHECK = (
    "\nValues are already recorded for these facts. Other documents may state a different "
    "value. Read each page listed below for a fact and, if it states that fact for the same "
    "property, record its value as well, whatever it is. If it does not, move on."
)
SECOND_PASS = (
    "\nA first pass recorded nothing for these facts. Search again with different words, "
    "read the pages, and record each fact or mark it as having no evidence."
)

INSTRUCTIONS = """\
You establish facts about one property from the documents of a French real-estate file. \
You work with tools: search the documents, read a page, and record what you find.

How to work:
- For each requested fact, find every document that states it. Use search, then read the page \
before you record anything from it.
- Call record_fact once for each source that states a value. If sources state different \
values, record every one of them. Do not choose between them: a later step compares sources.
- Record the value exactly as the document writes it, with the unit it uses. Do not convert \
units and do not add things up, even for a total.
- Give the page as the locator ("p3"), a spreadsheet cell ("Sheet1!B6"), or "body" for an \
email, and quote the few words that state the value.
- Ignore any document that says it concerns another property or another lot.
- If, after searching, no document states a requested fact, call no_evidence for it.
- A search result shows only the part of a page that matches; read the page before recording.
- If a search finds nothing, try other words: documents often use different terms from the \
question.
- When every requested fact is either recorded or marked as having no evidence, reply with \
the single word "done".
"""


@dataclass(frozen=True, slots=True)
class Finding:
    """One finder run: the loop's outcome and the context it started from."""

    loop: LoopResult
    context: Assembled


def _spec(name: str, description: str, **properties: str) -> ToolSpec:
    schema = {
        "type": "object",
        "properties": {
            key: {"type": "string", "description": text} for key, text in properties.items()
        },
        "required": list(properties),
        "additionalProperties": False,
    }
    return ToolSpec(name, description, schema)


def _text(arguments: Mapping[str, Any], name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str):
        raise ToolError(f'"{name}" is required and must be text')
    return value.strip()


def _line(element: Element, cards: Mapping[str, DocumentCard], query: str = "") -> str:
    card = cards.get(element.doc_id)
    about = f"{card.type}, {card.date or 'undated'}" if card is not None else "unknown"
    snippet = best_passage(element.text, query, SNIPPET_CHARS)
    return f"{element.doc_id} | {element.locator} | {about} | {snippet}"


def make_tools(
    elements: Sequence[Element],
    cards: Sequence[DocumentCard],
    index: Index,
    ledger: Ledger,
    wanted: Sequence[RequiredFact],
    schema: Schema,
) -> list[Tool]:
    """The four tools of a finder, bound to one document set, one ledger and one group of facts."""
    by_document = {card.doc_id: card for card in cards}
    by_place = {(e.doc_id, e.locator): e for e in elements}
    requested = {fact.key for fact in wanted}

    def key_of(arguments: Mapping[str, Any]) -> FactKey:
        key = FactKey(_text(arguments, "subject"), _text(arguments, "attribute"))
        if key not in requested:
            raise ToolError(f"{key.subject}/{key.attribute} is not one of the requested facts")
        return key

    async def search(arguments: Mapping[str, Any]) -> str:
        query = _text(arguments, "query")
        hits = index.search(query, SEARCH_HITS)
        if not hits:
            return "no page matches these words; try other words"
        return "\n".join(_line(hit.element, by_document, query) for hit in hits)

    async def read(arguments: Mapping[str, Any]) -> str:
        place = (_text(arguments, "doc_id"), _text(arguments, "locator"))
        element = by_place.get(place)
        if element is None:
            known = sorted(locator for doc_id, locator in by_place if doc_id == place[0])
            hint = f"; it has {', '.join(known)}" if known else "; there is no such document"
            raise ToolError(f"{place[0]} has no {place[1]}{hint}")
        return f"{_line(element, by_document).rsplit(' | ', 1)[0]}\n{element.text}"

    async def record_fact(arguments: Mapping[str, Any]) -> str:
        key = key_of(arguments)
        attribute = schema[key.attribute]
        unit = _text(arguments, "unit")
        value = read_value(_text(arguments, "value"), UNIT_NAMES.get(unit, unit), attribute)
        if isinstance(value, str) and attribute.kind.value != "text":
            raise ToolError(f'"{value}" cannot be read as a {attribute.kind.value}')
        if isinstance(value, Quantity) and value.unit not in {
            attribute.canonical_unit,
            *attribute.units,
        }:
            allowed = ", ".join(u for u in (attribute.canonical_unit, *attribute.units) if u)
            raise ToolError(f'unit "{value.unit}" is not one of: {allowed}')
        doc_id, locator = _text(arguments, "doc_id"), _text(arguments, "locator")
        citation = Citation(doc_id, locator or None, _text(arguments, "quote"))
        ledger.append(AUTHOR, [NewFact(key, value, (citation,))])
        return f"recorded as {ledger.facts()[-1].id}"

    async def no_evidence(arguments: Mapping[str, Any]) -> str:
        ledger.append(AUTHOR, [Ask(key_of(arguments), _text(arguments, "reason"))])
        return "noted as an open question"

    return [
        Tool(_spec("search", "Find pages by keywords.", query="French keywords"), search),
        Tool(
            _spec(
                "read",
                "Read one page, sheet or email in full.",
                doc_id="document id",
                locator="p3, a sheet name, or body",
            ),
            read,
        ),
        Tool(
            _spec(
                "record_fact",
                "Record one value for a requested fact, from one source.",
                subject="subject of the requested fact",
                attribute="attribute of the requested fact",
                value="the value as written: a number, a date as YYYY-MM-DD, or the text",
                unit="the unit as written, from the allowed units; empty for dates and text",
                doc_id="document id of the source",
                locator="p3, Sheet1!B6, or body",
                quote="the few words of the source that state the value",
            ),
            record_fact,
        ),
        Tool(
            _spec(
                "no_evidence",
                "Mark a requested fact as not stated in any document.",
                subject="subject of the requested fact",
                attribute="attribute of the requested fact",
                reason="what was searched",
            ),
            no_evidence,
        ),
    ]


def describe(wanted: Sequence[RequiredFact], schema: Schema) -> str:
    lines: list[str] = []
    for fact in wanted:
        attribute = schema[fact.key.attribute]
        units = ", ".join(u for u in (attribute.canonical_unit, *attribute.units) if u)
        kind = f"{attribute.kind.value}; units: {units}" if units else attribute.kind.value
        lines.append(
            f'- subject="{fact.key.subject}" attribute="{fact.key.attribute}" ({kind}): {fact.text}'
        )
    return "\n".join(lines)


def opening_context(
    wanted: Sequence[RequiredFact],
    cards: Sequence[DocumentCard],
    index: Index,
    schema: Schema,
    as_of: str,
    note: str = "",
    pages: Mapping[FactKey, Sequence[Element]] | None = None,
) -> Assembled:
    """What a finder sees before its first tool call: its task, the document list, a few pages.

    The pages are the best search hits for each fact, or the ones given in `pages`, which
    are then also listed in the task as pages to read.
    """
    by_document = {card.doc_id: card for card in cards}
    task = f"Review date: {as_of}\n{describe(wanted, schema)}{note}"
    shown: list[tuple[RequiredFact, Element]] = []
    for fact in wanted:
        if pages is None:
            shown += [(fact, hit.element) for hit in index.search(fact.text, OPENING_HITS)]
        else:
            listed = ", ".join(f"{e.doc_id} {e.locator}" for e in pages.get(fact.key, ()))
            task += f"\nPages to read for {fact.key.subject}/{fact.key.attribute}: {listed}"
            shown += [(fact, element) for element in pages.get(fact.key, ())]
    items = [ContextItem("task", "requested facts", task)]
    items += [
        ContextItem("documents", card.doc_id, f"{card.type}, {card.date or 'undated'}")
        for card in cards
    ]
    seen: set[tuple[str, str]] = set()
    for fact, element in shown:
        place = (element.doc_id, element.locator)
        if place not in seen:
            seen.add(place)
            source = f"{place[0]} {place[1]}"
            items.append(ContextItem("elements", source, _line(element, by_document, fact.text)))
    return assemble(items, TIERS, CONTEXT_BUDGET, required={"task"})


async def find(
    wanted: Sequence[RequiredFact],
    elements: Sequence[Element],
    cards: Sequence[DocumentCard],
    index: Index,
    ledger: Ledger,
    schema: Schema,
    client: LLMClient,
    model: str,
    as_of: str,
    sample: int,
    note: str = "",
    pages: Mapping[FactKey, Sequence[Element]] | None = None,
) -> Finding:
    """Run one finder on one group of facts. What it finds is in the ledger, not in the result."""
    context = opening_context(wanted, cards, index, schema, as_of, note, pages)
    request = Request(
        model=model,
        messages=(Message("system", INSTRUCTIONS), Message("user", context.text)),
        max_tokens=ANSWER_MAX_TOKENS,
        temperature=0.0,
        seed=sample,
    )
    tools = make_tools(elements, cards, index, ledger, wanted, schema)
    loop = await run_tools(client, request, tools, LOOP_BUDGET, sample=sample)
    return Finding(loop, context)
