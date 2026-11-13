import datetime as dt
import json
from collections.abc import Callable
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from haussmann.coretypes.values import FactKey, Quantity
from haussmann.ledger.codec import decode_entry, decode_record, encode_entry, encode_record
from haussmann.ledger.ledger import (
    Ask,
    Assess,
    Citation,
    Condition,
    Entry,
    Flag,
    Ledger,
    LedgerError,
    NewConflict,
    NewFact,
    Record,
    Resolve,
    Status,
)

text = st.text(max_size=20)
keys = st.builds(FactKey, text, text)
values = st.one_of(
    st.builds(Quantity, st.decimals(allow_nan=False, allow_infinity=False), text),
    st.dates(),
    text,
)
citations = st.builds(Citation, text, st.one_of(st.none(), text), text)
records = st.one_of(
    st.builds(
        NewFact,
        keys,
        values,
        st.lists(citations, max_size=3).map(tuple),
        text,
        st.one_of(st.none(), st.builds(Condition, keys, text)),
    ),
    st.builds(Assess, text, st.sampled_from(list(Status)), text),
    st.builds(NewConflict, keys, st.lists(text, max_size=3).map(tuple), text),
    st.builds(Resolve, text, st.one_of(st.none(), text), text),
    st.builds(Ask, keys, text),
    st.builds(Flag, text, text),
)


@given(records)
def test_any_record_survives_a_round_trip_through_json_text(record: Record) -> None:
    stored = json.dumps(encode_record(record))
    assert decode_record(json.loads(stored)) == record


def test_a_date_and_a_text_that_looks_like_one_stay_apart() -> None:
    key = FactKey("site", "certificate_date")
    as_date = NewFact(key, dt.date(2024, 2, 12))
    as_text = NewFact(key, "2024-02-12")
    assert decode_record(encode_record(as_date)) == as_date
    assert decode_record(encode_record(as_text)) == as_text


def test_an_amount_keeps_its_exact_digits() -> None:
    fact = NewFact(FactKey("site", "area"), Quantity(Decimal("4838.50"), "m2"))
    decoded = decode_record(json.loads(json.dumps(encode_record(fact))))
    assert isinstance(decoded, NewFact) and isinstance(decoded.value, Quantity)
    assert str(decoded.value.amount) == "4838.50"


def test_an_unknown_record_type_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown record type"):
        decode_record({"type": "note"})


HEIGHT = FactKey("site", "height")


def sample() -> Ledger:
    ledger = Ledger()
    ledger.append("finder", [NewFact(HEIGHT, Quantity(Decimal(9), "m"))])
    ledger.append(
        "finder",
        [NewFact(HEIGHT, Quantity(Decimal(12), "m")), Ask(FactKey("site", "owner"), "not found")],
    )
    ledger.append("verifier", [NewConflict(HEIGHT, ("f1", "f2"), "values differ")])
    ledger.append("verifier", [Resolve("c1", "f2", "later"), Flag("f2", "disputed")])
    return ledger


def test_a_ledger_loaded_from_its_stored_entries_gives_the_same_answers() -> None:
    ledger = sample()
    stored = json.dumps([encode_entry(entry) for entry in ledger.since(0)])
    loaded = Ledger.load([decode_entry(item) for item in json.loads(stored)])
    assert loaded.since(0) == ledger.since(0)
    assert loaded.facts() == ledger.facts()
    assert loaded.conflicts() == ledger.conflicts()
    assert loaded.questions() == ledger.questions()
    assert loaded.flags() == ledger.flags()
    assert loaded.append("x", [Ask(HEIGHT)]) == 5


def test_since_returns_only_the_later_transactions() -> None:
    ledger = sample()
    assert [entry.tx for entry in ledger.since(2)] == [3, 4, 4]
    assert ledger.since(4) == ()


def missing(e: list[Entry]) -> list[Entry]:
    return [e[0], e[3]]


def out_of_order(e: list[Entry]) -> list[Entry]:
    return [e[1], e[0]]


def another_id(e: list[Entry]) -> list[Entry]:
    return [Entry(e[0].tx, e[0].author, e[0].record, "f7"), *e[1:]]


def unknown_fact(e: list[Entry]) -> list[Entry]:
    return [e[0], Entry(2, "v", Assess("f9", Status.VERIFIED), None)]


@pytest.mark.parametrize("broken", [missing, out_of_order, another_id, unknown_fact])
def test_stored_entries_that_the_ledger_would_not_have_accepted_are_refused(
    broken: Callable[[list[Entry]], list[Entry]],
) -> None:
    with pytest.raises(LedgerError):
        Ledger.load(broken(list(sample().since(0))))
