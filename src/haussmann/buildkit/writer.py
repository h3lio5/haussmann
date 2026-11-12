"""An author that has a model write prose around inputs, and checks that it changed none."""

import re
from collections.abc import Awaitable, Callable, Sequence

from haussmann.buildkit.build import PLACEHOLDER, Author, Sentence, names_in
from haussmann.buildkit.targets import Input, Target

DRAFTS = 2
_DIGIT = re.compile(r"\d")

type Ask = Callable[[Target, Sequence[str]], Awaitable[Sequence[str]]]
"""A target and the reasons its previous draft was refused in; sentences out."""
type Refused = Callable[[Target, int, Sequence[str]], None]
type Dropped = Callable[[Target, Sequence[str]], None]


def supported(sentences: Sequence[str]) -> tuple[list[str], list[str]]:
    """The sentences that name an input, and those that name none and are left out."""
    kept = [sentence for sentence in sentences if names_in(sentence)]
    return kept, [sentence for sentence in sentences if not names_in(sentence)]


def check(sentences: Sequence[str], inputs: Sequence[Input]) -> list[str]:
    """The reasons a draft is refused; empty when it holds."""
    known = {item.name for item in inputs}
    reasons: list[str] = []
    used: set[str] = set()
    for sentence in sentences:
        names = names_in(sentence)
        used.update(names)
        unknown = [name for name in names if name not in known]
        if unknown:
            reasons.append(f"{{{unknown[0]}}} is not one of the facts of this section")
        if _DIGIT.search(PLACEHOLDER.sub("", sentence)):
            reasons.append(
                f'the sentence "{sentence}" contains a number; write every value with its '
                "placeholder and no digit yourself"
            )
    reasons.extend(f"{{{name}}} is not used" for name in sorted(known - used))
    return reasons


def plain(target: Target, label: Callable[[Input], str]) -> tuple[Sentence, ...]:
    """Each input as its label and value: what a section is when no draft holds."""
    return tuple(
        Sentence(f"{label(item)} : {{{item.name}}}.", (item.name,)) for item in target.inputs
    )


def prose_author(
    ask: Ask,
    label: Callable[[Input], str],
    refused: Refused | None = None,
    dropped: Dropped | None = None,
) -> Author:
    """Ask for a draft, check it, ask once more with the reasons, then fall back to `plain`.

    A sentence that names no input is left out before the check: prose with no fact behind
    it is removed, not negotiated. `dropped` is told those sentences; `refused` is told each
    refusal: the target, the draft's number and the reasons.
    """

    async def write(target: Target) -> Sequence[Sentence]:
        reasons: list[str] = []
        for draft in range(1, DRAFTS + 1):
            drafted = [s.strip() for s in await ask(target, reasons) if s.strip()]
            sentences, without_fact = supported(drafted)
            if without_fact and dropped is not None:
                dropped(target, without_fact)
            reasons = check(sentences, target.inputs)
            if not reasons:
                return [Sentence(sentence, names_in(sentence)) for sentence in sentences]
            if refused is not None:
                refused(target, draft, reasons)
        return plain(target, label)

    return write
