"""Value types shared across the platform: fact keys, values and their units."""

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
