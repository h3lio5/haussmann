"""Read and write a scenario manifest as JSON."""

import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from haussmann.coretypes.values import FactKey, Quantity, Value
from haussmann.evalkit.groundtruth import (
    GoldFact,
    Manifest,
    ManifestFile,
    Split,
    Statement,
    StatementKind,
    Trap,
    TrapType,
)


class _Wire(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class _QuantityWire(_Wire):
    kind: Literal["quantity"] = "quantity"
    amount: Decimal
    unit: str


class _DateWire(_Wire):
    kind: Literal["date"] = "date"
    value: dt.date


class _TextWire(_Wire):
    kind: Literal["text"] = "text"
    value: str


type _ValueWire = Annotated[_QuantityWire | _DateWire | _TextWire, Field(discriminator="kind")]


class _KeyWire(_Wire):
    subject: str
    attribute: str


class _GoldWire(_Wire):
    key: _KeyWire
    value: _ValueWire | None


class _TrapWire(_Wire):
    type: TrapType
    key: _KeyWire
    docs: tuple[str, ...]
    parts: tuple[_KeyWire, ...]


class _StatementWire(_Wire):
    locator: str
    key: _KeyWire
    value: _ValueWire
    kind: StatementKind


class _FileWire(_Wire):
    doc_id: str
    filename: str
    sha256: str
    statements: tuple[_StatementWire, ...]


class _ManifestWire(_Wire):
    scenario_id: str
    split: Split
    gold: tuple[_GoldWire, ...]
    traps: tuple[_TrapWire, ...]
    files: tuple[_FileWire, ...]


def _value_out(value: Value) -> _QuantityWire | _DateWire | _TextWire:
    if isinstance(value, Quantity):
        return _QuantityWire(amount=value.amount, unit=value.unit)
    if isinstance(value, dt.date):
        return _DateWire(value=value)
    return _TextWire(value=value)


def _value_in(wire: _QuantityWire | _DateWire | _TextWire) -> Value:
    if isinstance(wire, _QuantityWire):
        return Quantity(wire.amount, wire.unit)
    return wire.value


def _key_out(key: FactKey) -> _KeyWire:
    return _KeyWire(subject=key.subject, attribute=key.attribute)


def _key_in(wire: _KeyWire) -> FactKey:
    return FactKey(wire.subject, wire.attribute)


def dump_manifest(manifest: Manifest) -> str:
    wire = _ManifestWire(
        scenario_id=manifest.scenario_id,
        split=manifest.split,
        gold=tuple(
            _GoldWire(
                key=_key_out(fact.key),
                value=None if fact.value is None else _value_out(fact.value),
            )
            for fact in manifest.gold
        ),
        traps=tuple(
            _TrapWire(
                type=trap.type,
                key=_key_out(trap.key),
                docs=trap.docs,
                parts=tuple(_key_out(part) for part in trap.parts),
            )
            for trap in manifest.traps
        ),
        files=tuple(
            _FileWire(
                doc_id=file.doc_id,
                filename=file.filename,
                sha256=file.sha256,
                statements=tuple(
                    _StatementWire(
                        locator=s.locator,
                        key=_key_out(s.key),
                        value=_value_out(s.value),
                        kind=s.kind,
                    )
                    for s in file.statements
                ),
            )
            for file in manifest.files
        ),
    )
    return wire.model_dump_json(indent=2) + "\n"


def load_manifest(text: str) -> Manifest:
    """Raises pydantic.ValidationError on a malformed manifest."""
    wire = _ManifestWire.model_validate_json(text)
    return Manifest(
        scenario_id=wire.scenario_id,
        split=wire.split,
        gold=tuple(
            GoldFact(_key_in(g.key), None if g.value is None else _value_in(g.value))
            for g in wire.gold
        ),
        traps=tuple(
            Trap(t.type, _key_in(t.key), t.docs, tuple(_key_in(p) for p in t.parts))
            for t in wire.traps
        ),
        files=tuple(
            ManifestFile(
                doc_id=f.doc_id,
                filename=f.filename,
                sha256=f.sha256,
                statements=tuple(
                    Statement(f.doc_id, s.locator, _key_in(s.key), _value_in(s.value), s.kind)
                    for s in f.statements
                ),
            )
            for f in wire.files
        ),
    )
