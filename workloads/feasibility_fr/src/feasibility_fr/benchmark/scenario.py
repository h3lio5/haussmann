"""A benchmark scenario: its answer key, its wording, and helpers to write one compactly."""

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from feasibility_fr.benchmark.templates import Wording, make_templates
from feasibility_fr.benchmark.wording import FILLER
from feasibility_fr.engine.documents import COMMERCIAL, OFFICIAL, OWNER
from feasibility_fr.french import format_value
from feasibility_fr.schema import ATTRIBUTES
from haussmann.coretypes.values import FactKey, Quantity, Value
from haussmann.evalkit.generator import Generated, build
from haussmann.evalkit.groundtruth import (
    DocumentPlan,
    PlannedStatement,
    ScenarioSpec,
    StatementKind,
)


@dataclass(frozen=True, slots=True)
class Scenario:
    """`totals` declares which facts are sums of which others, as a deliverable spec would.

    `filler` is the pool of boilerplate paragraphs its long documents draw from.
    """

    spec: ScenarioSpec
    wording: Wording
    totals: Mapping[FactKey, tuple[FactKey, ...]] = field(
        default_factory=dict[FactKey, tuple[FactKey, ...]]
    )
    filler: tuple[str, ...] = FILLER


def generate(scenario: Scenario) -> Generated:
    templates = make_templates(scenario.wording)
    return build(scenario.spec, ATTRIBUTES, templates, format_value, scenario.filler)


def q(amount: str, unit: str) -> Quantity:
    return Quantity(Decimal(amount), unit)


def supports(key: FactKey, value: Value) -> PlannedStatement:
    return PlannedStatement(key, value, StatementKind.SUPPORTS)


def stale(key: FactKey, value: Value) -> PlannedStatement:
    return PlannedStatement(key, value, StatementKind.STALE)


def conflicts(key: FactKey, value: Value) -> PlannedStatement:
    return PlannedStatement(key, value, StatementKind.CONFLICTS)


def distractor(key: FactKey, value: Value) -> PlannedStatement:
    return PlannedStatement(key, value, StatementKind.DISTRACTOR)


def doc(
    doc_id: str,
    kind: str,
    fmt: str,
    date: dt.date,
    authority: int,
    *states: PlannedStatement,
    scanned: bool = False,
) -> DocumentPlan:
    return DocumentPlan(doc_id, kind, fmt, date, authority, scanned, states)


__all__ = [
    "COMMERCIAL",
    "OFFICIAL",
    "OWNER",
    "Scenario",
    "conflicts",
    "distractor",
    "doc",
    "generate",
    "q",
    "stale",
    "supports",
]
