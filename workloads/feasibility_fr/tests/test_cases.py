"""The regression gate: every held case must still pass on the recordings."""

import asyncio
from dataclasses import replace
from pathlib import Path

from feasibility_fr.benchmark.cases import CASES_FILE, found, report
from feasibility_fr.schema import ATTRIBUTES
from haussmann.evalkit.cases import Standing, load_cases, passes, regressions

DATA = Path(__file__).parent.parent / "benchmark_data"
CASES = load_cases((DATA / CASES_FILE).read_text(encoding="utf-8"))
VALUES = asyncio.run(found(DATA, CASES))
PASSING = [passes(case, value, ATTRIBUTES) for case, value in zip(CASES, VALUES, strict=True)]


def test_no_held_case_has_regressed() -> None:
    assert regressions(CASES, PASSING) == []


def test_every_case_has_the_standing_its_latest_check_gave_it() -> None:
    assert [case.standing is Standing.HELD for case in CASES] == PASSING


def test_the_gate_fails_when_a_held_case_no_longer_matches_the_engine() -> None:
    held = next(index for index, case in enumerate(CASES) if case.standing is Standing.HELD)
    wrong = [replace(case, expected="non") if n == held else case for n, case in enumerate(CASES)]
    passing = [passes(case, value, ATTRIBUTES) for case, value in zip(wrong, VALUES, strict=True)]
    assert regressions(wrong, passing) == [wrong[held]]


def test_the_committed_cases_report_reproduces_from_recordings() -> None:
    assert report(CASES, VALUES) == (DATA / "results" / "cases.md").read_text(encoding="utf-8")
