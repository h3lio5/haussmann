import asyncio
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from haussmann.llmkit.client import Message, Request, Response, Usage
from haussmann.llmkit.replay import ReplayClient, ReplayMiss, ReplayStore, request_key

REQUEST = Request(
    model="model-a",
    messages=(Message("system", "Be brief."), Message("user", "Größe?")),
    max_tokens=100,
    temperature=0.0,
    seed=7,
    output_schema={"type": "object", "properties": {"a": {"type": "string"}}},
)
RESPONSE = Response('{"a": "b"}', "stop", "model-a", Usage(12, 5, 4, Decimal("0.000021")), 0.25)


class Counting:
    def __init__(self) -> None:
        self.calls: list[tuple[Request, int]] = []

    async def complete(self, request: Request, *, sample: int = 0) -> Response:
        self.calls.append((request, sample))
        return replace(RESPONSE, text=f"call {len(self.calls)}")


def test_equal_requests_have_equal_keys() -> None:
    assert request_key(REQUEST, 0) == request_key(replace(REQUEST), 0)


@pytest.mark.parametrize(
    "changed",
    [
        replace(REQUEST, model="model-b"),
        replace(REQUEST, messages=(*REQUEST.messages, Message("user", "more"))),
        replace(REQUEST, messages=(Message("user", "Be brief."), REQUEST.messages[1])),
        replace(REQUEST, max_tokens=101),
        replace(REQUEST, temperature=0.1),
        replace(REQUEST, temperature=None),
        replace(REQUEST, seed=8),
        replace(REQUEST, output_schema=None),
        replace(REQUEST, output_schema={"type": "array"}),
    ],
)
def test_any_field_change_changes_the_key(changed: Request) -> None:
    assert request_key(changed, 0) != request_key(REQUEST, 0)


def test_sample_index_changes_the_key() -> None:
    assert request_key(REQUEST, 0) != request_key(REQUEST, 1)


def test_schema_key_order_and_int_temperature_do_not_change_the_key() -> None:
    reordered = replace(
        REQUEST,
        temperature=0,
        output_schema={"properties": {"a": {"type": "string"}}, "type": "object"},
    )
    assert request_key(reordered, 0) == request_key(REQUEST, 0)


def test_record_then_replay_returns_the_same_response(tmp_path: Path) -> None:
    live = Counting()
    recorded = asyncio.run(ReplayClient(ReplayStore(tmp_path), live).complete(REQUEST))
    replayed = asyncio.run(ReplayClient(ReplayStore(tmp_path)).complete(REQUEST))
    assert replayed == recorded
    assert len(live.calls) == 1


def test_unreported_usage_fields_stay_none_through_a_recording(tmp_path: Path) -> None:
    class Bare:
        async def complete(self, request: Request, *, sample: int = 0) -> Response:
            return replace(RESPONSE, usage=Usage(12, 5))

    asyncio.run(ReplayClient(ReplayStore(tmp_path), Bare()).complete(REQUEST))
    replayed = asyncio.run(ReplayClient(ReplayStore(tmp_path)).complete(REQUEST))
    assert replayed.usage == Usage(12, 5, None, None)


def test_a_hit_never_calls_the_inner_client(tmp_path: Path) -> None:
    live = Counting()
    client = ReplayClient(ReplayStore(tmp_path), live)
    first = asyncio.run(client.complete(REQUEST))
    second = asyncio.run(client.complete(REQUEST))
    assert first == second
    assert len(live.calls) == 1


def test_each_sample_is_its_own_recording(tmp_path: Path) -> None:
    live = Counting()
    client = ReplayClient(ReplayStore(tmp_path), live)
    texts = [asyncio.run(client.complete(REQUEST, sample=s)).text for s in (0, 1, 0)]
    assert texts == ["call 1", "call 2", "call 1"]
    assert [sample for _, sample in live.calls] == [0, 1]


def test_a_miss_without_an_inner_client_raises(tmp_path: Path) -> None:
    with pytest.raises(ReplayMiss, match=request_key(REQUEST, 2)):
        asyncio.run(ReplayClient(ReplayStore(tmp_path)).complete(REQUEST, sample=2))


def test_a_failed_call_stores_nothing(tmp_path: Path) -> None:
    class Failing:
        async def complete(self, request: Request, *, sample: int = 0) -> Response:
            raise RuntimeError("provider down")

    with pytest.raises(RuntimeError):
        asyncio.run(ReplayClient(ReplayStore(tmp_path), Failing()).complete(REQUEST))
    assert list(tmp_path.rglob("*.json")) == []


def test_a_corrupt_recording_raises_instead_of_missing(tmp_path: Path) -> None:
    asyncio.run(ReplayClient(ReplayStore(tmp_path), Counting()).complete(REQUEST))
    (recording,) = tmp_path.rglob("*.json")
    recording.write_text("{}")
    with pytest.raises(ValidationError):
        asyncio.run(ReplayClient(ReplayStore(tmp_path)).complete(REQUEST))
