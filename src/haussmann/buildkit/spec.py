"""What a deliverable is made of: sections, and the inputs each one selects."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Section:
    """`kind` names the author that writes it; `attributes` are the inputs it selects."""

    id: str
    title: str
    kind: str
    attributes: tuple[str, ...]
    guidance: str = ""


@dataclass(frozen=True, slots=True)
class Spec:
    id: str
    version: str
    sections: tuple[Section, ...]
