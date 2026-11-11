"""Turn a scenario spec into document files and their manifest."""

import hashlib
import random
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from haussmann.evalkit.documents import (
    Body,
    Filler,
    Formatter,
    Grid,
    Heading,
    Layout,
    Line,
    Paragraph,
    Rendered,
    Table,
    Template,
)
from haussmann.evalkit.groundtruth import (
    DocumentPlan,
    Manifest,
    ManifestFile,
    PlannedStatement,
    ScenarioSpec,
    Schema,
    Statement,
    StatementKind,
    TrapType,
)
from haussmann.evalkit.manifest import dump_manifest
from haussmann.evalkit.render import render_eml, render_pdf, render_xlsx
from haussmann.evalkit.scan import degrade
from haussmann.evalkit.validation import validate

MANIFEST_NAME = "manifest.json"
BURIED_FROM_PAGE = 5

_RENDERERS: Mapping[str, Callable[[Layout], Rendered]] = {
    "pdf": render_pdf,
    "xlsx": render_xlsx,
    "eml": render_eml,
}


class GeneratorError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Generated:
    files: Mapping[str, bytes]
    manifest: Manifest


def build(
    spec: ScenarioSpec,
    schema: Schema,
    templates: Mapping[str, Template],
    format_value: Formatter,
    filler: Sequence[str] = (),
    buried_from_page: int = BURIED_FROM_PAGE,
) -> Generated:
    violations = validate(spec, schema)
    if violations:
        raise GeneratorError(f"invalid spec: {violations[0].detail}")

    files: dict[str, bytes] = {}
    entries: list[ManifestFile] = []
    for plan in spec.documents:
        render = _RENDERERS.get(plan.format)
        template = templates.get(plan.source)
        if render is None or template is None:
            raise GeneratorError(f"{plan.doc_id}: unknown format or template")
        if plan.scanned and plan.format != "pdf":
            raise GeneratorError(f"{plan.doc_id}: only a PDF can be scanned")

        rng = random.Random(f"{spec.seed}:{plan.doc_id}")
        layout = _lay_out(template(plan, rng), plan, schema, format_value, filler, rng)
        data, located = render(layout)
        if plan.scanned:
            data = degrade(data, rng, plan.date)

        filename = f"{plan.doc_id}.{plan.format}"
        files[filename] = data
        statements = tuple(
            Statement(plan.doc_id, locator, s.key, s.value, s.kind) for s, locator in located
        )
        entries.append(
            ManifestFile(plan.doc_id, filename, hashlib.sha256(data).hexdigest(), statements)
        )

    manifest = Manifest(spec.id, spec.split, spec.gold, spec.traps, tuple(entries))
    _check_buried(manifest, buried_from_page)
    return Generated(files, manifest)


def write(generated: Generated, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, data in generated.files.items():
        (out_dir / filename).write_bytes(data)
    (out_dir / MANIFEST_NAME).write_text(dump_manifest(generated.manifest), encoding="utf-8")


def _lay_out(
    body: Body,
    plan: DocumentPlan,
    schema: Schema,
    format_value: Formatter,
    filler: Sequence[str],
    rng: random.Random,
) -> Layout:
    def written(statement: PlannedStatement) -> str:
        return format_value(statement.value, schema[statement.key.attribute])

    items: list[Line | Grid] = []
    placed: list[PlannedStatement] = []
    for block in body.blocks:
        match block:
            case Heading(text):
                items.append(Line("heading", text))
            case Paragraph(text, states):
                parts = text.split("{}")
                if len(parts) != len(states) + 1:
                    raise GeneratorError(f"{plan.doc_id}: slots and statements differ in number")
                filled = parts[0] + "".join(
                    written(s) + rest for s, rest in zip(states, parts[1:], strict=True)
                )
                items.append(Line("text", filled, states))
                placed.extend(states)
            case Filler(paragraphs):
                if not filler:
                    raise GeneratorError(f"{plan.doc_id}: filler requested but none supplied")
                items.extend(Line("text", rng.choice(filler)) for _ in range(paragraphs))
            case Table(header, rows):
                cells = tuple(
                    tuple(cell if isinstance(cell, str) else written(cell) for cell in row)
                    for row in rows
                )
                grid_states = tuple(
                    (r, c, cell)
                    for r, row in enumerate(rows)
                    for c, cell in enumerate(row)
                    if isinstance(cell, PlannedStatement)
                )
                items.append(Grid(header, cells, grid_states))
                placed.extend(statement for _, _, statement in grid_states)

    if Counter(placed) != Counter(plan.states):
        raise GeneratorError(f"{plan.doc_id}: template did not place each statement exactly once")
    return Layout(plan.doc_id, body.title, plan.date, tuple(items))


def _check_buried(manifest: Manifest, from_page: int) -> None:
    for trap in manifest.traps:
        if trap.type is not TrapType.BURIED:
            continue
        for file in manifest.files:
            for statement in file.statements:
                if statement.key != trap.key or statement.kind is not StatementKind.SUPPORTS:
                    continue
                on_page = statement.locator.startswith("p") and statement.locator[1:].isdigit()
                if not on_page or int(statement.locator[1:]) < from_page:
                    raise GeneratorError(
                        f"{file.doc_id}: buried statement at {statement.locator}, "
                        f"before page {from_page}"
                    )
