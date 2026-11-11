import datetime as dt
from decimal import Decimal

from haussmann.coretypes.values import FactKey, Quantity
from haussmann.evalkit.documents import Layout, Line
from haussmann.evalkit.groundtruth import PlannedStatement, StatementKind
from haussmann.evalkit.render import render_pdf

LONG = "Texte sans rapport avec la question posée, répété pour remplir la page. " * 12


def test_a_long_pdf_locates_each_statement_once_however_often_it_is_rendered() -> None:
    """Paragraphs split across pages are short-lived objects; none may pass for a statement."""
    first = PlannedStatement(
        FactKey("site", "height"), Quantity(Decimal(9), "m"), StatementKind.SUPPORTS
    )
    last = PlannedStatement(
        FactKey("site", "width"), Quantity(Decimal(4), "m"), StatementKind.SUPPORTS
    )
    filler = tuple(Line("text", LONG) for _ in range(150))
    items = (
        Line("text", "Hauteur : 9 m.", (first,)),
        *filler,
        Line("text", "Largeur : 4 m.", (last,)),
    )
    layout = Layout("long", "Document long", dt.date(2026, 1, 1), items)
    renders = [render_pdf(layout) for _ in range(12)]
    assert {data for data, _ in renders} == {renders[0][0]}
    for _, located in renders:
        assert [statement for statement, _ in located] == [first, last]
        assert located[0][1] == "p1" and located[1][1] != "p1"
