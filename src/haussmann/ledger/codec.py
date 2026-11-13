"""Ledger entries as JSON, for storage. Every value carries a tag that names its type."""

import datetime as dt
from decimal import Decimal
from typing import Any, cast

from haussmann.coretypes.values import FactKey, Quantity, Value
from haussmann.ledger.ledger import (
    Ask,
    Assess,
    Citation,
    Condition,
    Entry,
    Flag,
    NewConflict,
    NewFact,
    Record,
    Resolve,
    Status,
)

type Json = dict[str, Any]


def _key(key: FactKey) -> Json:
    return {"subject": key.subject, "attribute": key.attribute}


def _read_key(data: Json) -> FactKey:
    return FactKey(data["subject"], data["attribute"])


def encode_value(value: Value) -> Json:
    if isinstance(value, Quantity):
        return {"quantity": {"amount": str(value.amount), "unit": value.unit}}
    if isinstance(value, dt.date):
        return {"date": value.isoformat()}
    return {"text": value}


def decode_value(data: Json) -> Value:
    if "quantity" in data:
        return Quantity(Decimal(data["quantity"]["amount"]), data["quantity"]["unit"])
    if "date" in data:
        return dt.date.fromisoformat(data["date"])
    return cast(str, data["text"])


def encode_record(record: Record) -> Json:
    match record:
        case NewFact():
            condition = record.holds_when
            return {
                "type": "fact",
                "key": _key(record.key),
                "value": encode_value(record.value),
                "citations": [
                    {"doc_id": c.doc_id, "locator": c.locator, "quote": c.quote}
                    for c in record.citations
                ],
                "method": record.method,
                "holds_when": None
                if condition is None
                else {"key": _key(condition.key), "value": condition.value},
            }
        case Assess():
            return {
                "type": "assess",
                "fact_id": record.fact_id,
                "status": record.status.value,
                "reason": record.reason,
            }
        case NewConflict():
            return {
                "type": "conflict",
                "key": _key(record.key),
                "fact_ids": list(record.fact_ids),
                "kind": record.kind,
            }
        case Resolve():
            return {
                "type": "resolve",
                "conflict_id": record.conflict_id,
                "chosen": record.chosen,
                "reason": record.reason,
            }
        case Ask():
            return {"type": "ask", "key": _key(record.key), "reason": record.reason}
        case Flag():
            return {"type": "flag", "fact_id": record.fact_id, "reason": record.reason}


def decode_record(data: Json) -> Record:
    match data["type"]:
        case "fact":
            condition = data["holds_when"]
            return NewFact(
                _read_key(data["key"]),
                decode_value(data["value"]),
                tuple(Citation(c["doc_id"], c["locator"], c["quote"]) for c in data["citations"]),
                data["method"],
                None
                if condition is None
                else Condition(_read_key(condition["key"]), condition["value"]),
            )
        case "assess":
            return Assess(data["fact_id"], Status(data["status"]), data["reason"])
        case "conflict":
            return NewConflict(_read_key(data["key"]), tuple(data["fact_ids"]), data["kind"])
        case "resolve":
            return Resolve(data["conflict_id"], data["chosen"], data["reason"])
        case "ask":
            return Ask(_read_key(data["key"]), data["reason"])
        case "flag":
            return Flag(data["fact_id"], data["reason"])
        case other:
            raise ValueError(f"unknown record type {other!r}")


def encode_entry(entry: Entry) -> Json:
    return {
        "tx": entry.tx,
        "author": entry.author,
        "record": encode_record(entry.record),
        "assigned_id": entry.assigned_id,
    }


def decode_entry(data: Json) -> Entry:
    return Entry(data["tx"], data["author"], decode_record(data["record"]), data["assigned_id"])
