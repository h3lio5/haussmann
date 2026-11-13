import pytest
from tests.verify.test_settle import (
    CASE_SCHEMA,
    FIRST,
    GROUND,
    HEIGHT,
    LAND,
    LIMIT,
    PRICE,
    SCHEMA,
    TIER,
    TOTAL,
    case_ledger,
    found,
    limit,
    q,
    run,
    settle_cases,
)

from haussmann.coretypes.values import Value
from haussmann.ledger.ledger import Citation, Ledger, NewFact, Status
from haussmann.review.edits import EditRefused, edit
from haussmann.verify.settle import COMPUTED, EXPERT, settled


def disputed() -> Ledger:
    ledger = Ledger()
    found(ledger, HEIGHT, q("9", "m"), "rules", "p8")
    found(ledger, HEIGHT, q("15", "m"), "brochure")
    found(ledger, PRICE, q("260000", "EUR"), "notice_old")
    found(ledger, PRICE, q("245000", "EUR"), "notice_new")
    found(ledger, GROUND, q("115", "m2"), "table", "Sheet1!B6")
    found(ledger, FIRST, q("200", "m2"), "table", "Sheet1!B7")
    found(ledger, TOTAL, q("330", "m2"), "table", "Sheet1!B9")
    run(ledger)
    return ledger


def test_an_experts_value_wins_over_authority_date_and_a_computed_total() -> None:
    ledger = disputed()
    before = [(f.id, ledger.status(f.id)) for f in ledger.facts()]
    for key, value in [
        (HEIGHT, q("12", "m")),
        (PRICE, q("250000", "EUR")),
        (TOTAL, q("320", "m2")),
    ]:
        made = edit(ledger, key, value, "checked on site", "expert:a", SCHEMA)
        run(ledger)
        result = settled(ledger, key, SCHEMA)
        assert result.fact is not None and (result.fact.id, result.fact.method) == (made, EXPERT)
        assert result.fact.value == value and result.fact.author == "expert:a"
        assert result.reasons == ("set by an expert",)
        assert result.conflict is not None and made in result.conflict.fact_ids
    assert [(f.id, ledger.status(f.id)) for f in ledger.facts()][: len(before)] == before


def test_the_later_of_two_edits_wins_and_both_stay() -> None:
    ledger = disputed()
    first = edit(ledger, HEIGHT, q("12", "m"), "first reading", "expert:a", SCHEMA)
    run(ledger)
    second = edit(ledger, HEIGHT, q("11", "m"), "second reading", "expert:b", SCHEMA)
    run(ledger)
    result = settled(ledger, HEIGHT, SCHEMA)
    assert result.fact is not None and result.fact.id == second
    assert ledger.status(first) is Status.VERIFIED
    assert {first, second} <= {f.id for f in result.supporting}


def test_an_edit_of_a_fact_nobody_found_settles_it_without_a_disagreement() -> None:
    ledger = disputed()
    assert settled(ledger, LAND, SCHEMA).fact is None
    edit(ledger, LAND, q("0.12", "ha"), "from the deed", "expert:a", SCHEMA)
    run(ledger)
    result = settled(ledger, LAND, SCHEMA)
    assert result.fact is not None and result.fact.value == q("0.12", "ha")
    assert result.conflict is None and result.reasons == ()


def test_an_edited_part_changes_the_total_and_the_old_sum_is_rejected_not_removed() -> None:
    ledger = disputed()
    old = settled(ledger, TOTAL, SCHEMA).fact
    assert old is not None and (old.value, old.method) == (q("315", "m2"), COMPUTED)
    edit(ledger, GROUND, q("120", "m2"), "measured again", "expert:a", SCHEMA)
    run(ledger)
    result = settled(ledger, TOTAL, SCHEMA)
    assert result.fact is not None and (result.fact.value, result.fact.method) == (
        q("320", "m2"),
        COMPUTED,
    )
    assert ledger.status(old.id) is Status.REJECTED
    assert ledger.fact(old.id) == old


def test_an_edit_of_the_deciding_fact_swaps_which_conditional_facts_apply() -> None:
    ledger = case_ledger(
        NewFact(TIER, "B2", (Citation("letter", "p1"),)),
        limit("12", "rules_a", "Niveau A1"),
        limit("8", "rules_b", "Niveau B2"),
    )
    settle_cases(ledger)
    assert settled(ledger, LIMIT, CASE_SCHEMA).fact == ledger.fact("f3")
    edit(ledger, TIER, "A1", "the map shows A1", "expert:a", CASE_SCHEMA)
    settle_cases(ledger)
    result = settled(ledger, LIMIT, CASE_SCHEMA)
    assert result.fact is not None and result.fact.value == q("12", "m")
    assert (ledger.status("f2"), ledger.status("f3")) == (Status.VERIFIED, Status.SET_ASIDE)


def test_verifying_again_adds_nothing_before_or_after_an_edit() -> None:
    ledger = disputed()
    settled_once = ledger.tx
    run(ledger)
    assert ledger.tx == settled_once
    edit(ledger, GROUND, q("120", "m2"), "measured again", "expert:a", SCHEMA)
    run(ledger)
    after_edit = ledger.tx
    run(ledger)
    run(ledger)
    assert ledger.tx == after_edit

    cases = case_ledger(
        NewFact(TIER, "B2", (Citation("letter", "p1"),)), limit("12", "rules_a", "Niveau A1")
    )
    settle_cases(cases)
    once = cases.tx
    settle_cases(cases)
    assert cases.tx == once


@pytest.mark.parametrize(
    ("value", "reason", "author"),
    [
        ("tall", "checked", "expert:a"),
        (q("12", "feet"), "checked", "expert:a"),
        (q("12", "m"), " ", "expert:a"),
        (q("12", "m"), "checked", ""),
    ],
)
def test_an_edit_that_does_not_fit_or_gives_no_reason_is_refused_and_writes_nothing(
    value: Value, reason: str, author: str
) -> None:
    ledger = disputed()
    before = ledger.tx
    with pytest.raises(EditRefused):
        edit(ledger, HEIGHT, value, reason, author, SCHEMA)
    assert ledger.tx == before
