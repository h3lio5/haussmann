"""An expert's correction and a reviewer's comment on a real memo, measured.

    python -m feasibility_fr.benchmark.review [--live]

On one dev scenario: the engine and the memo are replayed from recordings; an expert sets
a fact the engine left open; the memo is rebuilt and compared with the one before; then a
comment asks the model to reword a section and the proposal is checked. Two model calls
are new. Writes `benchmark_data/results/review.md` and the scenario's `review/` folder.
"""

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path

import httpx

from feasibility_fr.benchmark.answer import questions
from feasibility_fr.benchmark.memos import coverage, typed_digits
from feasibility_fr.benchmark.reading import read_folder
from feasibility_fr.benchmark.render import FILES_DIR
from feasibility_fr.benchmark.run import BASE_URL, DEFAULT_DATA, KEY_VARIABLE, MODEL
from feasibility_fr.benchmark.scenarios import SCENARIOS
from feasibility_fr.workload import FLAG_MARK, WORKLOAD
from haussmann.buildkit.build import Sentence
from haussmann.coretypes.values import FactKey
from haussmann.engine.ingest import describe_documents
from haussmann.engine.memo import Memo, memo_step, render, revise_step
from haussmann.engine.run import apply_edit, run_engine
from haussmann.evalkit.generator import MANIFEST_NAME
from haussmann.evalkit.manifest import load_manifest
from haussmann.flow.journal import MemoryJournal, StepCost
from haussmann.flow.runner import NO_CAP, open_run
from haussmann.llmkit.chat_completions import ChatCompletionsClient
from haussmann.llmkit.client import LLMClient
from haussmann.llmkit.pricing import PRICES
from haussmann.llmkit.replay import ReplayClient, ReplayMiss, ReplayStore
from haussmann.review.diff import SectionDiff, diff
from haussmann.review.proposal import Proposal, accept
from haussmann.review.state import Approve, Event, State, states, version

SCENARIO = "champagnole_ecole"
KEY = FactKey("site", "owner")
VALUE = "Commune de Champagnole"
REASON = "The notary's note for the property names the commune."
AUTHOR = "reviewer"
SECTION = "site"
COMMENT = "Regroupez la référence cadastrale et la contenance dans une seule phrase."
REVIEW_DIR = "review"
LIVE_ESTIMATE_USD = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class Review:
    before: Memo
    after: Memo
    changes: tuple[SectionDiff, ...]
    proposal: Proposal
    final: Memo
    kept_approvals: int
    approvals: int
    costs: tuple[StepCost, ...]
    text_before: str
    text_after: str
    text_final: str


async def run(data_dir: Path, client: LLMClient) -> Review:
    scenario = SCENARIOS[SCENARIO]
    folder = data_dir / SCENARIO / FILES_DIR
    manifest = load_manifest((folder / MANIFEST_NAME).read_text(encoding="utf-8"))
    asked = questions([fact.key for fact in manifest.gold], scenario.wording, scenario.totals)
    pages = await read_folder(folder, client, MODEL)
    cards = await describe_documents(WORKLOAD, pages, client, MODEL)
    as_of = max(plan.date for plan in scenario.spec.documents)
    journal = MemoryJournal()
    runner = await open_run(journal, "review", "", client, PRICES, NO_CAP)
    await run_engine(WORKLOAD, asked, pages, cards, runner, MODEL, as_of)
    cache: dict[str, tuple[Sentence, ...]] = {}
    before = await memo_step(WORKLOAD, runner, asked, MODEL, cache)
    events: list[Event] = [
        Approve(built.section_id, version(built), AUTHOR) for built in before.built
    ]

    await apply_edit(WORKLOAD, runner, asked, pages, cards, as_of, KEY, VALUE, REASON, AUTHOR)
    after = await memo_step(WORKLOAD, runner, asked, MODEL, cache)
    changes = diff(
        before.built,
        after.built,
        {item.input.name: item.input for item in before.bound},
        {item.input.name: item.input for item in after.bound},
        FLAG_MARK,
    )
    current = states(after.built, events)
    had = [s for s, state in states(before.built, events).items() if state is State.APPROVED]

    proposal = await revise_step(WORKLOAD, runner, after, SECTION, COMMENT, MODEL)
    final = after if proposal.refused else replace(after, built=accept(after.built, proposal))
    return Review(
        before,
        after,
        changes,
        proposal,
        final,
        sum(1 for section in had if current[section] is State.APPROVED),
        len(had),
        await journal.costs("review"),
        render(WORKLOAD, before, as_of),
        render(WORKLOAD, after, as_of),
        render(WORKLOAD, final, as_of),
    )


def report(review: Review) -> str:
    rewritten = [built.section_id for built in review.after.built if not built.reused]
    memo_calls = [cost for cost in review.costs if cost.step.startswith("memo:")]
    rebuild = memo_calls[-1] if len(memo_calls) > 1 else None
    revise = next((c for c in review.costs if c.step.startswith("revise:")), None)
    stated, total = coverage(review.final)
    lines = [
        "# Review report",
        "",
        f"Scenario `{SCENARIO}`. An expert sets `{KEY.subject}/{KEY.attribute}`, which the"
        " engine had left as an open question; then a comment asks for a rewording.",
        "",
        "## After the edit",
        "",
        "| measure | value |",
        "|---|---|",
        f"| sections rewritten | {len(rewritten)} of {len(review.after.built)}"
        f" ({', '.join(rewritten)}) |",
        f"| model calls for the rebuild | {rebuild.calls if rebuild else 0} |",
        f"| cost of the rebuild, USD | {rebuild.cost_usd if rebuild else Decimal(0):.5f} |",
        f"| approvals still valid | {review.kept_approvals} of {review.approvals} |",
        f"| digits typed by the model | {typed_digits(review.after)} |",
        "",
        "| section | value | before | after |",
        "|---|---|---|---|",
    ]
    for change in review.changes:
        for value in change.values:
            lines.append(
                f"| {change.section_id} | {value.name} | {value.before or 'absent'} "
                f"| {value.after or 'absent'} |"
            )
    for change in review.changes:
        lines += ["", f"Section `{change.section_id}`:", ""]
        lines += [f"- removed: {text}" for text in change.removed]
        lines += [f"- added: {text}" for text in change.added]
    lines += [
        "",
        "## After the comment",
        "",
        f"Comment on `{SECTION}`: {COMMENT}",
        "",
        "| measure | value |",
        "|---|---|",
        f"| proposal | {'refused' if review.proposal.refused else 'holds, accepted'} |",
        f"| model calls | {revise.calls if revise else 0} |",
        f"| cost, USD | {revise.cost_usd if revise else Decimal(0):.5f} |",
        f"| digits typed by the model | {typed_digits(review.final)} |",
        f"| facts stated in the memo | {stated} of {total} |",
        "",
    ]
    if review.proposal.refused:
        lines += [f"- refused: {reason}" for reason in review.proposal.refused]
    else:
        section = next(b for b in review.final.built if b.section_id == SECTION)
        lines += [f"- {sentence.text}" for sentence in section.sentences]
    return "\n".join(lines) + "\n"


def write(review: Review, data_dir: Path) -> None:
    folder = data_dir / SCENARIO / REVIEW_DIR
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "memo_before.md").write_text(review.text_before, encoding="utf-8")
    (folder / "memo_after_edit.md").write_text(review.text_after, encoding="utf-8")
    (folder / "memo_after_comment.md").write_text(review.text_final, encoding="utf-8")
    changes = [
        {
            "section": change.section_id,
            "rewritten": change.rewritten,
            "values": [[v.name, v.before, v.after] for v in change.values],
            "removed": list(change.removed),
            "added": list(change.added),
        }
        for change in review.changes
    ]
    text = json.dumps(changes, ensure_ascii=False, indent=2) + "\n"
    (folder / "diff.json").write_text(text, encoding="utf-8")
    (data_dir / "results" / "review.md").write_text(report(review), encoding="utf-8")


async def _main(args: argparse.Namespace) -> int:
    store = ReplayStore(args.data / "recordings" / "completions")
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
            review = await run(args.data, client)
        except ReplayMiss as miss:
            print(f"a call has no recording ({miss}); record it with --live")
            return 1
    write(review, args.data)
    print(report(review))
    return 0


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--live", action="store_true")
    return asyncio.run(_main(parser.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
