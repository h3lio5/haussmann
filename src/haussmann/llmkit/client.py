"""The single-call contract every model caller uses."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """A tool the model may call. `parameters` is the JSON Schema of its arguments."""

    name: str
    description: str
    parameters: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A call the model asked for. `arguments` is the JSON text exactly as it produced it."""

    id: str
    name: str
    arguments: str


@dataclass(frozen=True, slots=True)
class Message:
    """`images` are PNG or JPEG files sent with the text, for models that read images.

    An assistant message may carry `tool_calls`; a tool message answers one of them and
    names it in `tool_call_id`.
    """

    role: Literal["system", "user", "assistant", "tool"]
    text: str
    images: tuple[bytes, ...] = ()
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None


@dataclass(frozen=True, slots=True)
class Request:
    """`output_schema` is a JSON Schema the provider constrains its output to."""

    model: str
    messages: tuple[Message, ...]
    max_tokens: int
    temperature: float | None = None
    seed: int | None = None
    output_schema: Mapping[str, object] | None = None
    tools: tuple[ToolSpec, ...] = ()


@dataclass(frozen=True, slots=True)
class Usage:
    """Optional fields are None when the provider does not report them."""

    input_tokens: int
    output_tokens: int
    cached_input_tokens: int | None = None
    reported_cost_usd: Decimal | None = None


@dataclass(frozen=True, slots=True)
class Response:
    """`text` is exactly what the model produced; callers validate it.

    `tool_calls` is non-empty when the model asked for tools instead of answering.
    """

    text: str
    stop_reason: str
    model: str
    usage: Usage
    latency_s: float
    tool_calls: tuple[ToolCall, ...] = ()


class LLMClient(Protocol):
    async def complete(self, request: Request, *, sample: int = 0) -> Response: ...
