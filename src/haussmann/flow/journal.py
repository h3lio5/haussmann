"""What a run has done so far: its finished steps, its ledger entries and its model calls."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from haussmann.ledger.ledger import Entry
from haussmann.llmkit.client import Response

type Json = bool | int | str | list[Json] | dict[str, Json] | None


@dataclass(frozen=True, slots=True)
class RunState:
    """`done` maps each finished step to its result, in the order the steps finished."""

    run_id: str
    entries: tuple[Entry, ...]
    done: Mapping[str, Json]


@dataclass(frozen=True, slots=True)
class StepCost:
    step: str
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


class InputsChanged(Exception):
    """The run exists and was started on other inputs."""


class RunLocked(Exception):
    """Another process has the run open."""


class StepRepeated(Exception):
    """The step is already finished, or its entries are already stored."""


class Journal(Protocol):
    async def open(self, run_id: str, inputs_digest: str) -> RunState: ...

    async def call(self, run_id: str, key: str) -> Response | None: ...

    async def record_call(
        self, run_id: str, step: str, key: str, response: Response, cost_usd: Decimal
    ) -> None: ...

    async def commit(self, run_id: str, step: str, entries: Sequence[Entry], result: Json) -> None:
        """Store a step's entries and mark it finished, both or neither."""
        ...

    async def spent(self, run_id: str) -> Decimal: ...

    async def keys(self, run_id: str, step: str) -> frozenset[str]:
        """The keys of the calls recorded for a step."""
        ...

    async def costs(self, run_id: str) -> tuple[StepCost, ...]:
        """Calls, tokens and cost per step, in the order the steps first called a model."""
        ...


@dataclass(slots=True)
class _Call:
    step: str
    response: Response
    cost_usd: Decimal


@dataclass(slots=True)
class _Run:
    inputs_digest: str
    entries: list[Entry] = field(default_factory=list[Entry])
    done: dict[str, Json] = field(default_factory=dict[str, Json])
    calls: dict[str, _Call] = field(default_factory=dict[str, _Call])


def summarize(calls: Sequence[tuple[str, Response, Decimal]]) -> tuple[StepCost, ...]:
    """Group (step, response, cost) rows by step, keeping the order of first appearance."""
    by_step: dict[str, StepCost] = {}
    for step, response, cost in calls:
        so_far = by_step.get(step, StepCost(step, 0, 0, 0, Decimal(0)))
        by_step[step] = StepCost(
            step,
            so_far.calls + 1,
            so_far.input_tokens + response.usage.input_tokens,
            so_far.output_tokens + response.usage.output_tokens,
            so_far.cost_usd + cost,
        )
    return tuple(by_step.values())


class MemoryJournal:
    """Lives as long as the object; used where no database is wanted."""

    def __init__(self) -> None:
        self._runs: dict[str, _Run] = {}

    async def open(self, run_id: str, inputs_digest: str) -> RunState:
        run = self._runs.setdefault(run_id, _Run(inputs_digest))
        if run.inputs_digest != inputs_digest:
            raise InputsChanged(run_id)
        return RunState(run_id, tuple(run.entries), dict(run.done))

    async def call(self, run_id: str, key: str) -> Response | None:
        found = self._runs[run_id].calls.get(key)
        return found.response if found else None

    async def record_call(
        self, run_id: str, step: str, key: str, response: Response, cost_usd: Decimal
    ) -> None:
        self._runs[run_id].calls.setdefault(key, _Call(step, response, cost_usd))

    async def commit(self, run_id: str, step: str, entries: Sequence[Entry], result: Json) -> None:
        run = self._runs[run_id]
        last = run.entries[-1].tx if run.entries else 0
        if step in run.done or any(entry.tx <= last for entry in entries):
            raise StepRepeated(step)
        run.entries.extend(entries)
        run.done[step] = result

    async def spent(self, run_id: str) -> Decimal:
        return sum((call.cost_usd for call in self._runs[run_id].calls.values()), Decimal(0))

    async def keys(self, run_id: str, step: str) -> frozenset[str]:
        calls = self._runs[run_id].calls.items()
        return frozenset(key for key, call in calls if call.step == step)

    async def costs(self, run_id: str) -> tuple[StepCost, ...]:
        calls = self._runs[run_id].calls.values()
        return summarize([(call.step, call.response, call.cost_usd) for call in calls])
