"""Kill a run and continue it, with the journal in Postgres, and report what it cost.

    python -m feasibility_fr.benchmark.durable

Runs the large dev scenario from recordings, so no model is paid. A worker process is
killed with SIGKILL at three points and a second worker continues the run. Needs
HAUSSMANN_DB_URL. Writes `benchmark_data/results/durable.md`.
"""

import argparse
import asyncio
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from feasibility_fr.benchmark.answer import questions
from feasibility_fr.benchmark.reading import read_folder
from feasibility_fr.benchmark.render import FILES_DIR
from feasibility_fr.benchmark.run import DEFAULT_DATA, MODEL
from feasibility_fr.benchmark.scenarios import SCENARIOS
from feasibility_fr.engine.documents import DOCUMENT_AUTHORITY
from feasibility_fr.engine.ingest import describer
from feasibility_fr.engine.memo import memo_step, render
from feasibility_fr.engine.run import inputs_digest, run_engine
from feasibility_fr.schema import ATTRIBUTES
from haussmann.docparse.cards import build_cards
from haussmann.evalkit.generator import MANIFEST_NAME
from haussmann.evalkit.manifest import load_manifest
from haussmann.flow.journal import Journal, MemoryJournal, StepCost
from haussmann.flow.postgres import PostgresJournal, connect
from haussmann.flow.runner import NO_CAP, Counts, open_run
from haussmann.ledger.codec import encode_entry
from haussmann.llmkit.client import LLMClient, Request, Response
from haussmann.llmkit.pricing import PRICES, cost_usd
from haussmann.llmkit.replay import ReplayClient, ReplayStore, request_key

SCENARIO = "sainte_genevieve_gendarmerie"
URL_VARIABLE = "HAUSSMANN_DB_URL"
TIMED_RUNS = 3


class Noting:
    """Passes calls on, writes each key to a file first, and can kill the process instead."""

    def __init__(self, inner: LLMClient, log: Path | None, kill_before: int | None) -> None:
        self.keys: list[str] = []
        self.responses: list[Response] = []
        self._inner = inner
        self._log = log
        self._kill_before = kill_before

    async def complete(self, request: Request, *, sample: int = 0) -> Response:
        if self._kill_before is not None and len(self.keys) >= self._kill_before:
            os.kill(os.getpid(), signal.SIGKILL)
        key = request_key(request, sample)
        self.keys.append(key)
        if self._log is not None:
            with self._log.open("a", encoding="utf-8") as log:
                log.write(key + "\n")
        response = await self._inner.complete(request, sample=sample)
        self.responses.append(response)
        return response


@dataclass(frozen=True, slots=True)
class Outcome:
    """`result` is a digest of the final ledger and the rendered memo."""

    result: str
    keys: tuple[str, ...]
    counts: Counts
    costs: tuple[StepCost, ...]
    priced: Decimal
    seconds: float


async def one_run(
    data_dir: Path, journal: Journal, run_id: str, log: Path | None, kill_before: int | None
) -> Outcome:
    scenario = SCENARIOS[SCENARIO]
    folder = data_dir / SCENARIO / FILES_DIR
    manifest = load_manifest((folder / MANIFEST_NAME).read_text(encoding="utf-8"))
    asked = questions([fact.key for fact in manifest.gold], scenario.wording, scenario.totals)
    replay = ReplayClient(ReplayStore(data_dir / "recordings" / "completions"))
    pages = await read_folder(folder, replay, MODEL)
    cards = await build_cards(pages, describer(replay, MODEL), DOCUMENT_AUTHORITY)
    as_of = max(plan.date for plan in scenario.spec.documents)
    client = Noting(replay, log, kill_before)
    started = time.perf_counter()
    digest = inputs_digest(asked, pages, MODEL, as_of)
    runner = await open_run(journal, run_id, digest, client, PRICES, NO_CAP)
    await run_engine(asked, pages, cards, ATTRIBUTES, runner, MODEL, as_of)
    memo = await memo_step(runner, asked, ATTRIBUTES, MODEL, {})
    seconds = time.perf_counter() - started
    entries = [encode_entry(entry) for entry in runner.ledger.since(0)]
    text = json.dumps(entries, sort_keys=True, ensure_ascii=False) + render(memo, as_of)
    return Outcome(
        hashlib.sha256(text.encode()).hexdigest(),
        tuple(client.keys),
        runner.counts,
        await journal.costs(run_id),
        sum((cost_usd(MODEL, r.usage) for r in client.responses), Decimal(0)),
        seconds,
    )


async def in_postgres(
    data_dir: Path, run_id: str, log: Path | None = None, kill_before: int | None = None
) -> Outcome:
    connection = await connect(os.environ[URL_VARIABLE])
    try:
        return await one_run(data_dir, PostgresJournal(connection), run_id, log, kill_before)
    finally:
        await connection.close()


def worker(data_dir: Path, run_id: str, log: Path, kill_before: int | None) -> int:
    """One process of a run. Prints its result on one line, unless it is killed first."""
    done = asyncio.run(in_postgres(data_dir, run_id, log, kill_before))
    counts = done.counts
    print(
        json.dumps({"result": done.result, "paid": counts.calls_paid, "orphaned": counts.orphaned})
    )
    return 0


@dataclass(frozen=True, slots=True)
class Kill:
    where: str
    before_call: int
    exit_code: int
    sent_before: int
    sent_after: int
    repeated: int
    orphaned: int
    same_result: bool


def start(
    data_dir: Path, run_id: str, log: Path, kill_before: int | None
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "feasibility_fr.benchmark.durable", "--data", str(data_dir)]
    command += ["--worker", run_id, "--log", str(log)]
    if kill_before is not None:
        command += ["--kill-before", str(kill_before)]
    return subprocess.run(command, capture_output=True, text=True, check=False)


def kill_and_resume(data_dir: Path, scratch: Path, where: str, before: int, whole: Outcome) -> Kill:
    run_id = f"durable-{uuid.uuid4()}"
    first_log, second_log = scratch / f"{run_id}.1", scratch / f"{run_id}.2"
    killed = start(data_dir, run_id, first_log, before)
    resumed = start(data_dir, run_id, second_log, None)
    if resumed.returncode != 0:
        raise RuntimeError(resumed.stderr)
    report = json.loads(resumed.stdout.strip().splitlines()[-1])
    sent_before = first_log.read_text(encoding="utf-8").split() if first_log.exists() else []
    sent_after = second_log.read_text(encoding="utf-8").split() if second_log.exists() else []
    return Kill(
        where,
        before,
        killed.returncode,
        len(sent_before),
        len(sent_after),
        len(set(sent_before) & set(sent_after)),
        report["orphaned"],
        report["result"] == whole.result and (*sent_before, *sent_after) == whole.keys,
    )


def kill_points(costs: Sequence[StepCost]) -> list[tuple[str, int]]:
    """Call numbers at which to kill: inside a finder step, at a step boundary, inside the memo."""
    starts: dict[str, int] = {}
    total = 0
    for cost in costs:
        starts[cost.step] = total
        total += cost.calls
    finders = [cost for cost in costs if cost.step.startswith("find:") and cost.calls >= 4]
    middle = finders[len(finders) // 2]
    boundary = finders[-1]
    memo = next(cost for cost in costs if cost.step.startswith("memo:"))
    return [
        (f"inside a finder step ({middle.step})", starts[middle.step] + middle.calls // 2),
        (f"between two steps (before {boundary.step})", starts[boundary.step]),
        ("inside the memo", starts[memo.step] + memo.calls // 2),
    ]


def median(values: Sequence[float]) -> float:
    return sorted(values)[len(values) // 2]


def report(whole: Outcome, memory_s: float, postgres_s: float, kills: Sequence[Kill]) -> str:
    calls = len(whole.keys)
    total = sum((cost.cost_usd for cost in whole.costs), Decimal(0))
    lines = [
        "# Durable run report",
        "",
        f"Scenario `{SCENARIO}`, from recordings. One run: {len(whole.costs)} steps that call"
        f" a model, {calls} model calls.",
        "",
        "## Killed with SIGKILL, then continued by a new process",
        "",
        "Exit code -9 is the kill. A call is counted as sent when it reaches the client below"
        " the journal. Orphaned calls are calls the killed process paid for that the"
        " continued step never asked for.",
        "",
        "| killed | before call | exit code | calls sent before | calls sent after "
        "| sent twice | orphaned | same ledger and memo |",
        "|" + "---|" * 8,
    ]
    lines += [
        f"| {k.where} | {k.before_call + 1} of {calls} | {k.exit_code} | {k.sent_before} "
        f"| {k.sent_after} | {k.repeated} | {k.orphaned} | {'yes' if k.same_result else 'NO'} |"
        for k in kills
    ]
    lines += [
        "",
        "## Time added by the journal",
        "",
        f"Median of {TIMED_RUNS} uninterrupted runs, engine and memo, model calls served from"
        " recordings on disk:",
        "",
        "| journal | seconds |",
        "|---|---|",
        f"| memory | {memory_s:.2f} |",
        f"| Postgres, local | {postgres_s:.2f} |",
        "",
        "## Cost per step",
        "",
        "From the journal's record of calls: the cost the provider reported with each response,"
        " or list price times tokens when it reported none.",
        "",
        "| step | calls | tokens in | tokens out | USD |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {c.step} | {c.calls} | {c.input_tokens} | {c.output_tokens} | {c.cost_usd:.5f} |"
        for c in whole.costs
    ]
    lines += [
        f"| **total** | {calls} | {sum(c.input_tokens for c in whole.costs)} "
        f"| {sum(c.output_tokens for c in whole.costs)} | {total:.5f} |",
        "",
        f"The same responses priced one by one as they were received, outside the journal:"
        f" {whole.priced:.5f} USD ({'equal' if whole.priced == total else 'DIFFERENT'}). This"
        " checks that the journal stores and sums costs without loss; both figures use the"
        " same pricing function.",
    ]
    return "\n".join(lines) + "\n"


def measure(data_dir: Path) -> str:
    memory = [
        asyncio.run(one_run(data_dir, MemoryJournal(), "memory", None, None))
        for _ in range(TIMED_RUNS)
    ]
    postgres = [
        asyncio.run(in_postgres(data_dir, f"durable-{uuid.uuid4()}")) for _ in range(TIMED_RUNS)
    ]
    whole = postgres[0]
    if any(run.result != whole.result or run.keys != whole.keys for run in memory + postgres):
        raise RuntimeError("uninterrupted runs differ from each other")
    scratch = data_dir / "results" / ".durable"
    scratch.mkdir(parents=True, exist_ok=True)
    kills = [
        kill_and_resume(data_dir, scratch, where, before, whole)
        for where, before in kill_points(whole.costs)
    ]
    for file in scratch.iterdir():
        file.unlink()
    scratch.rmdir()
    return report(
        whole,
        median([run.seconds for run in memory]),
        median([run.seconds for run in postgres]),
        kills,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--worker", metavar="RUN_ID")
    parser.add_argument("--log", type=Path)
    parser.add_argument("--kill-before", type=int)
    args = parser.parse_args()
    if not os.environ.get(URL_VARIABLE):
        print(f"{URL_VARIABLE} is not set")
        return 2
    if args.worker:
        return worker(args.data, args.worker, args.log, args.kill_before)
    text = measure(args.data)
    (args.data / "results" / "durable.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
