import datetime as dt
from decimal import Decimal

import pytest

from haussmann.llmkit.client import Usage
from haussmann.llmkit.pricing import PRICES, Price, UnknownModel, cost_usd

TABLE = {"model-a": Price(Decimal("0.15"), Decimal("0.60"), "test", dt.date(2026, 1, 1))}


def test_cost_is_tokens_times_price_per_million() -> None:
    assert cost_usd("model-a", Usage(60_000, 8_000), TABLE) == Decimal("0.0138")


def test_zero_usage_costs_nothing() -> None:
    assert cost_usd("model-a", Usage(0, 0), TABLE) == 0


def test_unknown_model_raises() -> None:
    with pytest.raises(UnknownModel):
        cost_usd("model-b", Usage(1, 1), TABLE)


def test_every_listed_price_names_its_source() -> None:
    for price in PRICES.values():
        assert price.source.startswith("https://")
        assert price.input > 0 and price.output > 0


def test_reported_cost_wins_over_the_table() -> None:
    usage = Usage(60_000, 8_000, reported_cost_usd=Decimal("0.0151"))
    assert cost_usd("model-a", usage, TABLE) == Decimal("0.0151")
    assert cost_usd("model-not-listed", usage, TABLE) == Decimal("0.0151")
