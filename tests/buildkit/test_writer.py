import asyncio
from collections.abc import Sequence

import pytest

from haussmann.buildkit.build import Author, Sentence
from haussmann.buildkit.spec import Section, Spec
from haussmann.buildkit.targets import Input, Target, targets
from haussmann.buildkit.writer import check, plain, prose_author

INPUTS = (
    Input("site.width", "width", "4 m", "4"),
    Input("floor:1.height", "height", "9 m", "9"),
)
SPEC = Spec("report", "1", (Section("size", "Size", "prose", ("width", "height")),))
TARGET = targets(SPEC, INPUTS, {})[0]
GOOD = ["The plot is {site.width} wide.", "The first floor is {floor:1.height} high."]


def label(item: Input) -> str:
    return item.attribute.capitalize()


@pytest.mark.parametrize(
    ("draft", "reason"),
    [
        ([*GOOD, "It is {site.depth} deep."], "{site.depth} is not one of the facts"),
        ([GOOD[0]], "{floor:1.height} is not used"),
        ([GOOD[0], "The first floor is 9 m high, {floor:1.height}."], "contains a number"),
        ([*GOOD, "The site is well placed."], "states no fact"),
        ([], "{site.width} is not used"),
    ],
)
def test_a_draft_is_refused_with_its_reason(draft: list[str], reason: str) -> None:
    assert any(reason in found for found in check(draft, INPUTS))


def test_a_draft_that_uses_every_input_and_types_no_number_holds() -> None:
    assert check(GOOD, INPUTS) == []


def write(author: Author) -> Sequence[Sentence]:
    async def go() -> Sequence[Sentence]:
        return await author(TARGET)

    return asyncio.run(go())


class Scripted:
    def __init__(self, *drafts: Sequence[str]) -> None:
        self.drafts = list(drafts)
        self.seen: list[Sequence[str]] = []

    async def __call__(self, target: Target, reasons: Sequence[str]) -> Sequence[str]:
        self.seen.append(tuple(reasons))
        return self.drafts.pop(0)


def test_a_good_first_draft_is_kept_with_the_inputs_each_sentence_uses() -> None:
    ask = Scripted(GOOD)
    written = write(prose_author(ask, label))
    assert [s.text for s in written] == GOOD
    assert [s.uses for s in written] == [("site.width",), ("floor:1.height",)]
    assert ask.seen == [()]


def test_a_refused_draft_is_retried_once_with_the_reasons() -> None:
    ask = Scripted([GOOD[0]], GOOD)
    refusals: list[tuple[str, int]] = []
    author = prose_author(
        ask, label, lambda target, draft, why: refusals.append((target.section.id, draft))
    )
    written = write(author)
    assert [s.text for s in written] == GOOD
    assert ask.seen == [(), ("{floor:1.height} is not used",)]
    assert refusals == [("size", 1)]


def test_two_refused_drafts_give_the_plain_list() -> None:
    ask = Scripted(["Width 4 m."], ["Still 4 m."])
    refusals: list[int] = []
    author = prose_author(ask, label, lambda target, draft, why: refusals.append(draft))
    written = write(author)
    assert tuple(written) == plain(TARGET, label)
    assert [s.text for s in written] == ["Height : {floor:1.height}.", "Width : {site.width}."]
    assert refusals == [1, 2] and ask.drafts == []
