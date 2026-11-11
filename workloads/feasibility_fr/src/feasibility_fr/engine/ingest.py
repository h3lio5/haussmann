"""Ingest for this workload: the model-backed functions `docparse` needs, and one entry point."""

import datetime as dt
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ValidationError

from feasibility_fr.engine.documents import DOCUMENT_AUTHORITY, OTHER
from haussmann.docparse.cards import Describer, Description, DocumentCard, build_cards
from haussmann.docparse.elements import Element, Transcriber, parse_folder, transcribe
from haussmann.llmkit.client import LLMClient, Message, Request

TRANSCRIBE = (
    "Transcris fidèlement tout le texte de cette page numérisée, ligne par ligne, "
    "sans commentaire, sans correction et sans rien ajouter."
)
TRANSCRIPTION_MAX_TOKENS = 3000

DESCRIBE = (
    "You are given the beginning of a document from a French real-estate file. "
    'Return its type from the allowed list ("other" if none fits) and the date the document '
    "was drawn up as YYYY-MM-DD, or an empty string if it states none."
)
DESCRIPTION_MAX_TOKENS = 200


def transcriber(client: LLMClient, model: str) -> Transcriber:
    async def transcribe_image(image: bytes) -> str:
        request = Request(
            model=model,
            messages=(Message("user", TRANSCRIBE, images=(image,)),),
            max_tokens=TRANSCRIPTION_MAX_TOKENS,
            temperature=0.0,
        )
        return (await client.complete(request)).text

    return transcribe_image


class _DescriptionWire(BaseModel):
    type: str
    date: str


_DESCRIPTION_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": [*DOCUMENT_AUTHORITY, OTHER]},
        "date": {"type": "string"},
    },
    "required": ["type", "date"],
    "additionalProperties": False,
}


def read_description(text: str) -> Description:
    """An answer that cannot be read describes nothing: type "other", no date."""
    try:
        wire = _DescriptionWire.model_validate_json(text)
    except ValidationError:
        return Description(OTHER, None)
    try:
        date = dt.date.fromisoformat(wire.date.strip())
    except ValueError:
        date = None
    return Description(wire.type, date)


def describer(client: LLMClient, model: str) -> Describer:
    async def describe(head: str) -> Description:
        request = Request(
            model=model,
            messages=(Message("system", DESCRIBE), Message("user", head)),
            max_tokens=DESCRIPTION_MAX_TOKENS,
            temperature=0.0,
            output_schema=_DESCRIPTION_SCHEMA,
        )
        return read_description((await client.complete(request)).text)

    return describe


@dataclass(frozen=True, slots=True)
class Ingested:
    elements: tuple[Element, ...]
    cards: tuple[DocumentCard, ...]


async def ingest(
    folder: Path, client: LLMClient, model: str, skip: Collection[str] = ()
) -> Ingested:
    """Parse every file, transcribe scanned pages, and describe each document."""
    elements = await transcribe(parse_folder(folder, skip), transcriber(client, model))
    cards = await build_cards(elements, describer(client, model), DOCUMENT_AUTHORITY)
    return Ingested(elements, cards)
