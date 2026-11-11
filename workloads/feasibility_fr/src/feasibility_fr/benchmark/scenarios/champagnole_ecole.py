"""Dev scenario: a former school offered for sale by the commune of Champagnole.

What is real and what is invented is recorded in benchmark_data/champagnole_ecole/CARD.md.
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
from haussmann.evalkit.groundtruth import FactKey, GoldFact, ScenarioSpec, Split, Trap, TrapType

PARCEL = FactKey("site", "parcel_ref")
AREA = FactKey("site", "land_area")
ZONE = FactKey("site", "zone")
LEVELS = FactKey("site", "max_levels")
SETBACK = FactKey("site", "street_setback")
CERTIFICATE = FactKey("site", "planning_certificate_date")
FLOOD = FactKey("site", "flood_risk")
OWNER_KEY = FactKey("site", "owner")
PRICE = FactKey("site", "asking_price")
SOIL = FactKey("site", "soil_study")
CLUB_RENT = FactKey("lease:club", "annual_rent")
CLUB_END = FactKey("lease:club", "lease_end")
WORKSHOP_RENT = FactKey("lease:atelier", "annual_rent")
WORKSHOP_END = FactKey("lease:atelier", "lease_end")
TOTAL_RENT = FactKey("loyers", "annual_rent")
BASEMENT = FactKey("floor:sous_sol", "floor_area")
GROUND = FactKey("floor:rdc", "floor_area")
FIRST = FactKey("floor:r1", "floor_area")
TOTAL_AREA = FactKey("batiment", "floor_area")

_FICTION = "Document fictif établi pour un banc d'essai."

SPEC = ScenarioSpec(
    id="champagnole_ecole",
    split=Split.DEV,
    seed=3909,
    gold=(
        GoldFact(PARCEL, "AI 308"),
        GoldFact(AREA, q("6615", "m2")),
        GoldFact(ZONE, "UB"),
        GoldFact(LEVELS, "R+4+C"),
        GoldFact(SETBACK, q("6", "m")),
        GoldFact(CERTIFICATE, dt.date(2022, 11, 8)),
        GoldFact(FLOOD, "non"),
        GoldFact(OWNER_KEY, "Commune de Champagnole"),
        GoldFact(PRICE, q("128000", "EUR")),
        GoldFact(SOIL, None),
        GoldFact(CLUB_RENT, q("3600", "EUR/year")),
        GoldFact(CLUB_END, dt.date(2027, 8, 31)),
        GoldFact(WORKSHOP_RENT, q("2400", "EUR/year")),
        GoldFact(WORKSHOP_END, dt.date(2024, 6, 30)),
        GoldFact(TOTAL_RENT, q("6000", "EUR/year")),
        GoldFact(BASEMENT, q("310", "m2")),
        GoldFact(GROUND, q("1240", "m2")),
        GoldFact(FIRST, q("620", "m2")),
        GoldFact(TOTAL_AREA, q("2170", "m2")),
    ),
    documents=(
        doc(
            "certificat_urbanisme",
            "planning_certificate",
            "pdf",
            dt.date(2022, 11, 8),
            OFFICIAL,
            supports(ZONE, "UB"),
            supports(CERTIFICATE, dt.date(2022, 11, 8)),
        ),
        doc(
            "reglement_zone",
            "zoning_rules",
            "pdf",
            dt.date(2023, 9, 28),
            OFFICIAL,
            supports(SETBACK, q("6", "m")),
            supports(LEVELS, "R+4+C"),
        ),
        doc(
            "extrait_cadastral",
            "cadastral_extract",
            "pdf",
            dt.date(2026, 10, 5),
            OFFICIAL,
            supports(PARCEL, "AI 308"),
            supports(AREA, q("0.6615", "ha")),
        ),
        doc(
            "note_notaire",
            "title_note",
            "pdf",
            dt.date(2025, 6, 12),
            OFFICIAL,
            supports(OWNER_KEY, "Commune de Champagnole"),
            scanned=True,
        ),
        doc(
            "etat_risques",
            "risk_report",
            "pdf",
            dt.date(2026, 10, 5),
            OFFICIAL,
            supports(FLOOD, "non"),
        ),
        doc(
            "avis_cession",
            "sale_notice",
            "pdf",
            dt.date(2025, 9, 15),
            OFFICIAL,
            supports(PRICE, q("128000", "EUR")),
        ),
        doc(
            "plaquette",
            "sales_memo",
            "pdf",
            dt.date(2025, 10, 1),
            COMMERCIAL,
            conflicts(PRICE, q("150000", "EUR")),
            conflicts(LEVELS, "R+6"),
        ),
        doc(
            "bail_club",
            "lease",
            "pdf",
            dt.date(2021, 9, 1),
            OFFICIAL,
            stale(CLUB_RENT, q("3000", "EUR/year")),
            supports(CLUB_END, dt.date(2027, 8, 31)),
            scanned=True,
        ),
        doc(
            "avenant_club",
            "lease_amendment",
            "pdf",
            dt.date(2023, 9, 1),
            OFFICIAL,
            supports(CLUB_RENT, q("3600", "EUR/year")),
        ),
        doc(
            "bail_atelier",
            "lease",
            "pdf",
            dt.date(2020, 7, 1),
            OFFICIAL,
            supports(WORKSHOP_RENT, q("200", "EUR/month")),
            supports(WORKSHOP_END, dt.date(2024, 6, 30)),
        ),
        doc(
            "etat_locatif",
            "rent_roll",
            "xlsx",
            dt.date(2026, 9, 30),
            OWNER,
            conflicts(TOTAL_RENT, q("5400", "EUR/year")),
        ),
        doc(
            "tableau_surfaces",
            "area_schedule",
            "xlsx",
            dt.date(2026, 9, 30),
            OWNER,
            supports(BASEMENT, q("310", "m2")),
            supports(GROUND, q("1240", "m2")),
            supports(FIRST, q("620", "m2")),
            conflicts(TOTAL_AREA, q("2270", "m2")),
        ),
        doc(
            "courriel_risques",
            "email",
            "eml",
            dt.date(2026, 10, 6),
            COMMERCIAL,
            supports(FLOOD, "non"),
        ),
        doc(
            "lot2_note_notaire",
            "title_note",
            "pdf",
            dt.date(2025, 6, 12),
            OFFICIAL,
            distractor(OWNER_KEY, "SCI des Sapins"),
        ),
    ),
    traps=(
        Trap(TrapType.UNIT, AREA, ("extrait_cadastral",)),
        Trap(TrapType.CONTRADICTION, LEVELS, ("plaquette", "reglement_zone")),
        Trap(TrapType.BURIED, SETBACK, ("reglement_zone",)),
        Trap(TrapType.DATE_LOGIC, CERTIFICATE, ("certificat_urbanisme",)),
        Trap(TrapType.DISTRACTOR, OWNER_KEY, ("lot2_note_notaire",)),
        Trap(TrapType.CONTRADICTION, PRICE, ("plaquette", "avis_cession")),
        Trap(TrapType.MISSING, SOIL, ()),
        Trap(TrapType.SUPERSEDED, CLUB_RENT, ("bail_club", "avenant_club")),
        Trap(TrapType.UNIT, WORKSHOP_RENT, ("bail_atelier",)),
        Trap(TrapType.DATE_LOGIC, WORKSHOP_END, ("bail_atelier",)),
        Trap(TrapType.ARITHMETIC, TOTAL_RENT, ("etat_locatif",), (CLUB_RENT, WORKSHOP_RENT)),
        Trap(TrapType.ARITHMETIC, TOTAL_AREA, ("tableau_surfaces",), (BASEMENT, GROUND, FIRST)),
    ),
)

SCENARIO = Scenario(
    spec=SPEC,
    wording=Wording(
        site=(
            f"Ancienne école Hubert Reeves, rue du Colonel Gruyer à Champagnole (Jura). {_FICTION}"
        ),
        labels={
            "lease:club": "Convention avec le club associatif",
            "lease:atelier": "Convention avec l'atelier",
            "loyers": "Total des loyers",
            "floor:sous_sol": "Sous-sol",
            "floor:rdc": "Rez-de-chaussée",
            "floor:r1": "Premier étage",
            "batiment": "Total du bâtiment",
        },
        intros={
            "lot2_note_notaire": (
                "Lot n° 2 : autre bien de la même consultation, sans lien avec l'ancienne "
                f"école. {_FICTION}"
            ),
        },
    ),
)
