import datetime as dt
import email
import io
import random
from dataclasses import replace
from decimal import Decimal
from email.policy import default as email_policy
from pathlib import Path

import pytest
from openpyxl import load_workbook
from pypdf import PdfReader

from haussmann.coretypes.values import AttributeDef, FactKey, Quantity, Schema, Value, ValueKind
from haussmann.evalkit.documents import Body, Filler, Heading, Paragraph, Table, Template
from haussmann.evalkit.generator import MANIFEST_NAME, Generated, GeneratorError, build, write
from haussmann.evalkit.groundtruth import (
    DocumentPlan,
    GoldFact,
    PlannedStatement,
    ScenarioSpec,
    Split,
    Statement,
    StatementKind,
    Trap,
    TrapType,
)
from haussmann.evalkit.manifest import load_manifest

SUPPORTS, STALE = StatementKind.SUPPORTS, StatementKind.STALE

SCHEMA: Schema = {
    "height": AttributeDef("height", ValueKind.QUANTITY, "m"),
    "area": AttributeDef("area", ValueKind.QUANTITY, "m2", {"ha": Decimal(10000)}),
    "label": AttributeDef("label", ValueKind.TEXT),
    "signed": AttributeDef("signed", ValueKind.DATE),
}

HEIGHT = FactKey("site", "height")
AREA = FactKey("site", "area")
LABEL = FactKey("site", "label")
SIGNED = FactKey("permit", "signed")
FILLER = tuple(f"Clause {n}. " + "Général wording that fills the page. " * 14 for n in range(8))


def q(amount: str, unit: str) -> Quantity:
    return Quantity(Decimal(amount), unit)


def format_value(value: Value, attribute: AttributeDef) -> str:
    if isinstance(value, Quantity):
        return f"{value.amount} {value.unit}"
    if isinstance(value, dt.date):
        return value.strftime("%d/%m/%Y")
    return f"«{value}»"


def letter(plan: DocumentPlan, rng: random.Random) -> Body:
    blocks = [
        Heading("Objet"),
        *(Paragraph("Il est établi que {} s'applique.", (s,)) for s in plan.states),
    ]
    return Body(f"Courrier {plan.doc_id} & annexes", tuple(blocks))


def long_report(plan: DocumentPlan, rng: random.Random) -> Body:
    statement_paragraphs = [Paragraph("Valeur retenue : {}.", (s,)) for s in plan.states]
    return Body("Rapport", (Filler(60), *statement_paragraphs, Filler(5)))


def table(plan: DocumentPlan, rng: random.Random) -> Body:
    rows = tuple((s.key.attribute, s) for s in plan.states)
    return Body("Tableau", (Paragraph("Synthèse"), Table(("Poste", "Valeur"), rows)))


TEMPLATES: dict[str, Template] = {"letter": letter, "long_report": long_report, "table": table}


def doc(
    doc_id: str,
    source: str,
    fmt: str,
    year: int,
    *states: PlannedStatement,
    scanned: bool = False,
) -> DocumentPlan:
    return DocumentPlan(doc_id, source, fmt, dt.date(year, 3, 4), 1, scanned, states)


SPEC = ScenarioSpec(
    id="base",
    split=Split.DEV,
    seed=11,
    gold=(
        GoldFact(HEIGHT, q("12", "m")),
        GoldFact(AREA, q("1200", "m2")),
        GoldFact(LABEL, "UA"),
        GoldFact(SIGNED, dt.date(2019, 5, 2)),
    ),
    documents=(
        doc("old", "letter", "pdf", 2020, PlannedStatement(HEIGHT, q("9", "m"), STALE)),
        doc(
            "new",
            "letter",
            "pdf",
            2023,
            PlannedStatement(HEIGHT, q("12", "m"), SUPPORTS),
            PlannedStatement(SIGNED, dt.date(2019, 5, 2), SUPPORTS),
        ),
        doc("report", "long_report", "pdf", 2022, PlannedStatement(LABEL, "UA", SUPPORTS)),
        doc("sheet", "table", "xlsx", 2022, PlannedStatement(AREA, q("0.12", "ha"), SUPPORTS)),
        doc("mail", "table", "eml", 2022, PlannedStatement(SIGNED, dt.date(2019, 5, 2), SUPPORTS)),
        doc(
            "scan",
            "letter",
            "pdf",
            2021,
            PlannedStatement(HEIGHT, q("12", "m"), SUPPORTS),
            scanned=True,
        ),
    ),
    traps=(
        Trap(TrapType.SUPERSEDED, HEIGHT, ("old", "new")),
        Trap(TrapType.BURIED, LABEL, ("report",)),
        Trap(TrapType.UNIT, AREA, ("sheet",)),
    ),
)


def generate(spec: ScenarioSpec = SPEC, templates: dict[str, Template] = TEMPLATES) -> Generated:
    return build(spec, SCHEMA, templates, format_value, FILLER)


GENERATED = generate()


def stated(generated: Generated) -> list[tuple[FactKey, Value, StatementKind]]:
    return [(s.key, s.value, s.kind) for f in generated.manifest.files for s in f.statements]


def statements(doc_id: str) -> tuple[Statement, ...]:
    return next(f.statements for f in GENERATED.manifest.files if f.doc_id == doc_id)


def test_two_builds_are_byte_identical() -> None:
    again = generate()
    assert again.files == GENERATED.files
    assert again.manifest == GENERATED.manifest


def test_seed_changes_filler_but_no_statement() -> None:
    other = generate(replace(SPEC, seed=12))
    assert other.files["report.pdf"] != GENERATED.files["report.pdf"]
    assert other.files["new.pdf"] == GENERATED.files["new.pdf"]
    assert stated(other) == stated(GENERATED)


def test_every_planned_statement_and_trap_is_in_the_manifest() -> None:
    manifest = GENERATED.manifest
    assert manifest.traps == SPEC.traps and manifest.gold == SPEC.gold
    for plan in SPEC.documents:
        written = [(s.key, s.value, s.kind) for s in statements(plan.doc_id)]
        assert written == [(s.key, s.value, s.kind) for s in plan.states]
        assert all(s.locator and s.doc_id == plan.doc_id for s in statements(plan.doc_id))


@pytest.mark.parametrize("doc_id", ["old", "new", "report"])
def test_pdf_statement_text_is_on_the_page_its_locator_names(doc_id: str) -> None:
    reader = PdfReader(io.BytesIO(GENERATED.files[f"{doc_id}.pdf"]))
    for statement in statements(doc_id):
        page = reader.pages[int(statement.locator.removeprefix("p")) - 1]
        expected = format_value(statement.value, SCHEMA[statement.key.attribute])
        assert expected in page.extract_text()


def test_accents_and_markup_characters_survive_in_a_pdf() -> None:
    text = PdfReader(io.BytesIO(GENERATED.files["new.pdf"])).pages[0].extract_text()
    assert "Courrier new & annexes" in text
    assert "Il est établi que" in text


def test_buried_statement_is_deep_in_a_long_document() -> None:
    (statement,) = statements("report")
    assert int(statement.locator.removeprefix("p")) >= 5


def test_spreadsheet_cell_at_the_locator_holds_the_value() -> None:
    (statement,) = statements("sheet")
    sheet_name, cell = statement.locator.split("!")
    workbook = load_workbook(io.BytesIO(GENERATED.files["sheet.xlsx"]))
    assert workbook[sheet_name][cell].value == "0.12 ha"


def test_email_body_contains_the_value_and_fixed_headers() -> None:
    (statement,) = statements("mail")
    message = email.message_from_bytes(GENERATED.files["mail.eml"], policy=email_policy)
    assert statement.locator == "body"
    assert "02/05/2019" in message.get_content()
    assert message["Subject"] == "Tableau"
    assert "2022" in message["Date"]


def test_scan_keeps_page_count_and_has_no_text_layer() -> None:
    scan = PdfReader(io.BytesIO(GENERATED.files["scan.pdf"]))
    source = build(
        replace(SPEC, documents=tuple(replace(d, scanned=False) for d in SPEC.documents)),
        SCHEMA,
        TEMPLATES,
        format_value,
        FILLER,
    )
    assert len(scan.pages) == len(PdfReader(io.BytesIO(source.files["scan.pdf"])).pages)
    assert all(page.extract_text().strip() == "" for page in scan.pages)
    assert statements("scan")[0].locator == "p1"


def test_file_hashes_in_the_manifest_match_the_files() -> None:
    import hashlib

    for file in GENERATED.manifest.files:
        assert hashlib.sha256(GENERATED.files[file.filename]).hexdigest() == file.sha256


def test_write_puts_files_and_a_readable_manifest_on_disk(tmp_path: Path) -> None:
    write(GENERATED, tmp_path)
    assert (
        load_manifest((tmp_path / MANIFEST_NAME).read_text(encoding="utf-8")) == GENERATED.manifest
    )
    assert (tmp_path / "sheet.xlsx").read_bytes() == GENERATED.files["sheet.xlsx"]


def test_invalid_spec_is_refused() -> None:
    with pytest.raises(GeneratorError, match="invalid spec"):
        generate(replace(SPEC, traps=()))


def test_buried_statement_too_early_fails_the_build() -> None:
    with pytest.raises(GeneratorError, match="buried"):
        generate(templates={**TEMPLATES, "long_report": letter})


def test_template_cannot_drop_or_duplicate_a_statement() -> None:
    def forgetful(plan: DocumentPlan, rng: random.Random) -> Body:
        return Body("Empty", (Paragraph("Nothing here."),))

    def doubling(plan: DocumentPlan, rng: random.Random) -> Body:
        return Body("Twice", tuple(Paragraph("{} and {}", (s, s)) for s in plan.states))

    for template in (forgetful, doubling):
        with pytest.raises(GeneratorError, match="exactly once"):
            generate(templates={**TEMPLATES, "table": template})


def test_slot_count_must_match_statement_count() -> None:
    def wrong(plan: DocumentPlan, rng: random.Random) -> Body:
        return Body("Bad", (Paragraph("No slot at all.", plan.states),))

    with pytest.raises(GeneratorError, match="slots"):
        generate(templates={**TEMPLATES, "table": wrong})


@pytest.mark.parametrize(
    "broken",
    [
        replace(SPEC.documents[3], source="missing"),
        replace(SPEC.documents[3], format="docx"),
        replace(SPEC.documents[3], scanned=True),
    ],
)
def test_unknown_template_format_or_scanned_spreadsheet_fails(broken: DocumentPlan) -> None:
    documents = tuple(broken if d.doc_id == broken.doc_id else d for d in SPEC.documents)
    with pytest.raises(GeneratorError):
        generate(replace(SPEC, documents=documents))
