import asyncio
import datetime as dt
import random
from decimal import Decimal
from pathlib import Path

import pytest

from haussmann.coretypes.values import AttributeDef, FactKey, Quantity, Value, ValueKind
from haussmann.docparse.cards import Description, DocumentCard, build_cards
from haussmann.docparse.elements import (
    Element,
    UnsupportedFile,
    cells,
    parse_file,
    parse_folder,
    transcribe,
)
from haussmann.evalkit.documents import Body, Filler, Paragraph, Table
from haussmann.evalkit.generator import Generated, build, write
from haussmann.evalkit.groundtruth import (
    DocumentPlan,
    GoldFact,
    PlannedStatement,
    ScenarioSpec,
    Split,
    StatementKind,
)

AREA = FactKey("site", "area")
SCHEMA = {"area": AttributeDef("area", ValueKind.QUANTITY, "m2")}
STATED = PlannedStatement(AREA, Quantity(Decimal("310"), "m2"), StatementKind.SUPPORTS)


def template(plan: DocumentPlan, rng: random.Random) -> Body:
    table = Table(("Poste", "Valeur"), (("Surface", STATED),))
    return Body("Relevé général", (Paragraph("Première ligne."), Filler(40), table))


def formatted(value: Value, attribute: AttributeDef) -> str:
    return f"{value.amount} m²" if isinstance(value, Quantity) else str(value)


def generated() -> Generated:
    def plan(doc_id: str, fmt: str, scanned: bool = False) -> DocumentPlan:
        return DocumentPlan(doc_id, "t", fmt, dt.date(2024, 5, 6), 1, scanned, (STATED,))

    spec = ScenarioSpec(
        "s",
        Split.DEV,
        1,
        (GoldFact(AREA, STATED.value),),
        (
            plan("texte", "pdf"),
            plan("scan", "pdf", True),
            plan("feuille", "xlsx"),
            plan("mel", "eml"),
        ),
        (),
    )
    filler = ["Un paragraphe de remplissage assez long pour occuper la page. " * 6]
    return build(spec, SCHEMA, {"t": template}, formatted, filler)


FILES = generated().files


def test_text_pdf_gives_one_element_per_page_with_its_locator() -> None:
    elements = parse_file("texte.pdf", FILES["texte.pdf"])
    assert len(elements) >= 2
    assert [e.locator for e in elements] == [f"p{n}" for n in range(1, len(elements) + 1)]
    assert all(e.doc_id == "texte" and e.image is None and e.text for e in elements)
    assert "Relevé général" in elements[0].text
    assert any("310 m²" in e.text for e in elements)


def test_scanned_pdf_gives_image_only_elements() -> None:
    elements = parse_file("scan.pdf", FILES["scan.pdf"])
    assert len(elements) == len(parse_file("texte.pdf", FILES["texte.pdf"]))
    assert all(e.text == "" and e.image is not None for e in elements)
    assert all(e.image is not None and e.image.startswith(b"\xff\xd8") for e in elements)


def test_spreadsheet_gives_one_element_per_sheet_with_cell_references() -> None:
    (sheet,) = parse_file("feuille.xlsx", FILES["feuille.xlsx"])
    assert (sheet.doc_id, sheet.locator) == ("feuille", "Sheet1")
    assert "[Sheet1!A1] Relevé général" in sheet.text
    assert any(line.endswith("] 310 m²") for line in sheet.text.splitlines())


def test_email_gives_subject_date_and_body() -> None:
    (mail,) = parse_file("mel.eml", FILES["mel.eml"])
    assert mail.locator == "body"
    assert mail.text.startswith("Objet : Relevé général\nDate : ")
    assert "2024" in mail.text and "Première ligne." in mail.text


def test_unknown_extension_is_refused() -> None:
    with pytest.raises(UnsupportedFile):
        parse_file("plan.dwg", b"")


def test_parse_folder_reads_in_name_order_and_skips_named_files(tmp_path: Path) -> None:
    write(generated(), tmp_path)
    elements = parse_folder(tmp_path, skip={"manifest.json"})
    assert list(dict.fromkeys(e.doc_id for e in elements)) == ["feuille", "mel", "scan", "texte"]
    with pytest.raises(UnsupportedFile):
        parse_folder(tmp_path)


def test_transcribe_fills_only_image_elements() -> None:
    seen: list[bytes] = []

    async def reader(image: bytes) -> str:
        seen.append(image)
        return f"lu {len(seen)}"

    elements = (
        Element("a", "p1", "déjà du texte"),
        Element("b", "p1", "", b"image-1"),
        Element("b", "p2", "", b"image-2"),
    )
    done = asyncio.run(transcribe(elements, reader))
    assert seen == [b"image-1", b"image-2"]
    assert done == (
        Element("a", "p1", "déjà du texte"),
        Element("b", "p1", "lu 1"),
        Element("b", "p2", "lu 2"),
    )


def test_cards_describe_each_document_once_from_its_start() -> None:
    heads: list[str] = []

    async def describe(head: str) -> Description:
        heads.append(head)
        kind = "notice" if "Avis" in head else "mystery"
        return Description(kind, dt.date(2025, 1, 2) if kind == "notice" else None)

    elements = (
        Element("a", "p1", "Avis officiel"),
        Element("a", "p2", "suite de l'avis"),
        Element("b", "body", "x" * 5000),
    )
    cards = asyncio.run(build_cards(elements, describe, {"notice": 3}))
    assert cards == (
        DocumentCard("a", "notice", dt.date(2025, 1, 2), 3),
        DocumentCard("b", "mystery", None, 0),
    )
    assert heads[0] == "Avis officiel\nsuite de l'avis"
    assert len(heads[1]) == 1500


def test_each_element_says_what_kind_of_file_it_was_read_from() -> None:
    forms = {name: {e.form for e in parse_file(name, data)} for name, data in FILES.items()}
    assert forms["mel.eml"] == {"eml"} and forms["feuille.xlsx"] == {"xlsx"}
    assert all(form == {"pdf"} for name, form in forms.items() if name.endswith(".pdf"))


def test_cells_lists_each_cell_of_a_sheet_and_nothing_of_a_page() -> None:
    assert cells("[Sheet1!A7] Logements\n[Sheet1!B7] 384 m²") == (
        ("Sheet1!A7", "Logements"),
        ("Sheet1!B7", "384 m²"),
    )
    assert cells("La hauteur maximale est de 9 m.") == ()


def test_a_type_the_caller_knows_replaces_the_described_one_and_keeps_its_date() -> None:
    async def describe(head: str) -> Description:
        return Description("notice", dt.date(2025, 1, 2))

    elements = (Element("a", "p1", "Avis"), Element("b", "body", "Bonjour"))
    cards = asyncio.run(build_cards(elements, describe, {"notice": 3, "mail": 1}, {"b": "mail"}))
    assert cards == (
        DocumentCard("a", "notice", dt.date(2025, 1, 2), 3),
        DocumentCard("b", "mail", dt.date(2025, 1, 2), 1),
    )
