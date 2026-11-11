"""The question list a system receives and the answer it must return."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, ValidationError

from feasibility_fr.benchmark.reading import Page
from feasibility_fr.benchmark.templates import ROW_LABELS, Wording
from haussmann.evalkit.groundtruth import (
    AttributeDef,
    FactKey,
    Quantity,
    Schema,
    Value,
    ValueKind,
)
from haussmann.evalkit.scorer import Citation, ReportedFact, Submission

INSTRUCTIONS = """\
You are reviewing the documents of a French real-estate file. Establish each fact in the \
question list from the documents only.

Rules:
- Documents may contradict each other, be out of date, or concern a different property. Prefer \
official documents over commercial ones, and a later amendment over the text it amends.
- Set "flagged" to true when documents disagree about the fact, when a stated total does not \
match its parts, or when a date is expired or cannot be right. Cite every document involved.
- If the documents do not establish a fact, do not guess: leave it out of "facts" and list it \
in "open_questions".
- Report each fact at most once.
- Each document states the date it was drawn up. Use those dates to tell which document is \
later, and the review date to tell whether something has expired.

Formats:
- A quantity: "value" is a plain decimal number with a dot and no thousands separator, and \
"unit" is one of the allowed units. Answer in the unit the question asks for, converting if \
needed. A total is the sum of its parts.
- A date: "value" is YYYY-MM-DD and "unit" is empty.
- Text: "value" is copied exactly as written in the document and "unit" is empty.
- A citation gives the "doc_id" from the page marker and a "locator": the page as "p3", a \
spreadsheet cell as "Sheet1!B6", or "body" for an email.
"""


@dataclass(frozen=True, slots=True)
class Question:
    key: FactKey
    text: str


def questions(keys: Sequence[FactKey], wording: Wording) -> tuple[Question, ...]:
    """The fact keys with a French description, and no values."""
    asked: list[Question] = []
    for key in keys:
        label = wording.labels.get(key.subject, "Le bien objet du dossier")
        asked.append(Question(key, f"{label} - {ROW_LABELS[key.attribute]}"))
    return tuple(asked)


def render_questions(asked: Sequence[Question], schema: Schema) -> str:
    lines: list[str] = []
    for question in asked:
        attribute = schema[question.key.attribute]
        expected = attribute.kind.value
        if attribute.canonical_unit:
            expected += f", in {attribute.canonical_unit}"
        lines.append(
            f'- subject="{question.key.subject}" attribute="{question.key.attribute}" '
            f"({expected}): {question.text}"
        )
    return "\n".join(lines)


def render_pages(pages: Sequence[Page]) -> str:
    return "\n\n".join(
        f"=== doc_id: {page.doc_id} | locator: {page.locator} ===\n{page.text}" for page in pages
    )


def answer_schema(schema: Schema) -> dict[str, object]:
    units = sorted(
        {
            unit
            for attribute in schema.values()
            for unit in (attribute.canonical_unit, *attribute.units)
            if unit
        }
    )
    text = {"type": "string"}
    key = {"subject": text, "attribute": {"type": "string", "enum": sorted(schema)}}

    def strict(properties: dict[str, object]) -> dict[str, object]:
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }

    fact = strict(
        {
            **key,
            "value": text,
            "unit": {"type": "string", "enum": ["", *units]},
            "citations": {"type": "array", "items": strict({"doc_id": text, "locator": text})},
            "flagged": {"type": "boolean"},
        }
    )
    return strict(
        {
            "facts": {"type": "array", "items": fact},
            "open_questions": {"type": "array", "items": strict(dict(key))},
        }
    )


class _Wire(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _CitationWire(_Wire):
    doc_id: str
    locator: str


class _KeyWire(_Wire):
    subject: str
    attribute: str


class _FactWire(_KeyWire):
    value: str
    unit: str
    citations: list[_CitationWire]
    flagged: bool


class _AnswerWire(_Wire):
    facts: list[_FactWire]
    open_questions: list[_KeyWire]


class InvalidAnswer(ValueError):
    pass


def read_value(value: str, unit: str, attribute: AttributeDef | None) -> Value:
    """Read a reported value as its attribute's kind; an unreadable value stays text."""
    if attribute is None or attribute.kind is ValueKind.TEXT:
        return value
    if attribute.kind is ValueKind.DATE:
        try:
            return dt.date.fromisoformat(value.strip())
        except ValueError:
            return value
    cleaned = "".join(value.split()).replace(",", ".")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        return value
    if not amount.is_finite():
        return value
    return Quantity(amount, unit or attribute.canonical_unit or "")


def parse_answer(text: str, schema: Schema) -> Submission:
    try:
        wire = _AnswerWire.model_validate_json(text)
    except ValidationError as error:
        raise InvalidAnswer(f"answer does not match the expected shape: {error}") from error
    return Submission(
        facts=tuple(
            ReportedFact(
                key=FactKey(fact.subject, fact.attribute),
                value=read_value(fact.value, fact.unit, schema.get(fact.attribute)),
                citations=tuple(Citation(c.doc_id, c.locator or None) for c in fact.citations),
                flagged=fact.flagged,
            )
            for fact in wire.facts
        ),
        open_questions=tuple(FactKey(k.subject, k.attribute) for k in wire.open_questions),
    )
