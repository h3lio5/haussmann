"""How values are written in French documents."""

import datetime as dt
import re
from collections.abc import Mapping
from decimal import Decimal

from haussmann.coretypes.values import AttributeDef, Quantity, Value

UNIT_TEXT: Mapping[str, str] = {
    "m": "m",
    "m2": "m²",
    "ha": "ha",
    "percent": "%",
    "EUR": "€",
    "kEUR": "k€",
    "MEUR": "M€",
    "EUR/year": "€ par an",
    "EUR/month": "€ par mois",
    "EUR/quarter": "€ par trimestre",
}

_MONTHS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def format_number(amount: Decimal) -> str:
    """French convention: spaces between thousands, a comma before decimals."""
    sign = "-" if amount < 0 else ""
    whole, _, fraction = f"{abs(amount).normalize():f}".partition(".")
    groups: list[str] = []
    while whole:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    return sign + " ".join(groups) + (f",{fraction}" if fraction else "")


def format_date(date: dt.date) -> str:
    day = "1er" if date.day == 1 else str(date.day)
    return f"{day} {_MONTHS[date.month - 1]} {date.year}"


def format_value(value: Value, attribute: AttributeDef) -> str:
    if isinstance(value, Quantity):
        return f"{format_number(value.amount)} {UNIT_TEXT[value.unit]}"
    if isinstance(value, dt.date):
        return format_date(value)
    return value


_NUMERIC_DATE = re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})")
_WRITTEN_DATE = re.compile(r"(\d{1,2})(?:er)?\s+([^\W\d]+)\s+(\d{4})")


def parse_date(text: str) -> dt.date | None:
    """Read 2027-08-31, 31/08/2027 or "31 août 2027"; None for anything else."""
    cleaned = text.strip().casefold()
    try:
        return dt.date.fromisoformat(cleaned)
    except ValueError:
        pass
    numeric = _NUMERIC_DATE.fullmatch(cleaned)
    written = _WRITTEN_DATE.fullmatch(cleaned)
    try:
        if numeric is not None:
            day, month, year = (int(part) for part in numeric.groups())
            return dt.date(year, month, day)
        if written is not None and written.group(2) in _MONTHS:
            month = _MONTHS.index(written.group(2)) + 1
            return dt.date(int(written.group(3)), month, int(written.group(1)))
    except ValueError:
        return None
    return None
