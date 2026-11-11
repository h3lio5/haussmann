import datetime as dt
from dataclasses import replace
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from haussmann.evalkit.groundtruth import (
    AttributeDef,
    FactKey,
    GoldFact,
    Manifest,
    ManifestFile,
    Quantity,
    Schema,
    Split,
    Statement,
    StatementKind,
    Trap,
    TrapType,
    Value,
    ValueKind,
)
from haussmann.evalkit.scorer import (
    Citation,
    InvalidSubmission,
    Outcome,
    Rate,
    ReportedFact,
    Score,
    Submission,
    score,
)

SUPPORTS, STALE = StatementKind.SUPPORTS, StatementKind.STALE
CONFLICTS, DISTRACTOR = StatementKind.CONFLICTS, StatementKind.DISTRACTOR

SCHEMA: Schema = {
    "height": AttributeDef("height", ValueKind.QUANTITY, "m"),
    "area": AttributeDef("area", ValueKind.QUANTITY, "m2", {"ha": Decimal(10000)}),
    "amount": AttributeDef("amount", ValueKind.QUANTITY, "EUR", tolerance=Decimal(1)),
    "label": AttributeDef("label", ValueKind.TEXT),
    "holder": AttributeDef("holder", ValueKind.TEXT),
    "signed": AttributeDef("signed", ValueKind.DATE),
    "survey": AttributeDef("survey", ValueKind.TEXT),
}


def q(amount: str, unit: str) -> Quantity:
    return Quantity(Decimal(amount), unit)


HEIGHT = FactKey("site", "height")
LABEL = FactKey("site", "label")
AREA = FactKey("site", "area")
HOLDER = FactKey("site", "holder")
AMOUNT = FactKey("site", "amount")
TOTAL = FactKey("building", "area")
SIGNED = FactKey("permit", "signed")
SURVEY = FactKey("site", "survey")
PLAIN = FactKey("neighbour", "label")
UNASKED = FactKey("site", "colour")

GOLD: dict[FactKey, Value | None] = {
    HEIGHT: q("12", "m"),
    LABEL: "UA",
    AREA: q("1200", "m2"),
    HOLDER: "Société Générale d'Études",
    AMOUNT: q("500000", "EUR"),
    TOTAL: q("300", "m2"),
    SIGNED: dt.date(2019, 5, 2),
    SURVEY: None,
    PLAIN: "UB",
}

STATEMENTS = (
    Statement("old", "p1", HEIGHT, q("9", "m"), STALE),
    Statement("new", "p1", HEIGHT, q("12", "m"), SUPPORTS),
    Statement("new", "p40", LABEL, "UA", SUPPORTS),
    Statement("new", "p2", AREA, q("0.12", "ha"), SUPPORTS),
    Statement("new", "p3", HOLDER, "Société Générale d'Études", SUPPORTS),
    Statement("other", "p1", HOLDER, "Globex", DISTRACTOR),
    Statement("new", "p4", AMOUNT, q("500000", "EUR"), SUPPORTS),
    Statement("memo", "p1", AMOUNT, q("450000", "EUR"), CONFLICTS),
    Statement("new", "p5", TOTAL, q("320", "m2"), CONFLICTS),
    Statement("new", "p6", SIGNED, dt.date(2019, 5, 2), SUPPORTS),
    Statement("new", "p7", PLAIN, "UB", SUPPORTS),
)

TRAPS = (
    Trap(TrapType.SUPERSEDED, HEIGHT, ("old", "new")),
    Trap(TrapType.BURIED, LABEL, ("new",)),
    Trap(TrapType.UNIT, AREA, ("new",)),
    Trap(TrapType.DISTRACTOR, HOLDER, ("other",)),
    Trap(TrapType.CONTRADICTION, AMOUNT, ("memo", "new")),
    Trap(TrapType.ARITHMETIC, TOTAL, ("new",)),
    Trap(TrapType.DATE_LOGIC, SIGNED, ("new",)),
    Trap(TrapType.MISSING, SURVEY, ()),
)

MANIFEST = Manifest(
    scenario_id="base",
    split=Split.DEV,
    gold=tuple(GoldFact(key, value) for key, value in GOLD.items()),
    traps=TRAPS,
    files=tuple(
        ManifestFile(doc, f"{doc}.pdf", "0" * 64, tuple(s for s in STATEMENTS if s.doc_id == doc))
        for doc in ("old", "new", "memo", "other")
    ),
)


def cite(doc_id: str, locator: str | None = None) -> Citation:
    return Citation(doc_id, locator)


ORACLE = Submission(
    facts=(
        ReportedFact(HEIGHT, q("12", "m"), (cite("new", "p1"),)),
        ReportedFact(LABEL, "UA", (cite("new", "p40"),)),
        ReportedFact(AREA, q("1200", "m2"), (cite("new", "p2"),)),
        ReportedFact(HOLDER, "Société Générale d'Études", (cite("new", "p3"),)),
        ReportedFact(AMOUNT, q("500000", "EUR"), (cite("new", "p4"), cite("memo", "p1")), True),
        ReportedFact(TOTAL, q("300", "m2"), (cite("new", "p5"),), True),
        ReportedFact(SIGNED, dt.date(2019, 5, 2), (cite("new", "p6"),), True),
        ReportedFact(PLAIN, "UB", (cite("new", "p7"),)),
    ),
    open_questions=(SURVEY,),
)

BAIT_TAKER = Submission(
    facts=(
        ReportedFact(HEIGHT, q("9", "m"), (cite("old", "p1"),)),
        ReportedFact(AREA, q("0.12", "m2"), (cite("new", "p2"),)),
        ReportedFact(HOLDER, "Globex", (cite("other", "p1"),)),
        ReportedFact(AMOUNT, q("450000", "EUR"), (cite("memo", "p1"),)),
        ReportedFact(TOTAL, q("320", "m2"), (cite("new", "p5"),)),
        ReportedFact(SIGNED, dt.date(2019, 5, 2), (cite("new", "p6"),)),
        ReportedFact(SURVEY, "done"),
    ),
)


def run(submission: Submission) -> Score:
    return score(MANIFEST, SCHEMA, submission)


def swap(key: FactKey, **changes: object) -> Submission:
    """The oracle with one fact altered."""
    facts = tuple(replace(f, **changes) if f.key == key else f for f in ORACLE.facts)
    return replace(ORACLE, facts=facts)


def outcome(result: Score, key: FactKey) -> Outcome:
    return next(f.outcome for f in result.facts if f.key == key)


def passed(result: Score, key: FactKey) -> bool:
    return next(t.passed for t in result.traps if t.key == key)


def rates(result: Score) -> tuple[Rate, ...]:
    return (
        result.recall,
        result.precision,
        result.bait_rate,
        result.invented_rate,
        result.abstention,
        result.citation_correctness,
        *result.traps_passed.values(),
    )


def test_oracle_scores_one_everywhere() -> None:
    result = run(ORACLE)
    assert result.recall == Rate(8, 8)
    assert result.precision == Rate(8, 8)
    assert result.abstention == Rate(1, 1)
    assert result.citation_correctness == Rate(8, 8)
    assert result.bait_rate.value == 0 and result.invented_rate.value == 0
    assert all(trap.passed for trap in result.traps)
    assert set(result.traps_passed) == set(TrapType)


def test_bait_taker_passes_no_trap() -> None:
    result = run(BAIT_TAKER)
    assert not any(trap.passed for trap in result.traps)
    assert [outcome(result, k) for k in (HEIGHT, HOLDER, AMOUNT, TOTAL)] == [Outcome.BAIT] * 4
    assert outcome(result, AREA) is Outcome.INVENTED
    assert outcome(result, SURVEY) is Outcome.INVENTED
    assert outcome(result, LABEL) is Outcome.OMITTED
    assert result.abstention == Rate(0, 1)


def test_empty_submission_has_undefined_rates() -> None:
    result = run(Submission(facts=()))
    assert result.precision.value is None
    assert result.citation_correctness.value is None
    assert result.recall == Rate(0, 8)


def test_repeated_key_is_rejected() -> None:
    with pytest.raises(InvalidSubmission):
        run(replace(ORACLE, facts=(*ORACLE.facts, ORACLE.facts[0])))


def test_key_in_both_facts_and_open_questions_counts_as_reported() -> None:
    result = run(replace(BAIT_TAKER, open_questions=(SURVEY,)))
    assert outcome(result, SURVEY) is Outcome.INVENTED
    assert not passed(result, SURVEY)


@pytest.mark.parametrize(
    ("reported", "expected"),
    [
        (q("0.12", "ha"), Outcome.CORRECT),
        (q("1200.5", "m2"), Outcome.INVENTED),
        (q("1200", "acres"), Outcome.INVENTED),
        ("1200 m2", Outcome.INVENTED),
    ],
)
def test_quantity_matching(reported: Value, expected: Outcome) -> None:
    assert outcome(run(swap(AREA, value=reported)), AREA) is expected


@pytest.mark.parametrize(
    ("reported", "expected"),
    [
        (q("500001", "EUR"), Outcome.CORRECT),
        (q("500001.01", "EUR"), Outcome.INVENTED),
        (q("450000.5", "EUR"), Outcome.BAIT),
    ],
)
def test_tolerance_applies_to_gold_and_bait(reported: Value, expected: Outcome) -> None:
    assert outcome(run(swap(AMOUNT, value=reported)), AMOUNT) is expected


@pytest.mark.parametrize(
    ("reported", "expected"),
    [
        ("SOCIETE GENERALE D'ETUDES", Outcome.CORRECT),
        ("  société   générale d\u2019études. ", Outcome.CORRECT),
        ("Société Générale", Outcome.INVENTED),
        ("globex", Outcome.BAIT),
    ],
)
def test_text_matching(reported: str, expected: Outcome) -> None:
    assert outcome(run(swap(HOLDER, value=reported)), HOLDER) is expected


def test_date_must_be_equal() -> None:
    assert outcome(run(swap(SIGNED, value=dt.date(2019, 5, 3))), SIGNED) is Outcome.INVENTED


@pytest.mark.parametrize(
    ("citations", "well_cited"),
    [
        ((cite("new"),), True),
        ((cite("new", "p7"),), True),
        ((), False),
        ((cite("new", "p8"),), False),
        ((cite("new", "p7"), cite("memo")), False),
    ],
)
def test_citation_correctness(citations: tuple[Citation, ...], well_cited: bool) -> None:
    result = run(swap(PLAIN, citations=citations))
    assert next(f.well_cited for f in result.facts if f.key == PLAIN) is well_cited


def test_citing_only_the_conflicting_document_is_not_well_cited() -> None:
    result = run(swap(AMOUNT, citations=(cite("memo"),)))
    assert next(f.well_cited for f in result.facts if f.key == AMOUNT) is False


@pytest.mark.parametrize(
    ("key", "changes"),
    [
        (HEIGHT, {"citations": (cite("old"),)}),
        (LABEL, {"citations": (cite("new"),)}),
        (LABEL, {"citations": (cite("new", "p1"),)}),
        (AREA, {"value": q("0.12", "m2")}),
        (HOLDER, {"citations": (cite("new"), cite("other"))}),
        (AMOUNT, {"flagged": False}),
        (AMOUNT, {"citations": (cite("new"),)}),
        (TOTAL, {"flagged": False}),
        (TOTAL, {"value": q("320", "m2")}),
        (SIGNED, {"flagged": False}),
    ],
)
def test_each_trap_fails_when_its_condition_is_broken(
    key: FactKey, changes: dict[str, object]
) -> None:
    assert passed(run(ORACLE), key)
    assert not passed(run(swap(key, **changes)), key)


def test_date_logic_passes_on_a_flag_even_with_a_wrong_value() -> None:
    assert passed(run(swap(SIGNED, value=dt.date(2000, 1, 1))), SIGNED)


def test_missing_fails_when_neither_reported_nor_listed() -> None:
    result = run(replace(ORACLE, open_questions=()))
    assert outcome(result, SURVEY) is Outcome.OMITTED
    assert not passed(result, SURVEY)


subsets = st.lists(st.sampled_from(ORACLE.facts + BAIT_TAKER.facts), unique_by=lambda f: f.key)


@given(st.data())
def test_order_never_changes_the_score(data: st.DataObject) -> None:
    facts = data.draw(subsets)
    shuffled = tuple(
        replace(f, citations=tuple(data.draw(st.permutations(f.citations))))
        for f in data.draw(st.permutations(facts))
    )
    questions = (SURVEY, PLAIN, UNASKED)
    first = Submission(tuple(facts), questions)
    second = Submission(shuffled, tuple(data.draw(st.permutations(questions))))
    assert run(first) == run(second)


@given(subsets, st.text())
def test_an_invented_fact_never_raises_precision(facts: list[ReportedFact], text: str) -> None:
    free = next((k for k in (PLAIN, LABEL) if all(f.key != k for f in facts)), None)
    if free is None:
        return
    before = run(Submission(tuple(facts)))
    after = run(Submission((*facts, ReportedFact(free, f"{text} not stated anywhere"))))
    assert outcome(after, free) is Outcome.INVENTED
    assert (after.precision.value or 0) <= (before.precision.value or 0)


@given(subsets, st.text())
def test_an_unasked_fact_changes_no_rate(facts: list[ReportedFact], text: str) -> None:
    before = run(Submission(tuple(facts)))
    after = run(Submission((*facts, ReportedFact(UNASKED, text))))
    assert outcome(after, UNASKED) is Outcome.UNASKED
    assert rates(after) == rates(before)
