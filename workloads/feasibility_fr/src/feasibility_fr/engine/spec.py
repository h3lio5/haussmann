"""What a run is asked to establish, and how a value written by a model is read."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from feasibility_fr.french import parse_date
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
        return parse_date(value) or value
    cleaned = "".join(value.split()).replace(",", ".")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        return value
    if not amount.is_finite():
        return value
    return Quantity(amount, unit or attribute.canonical_unit or "")
