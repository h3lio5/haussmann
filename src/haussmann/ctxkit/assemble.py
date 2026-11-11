"""Assemble what a model call sees: ordered tiers of items under a token budget."""

import math
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContextItem:
    """`tier` says what kind of content this is; `source` says where it came from."""

    tier: str
    source: str
    text: str


@dataclass(frozen=True, slots=True)
class Entry:
    """One line of the manifest: an item, its cost, and whether it was kept."""

    tier: str
    source: str
    tokens: int
    included: bool


@dataclass(frozen=True, slots=True)
class Assembled:
    text: str
    items: tuple[ContextItem, ...]
    manifest: tuple[Entry, ...]
    tokens: int


class BudgetError(ValueError):
    pass


def estimate_tokens(text: str) -> int:
    """About one token per three characters, rounded up: a deliberate overestimate."""
    return math.ceil(len(text) / 3)


def render(item: ContextItem) -> str:
    return f"[{item.tier}: {item.source}]\n{item.text}"


def assemble(
    items: Sequence[ContextItem],
    tiers: Sequence[str],
    budget: int,
    required: Collection[str] = (),
    count: Callable[[str], int] = estimate_tokens,
) -> Assembled:
    """Keep items tier by tier, most important tier first, while they fit the budget.

    Items of a `required` tier must all fit or the call fails. In the other tiers an item
    that does not fit is left out and the next one is tried. Within a tier, items keep
    the order they were given in. The result depends only on the arguments.
    """
    order = {tier: position for position, tier in enumerate(tiers)}
    unknown = sorted({item.tier for item in items} - order.keys())
    if unknown:
        raise ValueError(f"items use tiers that are not in the order: {', '.join(unknown)}")

    ranked = sorted(enumerate(items), key=lambda pair: (order[pair[1].tier], pair[0]))
    kept: list[ContextItem] = []
    manifest: list[Entry] = []
    used = 0
    for _, item in ranked:
        cost = count(render(item))
        fits = used + cost <= budget
        if not fits and item.tier in required:
            raise BudgetError(
                f"required item {item.tier}: {item.source} needs {cost} tokens, "
                f"{budget - used} left of {budget}"
            )
        manifest.append(Entry(item.tier, item.source, cost, fits))
        if fits:
            kept.append(item)
            used += cost
    text = "\n\n".join(render(item) for item in kept)
    return Assembled(text, tuple(kept), tuple(manifest), used)
