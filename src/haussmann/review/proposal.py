"""A proposed rewrite of one section: checked like any draft, applied only when accepted."""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from haussmann.buildkit.build import Built, Sentence, names_in
from haussmann.buildkit.targets import Input
from haussmann.buildkit.writer import check, supported


class ProposalRefused(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Proposal:
    """`refused` holds the reasons when the draft does not hold; `sentences` is then empty.

    `hash` is the hash of the section the rewrite was written for.
    """

    section_id: str
    hash: str
    sentences: tuple[Sentence, ...]
    refused: tuple[str, ...] = ()


def checked(section: Built, drafted: Sequence[str], inputs: Sequence[Input]) -> Proposal:
    """A proposal from a draft, under the rules every section is written under: no sentence
    without a fact, no value typed outside a placeholder, every fact of the section stated."""
    sentences, _ = supported([text.strip() for text in drafted if text.strip()])
    reasons = check(sentences, inputs)
    if not reasons and tuple(sentences) == tuple(s.text for s in section.sentences):
        reasons = ["the proposal is the text the section already has"]
    if reasons:
        return Proposal(section.section_id, section.hash, (), tuple(reasons))
    made = tuple(Sentence(text, names_in(text)) for text in sentences)
    return Proposal(section.section_id, section.hash, made)


def accept(built: Sequence[Built], proposal: Proposal) -> tuple[Built, ...]:
    """The build with the section's text replaced by the proposal's.

    Refused when the proposal did not hold, or when the section has been rebuilt on other
    inputs since the proposal was written.
    """
    if proposal.refused:
        raise ProposalRefused("a refused proposal cannot be accepted")
    current = next((s for s in built if s.section_id == proposal.section_id), None)
    if current is None or current.hash != proposal.hash:
        raise ProposalRefused("the section has changed since the proposal was written")
    return tuple(
        replace(section, sentences=proposal.sentences, reused=False)
        if section.section_id == proposal.section_id
        else section
        for section in built
    )
