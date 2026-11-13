"""Spans for model calls. The attribute names of the OpenTelemetry generative AI conventions,
which are still at Development status, are written here and nowhere else."""

from collections.abc import Generator
from contextlib import contextmanager
from decimal import Decimal

from opentelemetry.trace import Span, SpanKind, Tracer

from haussmann.llmkit.client import Request, Response

OPERATION = "gen_ai.operation.name"
PROVIDER = "gen_ai.provider.name"
REQUEST_MODEL = "gen_ai.request.model"
RESPONSE_MODEL = "gen_ai.response.model"
INPUT_TOKENS = "gen_ai.usage.input_tokens"
OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
FINISH_REASONS = "gen_ai.response.finish_reasons"
ERROR_TYPE = "error.type"
CALL_KEY = "haussmann.call.key"
CALL_PAID = "haussmann.call.paid"
COST_USD = "haussmann.cost_usd"


@contextmanager
def call_span(tracer: Tracer, request: Request, key: str, provider: str) -> Generator[Span]:
    """A span around one model call. The request's text is not put on it; `key` finds it."""
    attributes = {
        OPERATION: "chat",
        PROVIDER: provider,
        REQUEST_MODEL: request.model,
        CALL_KEY: key,
    }
    with tracer.start_as_current_span(
        f"chat {request.model}", kind=SpanKind.CLIENT, attributes=attributes
    ) as span:
        try:
            yield span
        except Exception as error:
            span.set_attribute(ERROR_TYPE, type(error).__qualname__)
            raise


def record_response(span: Span, response: Response, cost_usd: Decimal, paid: bool) -> None:
    """`paid` is False when the response was stored by an earlier call and not bought now."""
    span.set_attributes(
        {
            RESPONSE_MODEL: response.model,
            INPUT_TOKENS: response.usage.input_tokens,
            OUTPUT_TOKENS: response.usage.output_tokens,
            FINISH_REASONS: [response.stop_reason],
            COST_USD: float(cost_usd),
            CALL_PAID: paid,
        }
    )
