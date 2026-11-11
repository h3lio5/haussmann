"""Checks that a scenario spec is a consistent ground truth."""

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum

from haussmann.evalkit.groundtruth import (
    DocumentPlan,
    FactKey,
    GoldFact,
    PlannedStatement,
    Quantity,
    ScenarioSpec,
    Schema,
    StatementKind,
    Trap,
    TrapType,
    normalize,
    within_tolerance,
)


class Rule(StrEnum):
    """One member per invariant in docs/notes/benchmark-ground-truth.md, in order."""

    SCHEMA = "schema"
    MISSING = "missing"
    UNSUPPORTED = "unsupported"
    VALUE = "value"
    OWNERSHIP = "ownership"
    SHAPE = "shape"
    REFERENCE = "reference"


@dataclass(frozen=True, slots=True)
class Violation:
    rule: Rule
    detail: str


type Stated = tuple[DocumentPlan, PlannedStatement]

_BAIT_KIND = {
    TrapType.SUPERSEDED: StatementKind.STALE,
    TrapType.CONTRADICTION: StatementKind.CONFLICTS,
    TrapType.ARITHMETIC: StatementKind.CONFLICTS,
    TrapType.DISTRACTOR: StatementKind.DISTRACTOR,
}


def validate(spec: ScenarioSpec, schema: Schema) -> list[Violation]:
    """Return every broken invariant; an empty list means the spec is usable.

    Value and trap checks assume sound references, so they run only when the
    structural checks find nothing.
    """
    structural = list(_structure(spec, schema))
    return structural or list(_semantics(spec, schema))


def _label(key: FactKey) -> str:
    return f"{key.subject}/{key.attribute}"


def _structure(spec: ScenarioSpec, schema: Schema) -> Iterator[Violation]:
    gold = {fact.key for fact in spec.gold}
    doc_ids = {doc.doc_id for doc in spec.documents}
    if len(gold) != len(spec.gold):
        yield Violation(Rule.REFERENCE, "a gold key appears twice")
    if len(doc_ids) != len(spec.documents):
        yield Violation(Rule.REFERENCE, "a document id appears twice")
    if len({trap.key for trap in spec.traps}) != len(spec.traps):
        yield Violation(Rule.OWNERSHIP, "a key has more than one trap")

    for fact in spec.gold:
        attribute = schema.get(fact.key.attribute)
        if attribute is None:
            yield Violation(Rule.SCHEMA, f"{_label(fact.key)}: attribute not in the schema")
        elif fact.value is not None and normalize(fact.value, attribute) != fact.value:
            yield Violation(Rule.SCHEMA, f"{_label(fact.key)}: gold value not canonical")

    for doc in spec.documents:
        for statement in doc.states:
            attribute = schema.get(statement.key.attribute)
            if statement.key not in gold:
                yield Violation(Rule.REFERENCE, f"{doc.doc_id}: states a key with no gold fact")
            elif attribute is not None and normalize(statement.value, attribute) is None:
                yield Violation(Rule.SCHEMA, f"{doc.doc_id}: {_label(statement.key)} unreadable")

    for trap in spec.traps:
        if trap.key not in gold or not gold.issuperset(trap.parts):
            yield Violation(Rule.REFERENCE, f"{_label(trap.key)}: trap on a key with no gold fact")
        if not doc_ids.issuperset(trap.docs):
            yield Violation(Rule.REFERENCE, f"{_label(trap.key)}: trap names an unknown document")
        if trap.parts and trap.type is not TrapType.ARITHMETIC:
            yield Violation(Rule.SHAPE, f"{_label(trap.key)}: only ARITHMETIC has parts")


def _semantics(spec: ScenarioSpec, schema: Schema) -> Iterator[Violation]:
    gold = {fact.key: fact for fact in spec.gold}
    traps = {trap.key: trap for trap in spec.traps}
    for fact in spec.gold:
        stated = [(doc, s) for doc in spec.documents for s in doc.states if s.key == fact.key]
        yield from _fact(fact, traps.get(fact.key), stated, gold, schema)


def _fact(
    fact: GoldFact,
    trap: Trap | None,
    stated: list[Stated],
    gold: dict[FactKey, GoldFact],
    schema: Schema,
) -> Iterator[Violation]:
    name = _label(fact.key)
    attribute = schema[fact.key.attribute]
    missing = trap is not None and trap.type is TrapType.MISSING

    if fact.value is None or missing:
        if fact.value is not None or not missing:
            yield Violation(Rule.MISSING, f"{name}: no gold value and a MISSING trap go together")
        if stated:
            yield Violation(Rule.MISSING, f"{name}: stated in {stated[0][0].doc_id}")
        return

    supports = [(doc, s) for doc, s in stated if s.kind is StatementKind.SUPPORTS]
    if not supports and (trap is None or trap.type is not TrapType.ARITHMETIC):
        yield Violation(Rule.UNSUPPORTED, f"{name}: no document supports the gold value")

    for doc, statement in stated:
        value = normalize(statement.value, attribute)
        assert value is not None
        if statement.kind is StatementKind.SUPPORTS:
            if value != fact.value:
                yield Violation(Rule.VALUE, f"{name}: {doc.doc_id} supports another value")
            continue
        if within_tolerance(value, fact.value, attribute.tolerance):
            yield Violation(Rule.VALUE, f"{name}: bait in {doc.doc_id} equals the gold value")
        owned = (
            trap is not None
            and _BAIT_KIND.get(trap.type) is statement.kind
            and doc.doc_id in trap.docs
        )
        if not owned:
            yield Violation(Rule.OWNERSHIP, f"{name}: bait in {doc.doc_id} belongs to no trap")

    if trap is not None and not _well_formed(trap, fact, stated, gold, schema):
        yield Violation(Rule.SHAPE, f"{name}: not a valid {trap.type} trap")


def _well_formed(
    trap: Trap,
    fact: GoldFact,
    stated: list[Stated],
    gold: dict[FactKey, GoldFact],
    schema: Schema,
) -> bool:
    attribute = schema[fact.key.attribute]
    supports = [(doc, s) for doc, s in stated if s.kind is StatementKind.SUPPORTS]
    inside = [(doc, s) for doc, s in stated if doc.doc_id in trap.docs]
    backing = [doc for doc, s in inside if s.kind is StatementKind.SUPPORTS]
    baits = [doc for doc, s in inside if s.kind is not StatementKind.SUPPORTS]

    match trap.type:
        case TrapType.SUPERSEDED:
            return bool(baits and backing) and max(d.date for d in baits) < min(
                d.date for d in backing
            )
        case TrapType.CONTRADICTION:
            return bool(baits and backing) and max(d.authority for d in baits) < min(
                d.authority for d in backing
            )
        case TrapType.UNIT:
            return all(normalize(s.value, attribute) != s.value for _, s in supports)
        case TrapType.BURIED:
            return len(supports) == 1 and len(backing) == 1
        case TrapType.DISTRACTOR:
            return bool(baits)
        case TrapType.ARITHMETIC:
            total = fact.value
            rows = [gold[part].value for part in trap.parts]
            if not baits or not rows or not isinstance(total, Quantity):
                return False
            amounts = [
                row.amount for row in rows if isinstance(row, Quantity) and row.unit == total.unit
            ]
            return len(amounts) == len(rows) and sum(amounts) == total.amount
        case TrapType.DATE_LOGIC | TrapType.MISSING:
            return True
