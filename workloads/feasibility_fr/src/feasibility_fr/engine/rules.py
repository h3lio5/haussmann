"""Date rules of this workload: what has expired or ended by the review date."""

import calendar
import datetime as dt
from collections.abc import Mapping, Sequence

from haussmann.coretypes.values import FactKey, Schema
from haussmann.ledger.ledger import Flag, Ledger
from haussmann.verify.settle import settled

AUTHOR = "date-rules"

# A planning certificate is valid for 18 months from its date (code de l'urbanisme, art. L410-1).
VALID_FOR_MONTHS: Mapping[str, int] = {"planning_certificate_date": 18}
END_DATES: frozenset[str] = frozenset({"lease_end"})


def add_months(date: dt.date, months: int) -> dt.date:
    year, month = divmod(date.month - 1 + months, 12)
    year += date.year
    month += 1
    return dt.date(year, month, min(date.day, calendar.monthrange(year, month)[1]))


def flag_dates(ledger: Ledger, keys: Sequence[FactKey], schema: Schema, as_of: dt.date) -> None:
    """Flag each settled date that has expired or ended before the review date."""
    flags: list[Flag] = []
    for key in keys:
        fact = settled(ledger, key, schema).fact
        if fact is None or not isinstance(fact.value, dt.date):
            continue
        months = VALID_FOR_MONTHS.get(key.attribute)
        if months is not None and add_months(fact.value, months) < as_of:
            expiry = add_months(fact.value, months).isoformat()
            flags.append(Flag(fact.id, f"valid for {months} months, expired on {expiry}"))
        elif key.attribute in END_DATES and fact.value < as_of:
            flags.append(Flag(fact.id, "ended before the review date"))
    if flags:
        ledger.append(AUTHOR, flags)
