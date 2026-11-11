"""Live client for providers that speak the chat-completions wire format."""

import base64
import time
from collections.abc import Mapping
from decimal import Decimal

import httpx
from pydantic import BaseModel

from haussmann.llmkit.client import Message, Request, Response, ToolCall, Usage


class _FunctionWire(BaseModel):
    name: str
    arguments: str


class _ToolCallWire(BaseModel):
    id: str
    function: _FunctionWire


class _MessageWire(BaseModel):
    content: str | None = None
    tool_calls: list[_ToolCallWire] | None = None


class _ChoiceWire(BaseModel):
    message: _MessageWire
    finish_reason: str


class _PromptDetailsWire(BaseModel):
    cached_tokens: int | None = None


class _UsageWire(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    prompt_tokens_details: _PromptDetailsWire | None = None
    cost: Decimal | None = None


class _ReplyWire(BaseModel):
    model: str
    choices: list[_ChoiceWire]
    usage: _UsageWire


_JPEG_MAGIC = b"\xff\xd8"


def _content(message: Message) -> object:
    if not message.images:
        return message.text
    parts: list[dict[str, object]] = [{"type": "text", "text": message.text}]
    for image in message.images:
        kind = "image/jpeg" if image.startswith(_JPEG_MAGIC) else "image/png"
        encoded = base64.b64encode(image).decode("ascii")
        parts.append({"type": "image_url", "image_url": {"url": f"data:{kind};base64,{encoded}"}})
    return parts


def _message(message: Message) -> dict[str, object]:
    wire: dict[str, object] = {"role": message.role, "content": _content(message)}
    if message.tool_calls:
        wire["tool_calls"] = [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
            for c in message.tool_calls
        ]
    if message.tool_call_id is not None:
        wire["tool_call_id"] = message.tool_call_id
    return wire


def request_body(request: Request, seed_param: str = "seed") -> dict[str, object]:
    body: dict[str, object] = {
        "model": request.model,
        "messages": [_message(m) for m in request.messages],
        "max_tokens": request.max_tokens,
    }
    if request.temperature is not None:
        body["temperature"] = request.temperature
    if request.seed is not None:
        body[seed_param] = request.seed
    if request.tools:
        body["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in request.tools
        ]
    if request.output_schema is not None:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "output", "schema": request.output_schema, "strict": True},
        }
    return body


def parse_reply(content: bytes, latency_s: float) -> Response:
    """Raises pydantic.ValidationError on a reply outside the format."""
    reply = _ReplyWire.model_validate_json(content)
    choice = reply.choices[0]
    details = reply.usage.prompt_tokens_details
    return Response(
        text=choice.message.content or "",
        stop_reason=choice.finish_reason,
        model=reply.model,
        usage=Usage(
            input_tokens=reply.usage.prompt_tokens,
            output_tokens=reply.usage.completion_tokens,
            cached_input_tokens=None if details is None else details.cached_tokens,
            reported_cost_usd=reply.usage.cost,
        ),
        latency_s=latency_s,
        tool_calls=tuple(
            ToolCall(call.id, call.function.name, call.function.arguments)
            for call in choice.message.tool_calls or ()
        ),
    )


class ChatCompletionsClient:
    """`base_url` ends before `/chat/completions`, for example `https://host/v1`.

    `extra_body` is merged into every request for provider-specific options,
    such as routing preferences on an aggregator.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        http: httpx.AsyncClient,
        *,
        seed_param: str = "seed",
        extra_body: Mapping[str, object] | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._http = http
        self._seed_param = seed_param
        self._extra_body = dict(extra_body or {})

    async def complete(self, request: Request, *, sample: int = 0) -> Response:
        body = {**self._extra_body, **request_body(request, self._seed_param)}
        started = time.perf_counter()
        reply = await self._http.post(self._url, headers=self._headers, json=body)
        reply.raise_for_status()
        return parse_reply(reply.content, time.perf_counter() - started)
