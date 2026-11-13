"""One engine run: find facts in groups, verify and settle them, apply the date rules."""

import datetime as dt
import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from feasibility_fr.engine.finder import CROSS_CHECK, SECOND_PASS, Finding, find
from feasibility_fr.engine.rules import flag_dates
from feasibility_fr.engine.spec import RequiredFact
from feasibility_fr.french import format_date
from haussmann.coretypes.values import FactKey, Schema, Value
from haussmann.ctxkit.search import Index
from haussmann.docparse.cards import DocumentCard
from haussmann.docparse.elements import Element
from haussmann.flow.journal import Json
from haussmann.flow.runner import Runner, StepFn
from haussmann.ledger.ledger import Ledger
from haussmann.llmkit.client import LLMClient
from haussmann.review.edits import edit
from haussmann.verify.settle import EXPERT, verify

MAIN_SUBJECT = "site"
GROUP_SIZE = 5
PASSES = 2
CROSS_CHECK_HITS = 4


@dataclass(frozen=True, slots=True)
class EngineRun:
    ledger: Ledger
    findings: tuple[Finding, ...]


def plan(wanted: Sequence[RequiredFact]) -> list[list[RequiredFact]]:
    """Split the required facts into groups, each small enough for one finder.

    Facts about the main subject go in chunks; the others are grouped by attribute, so the
    rows of a table and its total are looked for together.
    """
    main = [fact for fact in wanted if fact.key.subject == MAIN_SUBJECT]
    groups = [main[start : start + GROUP_SIZE] for start in range(0, len(main), GROUP_SIZE)]
    by_attribute: dict[str, list[RequiredFact]] = {}
    for fact in wanted:
        if fact.key.subject != MAIN_SUBJECT:
            by_attribute.setdefault(fact.key.attribute, []).append(fact)
    return groups + list(by_attribute.values())


def untouched(ledger: Ledger, group: Sequence[RequiredFact]) -> list[RequiredFact]:
    """The facts of a group for which nothing was recorded and no open question was raised."""
    asked = {question.key for question in ledger.questions()}
    return [fact for fact in group if not ledger.facts(fact.key) and fact.key not in asked]


def unchecked_pages(
    ledger: Ledger, group: Sequence[RequiredFact], index: Index
) -> dict[FactKey, list[Element]]:
    """For each fact with a recorded value, the best-matching pages of documents not yet cited.

    These are where a second, different value would be if there is one.
    """
    pages: dict[FactKey, list[Element]] = {}
    for fact in group:
        recorded = ledger.facts(fact.key)
        if not recorded:
            continue
        cited = {citation.doc_id for found in recorded for citation in found.citations}
        quotes = " ".join(citation.quote for found in recorded for citation in found.citations)
        hits = index.search(f"{fact.text} {quotes}", CROSS_CHECK_HITS)
        fresh = [hit.element for hit in hits if hit.element.doc_id not in cited]
        if fresh:
            pages[fact.key] = fresh
    return pages


def renderings(value: Value) -> list[str]:
    """Other ways this workload's documents write a value: dates in French."""
    return [format_date(value)] if isinstance(value, dt.date) else []


def inputs_digest(
    wanted: Sequence[RequiredFact], elements: Sequence[Element], model: str, as_of: dt.date
) -> str:
    """What a run was started on. A run is continued only on the inputs it began with."""
    parts = [model, as_of.isoformat()]
    parts += [f"{fact.key.subject}/{fact.key.attribute}" for fact in wanted]
    parts += [f"{element.doc_id}\t{element.locator}\t{element.text}" for element in elements]
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def settle_ledger(
    ledger: Ledger,
    wanted: Sequence[RequiredFact],
    elements: Sequence[Element],
    cards: Sequence[DocumentCard],
    schema: Schema,
    as_of: dt.date,
) -> None:
    """Verify, settle and apply the date rules. Running it again adds nothing new."""
    keys = [fact.key for fact in wanted]
    totals = {fact.key: fact.sum_of for fact in wanted if fact.sum_of}
    depends_on = {fact.key: fact.depends_on for fact in wanted if fact.depends_on}
    verify(ledger, elements, cards, schema, keys, totals, renderings, depends_on)
    flag_dates(ledger, keys, schema, as_of)


async def apply_edit(
    runner: Runner,
    wanted: Sequence[RequiredFact],
    elements: Sequence[Element],
    cards: Sequence[DocumentCard],
    schema: Schema,
    as_of: dt.date,
    key: FactKey,
    value: Value,
    reason: str,
    author: str,
) -> str:
    """Record an expert's value as a step of the run and settle what follows from it.

    Returns the id of the expert's fact. The memo is rebuilt by the next memo step.
    """
    number = sum(1 for fact in runner.ledger.facts() if fact.method == EXPERT) + 1

    async def step(ledger: Ledger, client: LLMClient) -> Json:
        fact_id = edit(ledger, key, value, reason, author, schema)
        settle_ledger(ledger, wanted, elements, cards, schema, as_of)
        return fact_id

    return str(await runner.step(f"edit:{number}:{key.subject}/{key.attribute}", step))


async def run_engine(
    wanted: Sequence[RequiredFact],
    elements: Sequence[Element],
    cards: Sequence[DocumentCard],
    schema: Schema,
    runner: Runner,
    model: str,
    as_of: dt.date,
    sample: int = 0,
) -> EngineRun:
    """Find, verify and settle the wanted facts, as named steps of `runner`.

    A step that an earlier process finished is not run again. `findings` holds the finder
    runs of this process only.
    """
    index = Index(elements)
    findings: list[Finding] = []

    def finder(
        group: Sequence[RequiredFact], note: str, pages: Mapping[FactKey, list[Element]] | None
    ) -> StepFn:
        async def step(ledger: Ledger, client: LLMClient) -> Json:
            finding = await find(
                group,
                elements,
                cards,
                index,
                ledger,
                schema,
                client,
                model,
                as_of.isoformat(),
                sample,
                note=note,
                pages=pages,
            )
            findings.append(finding)
            return {"stop": finding.loop.stop.value, "calls": len(finding.loop.responses)}

        return step

    for number, group in enumerate(plan(wanted)):
        pending = group
        for attempt in range(PASSES):
            note = SECOND_PASS if attempt > 0 else ""
            await runner.step(f"find:{number}:pass{attempt + 1}", finder(pending, note, None))
            pending = untouched(runner.ledger, pending)
            if not pending:
                break
        pages = unchecked_pages(runner.ledger, group, index)
        if pages:
            again = [fact for fact in group if fact.key in pages]
            await runner.step(f"find:{number}:cross-check", finder(again, CROSS_CHECK, pages))

    async def settle(ledger: Ledger, client: LLMClient) -> Json:
        settle_ledger(ledger, wanted, elements, cards, schema, as_of)
        return None

    await runner.step("settle", settle)
    return EngineRun(runner.ledger, tuple(findings))
