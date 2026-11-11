"""Cost of a call, derived from recorded usage and a price table."""

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from haussmann.llmkit.client import Usage

_PER_MILLION = Decimal(1_000_000)


@dataclass(frozen=True, slots=True)
class Price:
    """USD per million tokens, with where and when the figures were read."""

    input: Decimal
    output: Decimal
    source: str
    read_on: dt.date


PRICES: Mapping[str, Price] = {
    "mistralai/mistral-small-2603": Price(
        input=Decimal("0.15"),
        output=Decimal("0.60"),
        source="https://openrouter.ai/mistralai/mistral-small-2603",
        read_on=dt.date(2026, 11, 10),
    ),
}


class UnknownModel(KeyError):
    pass


def cost_usd(model: str, usage: Usage, prices: Mapping[str, Price] = PRICES) -> Decimal:
    """The cost the provider reported, or list price times tokens when it reported none."""
    if usage.reported_cost_usd is not None:
        return usage.reported_cost_usd
    price = prices.get(model)
    if price is None:
        raise UnknownModel(f"no price for model {model}")
    return (usage.input_tokens * price.input + usage.output_tokens * price.output) / _PER_MILLION
