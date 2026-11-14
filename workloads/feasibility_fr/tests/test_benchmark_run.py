import asyncio
import json
from collections.abc import Sequence
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from feasibility_fr.benchmark.answer import (
    InvalidAnswer,
    answer_schema,
    parse_answer,
    questions,
    render_questions,
)
from feasibility_fr.benchmark.baselines import retrieve
from feasibility_fr.benchmark.reading import read_folder, scan_folder
from feasibility_fr.benchmark.render import FILES_DIR
from feasibility_fr.benchmark.run import (
    Clients,
    OverCap,
    check_cap,
    estimate_cost,
    run,
    selected,
)
from feasibility_fr.benchmark.scenario import Scenario
from feasibility_fr.benchmark.scenarios import SCENARIOS
from feasibility_fr.engine.spec import read_value
from feasibility_fr.schema import ATTRIBUTES
from haussmann.coretypes.values import Quantity
from haussmann.evalkit.generator import MANIFEST_NAME
from haussmann.evalkit.groundtruth import Manifest, Split, StatementKind, TrapType
from haussmann.evalkit.manifest import load_manifest
from haussmann.evalkit.report import render_report
from haussmann.evalkit.scorer import Citation
from haussmann.llmkit.client import Request, Response, Usage
from haussmann.llmkit.embeddings import Embeddings, ReplayEmbedder
from haussmann.llmkit.replay import ReplayClient, ReplayStore

DATA = Path(__file__).parent.parent / "benchmark_data"
METZ = DATA / "metz_vigny" / FILES_DIR
FLAGGED = (TrapType.CONTRADICTION, TrapType.ARITHMETIC, TrapType.DATE_LOGIC)
BASELINE_SYSTEMS = ("one_prompt", "naive_rag")


def manifest_of(scenario_id: str) -> Manifest:
    path = DATA / scenario_id / FILES_DIR / MANIFEST_NAME
    return load_manifest(path.read_text(encoding="utf-8"))


def ideal_answer(manifest: Manifest) -> str:
    """The JSON a perfect system would return, built from the answer key."""
    statements = [s for f in manifest.files for s in f.statements]
    traps = {trap.key: trap for trap in manifest.traps}
    facts: list[dict[str, object]] = []
    for gold in manifest.gold:
        if gold.value is None:
            continue
        trap = traps.get(gold.key)
        cited = [
            s
            for s in statements
            if s.key == gold.key
            and (
                s.kind is StatementKind.SUPPORTS
                or (trap is not None and trap.type in FLAGGED and s.doc_id in trap.docs)
            )
        ]
        value = gold.value
        facts.append(
            {
                "subject": gold.key.subject,
                "attribute": gold.key.attribute,
                "value": str(value.amount) if isinstance(value, Quantity) else str(value),
                "unit": value.unit if isinstance(value, Quantity) else "",
                "citations": [{"doc_id": s.doc_id, "locator": s.locator} for s in cited],
                "flagged": trap is not None and trap.type in FLAGGED,
            }
        )
    missing = [
        {"subject": g.key.subject, "attribute": g.key.attribute}
        for g in manifest.gold
        if g.value is None
    ]
    return json.dumps({"facts": facts, "open_questions": missing})


class Scripted:
    """Transcribes any image as fixed text and answers every other request with `answer`."""

    def __init__(self, answers: dict[str, str]) -> None:
        self.answers = answers
        self.requests: list[Request] = []

    async def complete(self, request: Request, *, sample: int = 0) -> Response:
        self.requests.append(request)
        if any(message.images for message in request.messages):
            return Response("texte transcrit", "stop", request.model, Usage(900, 50), 0.5)
        prompt = request.messages[-1].text
        answer = next(a for marker, a in self.answers.items() if marker in prompt)
        return Response(answer, "stop", request.model, Usage(5000, 800), 1.5)


class FakeEmbedder:
    async def embed(self, model: str, texts: Sequence[str]) -> Embeddings:
        vectors = tuple(
            (float(len(t) % 7), float(len(t) % 5), float(t.count("e") % 3)) for t in texts
        )
        return Embeddings(vectors, 100, Decimal("0.000001"))


def scripted_for_all() -> Scripted:
    markers = {
        "metz_vigny": "Alfred de Vigny",
        "champagnole_ecole": "Hubert Reeves",
        "sainte_genevieve_gendarmerie": "association sportive",
        "heldout_presbytere": "Ancien presbytère",
        "heldout_caserne": "Ancienne caserne",
    }
    return Scripted({markers[sid]: ideal_answer(manifest_of(sid)) for sid in SCENARIOS})


def test_scan_folder_reads_every_file_and_leaves_the_manifest_out() -> None:
    pages = scan_folder(METZ)
    assert {p.doc_id for p in pages} == {f.doc_id for f in manifest_of("metz_vigny").files}
    scans = [p for p in pages if p.image is not None]
    assert {p.doc_id for p in scans} == {"bornage", "note_notaire"}
    assert all(p.image is not None and p.image.startswith(b"\xff\xd8") for p in scans)
    sheet = next(p for p in pages if p.doc_id == "tableau_surfaces")
    assert sheet.locator == "Sheet1" and "[Sheet1!B10] 330 m²" in sheet.text
    mail = next(p for p in pages if p.doc_id == "courriel_2024")
    assert mail.locator == "body" and "occupé" in mail.text
    rules = [p for p in pages if p.doc_id == "reglement_zone"]
    assert [p.locator for p in rules] == [f"p{n}" for n in range(1, len(rules) + 1)]


def test_read_folder_transcribes_only_image_pages() -> None:
    client = Scripted({})
    pages = asyncio.run(read_folder(METZ, client, "model-a"))
    assert len(client.requests) == 2
    assert all(r.temperature == 0.0 for r in client.requests)
    assert next(p for p in pages if p.doc_id == "bornage").text == "texte transcrit"


def test_questions_carry_no_values_and_name_kind_and_unit() -> None:
    scenario = SCENARIOS["champagnole_ecole"]
    asked = questions([g.key for g in scenario.spec.gold], scenario.wording)
    text = render_questions(asked, ATTRIBUTES)
    assert 'subject="lease:club" attribute="annual_rent" (quantity, in EUR/year)' in text
    assert "Convention avec le club associatif - Loyer" in text
    assert "3600" not in text and "128000" not in text


def test_answer_schema_is_strict_and_lists_known_attributes_and_units() -> None:
    schema: Any = answer_schema(ATTRIBUTES)
    fact = schema["properties"]["facts"]["items"]
    assert fact["additionalProperties"] is False
    assert set(fact["required"]) == {
        "subject",
        "attribute",
        "value",
        "unit",
        "citations",
        "flagged",
    }
    assert "max_levels" in fact["properties"]["attribute"]["enum"]
    assert {"", "ha", "EUR/month"} <= set(fact["properties"]["unit"]["enum"])


@pytest.mark.parametrize(
    ("value", "unit", "attribute", "expected"),
    [
        ("1138", "m2", "land_area", Quantity(Decimal("1138"), "m2")),
        ("0,1138", "ha", "land_area", Quantity(Decimal("0.1138"), "ha")),
        ("245 000", "", "asking_price", Quantity(Decimal("245000"), "EUR")),
        ("environ 9", "m", "max_height", "environ 9"),
        ("NaN", "m", "max_height", "NaN"),
        ("R+4+C", "", "max_levels", "R+4+C"),
        ("unknown", "", "not_an_attribute", "unknown"),
    ],
)
def test_values_are_read_as_their_attribute_kind(
    value: str, unit: str, attribute: str, expected: object
) -> None:
    assert read_value(value, unit, ATTRIBUTES.get(attribute)) == expected


def test_dates_are_read_in_common_forms_and_kept_as_text_otherwise() -> None:
    attribute = ATTRIBUTES["lease_end"]
    assert str(read_value("2027-08-31", "", attribute)) == "2027-08-31"
    assert str(read_value("31 août 2027", "", attribute)) == "2027-08-31"
    assert str(read_value("31/08/2027", "", attribute)) == "2027-08-31"
    assert read_value("fin août", "", attribute) == "fin août"


def test_parse_answer_builds_a_submission() -> None:
    submission = parse_answer(ideal_answer(manifest_of("metz_vigny")), ATTRIBUTES)
    height = next(f for f in submission.facts if f.key.attribute == "max_height")
    assert height.value == Quantity(Decimal("9"), "m")
    assert height.citations == (Citation("reglement_zone", "p8"),)
    assert {k.attribute for k in submission.open_questions} == {"soil_study", "pollution_study"}


@pytest.mark.parametrize("text", ["not json", "{}", '{"facts": [{"subject": "site"}]}'])
def test_malformed_answer_raises(text: str) -> None:
    with pytest.raises(InvalidAnswer):
        parse_answer(text, ATTRIBUTES)


def test_retrieve_is_deterministic_and_keeps_page_order() -> None:
    pages = [(1.0, 0.0), (0.0, 1.0), (0.9, 0.1), (0.1, 0.9)]
    queries = [(1.0, 0.0), (0.0, 1.0)]
    assert retrieve(queries, pages, 1) == [0, 1]
    assert retrieve(queries, pages, 2) == [0, 1, 2, 3]
    assert retrieve(queries[:1], pages, 2) == [0, 2]


def test_a_perfect_answer_scores_full_marks_through_the_whole_runner() -> None:
    client = scripted_for_all()
    scenarios = list(SCENARIOS.values())
    records = asyncio.run(
        run(DATA, scenarios, Clients(client, FakeEmbedder()), 2, BASELINE_SYSTEMS)
    )

    assert len(records) == len(scenarios) * len(BASELINE_SYSTEMS) * 2
    for record in records:
        assert record.failure is None and record.score is not None
        assert record.score.recall.value == 1.0
        assert record.score.citation_correctness.value == 1.0
        assert all(trap.passed for trap in record.score.traps), record
        assert record.cost_usd > 0 and record.latency_s > 0
    assert render_report(records) == render_report(
        asyncio.run(
            run(DATA, scenarios, Clients(scripted_for_all(), FakeEmbedder()), 2, BASELINE_SYSTEMS)
        )
    )


def test_the_retrieval_baseline_sends_fewer_pages_than_the_one_prompt_baseline() -> None:
    client = scripted_for_all()
    scenario = SCENARIOS["metz_vigny"]
    asyncio.run(run(DATA, [scenario], Clients(client, FakeEmbedder()), 1, BASELINE_SYSTEMS))
    answers = [r for r in client.requests if r.output_schema is not None]
    everything, retrieved = (r.messages[-1].text.count("=== doc_id:") for r in answers)
    assert everything == len(scan_folder(METZ))
    assert 0 < retrieved < everything
    assert all(r.temperature == 0.0 and r.seed == 0 for r in answers)


def test_an_unreadable_or_repeated_answer_is_a_failed_run_not_a_crash() -> None:
    scenario = SCENARIOS["metz_vigny"]
    ideal = json.loads(ideal_answer(manifest_of("metz_vigny")))
    repeated = json.dumps({**ideal, "facts": [*ideal["facts"], ideal["facts"][0]]})
    for answer in ("not json", repeated):
        client = Scripted({"Alfred de Vigny": answer})
        records = asyncio.run(
            run(DATA, [scenario], Clients(client, FakeEmbedder()), 1, BASELINE_SYSTEMS)
        )
        assert all(r.score is None and r.failure for r in records)
        assert all(r.cost_usd > 0 for r in records)


def test_cost_estimate_is_small_and_the_cap_refuses_above_it() -> None:
    estimate = estimate_cost(DATA, list(SCENARIOS.values()), samples=3)
    assert Decimal(0) < estimate < Decimal("1.50")
    check_cap(estimate, Decimal("2.0"))
    with pytest.raises(OverCap):
        check_cap(estimate, Decimal("0.001"))


def test_held_out_scenarios_are_left_out_unless_asked_for() -> None:
    dev = SCENARIOS["metz_vigny"]
    held = Scenario(replace(dev.spec, id="held", split=Split.HELDOUT), dev.wording)
    assert selected([dev, held], include_heldout=False) == [dev]
    assert selected([dev, held], include_heldout=True) == [dev, held]


def test_the_committed_report_reproduces_from_recordings_without_a_network() -> None:
    clients = Clients(
        ReplayClient(ReplayStore(DATA / "recordings" / "completions")),
        ReplayEmbedder(DATA / "recordings" / "embeddings"),
    )
    records = asyncio.run(run(DATA, selected(list(SCENARIOS.values()), False), clients, 3))
    committed = (DATA / "results" / "report.md").read_text(encoding="utf-8")
    assert render_report(records) == committed
