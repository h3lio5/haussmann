import datetime as dt
import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from haussmann.evalkit.groundtruth import (
    FactKey,
    GoldFact,
    Manifest,
    ManifestFile,
    Quantity,
    Split,
    Statement,
    StatementKind,
    Trap,
    TrapType,
)
from haussmann.evalkit.manifest import dump_manifest, load_manifest

AREA = FactKey("site", "area")
SIGNED = FactKey("permit", "signed")
LABEL = FactKey("site", "label")
SURVEY = FactKey("site", "survey")

MANIFEST = Manifest(
    scenario_id="base",
    split=Split.HELDOUT,
    gold=(
        GoldFact(AREA, Quantity(Decimal("1200.50"), "m2")),
        GoldFact(SIGNED, dt.date(2019, 5, 2)),
        GoldFact(LABEL, "2019-05-02"),
        GoldFact(SURVEY, None),
    ),
    traps=(
        Trap(TrapType.ARITHMETIC, AREA, ("a",), (LABEL,)),
        Trap(TrapType.MISSING, SURVEY, ()),
    ),
    files=(
        ManifestFile(
            doc_id="a",
            filename="a.pdf",
            sha256="0" * 64,
            statements=(
                Statement(
                    "a", "page 3", AREA, Quantity(Decimal("0.12005"), "ha"), StatementKind.SUPPORTS
                ),
                Statement("a", "page 4", SIGNED, dt.date(2019, 5, 2), StatementKind.SUPPORTS),
                Statement("a", "page 5", LABEL, "2019-05-02", StatementKind.CONFLICTS),
            ),
        ),
    ),
)


def test_manifest_round_trips_through_json() -> None:
    assert load_manifest(dump_manifest(MANIFEST)) == MANIFEST


def test_dump_is_stable() -> None:
    assert dump_manifest(load_manifest(dump_manifest(MANIFEST))) == dump_manifest(MANIFEST)


def test_amounts_are_written_as_strings_not_floats() -> None:
    written = json.loads(dump_manifest(MANIFEST))
    assert written["gold"][0]["value"] == {"kind": "quantity", "amount": "1200.50", "unit": "m2"}


def test_text_that_looks_like_a_date_stays_text() -> None:
    assert load_manifest(dump_manifest(MANIFEST)).gold[2].value == "2019-05-02"


def test_unknown_field_is_rejected() -> None:
    written = json.loads(dump_manifest(MANIFEST))
    written["extra"] = 1
    with pytest.raises(ValidationError):
        load_manifest(json.dumps(written))
