"""One engine run: find facts in groups, verify and settle them, apply the date rules."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

from feasibility_fr.engine.finder import Finding, find
from feasibility_fr.engine.rules import flag_dates
from feasibility_fr.engine.spec import RequiredFact
from feasibility_fr.french import format_date
from haussmann.coretypes.values import Schema, Value
from haussmann.ctxkit.search import Index
from haussmann.docparse.cards import DocumentCard
from haussmann.docparse.elements import Element
from haussmann.ledger.ledger import Ledger
from haussmann.llmkit.client import LLMClient
from haussmann.verify.settle import verify

MAIN_SUBJECT = "site"
GROUP_SIZE = 5


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


def renderings(value: Value) -> list[str]:
    """Other ways this workload's documents write a value: dates in French."""
    return [format_date(value)] if isinstance(value, dt.date) else []


async def run_engine(
    wanted: Sequence[RequiredFact],
    elements: Sequence[Element],
    cards: Sequence[DocumentCard],
    schema: Schema,
    client: LLMClient,
    model: str,
    as_of: dt.date,
    sample: int = 0,
) -> EngineRun:
    ledger = Ledger()
    index = Index(elements)
    findings: list[Finding] = []
    for group in plan(wanted):
        findings.append(
            await find(
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
            )
        )
    keys = [fact.key for fact in wanted]
    totals = {fact.key: fact.sum_of for fact in wanted if fact.sum_of}
    verify(ledger, elements, cards, schema, keys, totals, renderings)
    flag_dates(ledger, keys, schema, as_of)
    return EngineRun(ledger, tuple(findings))
