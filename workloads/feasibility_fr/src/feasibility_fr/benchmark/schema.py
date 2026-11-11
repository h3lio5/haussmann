"""Attributes a benchmark fact sheet may use, with their units."""

from decimal import Decimal

from haussmann.evalkit.groundtruth import AttributeDef, Schema, ValueKind

_TOLERANCE = {"EUR": Decimal(1), "EUR/year": Decimal(1), "m2": Decimal("0.5")}


def _quantity(name: str, unit: str, **other_units: str) -> AttributeDef:
    factors = {other: Decimal(factor) for other, factor in other_units.items()}
    tolerance = _TOLERANCE.get(unit, Decimal(0))
    return AttributeDef(name, ValueKind.QUANTITY, unit, factors, tolerance)


def _text(name: str) -> AttributeDef:
    return AttributeDef(name, ValueKind.TEXT)


def _date(name: str) -> AttributeDef:
    return AttributeDef(name, ValueKind.DATE)


_ATTRIBUTES = (
    # Regulation and site
    _text("parcel_ref"),
    _text("zone"),
    _quantity("max_height", "m"),
    _text("max_levels"),
    _quantity("footprint_limit", "percent"),
    _quantity("street_setback", "m"),
    _quantity("land_area", "m2", ha="10000"),
    _quantity("floor_area", "m2"),
    _date("planning_certificate_date"),
    _text("flood_risk"),
    # Ownership and finance
    _text("owner"),
    _text("occupancy"),
    _quantity("asking_price", "EUR", kEUR="1000", MEUR="1000000"),
    _quantity("annual_rent", "EUR/year", **{"EUR/month": "12", "EUR/quarter": "4"}),
    _date("lease_end"),
    _text("soil_study"),
    _text("pollution_study"),
)

ATTRIBUTES: Schema = {attribute.name: attribute for attribute in _ATTRIBUTES}
