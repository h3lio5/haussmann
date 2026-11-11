import asyncio
import json
import os
from decimal import Decimal

import httpx
import pytest
from pydantic import ValidationError

from haussmann.llmkit.chat_completions import ChatCompletionsClient, request_body
from haussmann.llmkit.client import Message, Request, Response, Usage

REQUEST = Request(
    model="model-a",
    messages=(Message("system", "Be brief."), Message("user", "Hello")),
    max_tokens=100,
    temperature=0.0,
    seed=7,
    output_schema={"type": "object"},
)

REPLY = {
    "id": "x",
    "model": "model-a-resolved",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "{}"}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17},
}


def call(handler: httpx.MockTransport, request: Request = REQUEST) -> Response:
    async def run() -> Response:
        async with httpx.AsyncClient(transport=handler) as http:
            client = ChatCompletionsClient(
                "https://host/v1/",
                "secret",
                http,
                seed_param="rs",
                extra_body={"provider": {"require_parameters": True}, "model": "ignored"},
            )
            return await client.complete(request)

    return asyncio.run(run())


def test_request_body_snapshot() -> None:
    assert request_body(REQUEST, "random_seed") == {
        "model": "model-a",
        "messages": [
            {"role": "system", "content": "Be brief."},
            {"role": "user", "content": "Hello"},
        ],
        "max_tokens": 100,
        "temperature": 0.0,
        "random_seed": 7,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "output", "schema": {"type": "object"}, "strict": True},
        },
    }


def test_optional_fields_are_omitted_when_unset() -> None:
    body = request_body(Request("model-a", (Message("user", "Hello"),), 10))
    assert set(body) == {"model", "messages", "max_tokens"}


def test_complete_sends_the_body_and_maps_the_reply() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=REPLY)

    response = call(httpx.MockTransport(handler))

    (sent,) = seen
    assert str(sent.url) == "https://host/v1/chat/completions"
    assert sent.headers["authorization"] == "Bearer secret"
    assert json.loads(sent.content) == {
        **request_body(REQUEST, "rs"),
        "provider": {"require_parameters": True},
    }
    assert response.text == "{}"
    assert response.stop_reason == "stop"
    assert response.model == "model-a-resolved"
    assert response.usage == Usage(12, 5, None, None)
    assert response.latency_s >= 0


def test_cached_tokens_and_cost_are_read_when_the_provider_reports_them() -> None:
    usage = {
        "prompt_tokens": 12,
        "completion_tokens": 5,
        "prompt_tokens_details": {"cached_tokens": 4, "cache_write_tokens": 0},
        "cost": 0.000021,
    }
    response = call(
        httpx.MockTransport(lambda _: httpx.Response(200, json={**REPLY, "usage": usage}))
    )
    assert response.usage == Usage(12, 5, 4, Decimal("0.000021"))


def test_empty_content_becomes_empty_text_with_its_stop_reason() -> None:
    reply = {**REPLY, "choices": [{"message": {"content": None}, "finish_reason": "length"}]}
    response = call(httpx.MockTransport(lambda _: httpx.Response(200, json=reply)))
    assert (response.text, response.stop_reason) == ("", "length")


def test_an_error_status_raises() -> None:
    with pytest.raises(httpx.HTTPStatusError):
        call(httpx.MockTransport(lambda _: httpx.Response(429, json={"message": "slow down"})))


def test_a_reply_outside_the_format_raises() -> None:
    with pytest.raises(ValidationError):
        call(httpx.MockTransport(lambda _: httpx.Response(200, json={"choices": []})))


@pytest.mark.live
def test_one_real_call_returns_schema_constrained_json() -> None:
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    request = Request(
        model="mistralai/mistral-small-2603",
        messages=(Message("user", "Reply with the word ok."),),
        max_tokens=50,
        temperature=0.0,
        seed=1,
        output_schema=schema,
    )

    async def run() -> Response:
        async with httpx.AsyncClient(timeout=60) as http:
            client = ChatCompletionsClient(
                "https://openrouter.ai/api/v1",
                os.environ["OPENROUTER_API_KEY"],
                http,
                extra_body={"provider": {"require_parameters": True}},
            )
            return await client.complete(request)

    response = asyncio.run(run())
    assert set(json.loads(response.text)) == {"answer"}
    assert response.usage.input_tokens > 0
    assert response.usage.reported_cost_usd is not None
