"""Date rules: what has expired or ended by the review date."""

import calendar
import datetime as dt
from collections.abc import Sequence

from haussmann.coretypes.values import FactKey, Schema
from haussmann.engine.workload import DateRules
from haussmann.ledger.ledger import Flag, Ledger
from haussmann.verify.settle import settled

AUTHOR = "date-rules"


def add_months(date: dt.date, months: int) -> dt.date:
    year, month = divmod(date.month - 1 + months, 12)
    year += date.year
    month += 1
    return dt.date(year, month, min(date.day, calendar.monthrange(year, month)[1]))


def flag_dates(
    ledger: Ledger, keys: Sequence[FactKey], schema: Schema, rules: DateRules, as_of: dt.date
) -> None:
    """Flag each settled date that has expired or ended before the review date, once."""
    flags: list[Flag] = []
    already = {(flag.fact_id, flag.reason) for flag in ledger.flags()}
    for key in keys:
        fact = settled(ledger, key, schema).fact
        if fact is None or not isinstance(fact.value, dt.date):
            continue
        months = rules.valid_for_months.get(key.attribute)
        if months is not None and add_months(fact.value, months) < as_of:
            expiry = add_months(fact.value, months).isoformat()
            flags.append(Flag(fact.id, f"valid for {months} months, expired on {expiry}"))
        elif key.attribute in rules.end_dates and fact.value < as_of:
            flags.append(Flag(fact.id, "ended before the review date"))
    flags = [flag for flag in flags if (flag.fact_id, flag.reason) not in already]
    if flags:
        ledger.append(AUTHOR, flags)
