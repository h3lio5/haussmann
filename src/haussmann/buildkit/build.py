"""Build the sections of a deliverable, reusing every section whose target is unchanged."""

import re
from collections.abc import Awaitable, Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass

from haussmann.buildkit.targets import Input, Target

PLACEHOLDER = re.compile(r"\{([^{}]+)\}")


@dataclass(frozen=True, slots=True)
class Sentence:
    """`text` holds a `{name}` placeholder for each input it states; `uses` lists the names."""

    text: str
    uses: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Built:
    """`reused` is True when the sentences came from the cache."""

    section_id: str
    hash: str
    sentences: tuple[Sentence, ...]
    reused: bool


type Author = Callable[[Target], Awaitable[Sequence[Sentence]]]
type Cache = MutableMapping[str, tuple[Sentence, ...]]


def names_in(text: str) -> tuple[str, ...]:
    """The placeholder names in a text, in order, each once."""
    return tuple(dict.fromkeys(PLACEHOLDER.findall(text)))


async def listing(target: Target) -> Sequence[Sentence]:
    """The author of a section that states each of its inputs as it is printed."""
    return [Sentence(f"{{{item.name}}}", (item.name,)) for item in target.inputs]


async def build(
    targets: Sequence[Target], authors: Mapping[str, Author], cache: Cache
) -> tuple[Built, ...]:
    """A stored section when its hash is in the cache; otherwise its author writes it.

    A section with no input is empty and no author is called for it.
    """
    missing = sorted({t.section.kind for t in targets if t.section.kind not in authors})
    if missing:
        raise ValueError(f'no author for sections of kind "{missing[0]}"')
    built: list[Built] = []
    for target in targets:
        stored = cache.get(target.hash)
        if stored is not None:
            built.append(Built(target.section.id, target.hash, stored, True))
            continue
        written: Sequence[Sentence] = ()
        if target.inputs:
            written = await authors[target.section.kind](target)
        cache[target.hash] = tuple(written)
        built.append(Built(target.section.id, target.hash, tuple(written), False))
    return tuple(built)


def fill(sentence: Sentence, inputs: Mapping[str, Input], flag_mark: str = "") -> str:
    """The sentence with each placeholder replaced by its input's text.

    A flagged input is followed by `flag_mark`, whatever the sentence says about it.
    """

    def printed(match: re.Match[str]) -> str:
        item = inputs.get(match.group(1))
        if item is None:
            raise ValueError(f"the sentence uses {match.group(1)}, which is not an input")
        return item.text + (flag_mark if item.flagged else "")

    return PLACEHOLDER.sub(printed, sentence.text)
