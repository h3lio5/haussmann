import datetime as dt
import io
from decimal import Decimal

import pytest
from pypdf import PdfReader

from feasibility_fr.benchmark.schema import ATTRIBUTES
from feasibility_fr.benchmark.templates import KINDS, PHRASES, ROW_LABELS, Wording, make_templates
from feasibility_fr.benchmark.wording import (
    FILLER,
    UNIT_TEXT,
    format_date,
    format_number,
    format_value,
)
from haussmann.evalkit.generator import build
from haussmann.evalkit.groundtruth import (
    DocumentPlan,
    FactKey,
    GoldFact,
    PlannedStatement,
    Quantity,
    ScenarioSpec,
    Split,
    StatementKind,
    Trap,
    TrapType,
)

SUPPORTS = StatementKind.SUPPORTS


@pytest.mark.parametrize(
    ("amount", "text"),
    [
        ("1200", "1 200"),
        ("0.12", "0,12"),
        ("500000", "500 000"),
        ("1234567.5", "1 234 567,5"),
        ("12.00", "12"),
        ("999", "999"),
        ("-1500", "-1 500"),
    ],
)
def test_numbers_use_french_grouping_and_decimal_comma(amount: str, text: str) -> None:
    assert format_number(Decimal(amount)) == text


def test_dates_are_written_out_in_french() -> None:
    assert format_date(dt.date(2019, 5, 2)) == "2 mai 2019"
    assert format_date(dt.date(2021, 8, 1)) == "1er août 2021"


def test_values_carry_their_unit() -> None:
    area = format_value(Quantity(Decimal("0.12"), "ha"), ATTRIBUTES["land_area"])
    rent = format_value(Quantity(Decimal("2500"), "EUR/month"), ATTRIBUTES["annual_rent"])
    assert (area, rent) == ("0,12 ha", "2 500 € par mois")
    assert format_value("UA", ATTRIBUTES["zone"]) == "UA"


def test_every_attribute_and_unit_has_wording() -> None:
    assert set(PHRASES) == set(ATTRIBUTES) == set(ROW_LABELS)
    assert all(phrase.count("{}") == 1 for phrase in PHRASES.values())
    units = {
        unit
        for attribute in ATTRIBUTES.values()
        for unit in (attribute.canonical_unit, *attribute.units)
        if unit
    }
    assert units == set(UNIT_TEXT)


SITE = FactKey("site", "max_height")
SHOP = FactKey("lease:shop", "annual_rent")
WORDING = Wording(
    site="Terrain situé 1 rue de l'Exemple.",
    labels={"lease:shop": "Local commercial"},
    intros={"doc_sales_memo": "Le présent document concerne un autre site."},
)


def spec_with_every_kind(fmt: str) -> ScenarioSpec:
    states = (
        PlannedStatement(SITE, Quantity(Decimal("12"), "m"), SUPPORTS),
        PlannedStatement(SHOP, Quantity(Decimal("2500"), "EUR/month"), SUPPORTS),
    )
    return ScenarioSpec(
        id="kinds",
        split=Split.DEV,
        seed=3,
        gold=(
            GoldFact(SITE, Quantity(Decimal("12"), "m")),
            GoldFact(SHOP, Quantity(Decimal("30000"), "EUR/year")),
        ),
        documents=tuple(
            DocumentPlan(f"doc_{name}", name, fmt, dt.date(2022, 6, 1), 1, False, states)
            for name in KINDS
        ),
        traps=(Trap(TrapType.UNIT, SHOP, tuple(f"doc_{name}" for name in KINDS)),),
    )


def test_every_kind_renders_as_pdf_with_its_statements_and_framing() -> None:
    generated = build(
        spec_with_every_kind("pdf"), ATTRIBUTES, make_templates(WORDING), format_value, FILLER
    )
    for name, kind in KINDS.items():
        reader = PdfReader(io.BytesIO(generated.files[f"doc_{name}.pdf"]))
        text = "\n".join(page.extract_text() for page in reader.pages)
        flat = " ".join(text.split())
        assert kind.title in flat
        assert "12 m" in flat and "2 500 € par mois" in flat
        assert "Local commercial" in flat
        expected_intro = WORDING.intros.get(f"doc_{name}", WORDING.site)
        assert expected_intro in flat


def test_zoning_rules_put_their_statements_deep_in_the_document() -> None:
    generated = build(
        spec_with_every_kind("pdf"), ATTRIBUTES, make_templates(WORDING), format_value, FILLER
    )
    rules = next(f for f in generated.manifest.files if f.doc_id == "doc_zoning_rules")
    assert all(int(s.locator.removeprefix("p")) >= 5 for s in rules.statements)


@pytest.mark.parametrize("fmt", ["xlsx", "eml"])
def test_every_kind_also_renders_as_spreadsheet_and_email(fmt: str) -> None:
    generated = build(
        spec_with_every_kind(fmt), ATTRIBUTES, make_templates(WORDING), format_value, FILLER
    )
    assert len(generated.files) == len(KINDS)
    assert all(len(f.statements) == 2 for f in generated.manifest.files)
