from decimal import Decimal
from typing import NamedTuple

import pytest
from hypothesis import given
from hypothesis import strategies as st

from haussmann.coretypes.values import FactKey, Quantity
from haussmann.ledger.ledger import (
    Ask,
    Assess,
    Citation,
    Conflict,
    Fact,
    Ledger,
    LedgerError,
    NewConflict,
    NewFact,
    Question,
    Record,
    Resolve,
    Status,
)

HEIGHT = FactKey("site", "height")
AREA = FactKey("site", "area")
NINE = Quantity(Decimal(9), "m")
TWELVE = Quantity(Decimal(12), "m")


def two_heights() -> Ledger:
    ledger = Ledger()
    ledger.append("finder", [NewFact(HEIGHT, NINE, (Citation("old", "p3", "9 m"),))])
    ledger.append("finder", [NewFact(HEIGHT, TWELVE, (Citation("new", "p1"),))])
    return ledger


def test_a_fact_gets_an_id_and_starts_as_a_candidate() -> None:
    ledger = two_heights()
    first, second = ledger.facts()
    assert (first.id, first.tx, first.author) == ("f1", 1, "finder")
    assert (second.id, second.tx) == ("f2", 2)
    assert first.citations == (Citation("old", "p3", "9 m"),)
    assert ledger.status("f1") is Status.CANDIDATE
    assert ledger.fact("f2").value == TWELVE


def test_facts_can_be_listed_by_key_and_several_may_share_one() -> None:
    ledger = two_heights()
    ledger.append("finder", [NewFact(AREA, Quantity(Decimal(1200), "m2"))])
    assert [f.id for f in ledger.facts(HEIGHT)] == ["f1", "f2"]
    assert [f.id for f in ledger.facts(AREA)] == ["f3"]
    assert len(ledger.facts()) == 3


def test_the_latest_assessment_is_the_status_and_the_fact_never_changes() -> None:
    ledger = two_heights()
    before = ledger.fact("f1")
    ledger.append("verifier", [Assess("f1", Status.VERIFIED, "found at p3")])
    ledger.append("verifier", [Assess("f1", Status.REJECTED, "superseded")])
    assert ledger.status("f1") is Status.REJECTED
    assert ledger.status("f2") is Status.CANDIDATE
    assert ledger.fact("f1") == before


def test_a_conflict_is_open_until_resolved_and_can_be_escalated() -> None:
    ledger = two_heights()
    ledger.append("verifier", [NewConflict(HEIGHT, ("f1", "f2"), "values differ")])
    (conflict,) = ledger.conflicts()
    assert (conflict.id, conflict.fact_ids, conflict.resolution) == ("c1", ("f1", "f2"), None)

    ledger.append("resolver", [Resolve("c1", "f2", "later document")])
    resolution = ledger.conflicts()[0].resolution
    assert resolution is not None
    assert (resolution.chosen, resolution.reason, resolution.author) == (
        "f2",
        "later document",
        "resolver",
    )

    ledger.append("resolver", [Resolve("c1", None, "equal authority")])
    escalated = ledger.conflicts()[0].resolution
    assert escalated is not None and escalated.chosen is None


def test_open_questions_are_recorded_with_their_reason() -> None:
    ledger = Ledger()
    ledger.append("finder", [Ask(AREA, "no document states it")])
    (question,) = ledger.questions()
    assert (question.key, question.reason, question.author) == (
        AREA,
        "no document states it",
        "finder",
    )


def test_a_record_may_refer_to_a_fact_written_earlier_in_the_same_transaction() -> None:
    ledger = Ledger()
    tx = ledger.append("finder", [NewFact(HEIGHT, NINE), Assess("f1", Status.UNVERIFIED)])
    assert tx == 1 and ledger.status("f1") is Status.UNVERIFIED


@pytest.mark.parametrize(
    "records",
    [
        [],
        [Assess("f9", Status.VERIFIED)],
        [NewFact(AREA, NINE), Assess("f9", Status.VERIFIED)],
        [NewConflict(HEIGHT, ("f1",), "alone")],
        [NewConflict(HEIGHT, ("f1", "f1"), "same fact twice")],
        [NewConflict(AREA, ("f1", "f2"), "wrong key")],
        [Resolve("c9", "f1")],
        [NewConflict(HEIGHT, ("f1", "f2"), "x"), Resolve("c1", "f3")],
    ],
)
def test_an_invalid_transaction_is_refused_and_writes_nothing(records: list[Record]) -> None:
    ledger = two_heights()
    ledger.append("finder", [NewFact(AREA, NINE)])
    before = (ledger.tx, ledger.facts(), ledger.conflicts(), ledger.questions())
    with pytest.raises(LedgerError):
        ledger.append("anyone", records)
    assert (ledger.tx, ledger.facts(), ledger.conflicts(), ledger.questions()) == before


def test_at_gives_the_ledger_as_it_was() -> None:
    ledger = two_heights()
    ledger.append("verifier", [Assess("f1", Status.VERIFIED)])
    earlier = ledger.at(1)
    assert [f.id for f in earlier.facts()] == ["f1"]
    assert earlier.status("f1") is Status.CANDIDATE
    assert ledger.at(3).status("f1") is Status.VERIFIED
    assert ledger.at(0).facts() == ()


fact_ids = st.sampled_from(["f1", "f2", "f3", "f4", "f9"])
records = st.one_of(
    st.builds(NewFact, st.sampled_from([HEIGHT, AREA]), st.sampled_from([NINE, TWELVE])),
    st.builds(Assess, fact_ids, st.sampled_from(list(Status))),
    st.builds(
        NewConflict,
        st.sampled_from([HEIGHT, AREA]),
        st.lists(fact_ids, min_size=1, max_size=3).map(tuple),
        st.just("differ"),
    ),
    st.builds(Resolve, st.sampled_from(["c1", "c2", "c9"]), st.one_of(st.none(), fact_ids)),
    st.builds(Ask, st.sampled_from([HEIGHT, AREA])),
)
transactions = st.lists(st.lists(records, max_size=3), max_size=12)


class View(NamedTuple):
    tx: int
    facts: tuple[Fact, ...]
    conflicts: tuple[Conflict, ...]
    questions: tuple[Question, ...]
    statuses: tuple[Status, ...]


def view(ledger: Ledger) -> View:
    statuses = tuple(ledger.status(fact.id) for fact in ledger.facts())
    return View(ledger.tx, ledger.facts(), ledger.conflicts(), ledger.questions(), statuses)


@given(transactions)
def test_ledger_invariants_hold_for_any_sequence_of_transactions(
    batches: list[list[Record]],
) -> None:
    ledger = Ledger()
    snapshots: list[tuple[int, View]] = []
    for batch in batches:
        before = view(ledger)
        try:
            ledger.append("author", batch)
        except LedgerError:
            assert view(ledger) == before
            continue
        assert ledger.tx == before.tx + 1
        assert ledger.facts()[: len(before.facts)] == before.facts
        assert ledger.questions()[: len(before.questions)] == before.questions
        snapshots.append((ledger.tx, view(ledger)))

    for tx, seen in snapshots:
        assert view(ledger.at(tx)) == seen
    ids = [fact.id for fact in ledger.facts()]
    assert ids == [f"f{n}" for n in range(1, len(ids) + 1)]
    assert [fact.tx for fact in ledger.facts()] == sorted(fact.tx for fact in ledger.facts())
    conflict_ids = [conflict.id for conflict in ledger.conflicts()]
    assert conflict_ids == [f"c{n}" for n in range(1, len(conflict_ids) + 1)]
