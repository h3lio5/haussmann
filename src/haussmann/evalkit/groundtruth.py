"""Ground truth of a benchmark scenario: what is true and what every document states."""

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class Quantity:
    amount: Decimal
    unit: str


type Value = Quantity | dt.date | str


class ValueKind(StrEnum):
    QUANTITY = "quantity"
    DATE = "date"
    TEXT = "text"


def kind_of(value: Value) -> ValueKind:
    if isinstance(value, Quantity):
        return ValueKind.QUANTITY
    if isinstance(value, dt.date):
        return ValueKind.DATE
    return ValueKind.TEXT


@dataclass(frozen=True, slots=True)
class FactKey:
    subject: str
    attribute: str


@dataclass(frozen=True, slots=True)
class AttributeDef:
    """`units` maps each non-canonical unit to its factor towards the canonical unit."""

    name: str
    kind: ValueKind
    canonical_unit: str | None = None
    units: Mapping[str, Decimal] = field(default_factory=dict[str, Decimal])
    tolerance: Decimal = Decimal(0)


type Schema = Mapping[str, AttributeDef]


def normalize(value: Value, attribute: AttributeDef) -> Value | None:
    """Express a value in the attribute's canonical unit; None if it cannot be."""
    if kind_of(value) is not attribute.kind:
        return None
    if not isinstance(value, Quantity) or value.unit == attribute.canonical_unit:
        return value
    factor = attribute.units.get(value.unit)
    if factor is None or attribute.canonical_unit is None:
        return None
    return Quantity(value.amount * factor, attribute.canonical_unit)


def within_tolerance(left: Value, right: Value, tolerance: Decimal) -> bool:
    """Compare two normalized values of the same attribute."""
    if isinstance(left, Quantity) and isinstance(right, Quantity):
        return left.unit == right.unit and abs(left.amount - right.amount) <= tolerance
    return left == right


@dataclass(frozen=True, slots=True)
class GoldFact:
    """`value` is None when the documents cannot establish the fact."""

    key: FactKey
    value: Value | None


class StatementKind(StrEnum):
    SUPPORTS = "supports"
    STALE = "stale"
    CONFLICTS = "conflicts"
    DISTRACTOR = "distractor"


@dataclass(frozen=True, slots=True)
class PlannedStatement:
    key: FactKey
    value: Value
    kind: StatementKind


@dataclass(frozen=True, slots=True)
class Statement:
    doc_id: str
    locator: str
    key: FactKey
    value: Value
    kind: StatementKind


@dataclass(frozen=True, slots=True)
class DocumentPlan:
    doc_id: str
    source: str
    format: str
    date: dt.date
    authority: int
    scanned: bool
    states: tuple[PlannedStatement, ...]


class TrapType(StrEnum):
    CONTRADICTION = "contradiction"
    SUPERSEDED = "superseded"
    BURIED = "buried"
    UNIT = "unit"
    ARITHMETIC = "arithmetic"
    DATE_LOGIC = "date_logic"
    MISSING = "missing"
    DISTRACTOR = "distractor"


@dataclass(frozen=True, slots=True)
class Trap:
    """`parts` are the rows of an ARITHMETIC total and are empty for every other type."""

    type: TrapType
    key: FactKey
    docs: tuple[str, ...]
    parts: tuple[FactKey, ...] = ()


class Split(StrEnum):
    DEV = "dev"
    HELDOUT = "heldout"


@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    id: str
    split: Split
    seed: int
    gold: tuple[GoldFact, ...]
    documents: tuple[DocumentPlan, ...]
    traps: tuple[Trap, ...]


@dataclass(frozen=True, slots=True)
class ManifestFile:
    doc_id: str
    filename: str
    sha256: str
    statements: tuple[Statement, ...]


@dataclass(frozen=True, slots=True)
class Manifest:
    scenario_id: str
    split: Split
    gold: tuple[GoldFact, ...]
    traps: tuple[Trap, ...]
    files: tuple[ManifestFile, ...]
