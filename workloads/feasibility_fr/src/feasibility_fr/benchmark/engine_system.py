"""The engine as a benchmark contestant: run it, then read its ledger as a submission."""

import datetime as dt
from collections.abc import Sequence

from feasibility_fr.benchmark.baselines import Attempt
from feasibility_fr.engine.run import run_engine
from feasibility_fr.engine.spec import RequiredFact
from haussmann.coretypes.values import FactKey, Schema
from haussmann.docparse.cards import DocumentCard
from haussmann.docparse.elements import Element
from haussmann.evalkit.scorer import Citation, ReportedFact, Submission
from haussmann.flow.journal import MemoryJournal
from haussmann.flow.runner import NO_CAP, open_run
from haussmann.ledger.ledger import Ledger
from haussmann.llmkit.client import LLMClient
from haussmann.llmkit.pricing import PRICES
from haussmann.verify.settle import groups, settled


def to_submission(ledger: Ledger, asked: Sequence[RequiredFact], schema: Schema) -> Submission:
    """One reported fact per settled key; everything else is an open question.

    A fact is flagged when its key had a disagreement or a date rule fired. It cites every
    verified source of the reported value, and both sides when there was a disagreement.
    """
    facts: list[ReportedFact] = []
    open_questions: list[FactKey] = []
    for required in asked:
        result = settled(ledger, required.key, schema)
        if result.fact is None:
            open_questions.append(required.key)
            continue
        if result.conflict is not None:
            sources = result.supporting
        else:
            sources = tuple(groups(result.supporting, schema)[0])
        citations = tuple(
            dict.fromkeys(Citation(c.doc_id, c.locator) for fact in sources for c in fact.citations)
        )
        flagged = result.conflict is not None or bool(result.reasons)
        facts.append(ReportedFact(required.key, result.fact.value, citations, flagged))
    return Submission(tuple(facts), tuple(open_questions))


async def engine(
    pages: Sequence[Element],
    cards: Sequence[DocumentCard],
    asked: Sequence[RequiredFact],
    schema: Schema,
    client: LLMClient,
    model: str,
    sample: int,
    as_of: dt.date,
) -> Attempt:
    runner = await open_run(MemoryJournal(), "benchmark", "", client, PRICES, NO_CAP)
    done = await run_engine(asked, pages, cards, schema, runner, model, as_of, sample)
    responses = tuple(r for finding in done.findings for r in finding.loop.responses)
    return Attempt(to_submission(done.ledger, asked, schema), None, responses)
