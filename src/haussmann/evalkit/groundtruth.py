"""Ground truth of a benchmark scenario: what is true and what every document states."""

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from haussmann.coretypes.values import FactKey, Value


@dataclass(frozen=True, slots=True)
class GoldFact:
    """`value` is None when the documents cannot establish the fact."""

    key: FactKey
    value: Value | None


class StatementKind(StrEnum):
    SUPPORTS = "supports"
    STALE = "stale"
    CONFLICTS = "conflicts"
    DISTRACTOR = "distractor"


@dataclass(frozen=True, slots=True)
class PlannedStatement:
    key: FactKey
    value: Value
    kind: StatementKind


@dataclass(frozen=True, slots=True)
class Statement:
    doc_id: str
    locator: str
    key: FactKey
    value: Value
    kind: StatementKind


@dataclass(frozen=True, slots=True)
class DocumentPlan:
    doc_id: str
    source: str
    format: str
    date: dt.date
    authority: int
    scanned: bool
    states: tuple[PlannedStatement, ...]


class TrapType(StrEnum):
    CONTRADICTION = "contradiction"
    SUPERSEDED = "superseded"
    BURIED = "buried"
    UNIT = "unit"
    ARITHMETIC = "arithmetic"
    DATE_LOGIC = "date_logic"
    MISSING = "missing"
    DISTRACTOR = "distractor"


@dataclass(frozen=True, slots=True)
class Trap:
    """`parts` are the rows of an ARITHMETIC total and are empty for every other type."""

    type: TrapType
    key: FactKey
    docs: tuple[str, ...]
    parts: tuple[FactKey, ...] = ()


class Split(StrEnum):
    DEV = "dev"
    HELDOUT = "heldout"


@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    id: str
    split: Split
    seed: int
    gold: tuple[GoldFact, ...]
    documents: tuple[DocumentPlan, ...]
    traps: tuple[Trap, ...]


@dataclass(frozen=True, slots=True)
class ManifestFile:
    doc_id: str
    filename: str
    sha256: str
    statements: tuple[Statement, ...]


@dataclass(frozen=True, slots=True)
class Manifest:
    scenario_id: str
    split: Split
    gold: tuple[GoldFact, ...]
    traps: tuple[Trap, ...]
    files: tuple[ManifestFile, ...]
