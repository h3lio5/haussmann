"""Regression cases: values an expert set, which every later engine is checked against."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from haussmann.coretypes.values import FactKey, Schema, Value, normalize, within_tolerance
from haussmann.ledger.codec import decode_value, encode_value


class Standing(StrEnum):
    """A held case passed when last checked and must keep passing; an open one did not."""

    HELD = "held"
    OPEN = "open"


@dataclass(frozen=True, slots=True)
class Case:
    scenario_id: str
    sample: int
    key: FactKey
    expected: Value
    reason: str
    author: str
    standing: Standing = Standing.OPEN


def passes(case: Case, settled: Value | None, schema: Schema) -> bool:
    """Does the value a run settled on match the case, within the attribute's tolerance?"""
    attribute = schema[case.key.attribute]
    expected = normalize(case.expected, attribute)
    found = normalize(settled, attribute) if settled is not None else None
    if expected is None or found is None:
        return False
    return within_tolerance(found, expected, attribute.tolerance)


def regressions(cases: Sequence[Case], passing: Sequence[bool]) -> list[Case]:
    """The held cases that no longer pass."""
    return [
        case
        for case, ok in zip(cases, passing, strict=True)
        if case.standing is Standing.HELD and not ok
    ]


def restand(cases: Sequence[Case], passing: Sequence[bool]) -> list[Case]:
    """Each case with the standing its latest check gives it."""
    return [
        Case(
            case.scenario_id,
            case.sample,
            case.key,
            case.expected,
            case.reason,
            case.author,
            Standing.HELD if ok else Standing.OPEN,
        )
        for case, ok in zip(cases, passing, strict=True)
    ]


def dump_cases(cases: Sequence[Case]) -> str:
    rows = [
        {
            "scenario": case.scenario_id,
            "sample": case.sample,
            "subject": case.key.subject,
            "attribute": case.key.attribute,
            "expected": encode_value(case.expected),
            "reason": case.reason,
            "author": case.author,
            "standing": case.standing.value,
        }
        for case in cases
    ]
    return json.dumps(rows, ensure_ascii=False, indent=2) + "\n"


def load_cases(text: str) -> list[Case]:
    return [
        Case(
            row["scenario"],
            row["sample"],
            FactKey(row["subject"], row["attribute"]),
            decode_value(row["expected"]),
            row["reason"],
            row["author"],
            Standing(row["standing"]),
        )
        for row in json.loads(text)
    ]
