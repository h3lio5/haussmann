"""The single-call contract every model caller uses."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class Message:
    role: Literal["system", "user", "assistant"]
    text: str


@dataclass(frozen=True, slots=True)
class Request:
    """`output_schema` is a JSON Schema the provider constrains its output to."""

    model: str
    messages: tuple[Message, ...]
    max_tokens: int
    temperature: float | None = None
    seed: int | None = None
    output_schema: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class Usage:
    """Optional fields are None when the provider does not report them."""

    input_tokens: int
    output_tokens: int
    cached_input_tokens: int | None = None
    reported_cost_usd: Decimal | None = None


@dataclass(frozen=True, slots=True)
class Response:
    """`text` is exactly what the model produced; callers validate it."""

    text: str
    stop_reason: str
    model: str
    usage: Usage
    latency_s: float


class LLMClient(Protocol):
    async def complete(self, request: Request, *, sample: int = 0) -> Response: ...
