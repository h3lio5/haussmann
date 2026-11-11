import hashlib
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from feasibility_fr.benchmark.render import FILES_DIR
from feasibility_fr.benchmark.scenario import generate
from feasibility_fr.benchmark.scenarios import SCENARIOS
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
    assert 12 <= len(spec.documents) <= 20
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


@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_frozen_public_data_matches_its_recorded_hashes(scenario_id: str) -> None:
    folder = DATA / scenario_id / "public"
    sources = json.loads((folder / "sources.json").read_text(encoding="utf-8"))
    assert {entry["file"] for entry in sources} == {"cadastre.json", "zone.json", "risks.json"}
    for entry in sources:
        digest = hashlib.sha256((folder / entry["file"]).read_bytes()).hexdigest()
        assert digest == entry["sha256"]
        assert entry["url"].startswith("https://") and entry["fetched_on"]


def test_real_public_values_agree_with_the_frozen_data() -> None:
    expected = {"metz_vigny": ("RK", "0357", 1138), "champagnole_ecole": ("AI", "0308", 6615)}
    for scenario_id, (section, number, area) in expected.items():
        parcel = json.loads((DATA / scenario_id / "public" / "cadastre.json").read_text())
        properties = parcel["features"][0]["properties"]
        assert (properties["section"], properties["numero"], properties["contenance"]) == (
            section,
            number,
            area,
        )
