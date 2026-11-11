"""Run every system on every scenario and write the report.

Run: python -m feasibility_fr.benchmark.run [--live] [--samples 3] [--cap-usd 2.0]
"""

import argparse
import asyncio
import datetime as dt
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import httpx

from feasibility_fr.benchmark.answer import questions
from feasibility_fr.benchmark.baselines import ANSWER_MAX_TOKENS, Attempt, naive_rag, one_prompt
from feasibility_fr.benchmark.reading import TRANSCRIPTION_MAX_TOKENS, read_folder, scan_folder
from feasibility_fr.benchmark.render import FILES_DIR
from feasibility_fr.benchmark.scenario import Scenario
from feasibility_fr.benchmark.scenarios import SCENARIOS
from feasibility_fr.benchmark.schema import ATTRIBUTES
from haussmann.evalkit.generator import MANIFEST_NAME
from haussmann.evalkit.groundtruth import Manifest, Split
from haussmann.evalkit.manifest import load_manifest
from haussmann.evalkit.report import RunRecord, experiment_row, render_report
from haussmann.evalkit.scorer import InvalidSubmission, score
from haussmann.llmkit.chat_completions import ChatCompletionsClient
from haussmann.llmkit.client import LLMClient, Usage
from haussmann.llmkit.embeddings import Embedder, EmbeddingMiss, EmbeddingsClient, ReplayEmbedder
from haussmann.llmkit.pricing import cost_usd
from haussmann.llmkit.replay import ReplayClient, ReplayMiss, ReplayStore

MODEL = "mistralai/mistral-small-2603"
EMBEDDING_MODEL = "baai/bge-m3"
BASE_URL = "https://openrouter.ai/api/v1"
KEY_VARIABLE = "OPENROUTER_API_KEY"
SYSTEMS = ("one_prompt", "naive_rag")
DEFAULT_DATA = Path("workloads/feasibility_fr/benchmark_data")
CHARS_PER_TOKEN = 3
TOKENS_PER_IMAGE = 2000
PROMPT_OVERHEAD_TOKENS = 3000


@dataclass(frozen=True, slots=True)
class Clients:
    llm: LLMClient
    embedder: Embedder


class OverCap(RuntimeError):
    pass


def selected(scenarios: Sequence[Scenario], include_heldout: bool) -> list[Scenario]:
    """Held-out scenarios are left out unless asked for."""
    return [s for s in scenarios if include_heldout or s.spec.split is not Split.HELDOUT]


def estimate_cost(data_dir: Path, scenarios: Sequence[Scenario], samples: int) -> Decimal:
    """An upper estimate of a fully live run, from what is on disk."""
    attempts = len(SYSTEMS) * samples
    tokens_in = tokens_out = 0
    for scenario in scenarios:
        pages = scan_folder(data_dir / scenario.spec.id / FILES_DIR)
        scans = sum(1 for page in pages if page.image is not None)
        text = sum(len(page.text) for page in pages) // CHARS_PER_TOKEN
        per_attempt = text + scans * TOKENS_PER_IMAGE + PROMPT_OVERHEAD_TOKENS
        tokens_in += attempts * per_attempt + scans * TOKENS_PER_IMAGE
        tokens_out += attempts * ANSWER_MAX_TOKENS + scans * TRANSCRIPTION_MAX_TOKENS
    return cost_usd(MODEL, Usage(tokens_in, tokens_out))


def check_cap(estimate: Decimal, cap: Decimal) -> None:
    if estimate > cap:
        raise OverCap(f"estimated {estimate:.2f} USD is above the cap of {cap:.2f} USD")


def _record(
    system: str, scenario: Scenario, sample: int, attempt: Attempt, manifest: Manifest
) -> RunRecord:
    result, failure = None, attempt.failure
    if attempt.submission is not None:
        try:
            result = score(manifest, ATTRIBUTES, attempt.submission)
        except InvalidSubmission as error:
            failure = str(error)
    cost = sum((cost_usd(MODEL, r.usage) for r in attempt.responses), attempt.embedding_cost_usd)
    latency = sum(r.latency_s for r in attempt.responses)
    spec = scenario.spec
    return RunRecord(system, spec.id, spec.split, sample, result, failure, cost, latency)


async def run_scenario(
    scenario: Scenario, folder: Path, clients: Clients, samples: int
) -> list[RunRecord]:
    manifest = load_manifest((folder / MANIFEST_NAME).read_text(encoding="utf-8"))
    asked = questions([fact.key for fact in manifest.gold], scenario.wording)
    pages = await read_folder(folder, clients.llm, MODEL)
    records: list[RunRecord] = []
    for system in SYSTEMS:
        for sample in range(samples):
            if system == "one_prompt":
                attempt = await one_prompt(pages, asked, ATTRIBUTES, clients.llm, MODEL, sample)
            else:
                attempt = await naive_rag(
                    pages,
                    asked,
                    ATTRIBUTES,
                    clients.llm,
                    clients.embedder,
                    MODEL,
                    EMBEDDING_MODEL,
                    sample,
                )
            records.append(_record(system, scenario, sample, attempt, manifest))
    return records


async def run(
    data_dir: Path, scenarios: Sequence[Scenario], clients: Clients, samples: int
) -> list[RunRecord]:
    records: list[RunRecord] = []
    for scenario in scenarios:
        folder = data_dir / scenario.spec.id / FILES_DIR
        records.extend(await run_scenario(scenario, folder, clients, samples))
    return records


async def _main(args: argparse.Namespace) -> int:
    data_dir: Path = args.data
    scenarios = selected(list(SCENARIOS.values()), args.include_heldout)
    store = ReplayStore(data_dir / "recordings" / "completions")
    vectors = data_dir / "recordings" / "embeddings"

    async with httpx.AsyncClient(timeout=300) as http:
        if args.live:
            key = os.environ.get(KEY_VARIABLE)
            if not key:
                print(f"{KEY_VARIABLE} is not set")
                return 2
            estimate = estimate_cost(data_dir, scenarios, args.samples)
            print(f"estimated cost if nothing is recorded yet: at most {estimate:.2f} USD")
            try:
                check_cap(estimate, args.cap_usd)
            except OverCap as error:
                print(f"refusing to run: {error}")
                return 2
            routing = {"provider": {"require_parameters": True}}
            live_llm = ChatCompletionsClient(BASE_URL, key, http, extra_body=routing)
            clients = Clients(
                ReplayClient(store, live_llm),
                ReplayEmbedder(vectors, EmbeddingsClient(BASE_URL, key, http)),
            )
        else:
            clients = Clients(ReplayClient(store), ReplayEmbedder(vectors))
        try:
            records = await run(data_dir, scenarios, clients, args.samples)
        except (ReplayMiss, EmbeddingMiss) as miss:
            print(f"a call has no recording ({miss}); record it with --live")
            return 1

    report = render_report(records)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    print(report)
    if args.experiment:
        experiment_id, change, hypothesis, decision = args.experiment.split("|")
        row = experiment_row(experiment_id, dt.date.today(), change, hypothesis, records, decision)
        with args.experiments_file.open("a", encoding="utf-8") as log:
            log.write(row + "\n")
    return 0


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--cap-usd", type=Decimal, default=Decimal("2.0"))
    parser.add_argument("--include-heldout", action="store_true")
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--experiment", help="id|change|hypothesis|decision")
    parser.add_argument("--experiments-file", type=Path, default=Path("EXPERIMENTS.md"))
    args = parser.parse_args(argv)
    if args.report is None:
        args.report = args.data / "results" / "report.md"
    return asyncio.run(_main(args))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
