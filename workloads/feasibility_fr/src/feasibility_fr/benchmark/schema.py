"""Attributes a benchmark fact sheet may use, with their units."""

from decimal import Decimal

from haussmann.evalkit.groundtruth import AttributeDef, Schema, ValueKind


def _quantity(name: str, unit: str, **other_units: str) -> AttributeDef:
    factors = {other: Decimal(factor) for other, factor in other_units.items()}
    return AttributeDef(name, ValueKind.QUANTITY, canonical_unit=unit, units=factors)


def _text(name: str) -> AttributeDef:
    return AttributeDef(name, ValueKind.TEXT)


def _date(name: str) -> AttributeDef:
    return AttributeDef(name, ValueKind.DATE)


_ATTRIBUTES = (
    # Regulation and site
    _text("zone"),
    _quantity("max_height", "m"),
    _quantity("footprint_limit", "percent"),
    _quantity("street_setback", "m"),
    _quantity("land_area", "m2", ha="10000"),
    _quantity("floor_area", "m2"),
    _date("planning_certificate_date"),
    # Ownership and finance
    _text("owner"),
    _text("occupancy"),
    _quantity("asking_price", "EUR", kEUR="1000", MEUR="1000000"),
    _quantity("annual_rent", "EUR/year", **{"EUR/month": "12", "EUR/quarter": "4"}),
    _date("lease_end"),
    _text("soil_study"),
)

ATTRIBUTES: Schema = {attribute.name: attribute for attribute in _ATTRIBUTES}
