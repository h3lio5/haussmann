import asyncio
import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest

from feasibility_fr.benchmark.render import FILES_DIR
from feasibility_fr.documents import COMMERCIAL, DOCUMENT_AUTHORITY, OFFICIAL, OTHER
from feasibility_fr.workload import WORKLOAD
from haussmann.docparse.cards import Description
from haussmann.docparse.elements import Element
from haussmann.engine.ingest import describe_documents, describer, ingest, read_description
from haussmann.evalkit.generator import MANIFEST_NAME
from haussmann.llmkit.client import Request, Response, Usage

METZ = Path(__file__).parent.parent / "benchmark_data" / "metz_vigny" / FILES_DIR


class Scripted:
    def __init__(self) -> None:
        self.requests: list[Request] = []

    async def complete(self, request: Request, *, sample: int = 0) -> Response:
        self.requests.append(request)
        if any(message.images for message in request.messages):
            text = "Note du notaire\nDocument établi le 18 avril 2025."
        elif "Certificat d'urbanisme" in request.messages[-1].text:
            text = json.dumps({"type": "planning_certificate", "date": "2023-03-14"})
        else:
            text = json.dumps({"type": "something_new", "date": ""})
        return Response(text, "stop", request.model, Usage(100, 10), 0.1)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"type": "lease", "date": "2021-09-01"}', Description("lease", dt.date(2021, 9, 1))),
        ('{"type": "email", "date": ""}', Description("email", None)),
        ('{"type": "email", "date": "1er mai"}', Description("email", None)),
        ("not json", Description(OTHER, None)),
        ('{"type": "lease"}', Description(OTHER, None)),
    ],
)
def test_description_is_read_leniently(text: str, expected: Description) -> None:
    assert read_description(text) == expected


def test_describer_constrains_the_type_to_the_workload_list() -> None:
    client = Scripted()
    describe = describer(WORKLOAD, client, "model-a")

    async def go() -> Description:
        return await describe("Certificat d'urbanisme d'information")

    found = asyncio.run(go())
    assert found == Description("planning_certificate", dt.date(2023, 3, 14))
    (request,) = client.requests
    schema: Any = request.output_schema
    allowed = schema["properties"]["type"]["enum"]
    assert set(allowed) == {*DOCUMENT_AUTHORITY, OTHER}
    assert request.temperature == 0.0


def test_ingest_gives_text_for_every_page_and_a_card_for_every_document() -> None:
    client = Scripted()
    result = asyncio.run(ingest(WORKLOAD, METZ, client, "model-a", skip={MANIFEST_NAME}))

    assert all(e.image is None and e.text for e in result.elements)
    documents = list(dict.fromkeys(e.doc_id for e in result.elements))
    assert [card.doc_id for card in result.cards] == documents
    by_id = {card.doc_id: card for card in result.cards}
    assert by_id["certificat_urbanisme"].type == "planning_certificate"
    assert by_id["certificat_urbanisme"].authority == OFFICIAL
    assert by_id["certificat_urbanisme"].date == dt.date(2023, 3, 14)
    assert by_id["plaquette"].authority == 0 and by_id["plaquette"].date is None

    transcriptions = [r for r in client.requests if r.messages[0].images]
    assert len(transcriptions) == 2
    assert len(client.requests) == 2 + len(documents)


def test_a_document_read_from_an_email_file_is_an_email_whatever_the_model_answers() -> None:
    class Mistaken:
        async def complete(self, request: Request, *, sample: int = 0) -> Response:
            text = json.dumps({"type": "sale_notice", "date": "2026-10-15"})
            return Response(text, "stop", request.model, Usage(100, 10), 0.1)

    elements = (
        Element("courriel", "body", "Objet : Cession\nLe bien est en vente.", form="eml"),
        Element("avis", "p1", "Avis de cession. Le bien est en vente.", form="pdf"),
    )
    mail, notice = asyncio.run(describe_documents(WORKLOAD, elements, Mistaken(), "model-a"))
    assert (mail.type, mail.date, mail.authority) == ("email", dt.date(2026, 10, 15), COMMERCIAL)
    assert (notice.type, notice.authority) == ("sale_notice", OFFICIAL)
