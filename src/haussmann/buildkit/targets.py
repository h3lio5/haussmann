"""Build targets: a section, the inputs it selects, and a hash over all its text depends on."""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from haussmann.buildkit.spec import Section, Spec


@dataclass(frozen=True, slots=True)
class Input:
    """One thing a section may state, prepared by the caller.

    `name` is stable from one run to the next. `text` is how the value is printed.
    `digest` identifies the value and where it comes from; it is what the hash covers.
    """

    name: str
    attribute: str
    text: str
    digest: str
    flagged: bool = False


@dataclass(frozen=True, slots=True)
class Target:
    """`inputs` are sorted by name."""

    section: Section
    inputs: tuple[Input, ...]
    hash: str


def target_hash(
    spec: Spec, section: Section, inputs: Sequence[Input], environment: Mapping[str, str]
) -> str:
    """The same for any order of the inputs; different when anything the text depends on is."""
    covered = {
        "spec": spec.id,
        "version": spec.version,
        "section": [section.id, section.title, section.kind, section.guidance],
        "environment": sorted(environment.items()),
        "inputs": sorted([item.name, item.digest] for item in inputs),
    }
    canonical = json.dumps(covered, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def targets(
    spec: Spec, inputs: Sequence[Input], environment: Mapping[str, str]
) -> tuple[Target, ...]:
    """One target per section of the spec, with the inputs whose attribute it selects.

    `environment` is whatever else the text depends on, such as a prompt version and a model.
    """
    names = [item.name for item in inputs]
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        raise ValueError(f"two inputs are named {repeated[0]}")
    built: list[Target] = []
    for section in spec.sections:
        selected = sorted(
            (item for item in inputs if item.attribute in section.attributes),
            key=lambda item: item.name,
        )
        digest = target_hash(spec, section, selected, environment)
        built.append(Target(section, tuple(selected), digest))
    return tuple(built)
