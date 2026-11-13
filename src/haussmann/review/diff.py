"""What changed between two builds of a deliverable, by value and by sentence."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from haussmann.buildkit.build import Built, fill
from haussmann.buildkit.targets import Input


@dataclass(frozen=True, slots=True)
class ValueChange:
    """`before` is None for an input the section did not have; `after` for one it lost."""

    name: str
    before: str | None
    after: str | None


@dataclass(frozen=True, slots=True)
class SectionDiff:
    """`rewritten` is True when the section's hash changed between the two builds."""

    section_id: str
    rewritten: bool
    values: tuple[ValueChange, ...]
    removed: tuple[str, ...]
    added: tuple[str, ...]


def _printed(built: Built | None, inputs: Mapping[str, Input], flag_mark: str) -> list[str]:
    return [fill(sentence, inputs, flag_mark) for sentence in built.sentences] if built else []


def _names(built: Built | None) -> list[str]:
    used = [name for sentence in built.sentences for name in sentence.uses] if built else []
    return list(dict.fromkeys(used))


def _shown(name: str, inputs: Mapping[str, Input], flag_mark: str) -> str:
    item = inputs[name]
    return item.text + (flag_mark if item.flagged else "")


def diff(
    before: Sequence[Built],
    after: Sequence[Built],
    inputs_before: Mapping[str, Input],
    inputs_after: Mapping[str, Input],
    flag_mark: str = "",
) -> tuple[SectionDiff, ...]:
    """One entry per section that differs, in the order of `after`, then sections that are gone.

    A value changes when an input is printed differently, flag mark included.
    """
    old = {built.section_id: built for built in before}
    new = {built.section_id: built for built in after}
    found: list[SectionDiff] = []
    for section_id in [*new, *(name for name in old if name not in new)]:
        was, now = old.get(section_id), new.get(section_id)
        names_was, names_now = _names(was), _names(now)
        values: list[ValueChange] = []
        for name in dict.fromkeys([*names_was, *names_now]):
            shown_was = _shown(name, inputs_before, flag_mark) if name in names_was else None
            shown_now = _shown(name, inputs_after, flag_mark) if name in names_now else None
            if shown_was != shown_now:
                values.append(ValueChange(name, shown_was, shown_now))
        text_was = _printed(was, inputs_before, flag_mark)
        text_now = _printed(now, inputs_after, flag_mark)
        removed = tuple(text for text in text_was if text not in text_now)
        added = tuple(text for text in text_now if text not in text_was)
        rewritten = (was.hash if was else None) != (now.hash if now else None)
        if rewritten or values or removed or added:
            found.append(SectionDiff(section_id, rewritten, tuple(values), removed, added))
    return tuple(found)
