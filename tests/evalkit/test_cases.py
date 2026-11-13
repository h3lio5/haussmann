import datetime as dt
from decimal import Decimal

from haussmann.coretypes.values import AttributeDef, FactKey, Quantity, ValueKind
from haussmann.evalkit.cases import (
    Case,
    Standing,
    dump_cases,
    load_cases,
    passes,
    regressions,
    restand,
)

SCHEMA = {
    "owner": AttributeDef("owner", ValueKind.TEXT),
    "area": AttributeDef("area", ValueKind.QUANTITY, "m2", {"ha": Decimal(10000)}, Decimal(1)),
    "signed": AttributeDef("signed", ValueKind.DATE),
}
OWNER = Case("s1", 0, FactKey("site", "owner"), "Town", "the deed names it", "expert:a")
AREA = Case(
    "s1",
    2,
    FactKey("site", "area"),
    Quantity(Decimal("0.12"), "ha"),
    "surveyed",
    "expert:b",
    Standing.HELD,
)
SIGNED = Case("s2", 1, FactKey("site", "signed"), dt.date(2024, 2, 12), "dated", "expert:a")


def test_a_case_passes_when_the_run_settles_on_its_value_in_any_unit_within_tolerance() -> None:
    assert passes(AREA, Quantity(Decimal("1200.5"), "m2"), SCHEMA)
    assert not passes(AREA, Quantity(Decimal(1250), "m2"), SCHEMA)
    assert passes(OWNER, "Town", SCHEMA) and not passes(OWNER, "County", SCHEMA)
    assert passes(SIGNED, dt.date(2024, 2, 12), SCHEMA)


def test_a_case_fails_when_the_run_settles_on_nothing_or_on_another_kind_of_value() -> None:
    assert not passes(OWNER, None, SCHEMA)
    assert not passes(AREA, "1200", SCHEMA)


def test_only_a_held_case_that_stops_passing_is_a_regression() -> None:
    assert regressions([OWNER, AREA, SIGNED], [False, False, False]) == [AREA]
    assert regressions([OWNER, AREA, SIGNED], [False, True, True]) == []


def test_a_check_gives_each_case_its_standing_and_keeps_everything_else() -> None:
    owner, area, signed = restand([OWNER, AREA, SIGNED], [True, False, False])
    assert (owner.standing, area.standing, signed.standing) == (
        Standing.HELD,
        Standing.OPEN,
        Standing.OPEN,
    )
    assert (owner.expected, owner.reason, owner.author) == ("Town", OWNER.reason, OWNER.author)


def test_cases_come_back_from_their_file_as_they_went_in() -> None:
    cases = [OWNER, AREA, SIGNED]
    assert load_cases(dump_cases(cases)) == cases
    assert '"standing": "held"' in dump_cases(cases)
