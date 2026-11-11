import datetime as dt
from dataclasses import replace
from decimal import Decimal

import pytest

from haussmann.evalkit.groundtruth import (
    AttributeDef,
    DocumentPlan,
    FactKey,
    GoldFact,
    PlannedStatement,
    Quantity,
    ScenarioSpec,
    Schema,
    Split,
    StatementKind,
    Trap,
    TrapType,
    Value,
    ValueKind,
)
from haussmann.evalkit.validation import Rule, validate

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
FLOOR_1 = FactKey("floor:1", "area")
FLOOR_2 = FactKey("floor:2", "area")
SIGNED = FactKey("permit", "signed")
SURVEY = FactKey("site", "survey")
PLAIN = FactKey("neighbour", "label")


def doc(doc_id: str, year: int, authority: int, *states: PlannedStatement) -> DocumentPlan:
    return DocumentPlan(doc_id, "template", "pdf", dt.date(year, 1, 1), authority, False, states)


def says(key: FactKey, value: Value, kind: StatementKind = SUPPORTS) -> PlannedStatement:
    return PlannedStatement(key, value, kind)


VALID = ScenarioSpec(
    id="base",
    split=Split.DEV,
    seed=1,
    gold=(
        GoldFact(HEIGHT, q("12", "m")),
        GoldFact(LABEL, "UA"),
        GoldFact(AREA, q("1200", "m2")),
        GoldFact(HOLDER, "Acme"),
        GoldFact(AMOUNT, q("500000", "EUR")),
        GoldFact(TOTAL, q("300", "m2")),
        GoldFact(FLOOR_1, q("100", "m2")),
        GoldFact(FLOOR_2, q("200", "m2")),
        GoldFact(SIGNED, dt.date(2019, 5, 2)),
        GoldFact(SURVEY, None),
        GoldFact(PLAIN, "UB"),
    ),
    documents=(
        doc("old", 2020, 2, says(HEIGHT, q("9", "m"), STALE)),
        doc(
            "new",
            2023,
            3,
            says(HEIGHT, q("12", "m")),
            says(LABEL, "UA"),
            says(AREA, q("0.12", "ha")),
            says(HOLDER, "Acme"),
            says(AMOUNT, q("500000", "EUR")),
            says(FLOOR_1, q("100", "m2")),
            says(FLOOR_2, q("200", "m2")),
            says(TOTAL, q("320", "m2"), CONFLICTS),
            says(SIGNED, dt.date(2019, 5, 2)),
            says(PLAIN, "UB"),
        ),
        doc("memo", 2023, 1, says(AMOUNT, q("450000", "EUR"), CONFLICTS)),
        doc("other", 2022, 2, says(HOLDER, "Globex", DISTRACTOR)),
    ),
    traps=(
        Trap(TrapType.SUPERSEDED, HEIGHT, ("old", "new")),
        Trap(TrapType.BURIED, LABEL, ("new",)),
        Trap(TrapType.UNIT, AREA, ("new",)),
        Trap(TrapType.DISTRACTOR, HOLDER, ("other",)),
        Trap(TrapType.CONTRADICTION, AMOUNT, ("memo", "new")),
        Trap(TrapType.ARITHMETIC, TOTAL, ("new",), (FLOOR_1, FLOOR_2)),
        Trap(TrapType.DATE_LOGIC, SIGNED, ("new",)),
        Trap(TrapType.MISSING, SURVEY, ()),
    ),
)


def gold(spec: ScenarioSpec, key: FactKey, value: Value | None) -> ScenarioSpec:
    facts = tuple(GoldFact(key, value) if f.key == key else f for f in spec.gold)
    return replace(spec, gold=facts)


def state(
    spec: ScenarioSpec, doc_id: str, key: FactKey, value: Value | None, kind: StatementKind
) -> ScenarioSpec:
    """Replace what one document says about a key; a value of None removes the statement."""

    def edit(plan: DocumentPlan) -> DocumentPlan:
        if plan.doc_id != doc_id:
            return plan
        kept = tuple(s for s in plan.states if s.key != key)
        added = () if value is None else (PlannedStatement(key, value, kind),)
        return replace(plan, states=kept + added)

    return replace(spec, documents=tuple(edit(d) for d in spec.documents))


def redate(spec: ScenarioSpec, doc_id: str, year: int) -> ScenarioSpec:
    docs = tuple(
        replace(d, date=dt.date(year, 1, 1)) if d.doc_id == doc_id else d for d in spec.documents
    )
    return replace(spec, documents=docs)


def rank(spec: ScenarioSpec, doc_id: str, authority: int) -> ScenarioSpec:
    docs = tuple(
        replace(d, authority=authority) if d.doc_id == doc_id else d for d in spec.documents
    )
    return replace(spec, documents=docs)


def trap(spec: ScenarioSpec, key: FactKey, new: Trap | None) -> ScenarioSpec:
    kept = tuple(t for t in spec.traps if t.key != key)
    return replace(spec, traps=kept if new is None else (*kept, new))


def test_valid_spec_has_no_violations() -> None:
    assert validate(VALID, SCHEMA) == []


BROKEN = {
    "gold attribute outside the schema": (
        replace(VALID, gold=(*VALID.gold, GoldFact(FactKey("site", "colour"), "red"))),
        Rule.SCHEMA,
    ),
    "gold value of the wrong kind": (gold(VALID, PLAIN, dt.date(2020, 1, 1)), Rule.SCHEMA),
    "gold value in a non-canonical unit": (gold(VALID, AREA, q("0.12", "ha")), Rule.SCHEMA),
    "statement in an unknown unit": (
        state(VALID, "new", AREA, q("1200", "acres"), SUPPORTS),
        Rule.SCHEMA,
    ),
    "no gold value without a MISSING trap": (gold(VALID, PLAIN, None), Rule.MISSING),
    "MISSING trap on a fact with a value": (gold(VALID, SURVEY, "done"), Rule.MISSING),
    "missing fact stated in a document": (
        state(VALID, "memo", SURVEY, "done", SUPPORTS),
        Rule.MISSING,
    ),
    "fact with no supporting statement": (
        state(VALID, "new", PLAIN, None, SUPPORTS),
        Rule.UNSUPPORTED,
    ),
    "supporting statement with another value": (
        state(VALID, "new", PLAIN, "UC", SUPPORTS),
        Rule.VALUE,
    ),
    "bait equal to the gold value": (
        state(VALID, "old", HEIGHT, q("12", "m"), STALE),
        Rule.VALUE,
    ),
    "bait within tolerance of the gold value": (
        state(VALID, "memo", AMOUNT, q("500000.50", "EUR"), CONFLICTS),
        Rule.VALUE,
    ),
    "bait on a fact with no trap": (state(VALID, "memo", PLAIN, "UZ", CONFLICTS), Rule.OWNERSHIP),
    "bait in a document the trap does not name": (
        state(VALID, "other", AMOUNT, q("1", "EUR"), CONFLICTS),
        Rule.OWNERSHIP,
    ),
    "bait of a kind the trap does not plant": (
        state(VALID, "old", HEIGHT, q("9", "m"), DISTRACTOR),
        Rule.OWNERSHIP,
    ),
    "two traps on one key": (
        replace(VALID, traps=(*VALID.traps, Trap(TrapType.BURIED, HEIGHT, ("new",)))),
        Rule.OWNERSHIP,
    ),
    "stale document dated after its amendment": (redate(VALID, "old", 2024), Rule.SHAPE),
    "conflicting document of equal authority": (rank(VALID, "memo", 3), Rule.SHAPE),
    "unit trap stated in the canonical unit": (
        state(VALID, "new", AREA, q("1200", "m2"), SUPPORTS),
        Rule.SHAPE,
    ),
    "arithmetic total that is not the sum of its parts": (
        gold(VALID, TOTAL, q("310", "m2")),
        Rule.SHAPE,
    ),
    "arithmetic trap without parts": (
        trap(VALID, TOTAL, Trap(TrapType.ARITHMETIC, TOTAL, ("new",))),
        Rule.SHAPE,
    ),
    "buried fact supported in two documents": (
        state(VALID, "memo", LABEL, "UA", SUPPORTS),
        Rule.SHAPE,
    ),
    "distractor trap with no distractor": (
        state(VALID, "other", HOLDER, None, DISTRACTOR),
        Rule.SHAPE,
    ),
    "parts on a trap that is not arithmetic": (
        trap(VALID, LABEL, Trap(TrapType.BURIED, LABEL, ("new",), (FLOOR_1,))),
        Rule.SHAPE,
    ),
    "duplicate document id": (
        replace(VALID, documents=(*VALID.documents, doc("memo", 2021, 1))),
        Rule.REFERENCE,
    ),
    "duplicate gold key": (replace(VALID, gold=(*VALID.gold, VALID.gold[0])), Rule.REFERENCE),
    "trap naming an unknown document": (
        trap(VALID, LABEL, Trap(TrapType.BURIED, LABEL, ("ghost",))),
        Rule.REFERENCE,
    ),
    "trap on a key with no gold fact": (
        replace(VALID, traps=(*VALID.traps, Trap(TrapType.BURIED, FactKey("site", "x"), ("new",)))),
        Rule.REFERENCE,
    ),
    "statement about a key with no gold fact": (
        state(VALID, "memo", FactKey("site", "x"), "y", SUPPORTS),
        Rule.REFERENCE,
    ),
}


@pytest.mark.parametrize("name", BROKEN)
def test_each_broken_spec_reports_exactly_its_rule(name: str) -> None:
    spec, rule = BROKEN[name]
    assert {violation.rule for violation in validate(spec, SCHEMA)} == {rule}
