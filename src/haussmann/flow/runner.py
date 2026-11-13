"""Run a sequence of named steps so that a stopped run continues where it stopped."""

from collections.abc import Awaitable, Callable, Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal

from opentelemetry import trace
from opentelemetry.trace import Span, Tracer

from haussmann.flow.journal import Journal, Json
from haussmann.ledger.ledger import Ledger
from haussmann.llmkit.client import LLMClient, Request, Response
from haussmann.llmkit.pricing import Price, cost_usd
from haussmann.llmkit.replay import request_key
from haussmann.llmkit.tracing import ERROR_TYPE, call_span, record_response

type StepFn = Callable[[Ledger, LLMClient], Awaitable[Json]]

NO_CAP = Decimal("Infinity")
RUN_ID = "haussmann.run.id"
STEP_KEY = "haussmann.step.key"
STEP_REUSED = "haussmann.step.reused"


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
        with call_span(runner.tracer, request, key, runner.provider) as span:
            stored = await runner.journal.call(runner.run_id, key)
            if stored is not None:
                runner.counts.calls_reused += 1
                cost = cost_usd(request.model, stored.usage, runner.prices)
                record_response(span, stored, cost, False)
                return stored
            spent = await runner.journal.spent(runner.run_id)
            if spent >= runner.cap_usd:
                raise SpendCapReached(runner.run_id, spent, runner.cap_usd)
            response = await runner.client.complete(request, sample=sample)
            cost = cost_usd(request.model, response.usage, runner.prices)
            await runner.journal.record_call(runner.run_id, self._step, key, response, cost)
            runner.counts.calls_paid += 1
            record_response(span, response, cost, True)
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
        provider: str = "unknown",
        tracer: Tracer | None = None,
    ) -> None:
        self.journal = journal
        self.run_id = run_id
        self.ledger = ledger
        self.client = client
        self.prices = prices
        self.cap_usd = cap_usd
        self.provider = provider
        self.tracer = tracer or trace.get_tracer("haussmann.flow")
        self.counts = Counts()
        self._done = dict(done)

    def finished(self, prefix: str = "") -> list[tuple[str, Json]]:
        """The finished steps whose key starts with `prefix`, with their results, in order."""
        return [(key, result) for key, result in self._done.items() if key.startswith(prefix)]

    @contextmanager
    def span(self) -> Generator[Span]:
        """A span for the run in this process; the steps run inside it are its children."""
        with self.tracer.start_as_current_span("run", attributes={RUN_ID: self.run_id}) as span:
            yield span

    async def step(self, key: str, fn: StepFn) -> Json:
        """Run `fn` and store what it appended and returned, or return what a finished run of
        it stored. A step that raises stores nothing and leaves `ledger` as it was."""
        reused = key in self._done
        attributes = {RUN_ID: self.run_id, STEP_KEY: key, STEP_REUSED: reused}
        with self.tracer.start_as_current_span(f"step {key}", attributes=attributes) as span:
            if reused:
                self.counts.steps_reused += 1
                return self._done[key]
            before = self.ledger.tx
            working = self.ledger.at(before)
            client = _StepClient(self, key)
            try:
                result = await fn(working, client)
            except Exception as error:
                span.set_attribute(ERROR_TYPE, type(error).__qualname__)
                raise
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
    provider: str = "unknown",
    tracer: Tracer | None = None,
) -> Runner:
    """Start a run, or load one that was started on the same inputs."""
    state = await journal.open(run_id, inputs_digest)
    ledger = Ledger.load(state.entries)
    return Runner(journal, run_id, ledger, state.done, client, prices, cap_usd, provider, tracer)
