"""Fetch the public data for a scenario's parcel once and store it with its provenance.

Run: python -m feasibility_fr.benchmark.freeze <out_dir> <insee> <section> <numero>
"""

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import httpx

CADASTRE = "https://apicarto.ign.fr/api/cadastre/parcelle"
ZONING = "https://apicarto.ign.fr/api/gpu/zone-urba"
RISKS = "https://georisques.gouv.fr/api/v1/resultats_rapport_risque"

LICENCES = {
    "cadastre.json": (
        "Licence Ouverte / Open Licence (Etalab), the default under the platform's terms; "
        "version not stated",
        "https://cartes.gouv.fr/cgu/",
    ),
    "zone.json": (
        "Licence ouverte, per the terms of the Géoportail de l'urbanisme; version not stated",
        "https://www.geoportail-urbanisme.gouv.fr/cgu/",
    ),
    "risks.json": ("not confirmed: the service's licence pages could not be read", ""),
}


def source_entry(name: str, url: str, content: bytes, fetched_on: dt.date) -> dict[str, str]:
    return {
        "file": name,
        "url": url,
        "fetched_on": fetched_on.isoformat(),
        "sha256": hashlib.sha256(content).hexdigest(),
        "licence": LICENCES[name][0],
        "licence_stated_at": LICENCES[name][1],
    }


def inner_point(geometry: dict[str, Any]) -> tuple[float, float]:
    """A point for point-based services: the mean of the outer ring's vertices."""
    ring = geometry["coordinates"][0]
    if geometry["type"] == "MultiPolygon":
        ring = ring[0]
    lons = [point[0] for point in ring]
    lats = [point[1] for point in ring]
    return sum(lons) / len(lons), sum(lats) / len(lats)


def freeze(out_dir: Path, insee: str, section: str, numero: str, today: dt.date) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, str]] = []

    def fetch(name: str, url: str, params: dict[str, str]) -> Any:
        reply = http.get(url, params=params)
        reply.raise_for_status()
        (out_dir / name).write_bytes(reply.content)
        entries.append(source_entry(name, str(reply.url), reply.content, today))
        return reply.json()

    with httpx.Client(timeout=60, follow_redirects=True) as http:
        parcel = fetch(
            "cadastre.json", CADASTRE, {"code_insee": insee, "section": section, "numero": numero}
        )
        geometry = parcel["features"][0]["geometry"]
        lon, lat = inner_point(geometry)
        point = json.dumps({"type": "Point", "coordinates": [lon, lat]})
        fetch("zone.json", ZONING, {"geom": point})
        fetch("risks.json", RISKS, {"latlon": f"{lon},{lat}"})

    (out_dir / "sources.json").write_text(
        json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    target, insee_code, parcel_section, parcel_number = sys.argv[1:5]
    freeze(Path(target), insee_code, parcel_section, parcel_number, dt.date.today())
