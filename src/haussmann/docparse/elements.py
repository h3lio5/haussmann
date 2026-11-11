"""Files to elements: the unit that is searched, read and cited."""

import email
import io
from collections.abc import Awaitable, Callable, Collection, Sequence
from dataclasses import dataclass, replace
from email.policy import default as email_policy
from pathlib import Path

from openpyxl import load_workbook
from pypdf import PdfReader


@dataclass(frozen=True, slots=True)
class Element:
    """A PDF page, a sheet or an email body. `image` is set when a page has no text."""

    doc_id: str
    locator: str
    text: str
    image: bytes | None = None


class UnsupportedFile(ValueError):
    pass


type Transcriber = Callable[[bytes], Awaitable[str]]


def parse_file(filename: str, data: bytes) -> tuple[Element, ...]:
    """The document id is the file name without its extension."""
    path = Path(filename)
    reader = _READERS.get(path.suffix.lower())
    if reader is None:
        raise UnsupportedFile(f"unsupported file type: {filename}")
    return tuple(reader(path.stem, data))


def parse_folder(folder: Path, skip: Collection[str] = ()) -> tuple[Element, ...]:
    """Every file in name order, except the names in `skip`."""
    elements: list[Element] = []
    for path in sorted(folder.iterdir()):
        if path.name not in skip:
            elements.extend(parse_file(path.name, path.read_bytes()))
    return tuple(elements)


async def transcribe(elements: Sequence[Element], transcriber: Transcriber) -> tuple[Element, ...]:
    """Give every image-only element its text; the others pass through unchanged."""
    done: list[Element] = []
    for element in elements:
        if element.image is None:
            done.append(element)
        else:
            done.append(replace(element, text=await transcriber(element.image), image=None))
    return tuple(done)


def _pdf(doc_id: str, data: bytes) -> list[Element]:
    elements: list[Element] = []
    for number, page in enumerate(PdfReader(io.BytesIO(data)).pages, start=1):
        text = (page.extract_text() or "").strip()
        image = None
        if not text:
            images = list(page.images)
            if not images:
                raise UnsupportedFile(f"{doc_id} page {number} has neither text nor an image")
            image = images[0].data
        elements.append(Element(doc_id, f"p{number}", text, image))
    return elements


def _xlsx(doc_id: str, data: bytes) -> list[Element]:
    elements: list[Element] = []
    workbook = load_workbook(io.BytesIO(data), read_only=True)
    for sheet in workbook.worksheets:
        lines = [
            f"[{sheet.title}!{cell.coordinate}] {cell.value}"
            for row in sheet.iter_rows()
            for cell in row
            if cell.value is not None
        ]
        elements.append(Element(doc_id, sheet.title, "\n".join(lines)))
    return elements


def _eml(doc_id: str, data: bytes) -> list[Element]:
    message = email.message_from_bytes(data, policy=email_policy)
    body = message.get_body(preferencelist=("plain",))
    text = body.get_content() if body is not None else ""
    header = f"Objet : {message['Subject']}\nDate : {message['Date']}\n"
    return [Element(doc_id, "body", header + text)]


_READERS: dict[str, Callable[[str, bytes], list[Element]]] = {
    ".pdf": _pdf,
    ".xlsx": _xlsx,
    ".eml": _eml,
}
