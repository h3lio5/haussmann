"""Renderers: a layout in, file bytes and the locator of every statement out."""

import datetime as dt
import io
import re
import zipfile
from email.message import EmailMessage
from email.utils import format_datetime
from xml.sax.saxutils import escape

from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Flowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table

from haussmann.evalkit.documents import Layout, Line, Located, Rendered
from haussmann.evalkit.groundtruth import PlannedStatement

SHEET = "Sheet1"
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
_MODIFIED = re.compile(rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)")


def _stamp(date: dt.date) -> dt.datetime:
    return dt.datetime(date.year, date.month, date.day, 9, 0, tzinfo=dt.UTC)


def render_pdf(layout: Layout) -> Rendered:
    """Locators are `p<N>`, the 1-based page each statement landed on."""
    styles = getSampleStyleSheet()
    tagged: dict[int, tuple[PlannedStatement, ...]] = {}
    located: list[Located] = []

    class Tracking(SimpleDocTemplate):
        def afterFlowable(self, flowable: Flowable) -> None:
            for statement in tagged.get(id(flowable), ()):
                located.append((statement, f"p{self.page}"))

    story: list[Flowable] = [Paragraph(escape(layout.title), styles["Title"])]
    for item in layout.items:
        if isinstance(item, Line):
            style = styles["Heading2"] if item.style == "heading" else styles["BodyText"]
            flowable: Flowable = Paragraph(escape(item.text), style)
            states = item.states
        else:
            flowable = Table([list(item.header), *(list(row) for row in item.rows)])
            flowable.setStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey)])
            states = tuple(statement for _, _, statement in item.states)
        if states:
            tagged[id(flowable)] = states
            story.append(KeepTogether([flowable]))
        else:
            story.append(flowable)
        story.append(Spacer(1, 6))

    buffer = io.BytesIO()
    Tracking(buffer, pagesize=A4, invariant=1, title=layout.title).build(story)
    return buffer.getvalue(), located


def render_xlsx(layout: Layout) -> Rendered:
    """Locators are `<sheet>!<cell>`."""
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = SHEET
    located: list[Located] = []

    sheet.cell(1, 1, layout.title)
    row = 3
    for item in layout.items:
        if isinstance(item, Line):
            sheet.cell(row, 1, item.text)
            located.extend((statement, f"{SHEET}!A{row}") for statement in item.states)
            row += 1
            continue
        for column, text in enumerate(item.header, start=1):
            sheet.cell(row, column, text)
        for offset, cells in enumerate(item.rows, start=1):
            for column, text in enumerate(cells, start=1):
                sheet.cell(row + offset, column, text)
        located.extend(
            (statement, f"{SHEET}!{get_column_letter(c + 1)}{row + 1 + r}")
            for r, c, statement in item.states
        )
        row += len(item.rows) + 2

    stamp = _stamp(layout.date).replace(tzinfo=None)
    workbook.properties.created = stamp
    workbook.properties.modified = stamp
    raw = io.BytesIO()
    workbook.save(raw)
    return _fixed_archive(raw.getvalue(), stamp), located


def _fixed_archive(data: bytes, stamp: dt.datetime) -> bytes:
    """Rewrite a spreadsheet archive without the save time the library puts in it."""
    modified = stamp.strftime("%Y-%m-%dT%H:%M:%SZ").encode()
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(out, "w") as target:
        for info in source.infolist():
            content = source.read(info.filename)
            if info.filename == "docProps/core.xml":
                content = _MODIFIED.sub(rb"\g<1>" + modified + rb"\g<2>", content)
            entry = zipfile.ZipInfo(info.filename, _ZIP_EPOCH)
            target.writestr(entry, content, zipfile.ZIP_DEFLATED)
    return out.getvalue()


def render_eml(layout: Layout) -> Rendered:
    """Every statement has the locator `body`."""
    lines: list[str] = []
    located: list[Located] = []
    for item in layout.items:
        if isinstance(item, Line):
            lines.extend((item.text, ""))
            located.extend((statement, "body") for statement in item.states)
        else:
            lines.extend(" | ".join(cells) for cells in (item.header, *item.rows))
            lines.append("")
            located.extend((statement, "body") for _, _, statement in item.states)

    message = EmailMessage()
    message["Subject"] = layout.title
    message["From"] = "sender@example.com"
    message["To"] = "recipient@example.com"
    message["Date"] = format_datetime(_stamp(layout.date))
    message["Message-ID"] = f"<{layout.doc_id}@scenario.invalid>"
    message.set_content("\n".join(lines))
    return message.as_bytes(), located
