"""Layout-neutral documents: what a template returns and what a renderer receives."""

import datetime as dt
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from haussmann.coretypes.values import AttributeDef, Value
from haussmann.evalkit.groundtruth import DocumentPlan, PlannedStatement


@dataclass(frozen=True, slots=True)
class Heading:
    text: str


@dataclass(frozen=True, slots=True)
class Paragraph:
    """`text` holds one `{}` slot per statement, filled by the generator."""

    text: str
    states: tuple[PlannedStatement, ...] = ()


type Cell = str | PlannedStatement


@dataclass(frozen=True, slots=True)
class Table:
    header: tuple[str, ...]
    rows: tuple[tuple[Cell, ...], ...]


@dataclass(frozen=True, slots=True)
class Filler:
    paragraphs: int


type Block = Heading | Paragraph | Table | Filler


@dataclass(frozen=True, slots=True)
class Body:
    title: str
    blocks: tuple[Block, ...]


type Template = Callable[[DocumentPlan, random.Random], Body]
type Formatter = Callable[[Value, AttributeDef], str]


@dataclass(frozen=True, slots=True)
class Line:
    style: Literal["heading", "text"]
    text: str
    states: tuple[PlannedStatement, ...] = ()


@dataclass(frozen=True, slots=True)
class Grid:
    """`states` gives the row and column, within `rows`, of each statement cell."""

    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    states: tuple[tuple[int, int, PlannedStatement], ...] = ()


@dataclass(frozen=True, slots=True)
class Layout:
    """A document with every value written out, ready to render."""

    doc_id: str
    title: str
    date: dt.date
    items: tuple[Line | Grid, ...]


type Located = tuple[PlannedStatement, str]
type Rendered = tuple[bytes, list[Located]]
