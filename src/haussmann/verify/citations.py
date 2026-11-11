"""The citation check: does the cited passage really state the value?"""

import datetime as dt
import re
import unicodedata
from collections.abc import Callable, Sequence
from decimal import Decimal

from haussmann.coretypes.values import Quantity, Value
from haussmann.docparse.elements import Element
from haussmann.ledger.ledger import Citation, Fact

type Renderings = Callable[[Value], Sequence[str]]

_NUMBER = re.compile(r"\d{1,3}(?:[^\S\r\n]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?")
_DOTTED_THOUSANDS = re.compile(r"\d{1,3}(?:\.\d{3})+")
_CELL = re.compile(r"^\[(?P<ref>[^\]]+)\] ?(?P<text>.*)$")


def canonical(text: str) -> str:
    """Lower case, no accents, no punctuation, single spaces."""
    decomposed = unicodedata.normalize("NFKD", text)
    kept = "".join(
        char if char.isalnum() else " " for char in decomposed if not unicodedata.combining(char)
    )
    return " ".join(kept.casefold().split())


def numbers_in(text: str) -> set[Decimal]:
    """Every number written in the text, reading a comma or a dot as the decimal mark.

    Digits grouped by spaces are one number. A number written like 1.200 is read both as
    one point two and as twelve hundred.
    """
    found: set[Decimal] = set()
    for match in _NUMBER.finditer(text):
        raw = "".join(match.group().split())
        found.add(Decimal(raw.replace(",", ".")))
        if _DOTTED_THOUSANDS.fullmatch(raw):
            found.add(Decimal(raw.replace(".", "")))
    return found


def passage(elements: Sequence[Element], citation: Citation) -> str | None:
    """The text a citation points at, or None when it points at nothing.

    Without a locator it is the whole document. A locator naming a cell of a sheet gives
    that cell's line.
    """
    of_document = [e for e in elements if e.doc_id == citation.doc_id]
    if not of_document:
        return None
    if citation.locator is None:
        return "\n".join(e.text for e in of_document)
    for element in of_document:
        if element.locator == citation.locator:
            return element.text
    for element in of_document:
        for line in element.text.splitlines():
            cell = _CELL.match(line)
            if cell is not None and cell.group("ref") == citation.locator:
                return cell.group("text")
    return None


def value_appears(value: Value, text: str, renderings: Sequence[str] = ()) -> bool:
    """Is the value written in the text, as a number, a date or the same words?"""
    plain = canonical(text)
    if any(canonical(rendering) in plain for rendering in renderings if canonical(rendering)):
        return True
    if isinstance(value, Quantity):
        return value.amount in numbers_in(text)
    if isinstance(value, dt.date):
        numeric = (value.isoformat(), value.strftime("%d/%m/%Y"), value.strftime("%d.%m.%Y"))
        return any(form in text for form in numeric)
    wanted = canonical(value)
    return bool(wanted) and wanted in plain


def check_citation(
    fact: Fact, citation: Citation, elements: Sequence[Element], renderings: Renderings
) -> str | None:
    """None when the citation holds, otherwise the reason it does not."""
    text = passage(elements, citation)
    if text is None:
        where = citation.locator or "the document"
        return f"{citation.doc_id} has no {where}"
    if citation.quote:
        if canonical(citation.quote) not in canonical(text):
            return f"the quote is not in {citation.doc_id} {citation.locator or ''}".strip()
        text = citation.quote
    if not value_appears(fact.value, text, renderings(fact.value)):
        return f"the value is not stated in {citation.doc_id} {citation.locator or ''}".strip()
    return None


def check_fact(fact: Fact, elements: Sequence[Element], renderings: Renderings) -> str | None:
    """None when every citation of the fact holds, otherwise the first reason one does not."""
    if not fact.citations:
        return "the fact cites no source"
    for citation in fact.citations:
        reason = check_citation(fact, citation, elements, renderings)
        if reason is not None:
            return reason
    return None
