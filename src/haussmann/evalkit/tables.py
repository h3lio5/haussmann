"""Read the tables of a Markdown file: the experiment log and the reports are kept as text."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Table:
    heading: str
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


def _cells(line: str) -> tuple[str, ...]:
    return tuple(cell.strip() for cell in line.strip().strip("|").split("|"))


def _is_rule(line: str) -> bool:
    cells = _cells(line)
    return bool(cells) and all(cell and set(cell) <= set("-: ") for cell in cells)


def read_tables(markdown: str) -> list[Table]:
    """Each table with the nearest heading above it. A row whose cell count differs from
    the header's is not a row of that table and ends it."""
    tables: list[Table] = []
    heading = ""
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
        is_header = line.startswith("|") and index + 1 < len(lines) and _is_rule(lines[index + 1])
        if not is_header:
            index += 1
            continue
        header = _cells(line)
        rows: list[tuple[str, ...]] = []
        index += 2
        while index < len(lines) and lines[index].startswith("|"):
            cells = _cells(lines[index])
            if len(cells) != len(header):
                break
            rows.append(cells)
            index += 1
        tables.append(Table(heading, header, tuple(rows)))
    return tables
