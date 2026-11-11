# ruff: noqa: E501
import datetime as dt
from decimal import Decimal

from haussmann.coretypes.values import FactKey
from haussmann.evalkit.groundtruth import Split, TrapType
from haussmann.evalkit.report import RunRecord, experiment_row, pooled, render_report
from haussmann.evalkit.scorer import FactResult, Outcome, Score, TrapResult

A, B, C = FactKey("s", "a"), FactKey("s", "b"), FactKey("s", "c")


def result(outcomes: tuple[Outcome, Outcome], trap_passed: bool) -> Score:
    return Score(
        facts=(
            FactResult(A, outcomes[0], True, outcomes[0] is Outcome.CORRECT),
            FactResult(B, outcomes[1], True, False),
            FactResult(C, Outcome.ABSTAINED, False, False),
        ),
        traps=(
            TrapResult(TrapType.BURIED, A, trap_passed),
            TrapResult(TrapType.MISSING, C, True),
        ),
    )


RECORDS = [
    RunRecord(
        "one_prompt",
        "x",
        Split.DEV,
        0,
        result((Outcome.CORRECT, Outcome.BAIT), True),
        None,
        Decimal("0.0010"),
        2.0,
    ),
    RunRecord(
        "one_prompt",
        "x",
        Split.DEV,
        1,
        result((Outcome.CORRECT, Outcome.CORRECT), False),
        None,
        Decimal("0.0012"),
        4.0,
    ),
    RunRecord("naive_rag", "x", Split.DEV, 0, None, "stop: bad json", Decimal("0.0005"), 1.0),
]

EXPECTED = """\
# Benchmark report

## dev: x

| system | recall | precision | bait | invented | abstention | citations | recall spread | failed runs | cost USD | mean latency s |
|---|---|---|---|---|---|---|---|---|---|---|
| one_prompt | 75% (3/4) | 75% (3/4) | 25% (1/4) | 0% (0/4) | 100% (2/2) | 67% (2/3) | 50% to 100% | 0/2 | 0.0022 | 3.0 |
| naive_rag | - | - | - | - | - | - | - | 1/1 | 0.0005 | 1.0 |

Traps passed, by type:

| system | arithmetic | buried | contradiction | date_logic | distractor | missing | superseded | unit |
|---|---|---|---|---|---|---|---|---|
| one_prompt | - | 50% (1/2) | - | - | - | 100% (2/2) | - | - |
| naive_rag | - | - | - | - | - | - | - | - |
"""


def test_report_snapshot() -> None:
    assert render_report(RECORDS) == EXPECTED


def test_held_out_results_get_their_own_table() -> None:
    held = RunRecord(
        "one_prompt",
        "y",
        Split.HELDOUT,
        0,
        result((Outcome.CORRECT, Outcome.CORRECT), True),
        None,
        Decimal(0),
        1.0,
    )
    report = render_report([*RECORDS, held])
    assert report.index("## dev: x") < report.index("## heldout: y")


def test_pooling_sums_counts_and_skips_failed_runs() -> None:
    rate = pooled(RECORDS, lambda s: s.recall)
    assert (rate.count, rate.total) == (3, 4)


def test_experiment_row_carries_metrics_and_cost() -> None:
    row = experiment_row("E001", dt.date(2026, 11, 11), "first baselines", "none", RECORDS, "kept")
    assert row == (
        "| E001 | 2026-11-11 | first baselines | none | dev | - | "
        "one_prompt: recall 75% (3/4), traps 75% (3/4); naive_rag: recall -, traps - | "
        "0.0027 | kept |"
    )
