"""The review API on the recorded dev scenarios, through the framework's test client."""

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from feasibility_fr.app.demo import committed_cases, measured, open_scenario
from feasibility_fr.app.http import create_app
from feasibility_fr.app.session import Session
from haussmann.llmkit.replay import ReplayClient, ReplayStore

DATA = Path(__file__).parent.parent / "benchmark_data"
RUN = "champagnole_ecole"
OWNER = {
    "name": "site.owner",
    "value": "Commune de Champagnole",
    "reason": "The notary's note for the property names the commune.",
    "author": "reviewer",
}
REWORD = "Regroupez la référence cadastrale et la contenance dans une seule phrase."


def opened() -> tuple[Any, Session]:
    replay = ReplayClient(ReplayStore(DATA / "recordings" / "completions"))
    session = asyncio.run(open_scenario(DATA, RUN, replay, rehearse=True))
    app = create_app(
        {RUN: session},
        lambda: committed_cases(DATA),
        evals=lambda: measured(DATA, DATA.parents[2] / "EXPERIMENTS.md"),
    )
    return TestClient(app), session


@pytest.fixture
def api() -> Any:
    return opened()[0]


def sections(memo: Any) -> dict[str, Any]:
    return {section["id"]: section for section in memo["sections"]}


def test_the_memo_gives_each_sentence_the_facts_it_states_and_each_fact_its_sources(
    api: Any,
) -> None:
    assert [run["run"] for run in api.get("/api/runs").json()] == [RUN]
    memo = api.get(f"/api/runs/{RUN}/memo").json()
    site = sections(memo)["site"]
    assert site["title"] == "Le site et sa propriété" and site["state"] == "in_review"
    sentence = site["sentences"][0]
    assert "6 615 m²" in sentence["text"] and sentence["uses"] == ["site.land_area"]
    area = memo["inputs"]["site.land_area"]
    assert area["text"] == "6 615 m²" and area["citations"]
    assert memo["approved"] is False


def test_a_fact_shows_every_value_found_with_its_standing_and_a_source_opens_at_the_citation(
    api: Any,
) -> None:
    fact = api.get(f"/api/runs/{RUN}/facts/site.land_area").json()
    assert fact["settled"] == "6 615 m²" and fact["settled_fact"] in [
        f["id"] for f in fact["facts"]
    ]
    cited = next(f for f in fact["facts"] if f["id"] == fact["settled_fact"])["citations"][0]
    assert cited["quote"]
    source = api.get(f"/api/runs/{RUN}/sources/{cited['doc_id']}/{cited['locator']}").json()
    assert cited["quote"] in source["text"] and source["form"] == "pdf"
    file = api.get(f"/api/runs/{RUN}/files/{cited['doc_id']}")
    assert file.status_code == 200 and file.content.startswith(b"%PDF")


def test_what_the_run_does_not_have_is_not_found(api: Any) -> None:
    assert api.get("/api/runs/unknown/memo").status_code == 404
    assert api.get(f"/api/runs/{RUN}/facts/site.colour").status_code == 404
    assert api.get(f"/api/runs/{RUN}/sources/nothing/p1").status_code == 404
    assert api.get(f"/api/runs/{RUN}/files/nothing").status_code == 404


def test_an_edit_rebuilds_the_memo_returns_the_diff_and_becomes_a_case(api: Any) -> None:
    before = api.get(f"/api/runs/{RUN}/memo").json()
    assert "site.owner" not in before["inputs"]
    for section in ("site", "rules"):
        api.post(f"/api/runs/{RUN}/sections/{section}/approve", json={"author": "reviewer"})

    answer = api.post(f"/api/runs/{RUN}/edits", json=OWNER).json()
    changes = {change["section"]: change for change in answer["changes"]}
    assert set(changes) == {"site", "open"}
    assert changes["site"]["values"] == [
        {"name": "site.owner", "before": None, "after": "Commune de Champagnole"}
    ]
    after = sections(answer["memo"])
    assert (after["site"]["state"], after["rules"]["state"]) == ("in_review", "approved")
    assert any("Commune de Champagnole" in s["text"] for s in after["site"]["sentences"])

    fact = api.get(f"/api/runs/{RUN}/facts/site.owner").json()
    assert fact["settled"] == "Commune de Champagnole"
    assert [f["method"] for f in fact["facts"] if f["id"] == fact["settled_fact"]] == ["expert"]
    cases = api.get("/api/cases").json()
    assert (
        '"attribute": "owner"' in cases["from_review"]
        and '"author": "reviewer"' in cases["from_review"]
    )
    assert cases["committed"].count('"scenario"') == 3


def test_an_edit_with_no_recording_or_a_value_that_does_not_fit_changes_nothing(
    api: Any,
) -> None:
    before = api.get(f"/api/runs/{RUN}/memo").json()
    unrecorded = api.post(f"/api/runs/{RUN}/edits", json={**OWNER, "value": "SCI des Sapins"})
    assert unrecorded.status_code == 409 and "no recording" in unrecorded.json()["detail"]
    misfit = {"name": "site.land_area", "value": "vaste", "reason": "x", "author": "reviewer"}
    assert api.post(f"/api/runs/{RUN}/edits", json=misfit).status_code == 422
    unknown = {**OWNER, "name": "site.colour"}
    assert api.post(f"/api/runs/{RUN}/edits", json=unknown).status_code == 422
    no_reason = {**OWNER, "reason": " "}
    assert api.post(f"/api/runs/{RUN}/edits", json=no_reason).status_code == 422
    assert api.get(f"/api/runs/{RUN}/memo").json() == before
    assert api.get(f"/api/runs/{RUN}/facts/site.owner").json()["settled"] is None


def test_a_comment_to_the_agent_gives_a_proposal_that_applies_only_once_accepted(
    api: Any,
) -> None:
    api.post(f"/api/runs/{RUN}/edits", json=OWNER)
    api.post(f"/api/runs/{RUN}/sections/site/approve", json={"author": "reviewer"})
    body = {"author": "reviewer", "text": REWORD, "to_agent": True}
    answer = api.post(f"/api/runs/{RUN}/sections/site/comments", json=body).json()
    proposal = answer["proposal"]
    assert proposal["refused"] == [] and "6 615 m²" in proposal["sentences"][0]
    assert "AI 308" in proposal["sentences"][0]
    site = sections(answer["memo"])["site"]
    assert site["state"] == "approved" and site["comments"][0]["text"] == REWORD
    assert "AI 308" not in site["sentences"][0]["text"]

    accepted = api.post(
        f"/api/runs/{RUN}/proposals/{proposal['id']}/accept", json={"author": "reviewer"}
    ).json()
    site = sections(accepted)["site"]
    assert site["sentences"][0]["text"] == proposal["sentences"][0]
    assert site["state"] == "in_review"
    again = api.post(f"/api/runs/{RUN}/proposals/{proposal['id']}/accept", json={"author": "r"})
    assert again.status_code == 422


def test_a_plain_comment_and_a_request_for_changes_are_kept_with_the_section(
    api: Any,
) -> None:
    body = {"author": "reviewer", "text": "Quelle pièce ?", "uses": ["site.land_area"]}
    answer = api.post(f"/api/runs/{RUN}/sections/site/comments", json=body).json()
    assert answer["proposal"] is None
    changes = {"author": "reviewer", "reason": "le propriétaire manque"}
    memo = api.post(f"/api/runs/{RUN}/sections/site/request-changes", json=changes).json()
    site = sections(memo)["site"]
    assert site["state"] == "changes_requested"
    assert site["comments"] == [
        {
            "author": "reviewer",
            "text": "Quelle pièce ?",
            "uses": ["site.land_area"],
            "to_agent": False,
        }
    ]
    unrecorded = {"author": "reviewer", "text": "Plus court.", "to_agent": True}
    refused = api.post(f"/api/runs/{RUN}/sections/site/comments", json=unrecorded)
    assert refused.status_code == 409
    assert (
        api.post(f"/api/runs/{RUN}/sections/nothing/approve", json={"author": "r"}).status_code
        == 422
    )


def test_the_evals_route_gives_the_log_the_report_by_split_and_the_cases(api: Any) -> None:
    evals = api.get("/api/evals").json()
    log = evals["experiments"][-1]
    assert log["header"][0] == "id" and log["header"][-1] == "decision"
    assert [row[0] for row in log["rows"]][-1] >= "E016"
    assert all(len(row) == len(log["header"]) for row in log["rows"])
    headings = [table["heading"] for table in evals["report"]]
    assert any(h.startswith("dev") for h in headings)
    assert any(h.startswith("heldout") for h in headings)
    assert {row[-1] for row in evals["cases"][0]["rows"]} <= {"held", "open"}
