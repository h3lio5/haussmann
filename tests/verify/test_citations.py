import datetime as dt
from decimal import Decimal

import pytest

from haussmann.coretypes.values import FactKey, Quantity, Value
from haussmann.docparse.elements import Element
from haussmann.ledger.ledger import Citation, Fact
from haussmann.verify.citations import (
    canonical,
    check_fact,
    numbers_in,
    passage,
    value_appears,
)

NBSP = chr(0xA0)
ELEMENTS = (
    Element("plu", "p1", "Dispositions générales."),
    Element("plu", "p8", "La hauteur maximale des constructions est fixée à 9 m."),
    Element("cadastre", "p1", f"Contenance : 0,1138 ha. Prix : 245{NBSP}000 €."),
    Element(
        "tableau", "Sheet1", "[Sheet1!A6] Rez-de-chaussée\n[Sheet1!B6] 115 m²\n[Sheet1!B9] 330 m²"
    ),
    Element(
        "avis", "p1", "Document établi le 28 septembre 2026. Le bien appartient à la Ville de Metz."
    ),
)
HEIGHT = FactKey("site", "height")


def no_renderings(value: Value) -> list[str]:
    return []


def french_dates(value: Value) -> list[str]:
    return ["28 septembre 2026"] if value == dt.date(2026, 9, 28) else []


def fact(value: Value, *citations: Citation) -> Fact:
    return Fact("f1", HEIGHT, value, citations, "extracted", "finder", 1)


def q(amount: str, unit: str = "m") -> Quantity:
    return Quantity(Decimal(amount), unit)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("fixée à 9 m", {"9"}),
        ("0,1138 ha et 12.5 m", {"0.1138", "12.5"}),
        ("245 000 € puis 1 234 567,5", {"245000", "1234567.5"}),
        (f"245{NBSP}000 €", {"245000"}),
        ("1.200 m²", {"1.200", "1200"}),
        ("page 3 sur 12", {"3", "12"}),
        ("2026\n150 000", {"2026", "150000"}),
        ("aucun chiffre", set[str]()),
    ],
)
def test_numbers_are_read_with_french_grouping_and_decimal_marks(
    text: str, expected: set[str]
) -> None:
    assert numbers_in(text) == {Decimal(n) for n in expected}


def test_canonical_text_ignores_case_accents_and_punctuation() -> None:
    assert canonical("  Société  Générale d'Études. ") == "societe generale d etudes"


def test_passage_finds_a_page_a_cell_a_whole_document_or_nothing() -> None:
    assert passage(ELEMENTS, Citation("plu", "p8")) == ELEMENTS[1].text
    assert passage(ELEMENTS, Citation("tableau", "Sheet1!B9")) == "330 m²"
    assert passage(ELEMENTS, Citation("tableau", "Sheet1")) == ELEMENTS[3].text
    assert (
        passage(ELEMENTS, Citation("plu", None)) == "Dispositions générales.\n" + ELEMENTS[1].text
    )
    assert passage(ELEMENTS, Citation("plu", "p9")) is None
    assert passage(ELEMENTS, Citation("tableau", "Sheet1!Z99")) is None
    assert passage(ELEMENTS, Citation("ghost", "p1")) is None


@pytest.mark.parametrize(
    ("value", "text", "appears"),
    [
        (q("9"), "fixée à 9 m", True),
        (q("9"), "fixée à 19 m", False),
        (q("0.1138", "ha"), "Contenance : 0,1138 ha", True),
        (q("245000", "EUR"), "Prix : 245 000 €", True),
        (q("1138", "m2"), "Contenance : 0,1138 ha", False),
        ("Ville de Metz", "appartient à la VILLE DE METZ.", True),
        ("Ville de Nancy", "appartient à la Ville de Metz.", False),
        ("", "n'importe quoi", False),
        (dt.date(2026, 9, 28), "signé le 2026-09-28", True),
        (dt.date(2026, 9, 28), "signé le 28/09/2026", True),
        (dt.date(2026, 9, 28), "signé le 28 septembre 2026", False),
    ],
)
def test_value_appears(value: Value, text: str, appears: bool) -> None:
    assert value_appears(value, text) is appears


def test_a_rendering_supplied_by_the_caller_counts() -> None:
    assert value_appears(dt.date(2026, 9, 28), "établi le 28 Septembre 2026", ["28 septembre 2026"])


def test_a_fact_stated_at_its_cited_source_passes() -> None:
    assert check_fact(fact(q("9"), Citation("plu", "p8")), ELEMENTS, no_renderings) is None
    assert (
        check_fact(fact(q("330", "m2"), Citation("tableau", "Sheet1!B9")), ELEMENTS, no_renderings)
        is None
    )
    dated = fact(
        dt.date(2026, 9, 28), Citation("avis", "p1", "Document établi le 28 septembre 2026")
    )
    assert check_fact(dated, ELEMENTS, french_dates) is None


@pytest.mark.parametrize(
    ("candidate", "reason"),
    [
        (fact(q("9")), "cites no source"),
        (fact(q("9"), Citation("plu", "p9")), "plu has no p9"),
        (fact(q("9"), Citation("ghost", None)), "ghost has no the document"),
        (fact(q("12"), Citation("plu", "p8")), "value is not stated in plu p8"),
        (fact(q("9"), Citation("plu", "p8", "une phrase inventée")), "quote is not in plu p8"),
        (
            fact(q("9"), Citation("plu", "p8", "La hauteur maximale")),
            "value is not stated in plu p8",
        ),
        (fact(q("115", "m2"), Citation("tableau", "Sheet1!B9")), "value is not stated"),
        (
            fact(q("9"), Citation("plu", "p8"), Citation("plu", "p1")),
            "value is not stated in plu p1",
        ),
    ],
)
def test_a_fact_not_stated_at_its_cited_source_fails_with_the_reason(
    candidate: Fact, reason: str
) -> None:
    found = check_fact(candidate, ELEMENTS, no_renderings)
    assert found is not None and reason in found
