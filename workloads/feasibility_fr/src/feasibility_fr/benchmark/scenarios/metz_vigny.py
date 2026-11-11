"""Dev scenario: a bare plot offered for sale by the city of Metz.

What is real and what is invented is recorded in benchmark_data/metz_vigny/CARD.md.
"""

import datetime as dt

from feasibility_fr.benchmark.scenario import (
    COMMERCIAL,
    OFFICIAL,
    OWNER,
    Scenario,
    conflicts,
    distractor,
    doc,
    q,
    stale,
    supports,
)
from feasibility_fr.benchmark.templates import Wording
from haussmann.coretypes.values import FactKey
from haussmann.evalkit.groundtruth import GoldFact, ScenarioSpec, Split, Trap, TrapType

PARCEL = FactKey("site", "parcel_ref")
AREA = FactKey("site", "land_area")
ZONE = FactKey("site", "zone")
HEIGHT = FactKey("site", "max_height")
FOOTPRINT = FactKey("site", "footprint_limit")
SETBACK = FactKey("site", "street_setback")
CERTIFICATE = FactKey("site", "planning_certificate_date")
FLOOD = FactKey("site", "flood_risk")
OWNER_KEY = FactKey("site", "owner")
OCCUPANCY = FactKey("site", "occupancy")
PRICE = FactKey("site", "asking_price")
SOIL = FactKey("site", "soil_study")
POLLUTION = FactKey("site", "pollution_study")
GROUND = FactKey("floor:rdc", "floor_area")
FIRST = FactKey("floor:r1", "floor_area")
SECOND = FactKey("floor:r2", "floor_area")
TOTAL = FactKey("projet", "floor_area")

_FICTION = "Document fictif établi pour un banc d'essai."

SPEC = ScenarioSpec(
    id="metz_vigny",
    split=Split.DEV,
    seed=5746,
    gold=(
        GoldFact(PARCEL, "RK 357"),
        GoldFact(AREA, q("1138", "m2")),
        GoldFact(ZONE, "UIL27"),
        GoldFact(HEIGHT, q("9", "m")),
        GoldFact(FOOTPRINT, q("30", "percent")),
        GoldFact(SETBACK, q("4", "m")),
        GoldFact(CERTIFICATE, dt.date(2023, 3, 14)),
        GoldFact(FLOOD, "oui"),
        GoldFact(OWNER_KEY, "Ville de Metz"),
        GoldFact(OCCUPANCY, "libre"),
        GoldFact(PRICE, q("245000", "EUR")),
        GoldFact(SOIL, None),
        GoldFact(POLLUTION, None),
        GoldFact(GROUND, q("115", "m2")),
        GoldFact(FIRST, q("115", "m2")),
        GoldFact(SECOND, q("80", "m2")),
        GoldFact(TOTAL, q("310", "m2")),
    ),
    documents=(
        doc(
            "certificat_urbanisme",
            "planning_certificate",
            "pdf",
            dt.date(2023, 3, 14),
            OFFICIAL,
            supports(ZONE, "UIL27"),
            supports(CERTIFICATE, dt.date(2023, 3, 14)),
        ),
        doc(
            "reglement_zone",
            "zoning_rules",
            "pdf",
            dt.date(2026, 9, 21),
            OFFICIAL,
            supports(SETBACK, q("4", "m")),
            supports(FOOTPRINT, q("30", "percent")),
            supports(HEIGHT, q("9", "m")),
        ),
        doc(
            "extrait_cadastral",
            "cadastral_extract",
            "pdf",
            dt.date(2026, 10, 2),
            OFFICIAL,
            supports(PARCEL, "RK 357"),
            supports(AREA, q("0.1138", "ha")),
        ),
        doc(
            "bornage",
            "survey",
            "pdf",
            dt.date(2025, 2, 6),
            OFFICIAL,
            supports(AREA, q("0.1138", "ha")),
            scanned=True,
        ),
        doc(
            "note_notaire",
            "title_note",
            "pdf",
            dt.date(2025, 4, 18),
            OFFICIAL,
            supports(OWNER_KEY, "Ville de Metz"),
            scanned=True,
        ),
        doc(
            "etat_risques",
            "risk_report",
            "pdf",
            dt.date(2026, 10, 2),
            OFFICIAL,
            supports(FLOOD, "oui"),
        ),
        doc(
            "avis_initial",
            "sale_notice",
            "pdf",
            dt.date(2026, 3, 9),
            OFFICIAL,
            stale(PRICE, q("260000", "EUR")),
        ),
        doc(
            "avis_modificatif",
            "sale_notice",
            "pdf",
            dt.date(2026, 9, 28),
            OFFICIAL,
            supports(PRICE, q("245000", "EUR")),
            supports(OCCUPANCY, "libre"),
        ),
        doc(
            "courriel_2024",
            "email",
            "eml",
            dt.date(2024, 6, 3),
            COMMERCIAL,
            stale(OCCUPANCY, "occupé"),
        ),
        doc(
            "plaquette",
            "sales_memo",
            "pdf",
            dt.date(2026, 4, 2),
            COMMERCIAL,
            conflicts(FOOTPRINT, q("40", "percent")),
        ),
        doc(
            "tableau_surfaces",
            "area_schedule",
            "xlsx",
            dt.date(2026, 10, 9),
            OWNER,
            supports(GROUND, q("115", "m2")),
            supports(FIRST, q("115", "m2")),
            supports(SECOND, q("80", "m2")),
            conflicts(TOTAL, q("330", "m2")),
        ),
        doc(
            "lot2_certificat",
            "planning_certificate",
            "pdf",
            dt.date(2026, 5, 20),
            OFFICIAL,
            distractor(ZONE, "UIG16"),
        ),
        doc(
            "lot2_cadastre",
            "cadastral_extract",
            "pdf",
            dt.date(2026, 10, 2),
            OFFICIAL,
            distractor(PARCEL, "RK 9999"),
        ),
    ),
    traps=(
        Trap(TrapType.UNIT, AREA, ("extrait_cadastral", "bornage")),
        Trap(TrapType.BURIED, HEIGHT, ("reglement_zone",)),
        Trap(TrapType.BURIED, SETBACK, ("reglement_zone",)),
        Trap(TrapType.CONTRADICTION, FOOTPRINT, ("plaquette", "reglement_zone")),
        Trap(TrapType.DATE_LOGIC, CERTIFICATE, ("certificat_urbanisme",)),
        Trap(TrapType.SUPERSEDED, PRICE, ("avis_initial", "avis_modificatif")),
        Trap(TrapType.SUPERSEDED, OCCUPANCY, ("courriel_2024", "avis_modificatif")),
        Trap(TrapType.ARITHMETIC, TOTAL, ("tableau_surfaces",), (GROUND, FIRST, SECOND)),
        Trap(TrapType.DISTRACTOR, ZONE, ("lot2_certificat",)),
        Trap(TrapType.DISTRACTOR, PARCEL, ("lot2_cadastre",)),
        Trap(TrapType.MISSING, SOIL, ()),
        Trap(TrapType.MISSING, POLLUTION, ()),
    ),
)

_LOT2 = f"Lot n° 2 : autre terrain de la même consultation, sans lien avec le lot n° 1. {_FICTION}"

SCENARIO = Scenario(
    spec=SPEC,
    wording=Wording(
        site=f"Lot n° 1 : terrain nu situé 8 rue Alfred de Vigny à Metz (Moselle). {_FICTION}",
        labels={
            "floor:rdc": "Rez-de-chaussée",
            "floor:r1": "Premier étage",
            "floor:r2": "Deuxième étage",
            "projet": "Total du projet",
        },
        intros={"lot2_certificat": _LOT2, "lot2_cadastre": _LOT2},
    ),
)
