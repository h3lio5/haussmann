import asyncio
import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from feasibility_fr.benchmark.answer import questions
from feasibility_fr.benchmark.engine_system import to_submission
from feasibility_fr.benchmark.reading import read_folder
from feasibility_fr.benchmark.render import FILES_DIR
from feasibility_fr.benchmark.run import MODEL
from feasibility_fr.benchmark.scenarios import SCENARIOS
from feasibility_fr.engine.finder import describe, find, make_tools
from feasibility_fr.engine.rules import add_months, flag_dates
from feasibility_fr.engine.run import EngineRun, plan, renderings, run_engine, unchecked_pages
from feasibility_fr.engine.spec import RequiredFact
from feasibility_fr.schema import ATTRIBUTES
from haussmann.coretypes.values import FactKey, Quantity
from haussmann.ctxkit.search import Index
from haussmann.docparse.cards import DocumentCard
from haussmann.docparse.elements import Element
from haussmann.evalkit.generator import MANIFEST_NAME
from haussmann.evalkit.groundtruth import StatementKind
from haussmann.evalkit.manifest import load_manifest
from haussmann.evalkit.scorer import score
from haussmann.flow.journal import MemoryJournal
from haussmann.flow.runner import NO_CAP, open_run
from haussmann.ledger.ledger import Citation, Condition, Ledger, NewFact, Status
from haussmann.llmkit.client import LLMClient, Request, Response, ToolCall, Usage
from haussmann.llmkit.pricing import Price
from haussmann.llmkit.replay import ReplayClient, ReplayStore
from haussmann.llmkit.tools import Stop, Tool, ToolError
from haussmann.verify.settle import settled, verify

DATA = Path(__file__).parent.parent / "benchmark_data"

HEIGHT = FactKey("site", "max_height")
PRICE = FactKey("site", "asking_price")
CERTIFICATE = FactKey("site", "planning_certificate_date")
LEASE_END = FactKey("lease:a", "lease_end")
ELEMENTS = (
    Element("reglement", "p8", "La hauteur maximale des constructions est fixée à 9 m."),
    Element("plaquette", "p1", "Hauteur possible : 15 m. Prix : 150 000 €."),
    Element("certificat", "p1", "Le certificat d'urbanisme a été délivré le 14 mars 2023."),
    Element("tableau", "Sheet1", "[Sheet1!A6] Rez-de-chaussée\n[Sheet1!B6] 115 m²"),
)
CARDS = (
    DocumentCard("reglement", "zoning_regulation", dt.date(2026, 9, 21), 3),
    DocumentCard("plaquette", "sales_brochure", dt.date(2026, 4, 2), 1),
    DocumentCard("certificat", "planning_certificate", dt.date(2023, 3, 14), 3),
    DocumentCard("tableau", "area_schedule", None, 2),
)
WANTED = (
    RequiredFact(HEIGHT, "Le bien - Hauteur maximale"),
    RequiredFact(PRICE, "Le bien - Prix demandé"),
)


def tools(ledger: Ledger) -> dict[str, Tool]:
    made = make_tools(ELEMENTS, CARDS, Index(ELEMENTS), ledger, WANTED, ATTRIBUTES)
    return {tool.spec.name: tool for tool in made}


def call(tool: Tool, **arguments: str) -> str:
    async def go() -> str:
        return await tool.run(arguments)

    return asyncio.run(go())


RECORD: dict[str, str] = {
    "subject": "site",
    "attribute": "max_height",
    "value": "9",
    "unit": "m",
    "doc_id": "reglement",
    "locator": "p8",
    "quote": "fixée à 9 m",
}


def test_a_search_result_shows_the_part_of_the_page_that_matches() -> None:
    long = "Dispositions générales. " * 40 + "Le recul minimal est de 4 m. Suite du texte."
    elements = (Element("reglement", "p8", long),)
    made = make_tools(elements, CARDS, Index(elements), Ledger(), WANTED, ATTRIBUTES)
    found = call(made[0], query="recul minimal")
    assert found.endswith("| Le recul minimal est de 4 m. Suite du texte.")


def test_search_lists_matching_pages_with_their_document_type_and_date() -> None:
    found = call(tools(Ledger())["search"], query="hauteur maximale")
    first = found.splitlines()[0]
    assert first.startswith("reglement | p8 | zoning_regulation, 2026-09-21 | La hauteur")
    assert "plaquette | p1 | sales_brochure" in found
    assert call(tools(Ledger())["search"], query="piscine").startswith("no page matches")


def test_read_returns_the_whole_page_and_explains_a_wrong_locator() -> None:
    read = tools(Ledger())["read"]
    assert call(read, doc_id="reglement", locator="p8").endswith(ELEMENTS[0].text)
    with pytest.raises(ToolError, match="reglement has no p9; it has p8"):
        call(read, doc_id="reglement", locator="p9")
    with pytest.raises(ToolError, match="no such document"):
        call(read, doc_id="ghost", locator="p1")


def test_record_fact_writes_a_candidate_with_its_source_to_the_ledger() -> None:
    ledger = Ledger()
    assert call(tools(ledger)["record_fact"], **RECORD) == "recorded as f1"
    (fact,) = ledger.facts()
    assert (fact.key, fact.value, fact.author) == (HEIGHT, Quantity(Decimal(9), "m"), "finder")
    assert fact.citations == (Citation("reglement", "p8", "fixée à 9 m"),)
    assert ledger.status("f1") is Status.CANDIDATE


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"attribute": "zone"}, "not one of the requested facts"),
        ({"value": "environ neuf"}, "cannot be read as a quantity"),
        ({"unit": "feet"}, 'unit "feet" is not one of: m'),
    ],
)
def test_record_fact_refuses_a_bad_call_and_writes_nothing(
    change: dict[str, str], message: str
) -> None:
    ledger = Ledger()
    with pytest.raises(ToolError, match=message):
        call(tools(ledger)["record_fact"], **{**RECORD, **change})
    assert ledger.facts() == ()


def test_a_missing_argument_is_reported_to_the_model() -> None:
    incomplete = {k: v for k, v in RECORD.items() if k != "quote"}
    with pytest.raises(ToolError, match='"quote" is required'):
        call(tools(Ledger())["record_fact"], **incomplete)


def test_no_evidence_records_an_open_question() -> None:
    ledger = Ledger()
    tool = tools(ledger)["no_evidence"]
    call(tool, subject="site", attribute="asking_price", reason="searched prix, cession")
    (question,) = ledger.questions()
    assert (question.key, question.reason) == (PRICE, "searched prix, cession")


class Scripted:
    """Plays a fixed list of model turns: tool calls as (name, arguments), or a final text."""

    def __init__(self, *turns: list[tuple[str, dict[str, str]]] | str) -> None:
        self.turns = list(turns)
        self.requests: list[Request] = []

    async def complete(self, request: Request, *, sample: int = 0) -> Response:
        self.requests.append(request)
        turn = self.turns.pop(0) if self.turns else "done"
        if isinstance(turn, str):
            return Response(turn, "stop", request.model, Usage(900, 20), 0.2)
        calls = tuple(
            ToolCall(f"c{len(self.requests)}{n}", name, json.dumps(arguments))
            for n, (name, arguments) in enumerate(turn)
        )
        return Response("", "tool_calls", request.model, Usage(900, 40), 0.2, calls)


def test_a_finder_run_searches_reads_records_and_stops() -> None:
    ledger = Ledger()
    client = Scripted(
        [("search", {"query": "hauteur maximale"})],
        [("read", {"doc_id": "reglement", "locator": "p8"})],
        [
            ("record_fact", RECORD),
            (
                "record_fact",
                {**RECORD, "value": "15", "doc_id": "plaquette", "locator": "p1", "quote": "15 m"},
            ),
            ("no_evidence", {"subject": "site", "attribute": "asking_price", "reason": "x"}),
        ],
        "done",
    )
    finding = asyncio.run(
        find(
            WANTED,
            ELEMENTS,
            CARDS,
            Index(ELEMENTS),
            ledger,
            ATTRIBUTES,
            client,
            "model-a",
            "2026-10-09",
            0,
        )
    )
    assert finding.loop.stop is Stop.ANSWERED and len(client.requests) == 4
    assert [f.value for f in ledger.facts(HEIGHT)] == [
        Quantity(Decimal(9), "m"),
        Quantity(Decimal(15), "m"),
    ]
    assert len(ledger.questions()) == 1

    first = client.requests[0]
    assert [tool.name for tool in first.tools] == ["search", "read", "record_fact", "no_evidence"]
    opening = first.messages[1].text
    assert opening.startswith("[task: requested facts]\nReview date: 2026-10-09")
    assert 'attribute="max_height" (quantity; units: m)' in opening
    assert "[documents: reglement]\nzoning_regulation, 2026-09-21" in opening
    assert "[elements: reglement p8]" in opening
    assert [e.tier for e in finding.context.manifest][:1] == ["task"]


def test_plan_chunks_the_main_subject_and_groups_the_rest_by_attribute() -> None:
    scenario = SCENARIOS["champagnole_ecole"]
    asked = questions([g.key for g in scenario.spec.gold], scenario.wording, scenario.totals)
    groups = plan(asked)
    assert sum(len(group) for group in groups) == len(asked)
    assert all(len(group) <= 5 for group in groups if group[0].key.subject == "site")
    rents = next(g for g in groups if g[0].key.attribute == "annual_rent")
    assert {fact.key.subject for fact in rents} == {"lease:club", "lease:atelier", "loyers"}
    total = next(fact for fact in rents if fact.key.subject == "loyers")
    assert {part.subject for part in total.sum_of} == {"lease:club", "lease:atelier"}


def test_add_months_keeps_the_day_or_clamps_to_the_month_end() -> None:
    assert add_months(dt.date(2023, 3, 14), 18) == dt.date(2024, 9, 14)
    assert add_months(dt.date(2023, 8, 31), 18) == dt.date(2025, 2, 28)
    assert add_months(dt.date(2023, 12, 1), 1) == dt.date(2024, 1, 1)


@pytest.mark.parametrize(
    ("as_of", "flagged"),
    [(dt.date(2024, 9, 14), False), (dt.date(2024, 9, 15), True), (dt.date(2026, 10, 9), True)],
)
def test_a_planning_certificate_is_flagged_once_eighteen_months_have_passed(
    as_of: dt.date, flagged: bool
) -> None:
    ledger = Ledger()
    ledger.append(
        "finder", [NewFact(CERTIFICATE, dt.date(2023, 3, 14), (Citation("certificat", "p1"),))]
    )
    verify(ledger, ELEMENTS, CARDS, ATTRIBUTES, [CERTIFICATE], {}, renderings)
    flag_dates(ledger, [CERTIFICATE], ATTRIBUTES, as_of)
    assert bool(settled(ledger, CERTIFICATE, ATTRIBUTES).reasons) is flagged


def test_a_lease_that_ended_before_the_review_date_is_flagged() -> None:
    elements = (Element("bail", "p1", "Le bail prend fin le 30 juin 2024."),)
    ledger = Ledger()
    ledger.append("finder", [NewFact(LEASE_END, dt.date(2024, 6, 30), (Citation("bail", "p1"),))])
    verify(ledger, elements, (), ATTRIBUTES, [LEASE_END], {}, renderings)
    flag_dates(ledger, [LEASE_END], ATTRIBUTES, dt.date(2026, 10, 9))
    assert settled(ledger, LEASE_END, ATTRIBUTES).reasons == ("ended before the review date",)


async def engine_run(client: LLMClient) -> EngineRun:
    prices = {"model-a": Price(Decimal(1), Decimal(1), "test", dt.date(2026, 1, 1))}
    runner = await open_run(MemoryJournal(), "run", "", client, prices, NO_CAP)
    return await run_engine(
        WANTED, ELEMENTS, CARDS, ATTRIBUTES, runner, "model-a", dt.date(2026, 10, 9)
    )


def test_an_engine_run_with_nothing_found_reports_only_open_questions() -> None:
    done = asyncio.run(engine_run(Scripted()))
    submission = to_submission(done.ledger, WANTED, ATTRIBUTES)
    assert submission.facts == () and set(submission.open_questions) == {HEIGHT, PRICE}
    assert len(done.findings) == 2
    second = done.findings[1].context.text
    assert "A first pass recorded nothing for these facts" in second


def test_a_second_pass_covers_only_what_the_first_left_untouched() -> None:
    client = Scripted([("record_fact", RECORD)], "done", "done", "done")
    done = asyncio.run(engine_run(client))
    retry = done.findings[1].context.text
    assert "A first pass recorded nothing" in retry
    assert 'attribute="asking_price"' in retry and 'attribute="max_height"' not in retry


def test_a_cross_check_sends_the_finder_to_documents_it_has_not_cited() -> None:
    brochure = {**RECORD, "value": "15", "doc_id": "plaquette", "locator": "p1", "quote": "15 m"}
    marked = ("no_evidence", {"subject": "site", "attribute": "asking_price", "reason": "x"})
    client = Scripted(
        [("record_fact", RECORD), marked], "done", [("record_fact", brochure)], "done"
    )
    done = asyncio.run(engine_run(client))
    assert len(done.findings) == 2
    check = done.findings[1].context.text
    assert "Values are already recorded for these facts" in check
    listed = next(line for line in check.splitlines() if line.startswith("Pages to read"))
    assert listed.startswith("Pages to read for site/max_height: ")
    assert "plaquette p1" in listed and "reglement" not in listed
    assert "[elements: plaquette p1]" in check and "[elements: reglement p8]" not in check
    assert 'attribute="asking_price"' not in check

    result = settled(done.ledger, HEIGHT, ATTRIBUTES)
    assert result.fact is not None and result.fact.value == Quantity(Decimal(9), "m")
    assert result.conflict is not None and len(result.supporting) == 2
    submission = to_submission(done.ledger, WANTED, ATTRIBUTES)
    (reported,) = submission.facts
    assert reported.flagged and {c.doc_id for c in reported.citations} == {"reglement", "plaquette"}


def test_nothing_is_cross_checked_when_no_other_document_matches() -> None:
    ledger = Ledger()
    ledger.append(
        "finder", [NewFact(CERTIFICATE, dt.date(2023, 3, 14), (Citation("certificat", "p1"),))]
    )
    wanted = [RequiredFact(CERTIFICATE, "Le bien - Date du certificat d'urbanisme")]
    assert unchecked_pages(ledger, wanted, Index(ELEMENTS[2:3])) == {}
    assert unchecked_pages(Ledger(), wanted, Index(ELEMENTS)) == {}


def test_a_unit_written_as_in_the_document_is_understood() -> None:
    ledger = Ledger()
    wanted = (RequiredFact(FactKey("floor:rdc", "floor_area"), "Rez-de-chaussée - Surface"),)
    made = make_tools(ELEMENTS, CARDS, Index(ELEMENTS), ledger, wanted, ATTRIBUTES)
    record = {tool.spec.name: tool for tool in made}["record_fact"]
    call(
        record,
        subject="floor:rdc",
        attribute="floor_area",
        value="115",
        unit="m²",
        doc_id="tableau",
        locator="Sheet1!B6",
        quote="115 m²",
    )
    assert ledger.facts()[0].value == Quantity(Decimal(115), "m2")


@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_with_a_perfect_finder_the_engine_passes_every_trap(scenario_id: str) -> None:
    """Every statement about the property goes in as a candidate; the code does the rest."""
    scenario = SCENARIOS[scenario_id]
    folder = DATA / scenario_id / FILES_DIR
    manifest = load_manifest((folder / MANIFEST_NAME).read_text(encoding="utf-8"))
    replay = ReplayClient(ReplayStore(DATA / "recordings" / "completions"))
    elements = asyncio.run(read_folder(folder, replay, MODEL))
    cards = [DocumentCard(p.doc_id, p.source, p.date, p.authority) for p in scenario.spec.documents]
    asked = questions([g.key for g in manifest.gold], scenario.wording, scenario.totals)

    ledger = Ledger()
    for file in manifest.files:
        for stated in file.statements:
            if stated.kind is not StatementKind.DISTRACTOR:
                source: Any = (Citation(stated.doc_id, stated.locator),)
                ledger.append("finder", [NewFact(stated.key, stated.value, source)])
    keys = [fact.key for fact in asked]
    totals = {fact.key: fact.sum_of for fact in asked if fact.sum_of}
    verify(ledger, elements, cards, ATTRIBUTES, keys, totals, renderings)
    flag_dates(ledger, keys, ATTRIBUTES, max(p.date for p in scenario.spec.documents))

    result = score(manifest, ATTRIBUTES, to_submission(ledger, asked, ATTRIBUTES))
    assert all(ledger.status(fact.id) is Status.VERIFIED for fact in ledger.facts())
    assert result.recall.value == 1.0 and result.abstention.value == 1.0
    assert [trap for trap in result.traps if not trap.passed] == []


ZONE = FactKey("site", "zone")
RENT = FactKey("lease:a", "annual_rent")
ZONED = (
    Element("zone_ua", "p1", "Règlement de la zone Ua."),
    Element("zone_ua", "p4", "Zone Ua : la hauteur maximale des constructions est fixée à 12 m."),
    Element("certificat", "p1", "Le terrain est situé en zone Uc. Hauteur maximale : 8 m."),
    Element("bail", "p2", "Le loyer est de 1 500 € par trimestre. Contenance : 0,48 ha."),
)
BY_ZONE = (
    RequiredFact(HEIGHT, "Le bien - Hauteur maximale", depends_on=ZONE),
    RequiredFact(RENT, "Bail - Loyer annuel"),
    RequiredFact(FactKey("site", "land_area"), "Le bien - Contenance"),
)
RULE: dict[str, str] = {
    "subject": "site",
    "attribute": "max_height",
    "value": "12",
    "unit": "m",
    "doc_id": "zone_ua",
    "locator": "p4",
    "quote": "fixée à 12 m",
    "applies_to": "Zone Ua",
}


def zoned(ledger: Ledger, wanted: tuple[RequiredFact, ...] = BY_ZONE) -> Tool:
    made = make_tools(ZONED, CARDS, Index(ZONED), ledger, wanted, ATTRIBUTES)
    return {tool.spec.name: tool for tool in made}["record_fact"]


def test_a_rule_is_recorded_with_the_case_it_is_written_for() -> None:
    ledger = Ledger()
    record = zoned(ledger)
    call(record, **RULE)
    site = {
        "value": "8",
        "doc_id": "certificat",
        "locator": "p1",
        "quote": "Hauteur maximale : 8 m",
    }
    call(record, **{**RULE, **site, "applies_to": ""})
    stated, plain = ledger.facts(HEIGHT)
    assert stated.holds_when == Condition(ZONE, "Zone Ua") and plain.holds_when is None


def test_a_case_that_the_cited_document_does_not_write_is_refused() -> None:
    ledger = Ledger()
    with pytest.raises(ToolError, match='"Zone Uc" is not written in zone_ua'):
        call(zoned(ledger), **{**RULE, "applies_to": "Zone Uc"})
    for words in ("Ua", "hauteur maximale", "Zone Ua et suivantes"):
        with pytest.raises(ToolError, match=f'"{words}" does not name a case'):
            call(zoned(ledger), **{**RULE, "applies_to": words})
    call(zoned(ledger), **{**RULE, "applies_to": "zone UA :"})
    assert [fact.holds_when for fact in ledger.facts()] == [Condition(ZONE, "zone UA :")]
    ledger = Ledger()
    with pytest.raises(ToolError, match='"applies_to" is required'):
        call(zoned(ledger), **{k: v for k, v in RULE.items() if k != "applies_to"})
    assert ledger.facts() == ()


def test_the_case_argument_is_offered_only_when_a_requested_fact_has_cases() -> None:
    assert "applies_to" in str(zoned(Ledger()).spec.parameters)
    assert "applies_to" not in str(tools(Ledger())["record_fact"].spec.parameters)
    assert "[one value per case]" in describe(BY_ZONE, ATTRIBUTES).splitlines()[0]
    assert "one value per case" not in describe(WANTED, ATTRIBUTES)


RENT_CALL: dict[str, str] = {
    "subject": "lease:a",
    "attribute": "annual_rent",
    "doc_id": "bail",
    "locator": "p2",
    "quote": "1 500 € par trimestre",
    "applies_to": "",
}


def test_a_number_the_quote_does_not_contain_is_refused_when_recorded() -> None:
    ledger = Ledger()
    record = zoned(ledger)
    with pytest.raises(ToolError, match="the quote does not contain the number 6000"):
        call(record, **RENT_CALL, value="6000", unit="EUR/year")
    with pytest.raises(ToolError, match="does not contain the number 6000"):
        call(record, **{**RENT_CALL, "quote": ""}, value="6000", unit="EUR/year")
    assert ledger.facts() == ()
    call(record, **RENT_CALL, value="1500", unit="EUR/quarter")
    area = {"subject": "site", "attribute": "land_area", "quote": "0,48 ha"}
    call(record, **{**RENT_CALL, **area}, value="0.48", unit="ha")
    assert [fact.value for fact in ledger.facts()] == [
        Quantity(Decimal(1500), "EUR/quarter"),
        Quantity(Decimal("0.48"), "ha"),
    ]


def test_an_engine_run_keeps_the_rule_of_the_zone_the_site_is_in() -> None:
    ledger = Ledger()
    ledger.append("finder", [NewFact(ZONE, "Uc", (Citation("certificat", "p1"),))])
    call(zoned(ledger), **RULE)
    site = {
        "value": "8",
        "doc_id": "certificat",
        "locator": "p1",
        "quote": "Hauteur maximale : 8 m",
    }
    call(zoned(ledger), **{**RULE, **site, "applies_to": "zone Uc"})
    verify(ledger, ZONED, CARDS, ATTRIBUTES, (HEIGHT, ZONE), {}, renderings, {HEIGHT: ZONE})
    result = settled(ledger, HEIGHT, ATTRIBUTES)
    assert result.fact is not None and result.fact.value == Quantity(Decimal(8), "m")
    assert result.conflict is None and len(result.set_aside) == 1


@pytest.mark.parametrize(("declared", "flagged"), [("300", False), ("310", True)])
def test_a_recomputed_total_cites_the_place_that_declares_it_and_not_its_parts(
    declared: str, flagged: bool
) -> None:
    first, second = FactKey("floor:a", "floor_area"), FactKey("floor:b", "floor_area")
    total = FactKey("building", "floor_area")
    sheet = Element("tableau", "p1", f"Rez-de-chaussée 100 m²\nÉtage 200 m²\nTotal {declared} m²")
    plan = Element("plans", "p1", "Rez-de-chaussée 100 m²")
    ledger = Ledger()
    for key, amount, doc in [(first, "100", "plans"), (second, "200", "tableau")]:
        value, source = Quantity(Decimal(amount), "m2"), (Citation(doc, "p1"),)
        ledger.append("finder", [NewFact(key, value, source)])
    stated = (Citation("tableau", "p1", f"Total {declared} m²"),)
    ledger.append("finder", [NewFact(total, Quantity(Decimal(declared), "m2"), stated)])
    wanted = (
        RequiredFact(first, "ground floor"),
        RequiredFact(second, "upper floor"),
        RequiredFact(total, "total", sum_of=(first, second)),
    )
    keys = [fact.key for fact in wanted]
    verify(ledger, (sheet, plan), (), ATTRIBUTES, keys, {total: (first, second)}, renderings)

    reported = to_submission(ledger, wanted, ATTRIBUTES).facts[-1]
    assert reported.value == Quantity(Decimal(300), "m2") and reported.flagged is flagged
    assert [(c.doc_id, c.locator) for c in reported.citations] == [("tableau", "p1")]
    computed = ledger.facts(total)[-1]
    assert {c.doc_id for c in computed.citations} == {"plans", "tableau"}


AREAS = (
    Element(
        "tableau",
        "Sheet1",
        "[Sheet1!A7] Logements - Surface de plancher\n[Sheet1!B7] 384 m²\n"
        "[Sheet1!A8] Pavillon - Surface de plancher\n[Sheet1!B8] 45 m²\n"
        "[Sheet1!A9] Annexe - Surface de plancher\n[Sheet1!B9] 45 m²",
    ),
    Element("notice", "p2", "La surface de plancher des logements est de 384 m²."),
)
HOUSING = FactKey("floor:logements", "floor_area")
ANNEX = FactKey("floor:annexe", "floor_area")
AREA: dict[str, str] = {
    "subject": "floor:logements",
    "attribute": "floor_area",
    "value": "384",
    "unit": "m2",
    "doc_id": "tableau",
    "locator": "Sheet1",
    "quote": "384 m²",
}


def area_tool(ledger: Ledger) -> Tool:
    wanted = (RequiredFact(HOUSING, "Logements"), RequiredFact(ANNEX, "Annexe"))
    made = make_tools(AREAS, (), Index(AREAS), ledger, wanted, ATTRIBUTES)
    return next(tool for tool in made if tool.spec.name == "record_fact")


def test_a_quote_that_joins_two_cells_is_refused_when_recorded() -> None:
    ledger = Ledger()
    joined = {**AREA, "quote": "Logements - Surface de plancher 384 m²"}
    with pytest.raises(ToolError, match="the quote is not in tableau Sheet1"):
        call(area_tool(ledger), **joined)
    assert ledger.facts() == ()


def test_a_value_quoted_from_one_cell_is_cited_at_that_cell() -> None:
    ledger = Ledger()
    call(area_tool(ledger), **AREA)
    assert ledger.facts()[0].citations == (Citation("tableau", "Sheet1!B7", "384 m²"),)
    assert verify(ledger, AREAS, (), ATTRIBUTES, [HOUSING], {}, renderings) is None
    assert ledger.status("f1") is Status.VERIFIED


def test_a_quote_found_in_several_cells_stays_cited_at_the_sheet() -> None:
    ledger = Ledger()
    twice = {**AREA, "subject": "floor:annexe", "value": "45", "quote": "45 m²"}
    call(area_tool(ledger), **twice)
    assert ledger.facts()[0].citations == (Citation("tableau", "Sheet1", "45 m²"),)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"doc_id": "notice", "locator": "p2", "quote": "plancher : 384 m²"}, "not in notice p2"),
        ({"doc_id": "notice", "locator": "p9"}, "notice has no p9"),
        ({"doc_id": "bail", "locator": "p1"}, "bail has no p1"),
    ],
)
def test_a_quote_or_a_page_that_is_not_in_the_file_is_refused_when_recorded(
    change: dict[str, str], message: str
) -> None:
    ledger = Ledger()
    with pytest.raises(ToolError, match=message):
        call(area_tool(ledger), **{**AREA, **change})
    assert ledger.facts() == ()
