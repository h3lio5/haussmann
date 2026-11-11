"""Turn scored benchmark attempts into a report."""

import datetime as dt
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from haussmann.evalkit.groundtruth import Split, TrapType
from haussmann.evalkit.scorer import Rate, Score


@dataclass(frozen=True, slots=True)
class RunRecord:
    """One attempt of one system on one scenario. `score` is None when the attempt failed."""

    system: str
    scenario: str
    split: Split
    sample: int
    score: Score | None
    failure: str | None
    cost_usd: Decimal
    latency_s: float


_RATES: tuple[tuple[str, Callable[[Score], Rate]], ...] = (
    ("recall", lambda s: s.recall),
    ("precision", lambda s: s.precision),
    ("bait", lambda s: s.bait_rate),
    ("invented", lambda s: s.invented_rate),
    ("abstention", lambda s: s.abstention),
    ("citations", lambda s: s.citation_correctness),
)


def pooled(records: Sequence[RunRecord], rate: Callable[[Score], Rate]) -> Rate:
    """Sum counts and totals over attempts, so every fact weighs the same."""
    rates = [rate(record.score) for record in records if record.score is not None]
    return Rate(sum(r.count for r in rates), sum(r.total for r in rates))


def pooled_traps(records: Sequence[RunRecord]) -> dict[TrapType, Rate]:
    totals: dict[TrapType, Rate] = {}
    for record in records:
        if record.score is None:
            continue
        for kind, rate in record.score.traps_passed.items():
            seen = totals.get(kind, Rate(0, 0))
            totals[kind] = Rate(seen.count + rate.count, seen.total + rate.total)
    return totals


def _percent(rate: Rate) -> str:
    return "-" if rate.value is None else f"{rate.value:.0%} ({rate.count}/{rate.total})"


def _spread(records: Sequence[RunRecord]) -> str:
    values = [
        record.score.recall.value
        for record in records
        if record.score is not None and record.score.recall.value is not None
    ]
    return "-" if not values else f"{min(values):.0%} to {max(values):.0%}"


def _systems(records: Sequence[RunRecord]) -> list[str]:
    return list(dict.fromkeys(record.system for record in records))


def render_report(records: Sequence[RunRecord]) -> str:
    lines = ["# Benchmark report", ""]
    for split in Split:
        in_split = [record for record in records if record.split is split]
        if not in_split:
            continue
        scenarios = ", ".join(dict.fromkeys(record.scenario for record in in_split))
        lines += [f"## {split.value}: {scenarios}", ""]
        header = ["system", *(name for name, _ in _RATES), "recall spread", "failed runs"]
        header += ["cost USD", "mean latency s"]
        lines += ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
        for system in _systems(in_split):
            runs = [record for record in in_split if record.system == system]
            cells = [system, *(_percent(pooled(runs, rate)) for _, rate in _RATES)]
            failed = sum(1 for record in runs if record.score is None)
            cost = sum((record.cost_usd for record in runs), Decimal(0))
            latency = sum(record.latency_s for record in runs) / len(runs)
            cells += [_spread(runs), f"{failed}/{len(runs)}", f"{cost:.4f}", f"{latency:.1f}"]
            lines.append("| " + " | ".join(cells) + " |")
        lines += ["", "Traps passed, by type:", ""]
        kinds = sorted(TrapType)
        lines += [
            "| system | " + " | ".join(kind.value for kind in kinds) + " |",
            "|" + "---|" * (len(kinds) + 1),
        ]
        for system in _systems(in_split):
            traps = pooled_traps([record for record in in_split if record.system == system])
            cells = [_percent(traps.get(kind, Rate(0, 0))) for kind in kinds]
            lines.append(f"| {system} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


def experiment_row(
    experiment_id: str,
    date: dt.date,
    change: str,
    hypothesis: str,
    records: Sequence[RunRecord],
    decision: str,
    before: str = "-",
) -> str:
    """One row for the experiment log; metrics and cost come from the records."""
    splits = ", ".join(split.value for split in Split if any(r.split is split for r in records))
    after = "; ".join(
        f"{system}: recall {_percent(pooled(runs, _RATES[0][1]))}, "
        f"traps {_percent(_all_traps(runs))}"
        for system in _systems(records)
        for runs in [[record for record in records if record.system == system]]
    )
    cost = sum((record.cost_usd for record in records), Decimal(0))
    cells = [experiment_id, date.isoformat(), change, hypothesis, splits, before, after]
    return "| " + " | ".join([*cells, f"{cost:.4f}", decision]) + " |"


def _all_traps(records: Sequence[RunRecord]) -> Rate:
    traps = pooled_traps(records).values()
    return Rate(sum(r.count for r in traps), sum(r.total for r in traps))
