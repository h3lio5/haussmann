import datetime as dt
from decimal import Decimal

from haussmann.coretypes.values import AttributeDef, FactKey, Quantity, Schema, Value, ValueKind
from haussmann.docparse.cards import DocumentCard
from haussmann.docparse.elements import Element
from haussmann.ledger.ledger import Citation, Flag, Ledger, NewFact, Status
from haussmann.verify.settle import COMPUTED, settled, verify

SCHEMA: Schema = {
    "height": AttributeDef("height", ValueKind.QUANTITY, "m"),
    "price": AttributeDef("price", ValueKind.QUANTITY, "EUR", tolerance=Decimal(1)),
    "area": AttributeDef("area", ValueKind.QUANTITY, "m2", {"ha": Decimal(10000)}),
}
HEIGHT = FactKey("site", "height")
PRICE = FactKey("site", "price")
LAND = FactKey("site", "area")
GROUND = FactKey("floor:0", "area")
FIRST = FactKey("floor:1", "area")
TOTAL = FactKey("building", "area")
KEYS = (HEIGHT, PRICE, LAND, GROUND, FIRST, TOTAL)
TOTALS = {TOTAL: (GROUND, FIRST)}

ELEMENTS = (
    Element("rules", "p8", "Hauteur maximale : 9 m."),
    Element("brochure", "p1", "Hauteur possible : 15 m. Prix : 150 000 €."),
    Element("notice_old", "p1", "Prix : 260 000 €."),
    Element("notice_new", "p1", "Prix : 245 000 €. Contenance 0,12 ha."),
    Element("survey", "p1", "Contenance : 1 200 m²."),
    Element("table", "Sheet1", "[Sheet1!B6] 115 m²\n[Sheet1!B7] 200 m²\n[Sheet1!B9] 330 m²"),
)
CARDS = (
    DocumentCard("rules", "regulation", dt.date(2023, 1, 1), 3),
    DocumentCard("brochure", "brochure", dt.date(2026, 1, 1), 1),
    DocumentCard("notice_old", "notice", dt.date(2026, 3, 1), 3),
    DocumentCard("notice_new", "notice", dt.date(2026, 9, 1), 3),
    DocumentCard("survey", "survey", dt.date(2025, 1, 1), 3),
    DocumentCard("table", "schedule", dt.date(2026, 1, 1), 2),
)


def q(amount: str, unit: str) -> Quantity:
    return Quantity(Decimal(amount), unit)


def found(ledger: Ledger, key: FactKey, value: Value, doc_id: str, locator: str = "p1") -> str:
    ledger.append("finder", [NewFact(key, value, (Citation(doc_id, locator),))])
    return ledger.facts()[-1].id


def run(ledger: Ledger) -> None:
    verify(ledger, ELEMENTS, CARDS, SCHEMA, KEYS, TOTALS, lambda value: [])


def test_a_fact_not_stated_at_its_source_is_unverified_and_left_out() -> None:
    ledger = Ledger()
    good = found(ledger, HEIGHT, q("9", "m"), "rules", "p8")
    invented = found(ledger, HEIGHT, q("12", "m"), "rules", "p8")
    wrong_unit = found(ledger, LAND, q("3", "acres"), "survey")
    run(ledger)
    assert ledger.status(good) is Status.VERIFIED
    assert ledger.status(invented) is Status.UNVERIFIED
    assert ledger.status(wrong_unit) is Status.UNVERIFIED
    result = settled(ledger, HEIGHT, SCHEMA)
    assert result.fact is not None and result.fact.id == good
    assert result.conflict is None and ledger.conflicts() == ()
    assert settled(ledger, LAND, SCHEMA).fact is None


def test_the_higher_authority_source_wins_a_disagreement() -> None:
    ledger = Ledger()
    official = found(ledger, HEIGHT, q("9", "m"), "rules", "p8")
    commercial = found(ledger, HEIGHT, q("15", "m"), "brochure")
    run(ledger)
    result = settled(ledger, HEIGHT, SCHEMA)
    assert result.fact is not None and result.fact.id == official
    assert {f.id for f in result.supporting} == {official, commercial}
    assert result.conflict is not None and result.reasons == ("higher-authority source",)


def test_between_equal_authorities_the_later_source_wins() -> None:
    ledger = Ledger()
    found(ledger, PRICE, q("260000", "EUR"), "notice_old")
    later = found(ledger, PRICE, q("245000", "EUR"), "notice_new")
    run(ledger)
    result = settled(ledger, PRICE, SCHEMA)
    assert result.fact is not None and result.fact.id == later
    assert result.reasons == ("later source",)


def test_sources_of_equal_standing_are_escalated_not_guessed() -> None:
    same_day = (
        *CARDS[:2],
        DocumentCard("notice_old", "notice", dt.date(2026, 9, 1), 3),
        *CARDS[3:],
    )
    ledger = Ledger()
    found(ledger, PRICE, q("260000", "EUR"), "notice_old")
    found(ledger, PRICE, q("245000", "EUR"), "notice_new")
    verify(ledger, ELEMENTS, same_day, SCHEMA, KEYS, TOTALS, lambda value: [])
    result = settled(ledger, PRICE, SCHEMA)
    assert result.fact is None and result.conflict is not None
    assert result.conflict.resolution is not None and result.conflict.resolution.chosen is None
    assert len(result.supporting) == 2


def test_the_same_value_from_two_sources_is_not_a_disagreement() -> None:
    ledger = Ledger()
    found(ledger, LAND, q("1200", "m2"), "survey")
    found(ledger, LAND, q("0.12", "ha"), "notice_new")
    found(ledger, PRICE, q("245000.4", "EUR"), "notice_new")
    run(ledger)
    assert ledger.conflicts() == ()
    assert len(settled(ledger, LAND, SCHEMA).supporting) == 2


def test_a_declared_total_is_recomputed_and_beats_a_stated_total_that_differs() -> None:
    ledger = Ledger()
    found(ledger, GROUND, q("115", "m2"), "table", "Sheet1!B6")
    found(ledger, FIRST, q("200", "m2"), "table", "Sheet1!B7")
    stated = found(ledger, TOTAL, q("330", "m2"), "table", "Sheet1!B9")
    run(ledger)
    result = settled(ledger, TOTAL, SCHEMA)
    assert result.fact is not None
    assert (result.fact.value, result.fact.method) == (q("315", "m2"), COMPUTED)
    assert result.fact.citations == (Citation("table", None),)
    assert result.reasons == ("recomputed from its parts",)
    assert stated in {f.id for f in result.supporting}


def test_a_stated_total_that_matches_its_parts_raises_no_conflict() -> None:
    ledger = Ledger()
    found(ledger, GROUND, q("115", "m2"), "table", "Sheet1!B6")
    found(ledger, FIRST, q("200", "m2"), "table", "Sheet1!B7")
    run(ledger)
    result = settled(ledger, TOTAL, SCHEMA)
    assert result.conflict is None
    assert result.fact is not None and result.fact.value == q("315", "m2")


def test_no_total_is_computed_while_a_part_is_missing() -> None:
    ledger = Ledger()
    found(ledger, GROUND, q("115", "m2"), "table", "Sheet1!B6")
    stated = found(ledger, TOTAL, q("330", "m2"), "table", "Sheet1!B9")
    run(ledger)
    result = settled(ledger, TOTAL, SCHEMA)
    assert result.fact is not None and result.fact.id == stated
    assert all(f.method != COMPUTED for f in ledger.facts())


def test_flags_on_a_fact_are_reported_with_its_key() -> None:
    ledger = Ledger()
    fact_id = found(ledger, HEIGHT, q("9", "m"), "rules", "p8")
    run(ledger)
    ledger.append("rules", [Flag(fact_id, "expired")])
    assert settled(ledger, HEIGHT, SCHEMA).reasons == ("expired",)
