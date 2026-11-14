import hashlib
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from feasibility_fr.benchmark.heldout_style import draw
from feasibility_fr.benchmark.reading import scan_folder
from feasibility_fr.benchmark.render import FILES_DIR
from feasibility_fr.benchmark.scenario import generate
from feasibility_fr.benchmark.scenarios import SCENARIOS
from feasibility_fr.benchmark.templates import DEV_STYLE, KINDS, PHRASES, ROW_LABELS
from feasibility_fr.schema import ATTRIBUTES
from haussmann.evalkit.generator import MANIFEST_NAME
from haussmann.evalkit.groundtruth import Manifest, Split, TrapType
from haussmann.evalkit.manifest import load_manifest
from haussmann.evalkit.validation import validate

DATA = Path(__file__).parent.parent / "benchmark_data"
DEV = [s for s in SCENARIOS.values() if s.spec.split is Split.DEV]


def committed(scenario_id: str) -> Manifest:
    path = DATA / scenario_id / FILES_DIR / MANIFEST_NAME
    return load_manifest(path.read_text(encoding="utf-8"))


def without_hashes(manifest: Manifest) -> Manifest:
    return replace(manifest, files=tuple(replace(f, sha256="") for f in manifest.files))


@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_spec_is_valid_and_sized(scenario_id: str) -> None:
    spec = SCENARIOS[scenario_id].spec
    assert validate(spec, ATTRIBUTES) == []
    assert 12 <= len(spec.documents) <= 60
    assert spec.id == scenario_id


def test_dev_scenarios_have_at_least_three_traps_of_each_type() -> None:
    counts = Counter(trap.type for scenario in DEV for trap in scenario.spec.traps)
    assert all(counts[kind] >= 3 for kind in TrapType)


@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_committed_files_match_their_manifest(scenario_id: str) -> None:
    folder = DATA / scenario_id / FILES_DIR
    manifest = committed(scenario_id)
    for file in manifest.files:
        assert hashlib.sha256((folder / file.filename).read_bytes()).hexdigest() == file.sha256
    assert {p.name for p in folder.iterdir()} == {
        MANIFEST_NAME,
        *(f.filename for f in manifest.files),
    }


@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_committed_manifest_is_what_the_spec_generates(scenario_id: str) -> None:
    regenerated = generate(SCENARIOS[scenario_id]).manifest
    assert without_hashes(regenerated) == without_hashes(committed(scenario_id))


@pytest.mark.parametrize("scenario_id", [scenario.spec.id for scenario in DEV])
def test_frozen_public_data_matches_its_recorded_hashes(scenario_id: str) -> None:
    folder = DATA / scenario_id / "public"
    sources = json.loads((folder / "sources.json").read_text(encoding="utf-8"))
    assert {entry["file"] for entry in sources} == {"cadastre.json", "zone.json", "risks.json"}
    for entry in sources:
        digest = hashlib.sha256((folder / entry["file"]).read_bytes()).hexdigest()
        assert digest == entry["sha256"]
        assert entry["url"].startswith("https://") and entry["fetched_on"]


def test_real_public_values_agree_with_the_frozen_data() -> None:
    expected = {
        "metz_vigny": ("RK", "0357", 1138),
        "champagnole_ecole": ("AI", "0308", 6615),
        "sainte_genevieve_gendarmerie": ("AC", "0198", 4838),
    }
    for scenario_id, (section, number, area) in expected.items():
        parcel = json.loads((DATA / scenario_id / "public" / "cadastre.json").read_text())
        properties = parcel["features"][0]["properties"]
        assert (properties["section"], properties["numero"], properties["contenance"]) == (
            section,
            number,
            area,
        )


def test_the_large_scenario_is_large_and_has_three_traps_of_each_type() -> None:
    scenario = SCENARIOS["sainte_genevieve_gendarmerie"]
    counts = Counter(trap.type for trap in scenario.spec.traps)
    assert all(counts[kind] == 3 for kind in TrapType)
    manifest = committed(scenario.spec.id)
    assert len(manifest.files) == 38
    rules = [s for f in manifest.files for s in f.statements if s.doc_id.startswith("reglement_")]
    assert len(rules) == 10
    assert all(int(statement.locator.removeprefix("p")) >= 15 for statement in rules)


def test_the_rules_of_other_zones_are_labelled_with_their_zone() -> None:
    folder = DATA / "sainte_genevieve_gendarmerie" / FILES_DIR
    pages = {(p.doc_id, p.locator): p.text for p in scan_folder(folder)}
    manifest = committed("sainte_genevieve_gendarmerie")
    for file in manifest.files:
        for statement in file.statements:
            if statement.doc_id.startswith("reglement_zone"):
                zone = statement.doc_id.removeprefix("reglement_zone_").capitalize()
                assert f"Zone {zone} : " in pages[(statement.doc_id, statement.locator)]


HELDOUT = [s for s in SCENARIOS.values() if s.spec.split is Split.HELDOUT]


def test_heldout_scenarios_follow_the_size_and_trap_rules_fixed_before_they_were_written() -> None:
    assert len(HELDOUT) == 2
    for scenario in HELDOUT:
        counts = Counter(trap.type for trap in scenario.spec.traps)
        assert 14 <= len(scenario.spec.documents) <= 24 and 15 <= len(scenario.spec.gold) <= 22
        assert len(scenario.spec.traps) == 12 and all(counts[kind] >= 1 for kind in TrapType)
    pooled = Counter(trap.type for scenario in HELDOUT for trap in scenario.spec.traps)
    assert all(pooled[kind] == 3 for kind in TrapType)


def test_no_heldout_document_shares_a_phrase_a_label_or_a_frame_with_the_dev_wording() -> None:
    dev_texts = {*PHRASES.values(), *ROW_LABELS.values()}
    dev_texts |= {
        text for kind in KINDS.values() for text in (kind.title, kind.opening, kind.closing)
    }
    for scenario in HELDOUT:
        style = scenario.wording.style
        assert style is not None
        used = {*style.phrases.values(), *style.row_labels.values(), style.dated, style.heading}
        used |= {
            t for kind in style.kinds.values() for t in (kind.title, kind.opening, kind.closing)
        }
        assert not (used - {""}) & dev_texts
        assert style.dated != DEV_STYLE.dated and style.columns != DEV_STYLE.columns
        assert style.prefix != DEV_STYLE.prefix and style.row != DEV_STYLE.row
        assert set(style.phrases) == set(PHRASES) and set(style.kinds) == set(KINDS)


def test_the_wording_of_a_heldout_scenario_is_drawn_from_its_seed_alone() -> None:
    for scenario in HELDOUT:
        assert scenario.wording.style == draw(scenario.spec.seed)
    assert draw(1) != draw(2)
