import asyncio
from pathlib import Path

from feasibility_fr.benchmark.retrieval import first_rank, fuse, report, run
from feasibility_fr.benchmark.run import selected
from feasibility_fr.benchmark.scenarios import SCENARIOS

DATA = Path(__file__).parent.parent / "benchmark_data"


def test_fusion_prefers_a_page_both_rankings_place_high() -> None:
    assert fuse([[3, 1, 2], [1, 2, 3]]) == [1, 3, 2]
    assert fuse([[7], [8, 7]])[0] == 7


def test_a_page_missing_from_one_ranking_is_still_ranked() -> None:
    assert sorted(fuse([[1], [2, 3]])) == [1, 2, 3]


def test_first_rank_counts_from_one_and_reports_an_absent_page() -> None:
    assert first_rank([4, 9, 2], {2, 9}) == 2
    assert first_rank([4, 9], {1}) is None


def test_the_committed_retrieval_report_reproduces_from_recordings() -> None:
    results = asyncio.run(run(DATA, selected(list(SCENARIOS.values()), False)))
    assert report(results) == (DATA / "results" / "retrieval.md").read_text(encoding="utf-8")
