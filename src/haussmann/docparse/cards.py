"""One card per document: what kind it is, when it was drawn up, how much it counts."""

import datetime as dt
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass

from haussmann.docparse.elements import Element

HEAD_CHARS = 1500
UNKNOWN_AUTHORITY = 0


@dataclass(frozen=True, slots=True)
class Description:
    type: str
    date: dt.date | None


@dataclass(frozen=True, slots=True)
class DocumentCard:
    """`authority` is the caller's ranking of `type`; higher wins a disagreement."""

    doc_id: str
    type: str
    date: dt.date | None
    authority: int


type Describer = Callable[[str], Awaitable[Description]]


async def build_cards(
    elements: Sequence[Element],
    describe: Describer,
    authority: Mapping[str, int],
    known: Mapping[str, str] | None = None,
) -> tuple[DocumentCard, ...]:
    """Describe each document from the start of its text, in first-seen order.

    `known` gives the type of the documents whose type the caller can tell without a
    model, by document id; the description is then used for the date only.
    """
    heads: dict[str, str] = {}
    for element in elements:
        seen = heads.get(element.doc_id, "")
        if len(seen) < HEAD_CHARS:
            heads[element.doc_id] = (seen + "\n" + element.text).strip()[:HEAD_CHARS]
    cards: list[DocumentCard] = []
    for doc_id, head in heads.items():
        found = await describe(head)
        kind = (known or {}).get(doc_id, found.type)
        rank = authority.get(kind, UNKNOWN_AUTHORITY)
        cards.append(DocumentCard(doc_id, kind, found.date, rank))
    return tuple(cards)
