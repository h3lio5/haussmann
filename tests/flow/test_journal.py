import asyncio
import contextlib
import uuid
from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from tests.flow.journals import BOTH, Opener, needs_db, postgres

from haussmann.coretypes.values import FactKey, Quantity
from haussmann.flow.journal import InputsChanged, Journal, RunLocked, StepCost, StepRepeated
from haussmann.ledger.ledger import Ask, Assess, Entry, Ledger, LedgerError, NewFact, Record, Status
from haussmann.llmkit.client import Response, ToolCall, Usage

HEIGHT = FactKey("site", "height")


def new_run() -> str:
    return f"test-{uuid.uuid4()}"


def response(text: str, tokens: int = 10) -> Response:
    return Response(text, "stop", "model-a", Usage(tokens, 2 * tokens), 0.5)


def appended(ledger: Ledger, *transactions: list[Record]) -> tuple[Entry, ...]:
    before = ledger.tx
    for records in transactions:
        ledger.append("author", records)
    return ledger.since(before)


@pytest.mark.db
@needs_db
def test_what_is_committed_is_there_for_a_later_connection() -> None:
    async def scenario() -> None:
        run, ledger = new_run(), Ledger()
        async with postgres() as journal:
            state = await journal.open(run, "digest")
            assert (state.entries, dict(state.done)) == ((), {})
            first = appended(
                ledger, [NewFact(HEIGHT, Quantity(Decimal("9.50"), "m"))], [Ask(HEIGHT)]
            )
            await journal.commit(run, "find", first, {"stop": "answered", "turns": 3})
            second = appended(ledger, [Assess("f1", Status.VERIFIED, "found")])
            await journal.commit(run, "verify", second, None)
            await journal.record_call(run, "find", "k1", response("one"), Decimal("0.01"))
        async with postgres() as journal:
            state = await journal.open(run, "digest")
            assert state.entries == ledger.since(0)
            assert list(state.done.items()) == [
                ("find", {"stop": "answered", "turns": 3}),
                ("verify", None),
            ]
            assert Ledger.load(state.entries).status("f1") is Status.VERIFIED
            assert await journal.call(run, "k1") == response("one")

    asyncio.run(scenario())


@pytest.mark.parametrize("opened", BOTH)
def test_reopening_in_the_same_journal_returns_the_committed_state(opened: Opener) -> None:
    async def scenario() -> None:
        run, ledger = new_run(), Ledger()
        async with opened() as journal:
            await journal.open(run, "digest")
            entries = appended(ledger, [NewFact(HEIGHT, "high")])
            await journal.commit(run, "a", entries, [1, "two", {"three": True}])
            await journal.commit(run, "b", (), "nothing appended")
            state = await journal.open(run, "digest")
            assert state.entries == entries
            assert list(state.done.items()) == [
                ("a", [1, "two", {"three": True}]),
                ("b", "nothing appended"),
            ]

    asyncio.run(scenario())


@pytest.mark.parametrize("opened", BOTH)
def test_a_step_cannot_be_committed_twice_and_the_second_attempt_stores_nothing(
    opened: Opener,
) -> None:
    async def scenario() -> None:
        run, ledger = new_run(), Ledger()
        async with opened() as journal:
            await journal.open(run, "digest")
            first = appended(ledger, [NewFact(HEIGHT, "high")])
            await journal.commit(run, "a", first, 1)
            later = appended(ledger, [Ask(HEIGHT)])
            with pytest.raises(StepRepeated):
                await journal.commit(run, "a", later, 2)
            with pytest.raises(StepRepeated):
                await journal.commit(run, "b", first, 3)
            state = await journal.open(run, "digest")
            assert state.entries == first
            assert dict(state.done) == {"a": 1}

    asyncio.run(scenario())


@pytest.mark.parametrize("opened", BOTH)
def test_a_run_started_on_other_inputs_is_refused(opened: Opener) -> None:
    async def scenario() -> None:
        run = new_run()
        async with opened() as journal:
            await journal.open(run, "digest")
            with pytest.raises(InputsChanged):
                await journal.open(run, "another digest")

    asyncio.run(scenario())


@pytest.mark.parametrize("opened", BOTH)
def test_a_recorded_call_is_returned_whole_and_counted_once(opened: Opener) -> None:
    async def scenario() -> None:
        run = new_run()
        with_tools = Response(
            "",
            "tool_calls",
            "model-a",
            Usage(100, 20, 40, Decimal("0.000123")),
            1.25,
            (ToolCall("call_1", "search", '{"query": "hauteur"}'),),
        )
        async with opened() as journal:
            await journal.open(run, "digest")
            assert await journal.call(run, "k1") is None
            assert await journal.spent(run) == Decimal(0)
            await journal.record_call(run, "find", "k1", with_tools, Decimal("0.000123"))
            await journal.record_call(run, "find", "k2", response("two"), Decimal("0.01"))
            await journal.record_call(run, "write", "k3", response("three", 7), Decimal("0.002"))
            await journal.record_call(run, "write", "k3", response("again"), Decimal("5"))
            assert await journal.call(run, "k1") == with_tools
            assert await journal.call(run, "k3") == response("three", 7)
            assert await journal.spent(run) == Decimal("0.012123")
            assert await journal.costs(run) == (
                StepCost("find", 2, 110, 40, Decimal("0.010123")),
                StepCost("write", 1, 7, 14, Decimal("0.002")),
            )

    asyncio.run(scenario())


records = st.one_of(
    st.builds(NewFact, st.just(HEIGHT), st.sampled_from(["low", "high"])),
    st.builds(Assess, st.sampled_from(["f1", "f2", "f3"]), st.sampled_from(list(Status))),
    st.builds(Ask, st.just(HEIGHT)),
)
steps = st.lists(st.lists(st.lists(records, min_size=1, max_size=3), max_size=3), max_size=5)


@pytest.mark.parametrize("opened", BOTH)
@settings(
    max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(steps)
def test_any_ledger_committed_in_steps_is_loaded_equal(
    opened: Opener, plan: list[list[list[Record]]]
) -> None:
    async def scenario() -> None:
        run, ledger = new_run(), Ledger()
        async with opened() as journal:
            await journal.open(run, "digest")
            for number, transactions in enumerate(plan):
                before = ledger.tx
                for transaction in transactions:
                    with contextlib.suppress(LedgerError):
                        ledger.append("author", transaction)
                await journal.commit(run, f"step {number}", ledger.since(before), number)
            state = await journal.open(run, "digest")
        loaded = Ledger.load(state.entries)
        assert loaded.since(0) == ledger.since(0)
        assert loaded.facts() == ledger.facts()
        assert [loaded.status(f.id) for f in loaded.facts()] == [
            ledger.status(f.id) for f in ledger.facts()
        ]
        assert list(state.done) == [f"step {number}" for number in range(len(plan))]

    asyncio.run(scenario())


@pytest.mark.db
@needs_db
def test_a_run_open_on_one_connection_is_refused_on_another_until_the_first_closes() -> None:
    async def scenario() -> None:
        run = new_run()
        async with postgres() as first:
            await first.open(run, "digest")
            async with postgres() as second:
                with pytest.raises(RunLocked):
                    await second.open(run, "digest")
        async with postgres() as third:
            await third.open(run, "digest")

    asyncio.run(scenario())


@pytest.mark.parametrize("opened", BOTH)
def test_a_commit_that_fails_part_way_stores_none_of_its_entries(opened: Opener) -> None:
    async def scenario() -> None:
        run, ledger = new_run(), Ledger()
        async with opened() as journal:
            await journal.open(run, "digest")
            first = appended(ledger, [NewFact(HEIGHT, "high")])
            await journal.commit(run, "a", first, 1)
            later = appended(ledger, [Ask(HEIGHT)], [Ask(HEIGHT)])
            with pytest.raises(StepRepeated):
                await journal.commit(run, "b", (*later, first[0]), 2)
            state = await journal.open(run, "digest")
            assert state.entries == first
            assert dict(state.done) == {"a": 1}

    asyncio.run(scenario())


def test_the_journal_protocol_is_what_both_classes_provide() -> None:
    from haussmann.flow.journal import MemoryJournal
    from haussmann.flow.postgres import PostgresJournal

    def accepts(journal: type[Journal]) -> None: ...

    accepts(MemoryJournal)
    accepts(PostgresJournal)
