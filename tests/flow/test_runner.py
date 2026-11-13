import asyncio
import datetime as dt
import uuid
from decimal import Decimal

import pytest
from tests.flow.journals import BOTH, Opener

from haussmann.coretypes.values import FactKey
from haussmann.flow.journal import Journal, Json
from haussmann.flow.runner import Runner, SpendCapReached, StepFn, open_run
from haussmann.ledger.ledger import Ledger, NewFact
from haussmann.llmkit.client import LLMClient, Message, Request, Response, Usage
from haussmann.llmkit.pricing import Price

MODEL = "model-a"
PRICES = {MODEL: Price(Decimal(1), Decimal(1), "test", dt.date(2026, 1, 1))}
EACH = Decimal("0.03")  # 10000 tokens in and 20000 out at 1 USD per million
NOTE = FactKey("site", "note")


class Killed(Exception):
    pass


class Provider:
    """Answers every request with its own text in capitals; can die before a given call."""

    def __init__(self, dies_before: int | None = None) -> None:
        self.seen: list[str] = []
        self._dies_before = dies_before

    async def complete(self, request: Request, *, sample: int = 0) -> Response:
        if self._dies_before is not None and len(self.seen) >= self._dies_before:
            raise Killed
        question = request.messages[-1].text
        self.seen.append(question)
        return Response(question.upper(), "stop", MODEL, Usage(10_000, 20_000), 0.1)


def ask(question: str) -> Request:
    return Request(MODEL, (Message("user", question),), 100)


def asking(*questions: str) -> StepFn:
    """A step that asks each question in turn and records each answer as a fact."""

    async def step(ledger: Ledger, client: LLMClient) -> Json:
        for question in questions:
            answer = await client.complete(ask(question))
            ledger.append("step", [NewFact(NOTE, answer.text)])
        return len(questions)

    return step


def notes(ledger: Ledger) -> list[object]:
    return [fact.value for fact in ledger.facts()]


async def opened_run(journal: Journal, run: str, provider: Provider, cap: str = "1") -> Runner:
    return await open_run(journal, run, "digest", provider, PRICES, Decimal(cap))


def new_run() -> str:
    return f"test-{uuid.uuid4()}"


@pytest.mark.parametrize("opened", BOTH)
def test_a_finished_step_is_not_run_again_and_returns_its_stored_result(opened: Opener) -> None:
    async def scenario() -> None:
        run, provider = new_run(), Provider()
        async with opened() as journal:
            first = await opened_run(journal, run, provider)
            assert await first.step("a", asking("one", "two")) == 2
            assert await first.step("a", asking("never")) == 2

            again = await opened_run(journal, run, provider)
            assert notes(again.ledger) == ["ONE", "TWO"]
            assert await again.step("a", asking("never")) == 2
            assert await again.step("b", asking("three")) == 1
            assert notes(again.ledger) == ["ONE", "TWO", "THREE"]
            assert provider.seen == ["one", "two", "three"]
            assert (again.counts.steps_reused, again.counts.steps_run) == (1, 1)

    asyncio.run(scenario())


@pytest.mark.parametrize("opened", BOTH)
def test_a_step_that_raises_stores_nothing_but_the_calls_it_paid_for(opened: Opener) -> None:
    async def scenario() -> None:
        run = new_run()
        async with opened() as journal:
            runner = await opened_run(journal, run, Provider(dies_before=2))
            await runner.step("a", asking("zero"))
            with pytest.raises(Killed):
                await runner.step("b", asking("one", "two", "three"))
            assert notes(runner.ledger) == ["ZERO"]
            state = await journal.open(run, "digest")
            assert list(state.done) == ["a"]
            assert len(state.entries) == 1
            assert await journal.spent(run) == 2 * EACH

    asyncio.run(scenario())


@pytest.mark.parametrize("opened", BOTH)
@pytest.mark.parametrize("dies_before", [0, 1, 2, 3, 4])
def test_a_run_killed_at_any_call_resumes_without_paying_twice_and_ends_the_same(
    opened: Opener, dies_before: int
) -> None:
    async def whole(runner: Runner) -> None:
        await runner.step("a", asking("one", "two"))
        await runner.step("b", asking("three", "four", "five"))

    async def scenario() -> None:
        async with opened() as journal:
            reference = await opened_run(journal, new_run(), Provider())
            await whole(reference)

            run, dying, healthy = new_run(), Provider(dies_before), Provider()
            with pytest.raises(Killed):
                await whole(await opened_run(journal, run, dying))
            resumed = await opened_run(journal, run, healthy)
            await whole(resumed)

            assert dying.seen + healthy.seen == ["one", "two", "three", "four", "five"]
            assert resumed.ledger.since(0) == reference.ledger.since(0)
            assert await journal.spent(run) == 5 * EACH
            assert resumed.counts.calls_paid == 5 - dies_before
            assert resumed.counts.orphaned == 0
            loaded = await journal.open(run, "digest")
            assert Ledger.load(loaded.entries).since(0) == reference.ledger.since(0)

    asyncio.run(scenario())


@pytest.mark.parametrize("opened", BOTH)
def test_the_cap_stops_a_run_before_the_call_that_would_pass_it_and_a_higher_cap_continues(
    opened: Opener,
) -> None:
    async def scenario() -> None:
        run, provider = new_run(), Provider()
        async with opened() as journal:
            capped = await opened_run(journal, run, provider, cap="0.05")
            with pytest.raises(SpendCapReached) as stopped:
                await capped.step("a", asking("one", "two", "three"))
            assert provider.seen == ["one", "two"]
            assert (stopped.value.spent, stopped.value.cap) == (2 * EACH, Decimal("0.05"))
            assert notes(capped.ledger) == []

            raised = await opened_run(journal, run, provider, cap="1")
            await raised.step("a", asking("one", "two", "three"))
            assert provider.seen == ["one", "two", "three"]
            assert notes(raised.ledger) == ["ONE", "TWO", "THREE"]

    asyncio.run(scenario())


@pytest.mark.parametrize("opened", BOTH)
def test_a_step_that_asks_something_else_the_second_time_pays_for_it_and_is_counted(
    opened: Opener,
) -> None:
    async def scenario() -> None:
        run, healthy = new_run(), Provider()
        async with opened() as journal:
            with pytest.raises(Killed):
                first = await opened_run(journal, run, Provider(dies_before=2))
                await first.step("a", asking("one", "two", "three"))
            resumed = await opened_run(journal, run, healthy)
            await resumed.step("a", asking("one", "other", "three"))
            assert healthy.seen == ["other", "three"]
            assert (resumed.counts.calls_reused, resumed.counts.calls_paid) == (1, 2)
            assert resumed.counts.orphaned == 1
            assert await journal.spent(run) == 4 * EACH

    asyncio.run(scenario())


@pytest.mark.parametrize("opened", BOTH)
def test_a_call_made_in_an_earlier_step_is_reused_by_a_later_one(opened: Opener) -> None:
    async def scenario() -> None:
        run, provider = new_run(), Provider()
        async with opened() as journal:
            runner = await opened_run(journal, run, provider)
            await runner.step("a", asking("one"))
            await runner.step("b", asking("one", "two"))
            assert provider.seen == ["one", "two"]
            assert runner.counts.orphaned == 0
            costs = await journal.costs(run)
            assert [(cost.step, cost.calls) for cost in costs] == [("a", 1), ("b", 1)]

    asyncio.run(scenario())
