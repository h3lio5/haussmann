import asyncio
from collections.abc import Sequence

import pytest
from hypothesis import given
from hypothesis import strategies as st

from haussmann.buildkit.build import Built, Sentence, build, fill, listing, names_in
from haussmann.buildkit.spec import Section, Spec
from haussmann.buildkit.targets import Input, Target, targets

SPEC = Spec(
    "report",
    "1",
    (
        Section("size", "Size", "prose", ("width", "height"), "Two sentences."),
        Section("cost", "Cost", "prose", ("price",)),
        Section("issues", "Issues", "listing", ("issue",)),
    ),
)
INPUTS = (
    Input("site.width", "width", "4 m", "4 m|plan p1"),
    Input("site.height", "height", "9 m", "9 m|rules p8"),
    Input("site.price", "price", "150 000 €", "150000 EUR|notice p1", flagged=True),
    Input("site.price#issue", "issue", "Price: 150 000 € against 160 000 €.", "two values"),
)
ENVIRONMENT = {"prompt": "1", "model": "small"}


def hashes(inputs: Sequence[Input] = INPUTS, spec: Spec = SPEC, **environment: str) -> list[str]:
    return [target.hash for target in targets(spec, inputs, {**ENVIRONMENT, **environment})]


def changed(inputs: Sequence[Input] = INPUTS, spec: Spec = SPEC, **environment: str) -> list[str]:
    before = hashes()
    after = hashes(inputs, spec, **environment)
    return [s.id for s, old, new in zip(SPEC.sections, before, after, strict=True) if old != new]


def with_digest(name: str, digest: str) -> tuple[Input, ...]:
    return tuple(
        Input(i.name, i.attribute, i.text, digest, i.flagged) if i.name == name else i
        for i in INPUTS
    )


def test_a_section_selects_its_inputs_by_attribute_sorted_by_name() -> None:
    size, cost, issues = targets(SPEC, INPUTS, ENVIRONMENT)
    assert [i.name for i in size.inputs] == ["site.height", "site.width"]
    assert [i.name for i in cost.inputs] == ["site.price"]
    assert [i.name for i in issues.inputs] == ["site.price#issue"]


@given(st.permutations(INPUTS))
def test_the_order_of_the_inputs_never_changes_a_hash(shuffled: list[Input]) -> None:
    assert hashes(shuffled) == hashes()


@given(st.sampled_from(INPUTS), st.text(min_size=1))
def test_one_changed_input_changes_only_the_sections_that_select_it(
    item: Input, digest: str
) -> None:
    selecting = [s.id for s in SPEC.sections if item.attribute in s.attributes]
    expected = selecting if digest != item.digest else []
    assert changed(with_digest(item.name, digest)) == expected


def test_what_else_the_text_depends_on_is_in_the_hash() -> None:
    assert changed(model="large") == ["size", "cost", "issues"]
    newer = Spec(SPEC.id, "2", SPEC.sections)
    assert changed(spec=newer) == ["size", "cost", "issues"]
    reworded = Section("size", "Size", "prose", ("width", "height"), "Three sentences.")
    assert changed(spec=Spec(SPEC.id, "1", (reworded, *SPEC.sections[1:]))) == ["size"]


def test_the_printed_text_and_the_flag_are_not_hashed_on_their_own() -> None:
    reprinted = tuple(Input(i.name, i.attribute, i.text.upper(), i.digest) for i in INPUTS)
    assert changed(reprinted) == []


def test_two_inputs_may_not_share_a_name() -> None:
    with pytest.raises(ValueError, match=r"two inputs are named site\.width"):
        targets(SPEC, (*INPUTS, INPUTS[0]), ENVIRONMENT)


class Counting:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[str] = []
        self.fail = fail

    async def __call__(self, target: Target) -> Sequence[Sentence]:
        self.calls.append(target.section.id)
        if self.fail:
            raise RuntimeError("no draft")
        return [Sentence(f"{{{i.name}}}.", (i.name,)) for i in target.inputs]


def run(
    inputs: Sequence[Input], author: Counting, cache: dict[str, tuple[Sentence, ...]]
) -> tuple[Built, ...]:
    made = targets(SPEC, inputs, ENVIRONMENT)
    return asyncio.run(build(made, {"prose": author, "listing": listing}, cache))


def test_a_second_build_calls_no_author_and_reuses_every_section() -> None:
    author, cache = Counting(), dict[str, tuple[Sentence, ...]]()
    first = run(INPUTS, author, cache)
    assert author.calls == ["size", "cost"] and not any(b.reused for b in first)
    second = run(INPUTS, author, cache)
    assert author.calls == ["size", "cost"] and all(b.reused for b in second)
    assert [b.sentences for b in second] == [b.sentences for b in first]


def test_after_one_input_changes_only_its_sections_are_rewritten() -> None:
    author, cache = Counting(), dict[str, tuple[Sentence, ...]]()
    run(INPUTS, author, cache)
    rebuilt = run(with_digest("site.height", "12 m|rules p8"), author, cache)
    assert author.calls == ["size", "cost", "size"]
    assert [b.reused for b in rebuilt] == [False, True, True]


def test_an_author_that_fails_leaves_the_cache_as_it_was() -> None:
    cache = dict[str, tuple[Sentence, ...]]()
    with pytest.raises(RuntimeError):
        run(INPUTS, Counting(fail=True), cache)
    assert cache == {}


def test_a_section_with_no_input_is_empty_and_calls_no_author() -> None:
    author = Counting()
    built = run(INPUTS[:2], author, {})
    assert author.calls == ["size"] and [len(b.sentences) for b in built] == [2, 0, 0]


def test_a_spec_with_a_kind_that_has_no_author_is_refused() -> None:
    made = targets(SPEC, INPUTS, ENVIRONMENT)
    with pytest.raises(ValueError, match='no author for sections of kind "listing"'):
        asyncio.run(build(made, {"prose": Counting()}, {}))


def test_fill_prints_each_input_and_marks_a_flagged_one() -> None:
    by_name = {i.name: i for i in INPUTS}
    sentence = Sentence(
        "It is {site.width} wide and costs {site.price}.", ("site.width", "site.price")
    )
    assert (
        fill(sentence, by_name, " (see issues)")
        == "It is 4 m wide and costs 150 000 € (see issues)."
    )
    with pytest.raises(ValueError, match=r"site\.depth, which is not an input"):
        fill(Sentence("{site.depth}", ("site.depth",)), by_name)
    assert names_in("{a} then {b} then {a}") == ("a", "b")
