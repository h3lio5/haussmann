"""Ingest: the model-backed functions `docparse` needs, and one entry point."""

import datetime as dt
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ValidationError

from haussmann.docparse.cards import Describer, Description, DocumentCard, build_cards
from haussmann.docparse.elements import Element, Transcriber, parse_folder, transcribe
from haussmann.engine.workload import OTHER, Workload
from haussmann.llmkit.client import LLMClient, Message, Request

TRANSCRIPTION_MAX_TOKENS = 3000

DESCRIPTION_MAX_TOKENS = 200


def transcriber(client: LLMClient, model: str, prompt: str) -> Transcriber:
    async def transcribe_image(image: bytes) -> str:
        request = Request(
            model=model,
            messages=(Message("user", prompt, images=(image,)),),
            max_tokens=TRANSCRIPTION_MAX_TOKENS,
            temperature=0.0,
        )
        return (await client.complete(request)).text

    return transcribe_image


class _DescriptionWire(BaseModel):
    type: str
    date: str


def description_schema(types: Sequence[str]) -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": [*types, OTHER]},
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


def describer(workload: Workload, client: LLMClient, model: str) -> Describer:
    schema = description_schema(list(workload.documents.authority))

    async def describe(head: str) -> Description:
        request = Request(
            model=model,
            messages=(Message("system", workload.prompts.describe), Message("user", head)),
            max_tokens=DESCRIPTION_MAX_TOKENS,
            temperature=0.0,
            output_schema=schema,
        )
        return read_description((await client.complete(request)).text)

    return describe


async def describe_documents(
    workload: Workload, elements: Sequence[Element], client: LLMClient, model: str
) -> tuple[DocumentCard, ...]:
    """One card per document. A document whose file form decides its type, as an email's
    does, is typed by code; the model gives its date, and the type of every other one."""
    documents = workload.documents
    forms = documents.type_of_form
    known = {e.doc_id: forms[e.form] for e in elements if e.form in forms}
    return await build_cards(
        elements, describer(workload, client, model), documents.authority, known
    )


@dataclass(frozen=True, slots=True)
class Ingested:
    elements: tuple[Element, ...]
    cards: tuple[DocumentCard, ...]


async def ingest(
    workload: Workload, folder: Path, client: LLMClient, model: str, skip: Collection[str] = ()
) -> Ingested:
    """Parse every file, transcribe scanned pages, and describe each document."""
    elements = await transcribe(
        parse_folder(folder, skip), transcriber(client, model, workload.prompts.transcribe)
    )
    cards = await describe_documents(workload, elements, client, model)
    return Ingested(elements, cards)
