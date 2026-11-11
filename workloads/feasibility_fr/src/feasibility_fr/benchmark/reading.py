"""Turn a scenario's files into pages of text. Shared by every system under test."""

import email
import io
from dataclasses import dataclass
from email.policy import default as email_policy
from pathlib import Path

from openpyxl import load_workbook
from pypdf import PdfReader

from haussmann.evalkit.generator import MANIFEST_NAME
from haussmann.llmkit.client import LLMClient, Message, Request

TRANSCRIBE = (
    "Transcris fidèlement tout le texte de cette page numérisée, ligne par ligne, "
    "sans commentaire, sans correction et sans rien ajouter."
)
TRANSCRIPTION_MAX_TOKENS = 3000


@dataclass(frozen=True, slots=True)
class RawPage:
    """A page as found on disk. `image` is set when the page has no text of its own."""

    doc_id: str
    locator: str
    text: str
    image: bytes | None = None


@dataclass(frozen=True, slots=True)
class Page:
    doc_id: str
    locator: str
    text: str


def scan_folder(folder: Path) -> tuple[RawPage, ...]:
    """Read every file except the manifest, without calling a model."""
    pages: list[RawPage] = []
    for path in sorted(folder.iterdir()):
        if path.name == MANIFEST_NAME:
            continue
        data = path.read_bytes()
        if path.suffix == ".pdf":
            pages.extend(_pdf(path.stem, data))
        elif path.suffix == ".xlsx":
            pages.extend(_xlsx(path.stem, data))
        elif path.suffix == ".eml":
            pages.append(_eml(path.stem, data))
        else:
            raise ValueError(f"unsupported file type: {path.name}")
    return tuple(pages)


async def read_folder(folder: Path, client: LLMClient, model: str) -> tuple[Page, ...]:
    """Pages with text taken as they are; image-only pages transcribed by one call each."""
    pages: list[Page] = []
    for raw in scan_folder(folder):
        text = raw.text
        if raw.image is not None:
            request = Request(
                model=model,
                messages=(Message("user", TRANSCRIBE, images=(raw.image,)),),
                max_tokens=TRANSCRIPTION_MAX_TOKENS,
                temperature=0.0,
            )
            text = (await client.complete(request)).text
        pages.append(Page(raw.doc_id, raw.locator, text))
    return tuple(pages)


def _pdf(doc_id: str, data: bytes) -> list[RawPage]:
    pages: list[RawPage] = []
    for number, page in enumerate(PdfReader(io.BytesIO(data)).pages, start=1):
        text = (page.extract_text() or "").strip()
        image = None
        if not text:
            images = list(page.images)
            if not images:
                raise ValueError(f"{doc_id} page {number} has neither text nor an image")
            image = images[0].data
        pages.append(RawPage(doc_id, f"p{number}", text, image))
    return pages


def _xlsx(doc_id: str, data: bytes) -> list[RawPage]:
    pages: list[RawPage] = []
    workbook = load_workbook(io.BytesIO(data), read_only=True)
    for sheet in workbook.worksheets:
        lines = [
            f"[{sheet.title}!{cell.coordinate}] {cell.value}"
            for row in sheet.iter_rows()
            for cell in row
            if cell.value is not None
        ]
        pages.append(RawPage(doc_id, sheet.title, "\n".join(lines)))
    return pages


def _eml(doc_id: str, data: bytes) -> RawPage:
    message = email.message_from_bytes(data, policy=email_policy)
    body = message.get_body(preferencelist=("plain",))
    text = body.get_content() if body is not None else ""
    return RawPage(
        doc_id, "body", f"Objet : {message['Subject']}\nDate : {message['Date']}\n{text}"
    )
