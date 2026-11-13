"""Where each section of a deliverable stands in review, derived from what reviewers did."""

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from haussmann.buildkit.build import Built


class State(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"


@dataclass(frozen=True, slots=True)
class Approve:
    section_id: str
    version: str
    author: str


@dataclass(frozen=True, slots=True)
class RequestChanges:
    section_id: str
    version: str
    author: str
    reason: str


@dataclass(frozen=True, slots=True)
class Comment:
    """`uses` names the facts of the sentence commented on; empty for the whole section.

    `to_agent` asks for a proposed rewrite of the section.
    """

    section_id: str
    version: str
    author: str
    text: str
    uses: tuple[str, ...] = ()
    to_agent: bool = False


type Event = Approve | RequestChanges | Comment


def version(section: Built) -> str:
    """What a decision is made on: the section's inputs and its text, as one digest.

    It changes when the section is rebuilt on other inputs and when its text is replaced
    by an accepted rewrite on the same inputs.
    """
    text = "\n".join([section.hash, *(sentence.text for sentence in section.sentences)])
    return hashlib.sha256(text.encode()).hexdigest()


def states(built: Sequence[Built], events: Sequence[Event]) -> Mapping[str, State]:
    """The state of each section of the current build.

    A section with nothing in it is a draft. A decision counts only if it names the version
    the section has now, and the latest such decision wins; a comment decides nothing.
    """
    found: dict[str, State] = {}
    for section in built:
        state = State.IN_REVIEW if section.sentences else State.DRAFT
        for event in events:
            if (event.section_id, event.version) != (section.section_id, version(section)):
                continue
            if isinstance(event, Approve):
                state = State.APPROVED
            elif isinstance(event, RequestChanges):
                state = State.CHANGES_REQUESTED
        found[section.section_id] = state
    return found


def approved(built: Sequence[Built], events: Sequence[Event]) -> bool:
    """Is every section that has content approved as it is now?"""
    current = states(built, events)
    with_content = [state for state in current.values() if state is not State.DRAFT]
    return bool(with_content) and all(state is State.APPROVED for state in with_content)


def comments(section: Built, events: Sequence[Event]) -> tuple[Comment, ...]:
    """The comments that still apply to a section: on the section as a whole, or on a
    sentence whose facts some sentence of the section still uses together."""
    kept: list[Comment] = []
    for event in events:
        if not isinstance(event, Comment) or event.section_id != section.section_id:
            continue
        if not event.uses or any(set(event.uses) <= set(s.uses) for s in section.sentences):
            kept.append(event)
    return tuple(kept)
