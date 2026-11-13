import asyncio
import datetime as dt
from decimal import Decimal

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode

from haussmann.flow.journal import Json, MemoryJournal
from haussmann.flow.runner import open_run
from haussmann.ledger.ledger import Ledger
from haussmann.llmkit.client import LLMClient, Message, Request, Response, Usage
from haussmann.llmkit.pricing import Price

MODEL = "model-a"
PRICES = {MODEL: Price(Decimal(1), Decimal(2), "test", dt.date(2026, 1, 1))}


class Provider:
    async def complete(self, request: Request, *, sample: int = 0) -> Response:
        if request.messages[-1].text == "fail":
            raise TimeoutError
        return Response("secret answer", "stop", "model-a-0613", Usage(1_000_000, 500_000), 0.1)


async def two_calls(ledger: Ledger, client: LLMClient) -> Json:
    await client.complete(Request(MODEL, (Message("user", "secret question one"),), 10))
    await client.complete(Request(MODEL, (Message("user", "secret question two"),), 10))
    return 2


async def one_call(ledger: Ledger, client: LLMClient) -> Json:
    await client.complete(Request(MODEL, (Message("user", "secret question one"),), 10))
    return 1


async def failing(ledger: Ledger, client: LLMClient) -> Json:
    await client.complete(Request(MODEL, (Message("user", "fail"),), 10))
    return None


def traced() -> tuple[TracerProvider, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def run() -> tuple[ReadableSpan, ...]:
    provider, exporter = traced()

    async def scenario() -> None:
        journal = MemoryJournal()
        tracer = provider.get_tracer("test")
        first = await open_run(journal, "r1", "", Provider(), PRICES, Decimal(100), "local", tracer)
        with first.span():
            await first.step("a", two_calls)
        again = await open_run(journal, "r1", "", Provider(), PRICES, Decimal(100), "local", tracer)
        with again.span():
            await again.step("a", two_calls)
            await again.step("b", one_call)
            with pytest.raises(TimeoutError):
                await again.step("c", failing)

    asyncio.run(scenario())
    return exporter.get_finished_spans()


def named(spans: tuple[ReadableSpan, ...], name: str) -> list[ReadableSpan]:
    return [span for span in spans if span.name == name]


def parent_of(span: ReadableSpan) -> int:
    assert span.parent is not None
    return span.parent.span_id


def id_of(span: ReadableSpan) -> int:
    assert span.context is not None
    return span.context.span_id


def test_each_call_is_under_its_step_and_each_step_under_its_run() -> None:
    spans = run()
    first_run, second_run = named(spans, "run")
    first_a, reused_a = named(spans, "step a")
    (step_b,) = named(spans, "step b")
    calls = named(spans, f"chat {MODEL}")

    assert first_run.parent is None and second_run.parent is None
    assert parent_of(first_a) == id_of(first_run)
    assert parent_of(reused_a) == parent_of(step_b) == id_of(second_run)
    assert [parent_of(call) for call in calls[:3]] == [
        id_of(first_a),
        id_of(first_a),
        id_of(step_b),
    ]
    assert all(call.kind is SpanKind.CLIENT for call in calls)


def test_a_reused_step_is_marked_and_has_no_call_under_it() -> None:
    spans = run()
    first_a, reused_a = named(spans, "step a")
    assert first_a.attributes is not None and reused_a.attributes is not None
    assert first_a.attributes["haussmann.step.reused"] is False
    assert reused_a.attributes["haussmann.step.reused"] is True
    assert reused_a.attributes["haussmann.run.id"] == "r1"
    assert all(parent_of(s) != id_of(reused_a) for s in spans if s.parent is not None)


def test_a_call_span_carries_model_tokens_cost_and_whether_it_was_paid() -> None:
    paid, _, served, _ = named(run(), f"chat {MODEL}")
    assert paid.attributes is not None and served.attributes is not None
    assert dict(paid.attributes) == {
        "gen_ai.operation.name": "chat",
        "gen_ai.provider.name": "local",
        "gen_ai.request.model": MODEL,
        "gen_ai.response.model": "model-a-0613",
        "gen_ai.usage.input_tokens": 1_000_000,
        "gen_ai.usage.output_tokens": 500_000,
        "gen_ai.response.finish_reasons": ("stop",),
        "haussmann.cost_usd": 2.0,
        "haussmann.call.paid": True,
        "haussmann.call.key": paid.attributes["haussmann.call.key"],
    }
    assert served.attributes["haussmann.call.paid"] is False
    assert served.attributes["haussmann.call.key"] == paid.attributes["haussmann.call.key"]


def test_no_span_carries_the_text_of_a_request_or_a_response() -> None:
    for span in run():
        assert "secret" not in span.name
        assert "secret" not in repr(dict(span.attributes or {}))


def test_a_failed_call_marks_its_span_and_its_step_with_the_error() -> None:
    spans = run()
    (step_c,) = named(spans, "step c")
    failed = named(spans, f"chat {MODEL}")[-1]
    for span in (step_c, failed):
        assert span.status.status_code is StatusCode.ERROR
        assert span.attributes is not None and span.attributes["error.type"] == "TimeoutError"
