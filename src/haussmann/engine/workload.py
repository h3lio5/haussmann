"""What a domain supplies to the engine: its declarations, its language and its wording."""

import datetime as dt
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from haussmann.buildkit.spec import Spec
from haussmann.coretypes.values import AttributeDef, FactKey, Quantity, Schema, Value, ValueKind

OTHER = "other"
ISSUE = "issue"
OPEN = "open"


@dataclass(frozen=True, slots=True)
class RequiredFact:
    """A fact to establish.

    `sum_of` names its parts when it is declared as a total. `depends_on` names the fact
    that decides which stated value applies, when documents state one value per case.
    """

    key: FactKey
    text: str
    sum_of: tuple[FactKey, ...] = ()
    depends_on: FactKey | None = None


@dataclass(frozen=True, slots=True)
class CaseForm:
    """How a case of a deciding fact is written, once lower-cased and without punctuation."""

    pattern: re.Pattern[str]
    example: str


@dataclass(frozen=True, slots=True)
class DocumentTypes:
    """`authority` ranks each type in a disagreement. `type_of_form` names the type that a
    file form decides by itself."""

    authority: Mapping[str, int]
    type_of_form: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class DateRules:
    """`valid_for_months` gives, by attribute, how long a dated document holds. `end_dates`
    are the attributes whose date is an end."""

    valid_for_months: Mapping[str, int]
    end_dates: frozenset[str]


@dataclass(frozen=True, slots=True)
class Language:
    """How the documents and the deliverable write values.

    `unit_names` maps a unit as written to its name in the schema. `reasons` maps a settling
    reason to how it is printed; `expired` prints an expiry from `{months}` and `{date}`.
    """

    format_date: Callable[[dt.date], str]
    format_value: Callable[[Value, AttributeDef], str]
    parse_date: Callable[[str], dt.date | None]
    unit_names: Mapping[str, str]
    reasons: Mapping[str, str]
    expired: str


@dataclass(frozen=True, slots=True)
class Prompts:
    """Every instruction text a model is sent. The engine owns the shape of a request; the
    words are here.

    `tools` holds the description of each finder tool under its name and of each parameter
    under `tool.parameter`. `the_subject` is how a tool's refusal names the main subject.
    Texts with braces are filled by name: `writer_section` with `{title}`,
    `writer_guidance` with `{guidance}`.
    """

    transcribe: str
    describe: str
    finder: str
    cross_check: str
    by_case: str
    applies_to: str
    second_pass: str
    tools: Mapping[str, str]
    the_subject: str
    writer: str
    writer_version: str
    writer_section: str
    writer_guidance: str
    writer_facts: str
    writer_flagged: str
    writer_refused: str
    revise: str
    revise_version: str
    revise_current: str
    revise_comment: str


@dataclass(frozen=True, slots=True)
class Deliverable:
    """The sections of the deliverable and the fixed wording printed in it.

    `open_question` is filled with `{label}`; `issue` with `{label}` and `{parts}`, the
    parts joined by `separator`; `stated` with `{values}`; `kept` with `{value}` and
    `{reason}`; `review_date` with `{date}`.
    """

    spec: Spec
    title: str
    review_date: str
    flag_mark: str
    nothing: str
    open_question: str
    issue: str
    separator: str
    stated: str
    undecided: str
    kept: str


@dataclass(frozen=True, slots=True)
class Workload:
    """`main_subject` is the subject whose facts the planner groups in chunks; the facts of
    every other subject are grouped by attribute."""

    schema: Schema
    main_subject: str
    documents: DocumentTypes
    dates: DateRules
    cases: Mapping[FactKey, CaseForm]
    language: Language
    prompts: Prompts
    deliverable: Deliverable


def read_value(value: str, unit: str, attribute: AttributeDef | None, language: Language) -> Value:
    """Read a reported value as its attribute's kind; an unreadable value stays text."""
    if attribute is None or attribute.kind is ValueKind.TEXT:
        return value
    if attribute.kind is ValueKind.DATE:
        return language.parse_date(value) or value
    cleaned = "".join(value.split()).replace(",", ".")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        return value
    if not amount.is_finite():
        return value
    return Quantity(amount, unit or attribute.canonical_unit or "")
