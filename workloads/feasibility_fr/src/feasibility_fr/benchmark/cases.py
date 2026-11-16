"""Check the engine against the values experts set.

    python -m feasibility_fr.benchmark.cases [--update]

Each case in `benchmark_data/cases.json` names a scenario, a sample, a fact and the value
an expert gave it. The engine is replayed from recordings and what it settles on is
compared with the case. A held case that no longer passes is a regression and the command
fails. `--update` records each case's standing as this check finds it. Writes
`benchmark_data/results/cases.md`.
"""

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from feasibility_fr.benchmark.answer import questions
from feasibility_fr.benchmark.reading import read_folder
from feasibility_fr.benchmark.render import FILES_DIR
from feasibility_fr.benchmark.run import DEFAULT_DATA, MODEL
from feasibility_fr.benchmark.scenarios import SCENARIOS
from feasibility_fr.french import format_value
from feasibility_fr.schema import ATTRIBUTES
from feasibility_fr.workload import WORKLOAD
from haussmann.coretypes.values import Value, normalize
from haussmann.engine.ingest import describe_documents
from haussmann.engine.run import run_engine
from haussmann.evalkit.cases import (
    Case,
    Standing,
    dump_cases,
    load_cases,
    passes,
    regressions,
    restand,
)
from haussmann.evalkit.generator import MANIFEST_NAME
from haussmann.evalkit.manifest import load_manifest
from haussmann.flow.journal import MemoryJournal
from haussmann.flow.runner import NO_CAP, open_run
from haussmann.ledger.ledger import Ledger
from haussmann.llmkit.pricing import PRICES
from haussmann.llmkit.replay import ReplayClient, ReplayStore
from haussmann.verify.settle import settled

CASES_FILE = "cases.json"


async def replayed(data_dir: Path, scenario_id: str, sample: int) -> Ledger:
    """The ledger of one engine run on a scenario, from recordings."""
    scenario = SCENARIOS[scenario_id]
    folder = data_dir / scenario_id / FILES_DIR
    manifest = load_manifest((folder / MANIFEST_NAME).read_text(encoding="utf-8"))
    asked = questions([fact.key for fact in manifest.gold], scenario.wording, scenario.totals)
    replay = ReplayClient(ReplayStore(data_dir / "recordings" / "completions"))
    pages = await read_folder(folder, replay, MODEL)
    cards = await describe_documents(WORKLOAD, pages, replay, MODEL)
    as_of = max(plan.date for plan in scenario.spec.documents)
    runner = await open_run(MemoryJournal(), "cases", "", replay, PRICES, NO_CAP)
    return (await run_engine(WORKLOAD, asked, pages, cards, runner, MODEL, as_of, sample)).ledger


async def found(data_dir: Path, cases: Sequence[Case]) -> list[Value | None]:
    """What the engine settles on for each case's fact; one replay per scenario and sample."""
    ledgers: dict[tuple[str, int], Ledger] = {}
    values: list[Value | None] = []
    for case in cases:
        run = (case.scenario_id, case.sample)
        if run not in ledgers:
            ledgers[run] = await replayed(data_dir, *run)
        fact = settled(ledgers[run], case.key, ATTRIBUTES).fact
        values.append(fact.value if fact is not None else None)
    return values


def _shown(key_attribute: str, value: Value | None) -> str:
    if value is None:
        return "nothing"
    attribute = ATTRIBUTES[key_attribute]
    return format_value(normalize(value, attribute) or value, attribute)


def report(cases: Sequence[Case], values: Sequence[Value | None]) -> str:
    passing = [passes(case, value, ATTRIBUTES) for case, value in zip(cases, values, strict=True)]
    held = sum(1 for case in cases if case.standing is Standing.HELD)
    lines = [
        "# Regression cases",
        "",
        f"{len(cases)} cases: {held} held, {len(cases) - held} open."
        f" Regressions: {len(regressions(cases, passing))}.",
        "",
        "| scenario | sample | fact | expert's value | engine settles on | passes | standing |",
        "|---|---|---|---|---|---|---|",
    ]
    for case, value, ok in zip(cases, values, passing, strict=True):
        name = f"{case.key.subject}/{case.key.attribute}"
        lines.append(
            f"| {case.scenario_id} | {case.sample} | {name} "
            f"| {_shown(case.key.attribute, case.expected)} | {_shown(case.key.attribute, value)} "
            f"| {'yes' if ok else 'no'} | {case.standing.value} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()
    path = args.data / CASES_FILE
    cases = load_cases(path.read_text(encoding="utf-8"))
    values = asyncio.run(found(args.data, cases))
    passing = [passes(case, value, ATTRIBUTES) for case, value in zip(cases, values, strict=True)]
    broken = regressions(cases, passing)
    if args.update and not broken:
        cases = restand(cases, passing)
        path.write_text(dump_cases(cases), encoding="utf-8")
    text = report(cases, values)
    (args.data / "results" / "cases.md").write_text(text, encoding="utf-8")
    print(text)
    for case in broken:
        name = f"{case.key.subject}/{case.key.attribute}"
        print(f"REGRESSION: {case.scenario_id} sample {case.sample} {name}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
