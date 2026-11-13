"""Build the memo of every dev scenario from its engine run, and measure a rebuild.

Run: python -m feasibility_fr.benchmark.memos [--live]
"""

import argparse
import asyncio
import json
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path

import httpx

from feasibility_fr.benchmark.answer import questions
from feasibility_fr.benchmark.reading import read_folder
from feasibility_fr.benchmark.render import FILES_DIR
from feasibility_fr.benchmark.run import BASE_URL, DEFAULT_DATA, KEY_VARIABLE, MODEL, selected
from feasibility_fr.benchmark.scenario import Scenario
from feasibility_fr.benchmark.scenarios import SCENARIOS
from feasibility_fr.engine.documents import DOCUMENT_AUTHORITY
from feasibility_fr.engine.ingest import describer
from feasibility_fr.engine.memo import ISSUE, MEMO, OPEN, Bound, Memo, record, render, write_memo
from feasibility_fr.engine.run import run_engine
from feasibility_fr.schema import ATTRIBUTES
from haussmann.buildkit.build import PLACEHOLDER, Sentence
from haussmann.docparse.cards import build_cards
from haussmann.evalkit.generator import MANIFEST_NAME
from haussmann.evalkit.manifest import load_manifest
from haussmann.flow.journal import MemoryJournal
from haussmann.flow.runner import NO_CAP, open_run
from haussmann.llmkit.chat_completions import ChatCompletionsClient
from haussmann.llmkit.client import LLMClient
from haussmann.llmkit.pricing import PRICES, cost_usd
from haussmann.llmkit.replay import ReplayClient, ReplayMiss, ReplayStore

MEMO_DIR = "memo"
EDITED = "site.land_area"
EDIT = "edited by a reviewer"
LIVE_ESTIMATE_USD = Decimal("0.05")
_DIGIT = re.compile(r"\d")


@dataclass(frozen=True, slots=True)
class MemoRun:
    """One scenario: its memo, and the same memo rebuilt after one input was edited."""

    scenario_id: str
    memo: Memo
    rebuilt: Memo
    text: str


def prose_sections() -> list[str]:
    return [section.id for section in MEMO.sections if section.kind == "prose"]


def typed_digits(memo: Memo) -> int:
    """Digits a draft typed itself: those left in a prose sentence once placeholders are out."""
    prose = set(prose_sections())
    return sum(
        len(_DIGIT.findall(PLACEHOLDER.sub("", sentence.text)))
        for built in memo.built
        if built.section_id in prose
        for sentence in built.sentences
    )


def coverage(memo: Memo) -> tuple[int, int]:
    """Settled facts stated in a sentence, out of all settled facts."""
    facts = {b.input.name for b in memo.bound if b.input.attribute not in (ISSUE, OPEN)}
    used = {name for built in memo.built for sentence in built.sentences for name in sentence.uses}
    return len(facts & used), len(facts)


def fallbacks(memo: Memo) -> int:
    return sum(1 for refusal in memo.refusals if refusal.draft == 2)


def edit(bound: Sequence[Bound], name: str) -> tuple[Bound, ...]:
    """The inputs after a reviewer corrects one value: its digest changes, nothing else does."""
    return tuple(
        replace(b, input=replace(b.input, digest=f"{b.input.digest}|{EDIT}"))
        if b.input.name == name
        else b
        for b in bound
    )


async def run_scenario(scenario: Scenario, data_dir: Path, client: LLMClient) -> MemoRun:
    folder = data_dir / scenario.spec.id / FILES_DIR
    manifest = load_manifest((folder / MANIFEST_NAME).read_text(encoding="utf-8"))
    asked = questions([fact.key for fact in manifest.gold], scenario.wording, scenario.totals)
    pages = await read_folder(folder, client, MODEL)
    cards = await build_cards(pages, describer(client, MODEL), DOCUMENT_AUTHORITY)
    as_of = max(plan.date for plan in scenario.spec.documents)
    runner = await open_run(MemoryJournal(), "memo", "", client, PRICES, NO_CAP)
    done = await run_engine(asked, pages, cards, ATTRIBUTES, runner, MODEL, as_of)
    cache: dict[str, tuple[Sentence, ...]] = {}
    memo = await write_memo(done.ledger, asked, ATTRIBUTES, client, MODEL, cache)
    changed = edit(memo.bound, EDITED)
    rebuilt = await write_memo(done.ledger, asked, ATTRIBUTES, client, MODEL, cache, bound=changed)
    return MemoRun(scenario.spec.id, memo, rebuilt, render(memo, as_of))


def _cost(memo: Memo) -> Decimal:
    return sum((cost_usd(MODEL, r.usage) for r in memo.responses), Decimal(0))


def summary(runs: Sequence[MemoRun]) -> str:
    header = (
        "| scenario | facts in memo | typed digits | dropped sentences | refused drafts "
        "| plain-list sections "
        "| cost USD | seconds | rewritten after one edit | calls after one edit |"
    )
    lines = ["# Memo report", "", header, "|" + "---|" * 10]
    sections = len(prose_sections())
    for run in runs:
        stated, total = coverage(run.memo)
        seconds = sum(r.latency_s for r in run.memo.responses)
        rewritten = sum(1 for built in run.rebuilt.built if not built.reused)
        lines.append(
            f"| {run.scenario_id} | {stated}/{total} | {typed_digits(run.memo)} "
            f"| {len(run.memo.dropped)} | {len(run.memo.refusals)} "
            f"| {fallbacks(run.memo)}/{sections} "
            f"| {_cost(run.memo):.4f} | {seconds:.1f} "
            f"| {rewritten}/{len(run.rebuilt.built)} | {len(run.rebuilt.responses)} |"
        )
    return "\n".join(lines) + "\n"


def write(runs: Sequence[MemoRun], data_dir: Path) -> None:
    for run in runs:
        folder = data_dir / run.scenario_id / MEMO_DIR
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "memo.md").write_text(run.text, encoding="utf-8")
        trace = json.dumps(record(run.memo), ensure_ascii=False, indent=2)
        (folder / "memo.json").write_text(trace + "\n", encoding="utf-8")
    results = data_dir / "results"
    results.mkdir(parents=True, exist_ok=True)
    (results / "memos.md").write_text(summary(runs), encoding="utf-8")


async def run(data_dir: Path, scenarios: Sequence[Scenario], client: LLMClient) -> list[MemoRun]:
    return [await run_scenario(scenario, data_dir, client) for scenario in scenarios]


async def _main(args: argparse.Namespace) -> int:
    data_dir: Path = args.data
    scenarios = selected(list(SCENARIOS.values()), False)
    store = ReplayStore(data_dir / "recordings" / "completions")
    async with httpx.AsyncClient(timeout=300) as http:
        if args.live:
            key = os.environ.get(KEY_VARIABLE)
            if not key:
                print(f"{KEY_VARIABLE} is not set")
                return 2
            print(f"estimated cost if nothing is recorded yet: at most {LIVE_ESTIMATE_USD} USD")
            routing = {"provider": {"require_parameters": True}}
            live = ChatCompletionsClient(BASE_URL, key, http, extra_body=routing)
            client: LLMClient = ReplayClient(store, live)
        else:
            client = ReplayClient(store)
        try:
            runs = await run(data_dir, scenarios, client)
        except ReplayMiss as miss:
            print(f"a call has no recording ({miss}); record it with --live")
            return 1
    write(runs, data_dir)
    print(summary(runs))
    return 0


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--live", action="store_true")
    return asyncio.run(_main(parser.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
