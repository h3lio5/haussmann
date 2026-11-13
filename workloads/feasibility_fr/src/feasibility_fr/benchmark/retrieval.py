"""Does a ranking put the page that states a fact among the first results?

    python -m feasibility_fr.benchmark.retrieval

Compares three rankings of a scenario's pages for each fact, using the fact's wording as
the query: keywords (BM25), embeddings, and the two fused by reciprocal rank. It reads
the vectors the retrieval baseline recorded, so no model is called. Writes
`benchmark_data/results/retrieval.md`.
"""

import argparse
import asyncio
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from feasibility_fr.benchmark.answer import questions
from feasibility_fr.benchmark.baselines import cosine
from feasibility_fr.benchmark.reading import read_folder
from feasibility_fr.benchmark.render import FILES_DIR
from feasibility_fr.benchmark.run import DEFAULT_DATA, EMBEDDING_MODEL, MODEL, selected
from feasibility_fr.benchmark.scenario import Scenario
from feasibility_fr.benchmark.scenarios import SCENARIOS
from haussmann.coretypes.values import FactKey
from haussmann.ctxkit.search import Index
from haussmann.evalkit.generator import MANIFEST_NAME
from haussmann.evalkit.groundtruth import StatementKind
from haussmann.evalkit.manifest import load_manifest
from haussmann.llmkit.embeddings import ReplayEmbedder
from haussmann.llmkit.replay import ReplayClient, ReplayStore

TOP = 5
RRF_K = 60
METHODS = ("keywords", "embeddings", "fused")


def fuse(rankings: Sequence[Sequence[int]]) -> list[int]:
    """Reciprocal rank fusion: each ranking gives a page 1 / (RRF_K + its rank)."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, page in enumerate(ranking, start=1):
            scores[page] = scores.get(page, 0.0) + 1 / (RRF_K + rank)
    return sorted(scores, key=lambda page: (-scores[page], page))


def first_rank(ranking: Sequence[int], wanted: set[int]) -> int | None:
    """The rank, from 1, of the first wanted page; None when the ranking has none of them."""
    return next((rank for rank, page in enumerate(ranking, start=1) if page in wanted), None)


@dataclass(frozen=True, slots=True)
class FactRanks:
    key: FactKey
    query: str
    ranks: dict[str, int | None]


@dataclass(frozen=True, slots=True)
class ScenarioRanks:
    scenario_id: str
    pages: int
    facts: tuple[FactRanks, ...]


async def rank_scenario(scenario: Scenario, data_dir: Path) -> ScenarioRanks:
    folder = data_dir / scenario.spec.id / FILES_DIR
    manifest = load_manifest((folder / MANIFEST_NAME).read_text(encoding="utf-8"))
    asked = questions([fact.key for fact in manifest.gold], scenario.wording, scenario.totals)
    replay = ReplayClient(ReplayStore(data_dir / "recordings" / "completions"))
    pages = await read_folder(folder, replay, MODEL)
    embedder = ReplayEmbedder(data_dir / "recordings" / "embeddings")
    texts = [question.text for question in asked] + [page.text for page in pages]
    vectors = (await embedder.embed(EMBEDDING_MODEL, texts)).vectors
    queries, page_vectors = vectors[: len(asked)], vectors[len(asked) :]

    position = {(page.doc_id, page.locator): number for number, page in enumerate(pages)}
    stating: dict[FactKey, set[int]] = {}
    for file in manifest.files:
        for stated in file.statements:
            place = (stated.doc_id, (stated.locator or "").split("!")[0])
            if stated.kind is not StatementKind.DISTRACTOR and place in position:
                stating.setdefault(stated.key, set()).add(position[place])

    index = Index(pages)
    facts: list[FactRanks] = []
    for number, question in enumerate(asked):
        wanted = stating.get(question.key)
        if not wanted:
            continue
        hits = index.search(question.text, len(pages))
        keywords = [position[(hit.element.doc_id, hit.element.locator)] for hit in hits]
        query = queries[number]
        embeddings = sorted(
            range(len(pages)), key=lambda page: (-cosine(query, page_vectors[page]), page)
        )
        rankings = {
            "keywords": keywords,
            "embeddings": embeddings,
            "fused": fuse([keywords, embeddings]),
        }
        ranks = {name: first_rank(ranking, wanted) for name, ranking in rankings.items()}
        facts.append(FactRanks(question.key, question.text, ranks))
    return ScenarioRanks(scenario.spec.id, len(pages), tuple(facts))


def within(rank: int | None) -> bool:
    return rank is not None and rank <= TOP


def report(results: Sequence[ScenarioRanks]) -> str:
    lines = [
        "# Retrieval report",
        "",
        f"For each fact that some page states, the rank of the first such page when the pages"
        f" are ranked for the fact's wording. A fact counts when that rank is {TOP} or better,"
        " the number of results the finder's search returns.",
        "",
        "| scenario | pages | facts | " + " | ".join(METHODS) + " |",
        "|---|---|---|" + "---|" * len(METHODS),
    ]
    for result in results:
        counts = [sum(within(fact.ranks[m]) for fact in result.facts) for m in METHODS]
        cells = " | ".join(f"{count}/{len(result.facts)}" for count in counts)
        lines.append(f"| {result.scenario_id} | {result.pages} | {len(result.facts)} | {cells} |")
    lines += ["", "## Facts that a ranking leaves below the first results", ""]
    lines += ["| scenario | fact | query | " + " | ".join(METHODS) + " |"]
    lines += ["|---|---|---|" + "---|" * len(METHODS)]
    for result in results:
        for fact in result.facts:
            if all(within(rank) for rank in fact.ranks.values()):
                continue
            ranks = " | ".join(str(fact.ranks[m] or "not ranked") for m in METHODS)
            name = f"{fact.key.subject}/{fact.key.attribute}"
            lines.append(f"| {result.scenario_id} | {name} | {fact.query} | {ranks} |")
    return "\n".join(lines) + "\n"


async def run(data_dir: Path, scenarios: Sequence[Scenario]) -> list[ScenarioRanks]:
    return [await rank_scenario(scenario, data_dir) for scenario in scenarios]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()
    results = asyncio.run(run(args.data, selected(list(SCENARIOS.values()), False)))
    text = report(results)
    (args.data / "results" / "retrieval.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
