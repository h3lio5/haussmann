"""Open the dev scenarios for review from recordings and serve them.

    python -m feasibility_fr.app.demo [--port 8000]

No model key is needed: the engine, the memos and the recorded edits are replayed. An
action that would need a new model call is refused. With OPENROUTER_API_KEY set and
`--live`, missing calls are made and recorded. With `--traces URL`, spans are sent to an
OTLP endpoint, for example the viewer of `docker compose --profile traces up -d`:

    python -m feasibility_fr.app.demo --traces http://127.0.0.1:4318
"""

import argparse
import asyncio
import os
import sys
from collections.abc import Callable
from pathlib import Path

import httpx
import uvicorn

from feasibility_fr.app.http import create_app
from feasibility_fr.app.session import Session
from feasibility_fr.benchmark.answer import questions
from feasibility_fr.benchmark.cases import CASES_FILE
from feasibility_fr.benchmark.reading import read_folder
from feasibility_fr.benchmark.render import FILES_DIR
from feasibility_fr.benchmark.run import BASE_URL, DEFAULT_DATA, KEY_VARIABLE, MODEL, selected
from feasibility_fr.benchmark.scenarios import SCENARIOS
from feasibility_fr.engine.ingest import describe_documents
from haussmann.evalkit.cases import Case, load_cases
from haussmann.evalkit.generator import MANIFEST_NAME
from haussmann.evalkit.manifest import load_manifest
from haussmann.flow.journal import MemoryJournal
from haussmann.flow.runner import NO_CAP, open_run
from haussmann.llmkit.chat_completions import ChatCompletionsClient
from haussmann.llmkit.client import LLMClient
from haussmann.llmkit.pricing import PRICES
from haussmann.llmkit.replay import ReplayClient, ReplayStore


async def open_scenario(
    data_dir: Path, scenario_id: str, client: LLMClient, rehearse: bool
) -> Session:
    scenario = SCENARIOS[scenario_id]
    folder = data_dir / scenario_id / FILES_DIR
    manifest = load_manifest((folder / MANIFEST_NAME).read_text(encoding="utf-8"))
    asked = questions([fact.key for fact in manifest.gold], scenario.wording, scenario.totals)
    pages = await read_folder(folder, client, MODEL)
    cards = await describe_documents(pages, client, MODEL)
    as_of = max(plan.date for plan in scenario.spec.documents)
    runner = await open_run(MemoryJournal(), scenario_id, "", client, PRICES, NO_CAP)
    with runner.span():
        return await Session.open(
            scenario_id,
            scenario_id,
            folder,
            runner,
            client,
            asked,
            pages,
            cards,
            as_of,
            MODEL,
            rehearse,
        )


async def open_all(data_dir: Path, client: LLMClient, rehearse: bool) -> dict[str, Session]:
    scenarios = selected(list(SCENARIOS.values()), False)
    return {
        scenario.spec.id: await open_scenario(data_dir, scenario.spec.id, client, rehearse)
        for scenario in scenarios
    }


def committed_cases(data_dir: Path) -> list[Case]:
    return load_cases((data_dir / CASES_FILE).read_text(encoding="utf-8"))


def measured(data_dir: Path, experiments: Path) -> dict[str, str]:
    """The experiment log, the benchmark report and the state of the regression cases."""
    files = {
        "experiments": experiments,
        "report": data_dir / "results" / "report.md",
        "cases": data_dir / "results" / "cases.md",
    }
    return {name: path.read_text(encoding="utf-8") for name, path in files.items() if path.exists()}


def export_traces(endpoint: str) -> Callable[[], None]:
    """Send this process's spans to an OTLP endpoint; returns what to call before exit so
    that pending spans are sent. The SDK and the exporter are development dependencies and
    are imported only when traces are asked for."""
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": "haussmann"}))
    exporter = OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return provider.shutdown


async def _serve(args: argparse.Namespace) -> int:
    store = ReplayStore(args.data / "recordings" / "completions")
    async with httpx.AsyncClient(timeout=300) as http:
        client: LLMClient = ReplayClient(store)
        if args.live:
            key = os.environ.get(KEY_VARIABLE)
            if not key:
                print(f"{KEY_VARIABLE} is not set")
                return 2
            routing = {"provider": {"require_parameters": True}}
            client = ReplayClient(
                store, ChatCompletionsClient(BASE_URL, key, http, extra_body=routing)
            )
        sessions = await open_all(args.data, client, rehearse=not args.live)
        if args.traces:
            print(f"one trace per file sent to {args.traces}")
        screen = args.screen if (args.screen / "index.html").exists() else None
        if screen is None:
            print(f"{args.screen} is not built; serving the API only (cd web && npm run build)")
        app = create_app(
            sessions,
            lambda: committed_cases(args.data),
            screen,
            lambda: measured(args.data, args.experiments),
        )
        config = uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="info")
        await uvicorn.Server(config).serve()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--screen", type=Path, default=Path("web/dist"))
    parser.add_argument("--experiments", type=Path, default=Path("EXPERIMENTS.md"))
    parser.add_argument("--traces", metavar="URL", default="")
    args = parser.parse_args()
    flush = export_traces(args.traces) if args.traces else None
    try:
        return asyncio.run(_serve(args))
    finally:
        if flush is not None:
            flush()


if __name__ == "__main__":
    sys.exit(main())
