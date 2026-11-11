from decimal import Decimal

from feasibility_fr.schema import ATTRIBUTES
from haussmann.coretypes.values import Quantity, ValueKind, normalize


def test_every_quantity_has_a_canonical_unit_and_positive_factors() -> None:
    for attribute in ATTRIBUTES.values():
        if attribute.kind is ValueKind.QUANTITY:
            assert attribute.canonical_unit
            assert attribute.canonical_unit not in attribute.units
            assert all(factor > 0 for factor in attribute.units.values())
        else:
            assert attribute.canonical_unit is None and not attribute.units


def test_units_convert_to_the_canonical_unit() -> None:
    area = normalize(Quantity(Decimal("0.12"), "ha"), ATTRIBUTES["land_area"])
    rent = normalize(Quantity(Decimal("2500"), "EUR/month"), ATTRIBUTES["annual_rent"])
    assert area == Quantity(Decimal("1200"), "m2")
    assert rent == Quantity(Decimal("30000"), "EUR/year")


def test_unknown_unit_and_wrong_kind_do_not_normalize() -> None:
    assert normalize(Quantity(Decimal("3"), "acres"), ATTRIBUTES["land_area"]) is None
    assert normalize("UA", ATTRIBUTES["land_area"]) is None
