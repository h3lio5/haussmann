"""What a run is asked to establish, and how a value written by a model is read."""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from haussmann.coretypes.values import AttributeDef, FactKey, Quantity, Value, ValueKind


@dataclass(frozen=True, slots=True)
class RequiredFact:
    """A fact to establish. `sum_of` names its parts when it is declared as a total."""

    key: FactKey
    text: str
    sum_of: tuple[FactKey, ...] = ()


def read_value(value: str, unit: str, attribute: AttributeDef | None) -> Value:
    """Read a reported value as its attribute's kind; an unreadable value stays text."""
    if attribute is None or attribute.kind is ValueKind.TEXT:
        return value
    if attribute.kind is ValueKind.DATE:
        try:
            return dt.date.fromisoformat(value.strip())
        except ValueError:
            return value
    cleaned = "".join(value.split()).replace(",", ".")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        return value
    if not amount.is_finite():
        return value
    return Quantity(amount, unit or attribute.canonical_unit or "")
