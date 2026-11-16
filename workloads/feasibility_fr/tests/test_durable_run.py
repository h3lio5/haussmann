"""An engine run on a real scenario, stopped part-way and continued, from recordings."""

import asyncio
import os
import uuid
from collections.abc import Sequence
from pathlib import Path

import pytest

from feasibility_fr.benchmark.answer import questions
from feasibility_fr.benchmark.reading import read_folder
from feasibility_fr.benchmark.render import FILES_DIR
from feasibility_fr.benchmark.run import MODEL
from feasibility_fr.benchmark.scenarios import SCENARIOS
from feasibility_fr.workload import WORKLOAD
from haussmann.docparse.cards import DocumentCard
from haussmann.docparse.elements import Element
from haussmann.engine.ingest import describe_documents
from haussmann.engine.memo import memo_step, record, render
from haussmann.engine.run import run_engine
from haussmann.engine.workload import RequiredFact
from haussmann.evalkit.generator import MANIFEST_NAME
from haussmann.evalkit.manifest import load_manifest
from haussmann.flow.journal import Journal, MemoryJournal
from haussmann.flow.postgres import PostgresJournal, connect
from haussmann.flow.runner import NO_CAP, Runner, open_run
from haussmann.ledger.ledger import Entry
from haussmann.llmkit.client import LLMClient, Request, Response
from haussmann.llmkit.pricing import PRICES
from haussmann.llmkit.replay import ReplayClient, ReplayStore, request_key

DATA = Path(__file__).parent.parent / "benchmark_data"
SCENARIO = SCENARIOS["metz_vigny"]
DB_URL = os.environ.get("HAUSSMANN_DB_URL", "")


class Stopped(Exception):
    pass


class Counting:
    """Passes calls to the recordings, notes each one, and can stop before a given call."""

    def __init__(self, inner: LLMClient, stops_before: int | None = None) -> None:
        self.keys: list[str] = []
        self._inner = inner
        self._stops_before = stops_before

    async def complete(self, request: Request, *, sample: int = 0) -> Response:
        if self._stops_before is not None and len(self.keys) >= self._stops_before:
            raise Stopped
        self.keys.append(request_key(request, sample))
        return await self._inner.complete(request, sample=sample)


async def inputs(
    replay: LLMClient,
) -> tuple[Sequence[RequiredFact], Sequence[Element], Sequence[DocumentCard]]:
    folder = DATA / SCENARIO.spec.id / FILES_DIR
    manifest = load_manifest((folder / MANIFEST_NAME).read_text(encoding="utf-8"))
    asked = questions([fact.key for fact in manifest.gold], SCENARIO.wording, SCENARIO.totals)
    pages = await read_folder(folder, replay, MODEL)
    cards = await describe_documents(WORKLOAD, pages, replay, MODEL)
    return asked, pages, cards


async def stopped_and_resumed(journal: Journal, stops_before: int) -> None:
    replay = ReplayClient(ReplayStore(DATA / "recordings" / "completions"))
    asked, pages, cards = await inputs(replay)
    as_of = max(plan.date for plan in SCENARIO.spec.documents)

    async def engine(runner: Runner) -> tuple[tuple[Entry, ...], object, str]:
        done = await run_engine(WORKLOAD, asked, pages, cards, runner, MODEL, as_of)
        memo = await memo_step(WORKLOAD, runner, asked, MODEL, {})
        return done.ledger.since(0), record(memo), render(WORKLOAD, memo, as_of)

    whole = Counting(replay)
    reference = await engine(await open_run(MemoryJournal(), "whole", "", whole, PRICES, NO_CAP))
    if stops_before < 0:
        stops_before += len(whole.keys)
    assert 0 < stops_before < len(whole.keys)

    run = f"test-{uuid.uuid4()}"
    first, second = Counting(replay, stops_before), Counting(replay)
    with pytest.raises(Stopped):
        await engine(await open_run(journal, run, "digest", first, PRICES, NO_CAP))
    resumed = await open_run(journal, run, "digest", second, PRICES, NO_CAP)
    assert await engine(resumed) == reference

    again = Counting(replay)
    finished = await open_run(journal, run, "digest", again, PRICES, NO_CAP)
    assert await engine(finished) == reference
    assert again.keys == [] and finished.counts.steps_run == 0
    assert first.keys + second.keys == whole.keys
    assert resumed.counts.calls_paid == len(whole.keys) - stops_before
    assert resumed.counts.orphaned == 0
    stored = await journal.open(run, "digest")
    assert stored.entries == reference[0]
    assert sum(cost.calls for cost in await journal.costs(run)) == len(set(whole.keys))


@pytest.mark.parametrize("stops_before", [1, 9, 23, -2])
def test_a_stopped_engine_run_continues_without_a_repeated_call_and_ends_the_same(
    stops_before: int,
) -> None:
    asyncio.run(stopped_and_resumed(MemoryJournal(), stops_before))


@pytest.mark.db
@pytest.mark.skipif(not DB_URL, reason="HAUSSMANN_DB_URL is not set")
def test_the_same_holds_with_the_journal_in_postgres() -> None:
    async def scenario() -> None:
        connection = await connect(DB_URL)
        try:
            await stopped_and_resumed(PostgresJournal(connection), 23)
            await stopped_and_resumed(PostgresJournal(connection), -2)
        finally:
            await connection.close()

    asyncio.run(scenario())
