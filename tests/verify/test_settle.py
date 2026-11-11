import datetime as dt
from decimal import Decimal

import pytest

from haussmann.coretypes.values import AttributeDef, FactKey, Quantity, Schema, Value, ValueKind
from haussmann.docparse.cards import DocumentCard
from haussmann.docparse.elements import Element
from haussmann.ledger.ledger import Citation, Condition, Flag, Ledger, NewFact, Status
from haussmann.verify.settle import COMPUTED, same_case, settled, verify

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


def no_renderings(value: Value) -> list[str]:
    return []


CASE_SCHEMA: Schema = {
    "tier": AttributeDef("tier", ValueKind.TEXT),
    "limit": AttributeDef("limit", ValueKind.QUANTITY, "m"),
    "area": AttributeDef("area", ValueKind.QUANTITY, "m2"),
}
TIER = FactKey("site", "tier")
LIMIT = FactKey("site", "limit")
CASE_ELEMENTS = (
    Element("letter", "p1", "Le terrain relève du niveau B2. Limite : 8 m."),
    Element("rules_a", "p1", "Niveau A1 : limite de 12 m."),
    Element("rules_b", "p1", "Niveau B2 : limite de 8 m."),
    Element("rules_c", "p1", "Niveau B2b : limite de 7 m."),
    Element("memo", "p1", "Le terrain relève du niveau A1."),
)
CASE_CARDS = tuple(
    DocumentCard(e.doc_id, "document", dt.date(2026, 1, 1), 3) for e in CASE_ELEMENTS
)


def limit(amount: str, doc_id: str, case: str | None) -> NewFact:
    condition = Condition(TIER, case) if case is not None else None
    return NewFact(LIMIT, q(amount, "m"), (Citation(doc_id, "p1"),), holds_when=condition)


def case_ledger(*records: NewFact) -> Ledger:
    ledger = Ledger()
    ledger.append("finder", list(records))
    return ledger


def settle_cases(ledger: Ledger) -> None:
    verify(
        ledger,
        CASE_ELEMENTS,
        CASE_CARDS,
        CASE_SCHEMA,
        (LIMIT, TIER),
        {},
        no_renderings,
        {LIMIT: TIER},
    )


def test_facts_stated_for_another_case_are_set_aside() -> None:
    ledger = case_ledger(
        NewFact(TIER, "B2", (Citation("letter", "p1"),)),
        limit("12", "rules_a", "Niveau A1"),
        limit("8", "rules_b", "niveau  b2"),
        limit("7", "rules_c", "Niveau B2b"),
        limit("8", "letter", None),
    )
    settle_cases(ledger)
    result = settled(ledger, LIMIT, CASE_SCHEMA)
    assert result.fact is not None and result.fact.value == q("8", "m")
    assert result.conflict is None
    assert [f.citations[0].doc_id for f in result.supporting] == ["rules_b", "letter"]
    assert [f.citations[0].doc_id for f in result.set_aside] == ["rules_a", "rules_c"]
    assert all(ledger.status(f.id) is Status.SET_ASIDE for f in result.set_aside)


def test_an_unconditioned_fact_that_disagrees_is_still_a_conflict() -> None:
    ledger = case_ledger(
        NewFact(TIER, "B2", (Citation("letter", "p1"),)),
        limit("12", "rules_a", None),
        limit("8", "rules_b", "Niveau B2"),
    )
    settle_cases(ledger)
    result = settled(ledger, LIMIT, CASE_SCHEMA)
    assert result.conflict is not None and result.set_aside == ()


def test_nothing_is_set_aside_when_the_deciding_fact_is_missing_or_escalated() -> None:
    missing = case_ledger(limit("12", "rules_a", "Niveau A1"), limit("8", "rules_b", "Niveau B2"))
    escalated = case_ledger(
        NewFact(TIER, "B2", (Citation("letter", "p1"),)),
        NewFact(TIER, "A1", (Citation("memo", "p1"),)),
        limit("12", "rules_a", "Niveau A1"),
        limit("8", "rules_b", "Niveau B2"),
    )
    for ledger in (missing, escalated):
        settle_cases(ledger)
        result = settled(ledger, LIMIT, CASE_SCHEMA)
        assert result.fact is None and result.conflict is not None
        assert result.set_aside == () and len(result.supporting) == 2


def test_a_set_aside_part_is_left_out_of_a_computed_total() -> None:
    part, whole = FactKey("lot:1", "area"), FactKey("all", "area")
    elements = (
        *CASE_ELEMENTS,
        Element("plan_a", "p1", "Niveau A1 : 300 m²."),
        Element("plan_b", "p1", "Niveau B2 : 200 m²."),
    )
    cards = tuple(DocumentCard(e.doc_id, "document", dt.date(2026, 1, 1), 3) for e in elements)
    ledger = case_ledger(
        NewFact(TIER, "B2", (Citation("letter", "p1"),)),
        NewFact(
            part, q("300", "m2"), (Citation("plan_a", "p1"),), holds_when=Condition(TIER, "A1")
        ),
        NewFact(
            part, q("200", "m2"), (Citation("plan_b", "p1"),), holds_when=Condition(TIER, "B2")
        ),
    )
    verify(
        ledger,
        elements,
        cards,
        CASE_SCHEMA,
        (part, whole, TIER),
        {whole: (part,)},
        no_renderings,
        {part: TIER},
    )
    total = settled(ledger, whole, CASE_SCHEMA).fact
    assert total is not None and total.value == q("200", "m2")


def test_a_chain_of_dependencies_is_refused() -> None:
    with pytest.raises(ValueError, match="depends on a dependent key"):
        verify(
            Ledger(),
            CASE_ELEMENTS,
            CASE_CARDS,
            CASE_SCHEMA,
            (LIMIT, TIER),
            {},
            no_renderings,
            {LIMIT: TIER, TIER: FactKey("site", "area")},
        )


@pytest.mark.parametrize(
    ("stated", "decided", "same"),
    [
        ("B2", "B2", True),
        ("Niveau B2", "b2", True),
        ("  niveau   B2 :", "B2", True),
        ("Niveau B2b", "B2", False),
        ("Niveau A1", "B2", False),
        ("B2", "Niveau B2", False),
    ],
)
def test_a_condition_matches_the_decided_case_as_whole_words(
    stated: str, decided: str, same: bool
) -> None:
    assert same_case(stated, decided) is same
