import pytest
from hypothesis import given
from hypothesis import strategies as st

from haussmann.ctxkit.assemble import BudgetError, ContextItem, assemble, estimate_tokens, render

TIERS = ("instructions", "task", "documents", "elements")
INSTRUCTIONS = ContextItem("instructions", "finder", "Find the facts.")
TASK = ContextItem("task", "group-1", "Height and setback.")
PAGE_1 = ContextItem("elements", "plu:p1", "a" * 300)
PAGE_8 = ContextItem("elements", "plu:p8", "b" * 30)
CARD = ContextItem("documents", "plu", "regulation, 2023")


def test_items_come_out_in_tier_order_then_given_order() -> None:
    result = assemble([PAGE_1, TASK, PAGE_8, CARD, INSTRUCTIONS], TIERS, budget=10_000)
    assert result.items == (INSTRUCTIONS, TASK, CARD, PAGE_1, PAGE_8)
    assert result.text.startswith("[instructions: finder]\nFind the facts.\n\n[task: group-1]")
    assert result.tokens == sum(entry.tokens for entry in result.manifest)
    assert all(entry.included for entry in result.manifest)


def test_an_item_that_does_not_fit_is_left_out_and_a_smaller_one_still_gets_in() -> None:
    room = sum(estimate_tokens(render(i)) for i in (INSTRUCTIONS, TASK, PAGE_8))
    result = assemble([INSTRUCTIONS, TASK, PAGE_1, PAGE_8], TIERS, budget=room)
    assert result.items == (INSTRUCTIONS, TASK, PAGE_8)
    assert [(e.source, e.included) for e in result.manifest] == [
        ("finder", True),
        ("group-1", True),
        ("plu:p1", False),
        ("plu:p8", True),
    ]
    assert result.tokens == room


def test_a_required_item_that_does_not_fit_fails_the_call() -> None:
    with pytest.raises(BudgetError, match="instructions: finder"):
        assemble([INSTRUCTIONS, TASK], TIERS, budget=3, required={"instructions", "task"})


def test_an_item_with_an_unknown_tier_is_an_error() -> None:
    with pytest.raises(ValueError, match="memory"):
        assemble([ContextItem("memory", "note", "x")], TIERS, budget=100)


def test_adding_lower_tier_items_never_changes_what_comes_before_them() -> None:
    base = assemble([INSTRUCTIONS, TASK, CARD], TIERS, budget=10_000)
    more = assemble([INSTRUCTIONS, TASK, CARD, PAGE_1, PAGE_8], TIERS, budget=10_000)
    assert more.text.startswith(base.text)


def test_the_token_counter_can_be_replaced() -> None:
    result = assemble([INSTRUCTIONS, TASK], TIERS, budget=1, count=lambda text: 1)
    assert result.items == (INSTRUCTIONS,) and result.tokens == 1


items = st.lists(
    st.builds(
        ContextItem,
        st.sampled_from(TIERS),
        st.text(alphabet="abc", min_size=1, max_size=4),
        st.text(max_size=200),
    ),
    max_size=15,
)


@given(items, st.integers(min_value=0, max_value=400))
def test_the_budget_is_never_exceeded_and_the_result_is_deterministic(
    given_items: list[ContextItem], budget: int
) -> None:
    result = assemble(given_items, TIERS, budget)
    assert result.tokens <= budget
    assert result == assemble(given_items, TIERS, budget)
    assert len(result.manifest) == len(given_items)
    assert [e.included for e in result.manifest].count(True) == len(result.items)
    positions = [TIERS.index(item.tier) for item in result.items]
    assert positions == sorted(positions)
