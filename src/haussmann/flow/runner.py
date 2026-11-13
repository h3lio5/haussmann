"""Run a sequence of named steps so that a stopped run continues where it stopped."""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal

from haussmann.flow.journal import Journal, Json
from haussmann.ledger.ledger import Ledger
from haussmann.llmkit.client import LLMClient, Request, Response
from haussmann.llmkit.pricing import Price, cost_usd
from haussmann.llmkit.replay import request_key

type StepFn = Callable[[Ledger, LLMClient], Awaitable[Json]]


class SpendCapReached(Exception):
    def __init__(self, run_id: str, spent: Decimal, cap: Decimal) -> None:
        super().__init__(f"run {run_id} has spent {spent} USD of a cap of {cap} USD")
        self.run_id, self.spent, self.cap = run_id, spent, cap


@dataclass(slots=True)
class Counts:
    """What the steps run in this process did. `orphaned` are calls an earlier attempt of a
    step paid for and this attempt never asked for: the step did not repeat itself."""

    steps_run: int = 0
    steps_reused: int = 0
    calls_paid: int = 0
    calls_reused: int = 0
    orphaned: int = 0


class _StepClient:
    """The client a step sees: a call the run already paid for is served from the journal."""

    def __init__(self, runner: "Runner", step: str) -> None:
        self._runner = runner
        self._step = step
        self.asked: set[str] = set()

    async def complete(self, request: Request, *, sample: int = 0) -> Response:
        runner = self._runner
        key = request_key(request, sample)
        self.asked.add(key)
        stored = await runner.journal.call(runner.run_id, key)
        if stored is not None:
            runner.counts.calls_reused += 1
            return stored
        spent = await runner.journal.spent(runner.run_id)
        if spent >= runner.cap_usd:
            raise SpendCapReached(runner.run_id, spent, runner.cap_usd)
        response = await runner.client.complete(request, sample=sample)
        cost = cost_usd(request.model, response.usage, runner.prices)
        await runner.journal.record_call(runner.run_id, self._step, key, response, cost)
        runner.counts.calls_paid += 1
        return response


class Runner:
    """`ledger` is the run's ledger as of the last finished step."""

    def __init__(
        self,
        journal: Journal,
        run_id: str,
        ledger: Ledger,
        done: Mapping[str, Json],
        client: LLMClient,
        prices: Mapping[str, Price],
        cap_usd: Decimal,
    ) -> None:
        self.journal = journal
        self.run_id = run_id
        self.ledger = ledger
        self.client = client
        self.prices = prices
        self.cap_usd = cap_usd
        self.counts = Counts()
        self._done = dict(done)

    async def step(self, key: str, fn: StepFn) -> Json:
        """Run `fn` and store what it appended and returned, or return what a finished run of
        it stored. A step that raises stores nothing and leaves `ledger` as it was."""
        if key in self._done:
            self.counts.steps_reused += 1
            return self._done[key]
        before = self.ledger.tx
        working = self.ledger.at(before)
        client = _StepClient(self, key)
        result = await fn(working, client)
        await self.journal.commit(self.run_id, key, working.since(before), result)
        recorded = await self.journal.keys(self.run_id, key)
        self.counts.orphaned += len(recorded - client.asked)
        self.counts.steps_run += 1
        self.ledger = working
        self._done[key] = result
        return result


async def open_run(
    journal: Journal,
    run_id: str,
    inputs_digest: str,
    client: LLMClient,
    prices: Mapping[str, Price],
    cap_usd: Decimal,
) -> Runner:
    """Start a run, or load one that was started on the same inputs."""
    state = await journal.open(run_id, inputs_digest)
    return Runner(journal, run_id, Ledger.load(state.entries), state.done, client, prices, cap_usd)
