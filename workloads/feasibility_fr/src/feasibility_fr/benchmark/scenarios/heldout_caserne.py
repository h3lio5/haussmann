"""Held-out scenario: a former fire station sold by an invented inter-municipal body.

Written after the engine was frozen, under the rules of docs/notes/heldout.md. Its
regulation is split by zone, with the rules of two other zones in the file. The site is
fictional; see benchmark_data/heldout_caserne/CARD.md.
"""

import datetime as dt

from feasibility_fr.benchmark.heldout_style import draw
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

SEED = 8233

PARCEL = FactKey("site", "parcel_ref")
AREA = FactKey("site", "land_area")
ZONE = FactKey("site", "zone")
HEIGHT = FactKey("site", "max_height")
SETBACK = FactKey("site", "street_setback")
FOOTPRINT = FactKey("site", "footprint_limit")
CERTIFICATE = FactKey("site", "planning_certificate_date")
FLOOD = FactKey("site", "flood_risk")
OWNER_KEY = FactKey("site", "owner")
PRICE = FactKey("site", "asking_price")
SOIL = FactKey("site", "soil_study")
POLLUTION = FactKey("site", "pollution_study")
CLUB_RENT = FactKey("lease:association", "annual_rent")
CLUB_END = FactKey("lease:association", "lease_end")
STORE_RENT = FactKey("lease:entrepot", "annual_rent")
STORE_END = FactKey("lease:entrepot", "lease_end")
MAST_RENT = FactKey("lease:antenne", "annual_rent")
TOTAL_RENT = FactKey("loyers", "annual_rent")
BAY = FactKey("floor:remise", "floor_area")
UPPER = FactKey("floor:etage", "floor_area")
OFFICES = FactKey("floor:bureaux", "floor_area")
TOTAL_AREA = FactKey("batiment", "floor_area")
RENTS = (CLUB_RENT, STORE_RENT, MAST_RENT)

_FICTION = "Site et document fictifs, établis pour un banc d'essai."
_OWNER = "Communauté de communes du Val d'Aubin"

SPEC = ScenarioSpec(
    id="heldout_caserne",
    split=Split.HELDOUT,
    seed=SEED,
    gold=(
        GoldFact(PARCEL, "BK 57"),
        GoldFact(AREA, q("3480", "m2")),
        GoldFact(ZONE, "Ub"),
        GoldFact(HEIGHT, q("15", "m")),
        GoldFact(SETBACK, q("4", "m")),
        GoldFact(FOOTPRINT, q("50", "percent")),
        GoldFact(CERTIFICATE, dt.date(2024, 1, 9)),
        GoldFact(FLOOD, "oui"),
        GoldFact(OWNER_KEY, _OWNER),
        GoldFact(PRICE, q("390000", "EUR")),
        GoldFact(SOIL, None),
        GoldFact(POLLUTION, None),
        GoldFact(CLUB_RENT, q("4800", "EUR/year")),
        GoldFact(CLUB_END, dt.date(2025, 12, 31)),
        GoldFact(STORE_RENT, q("6000", "EUR/year")),
        GoldFact(STORE_END, dt.date(2029, 6, 30)),
        GoldFact(MAST_RENT, q("2600", "EUR/year")),
        GoldFact(TOTAL_RENT, q("13400", "EUR/year")),
        GoldFact(BAY, q("420", "m2")),
        GoldFact(UPPER, q("260", "m2")),
        GoldFact(OFFICES, q("95", "m2")),
        GoldFact(TOTAL_AREA, q("775", "m2")),
    ),
    documents=(
        doc(
            "certificat_urbanisme",
            "planning_certificate",
            "pdf",
            dt.date(2024, 1, 9),
            OFFICIAL,
            supports(ZONE, "Ub"),
            supports(CERTIFICATE, dt.date(2024, 1, 9)),
        ),
        doc(
            "reglement_zone_ub",
            "zoning_rules",
            "pdf",
            dt.date(2025, 4, 28),
            OFFICIAL,
            supports(HEIGHT, q("15", "m")),
            supports(SETBACK, q("4", "m")),
            supports(FOOTPRINT, q("50", "percent")),
        ),
        doc(
            "reglement_zone_ua",
            "zoning_rules",
            "pdf",
            dt.date(2025, 4, 28),
            OFFICIAL,
            distractor(FOOTPRINT, q("70", "percent")),
        ),
        doc(
            "reglement_zone_uc",
            "zoning_rules",
            "pdf",
            dt.date(2025, 4, 28),
            OFFICIAL,
            distractor(FOOTPRINT, q("30", "percent")),
        ),
        doc(
            "releve_cadastral",
            "cadastral_extract",
            "pdf",
            dt.date(2026, 8, 31),
            OFFICIAL,
            supports(PARCEL, "BK 57"),
            supports(AREA, q("3480", "m2")),
        ),
        doc(
            "plan_bornage",
            "survey",
            "pdf",
            dt.date(2018, 6, 14),
            OFFICIAL,
            supports(AREA, q("3480", "m2")),
            scanned=True,
        ),
        doc(
            "attestation_notaire",
            "title_note",
            "pdf",
            dt.date(2025, 9, 8),
            OFFICIAL,
            supports(OWNER_KEY, _OWNER),
        ),
        doc(
            "etat_risques",
            "risk_report",
            "pdf",
            dt.date(2026, 8, 31),
            OFFICIAL,
            supports(FLOOD, "oui"),
        ),
        doc(
            "dossier_agence",
            "sales_memo",
            "pdf",
            dt.date(2026, 9, 7),
            COMMERCIAL,
            conflicts(FLOOD, "non"),
        ),
        doc(
            "appel_candidatures",
            "sale_notice",
            "pdf",
            dt.date(2026, 6, 1),
            OFFICIAL,
            supports(PRICE, q("390000", "EUR")),
        ),
        doc(
            "convention_association",
            "lease",
            "pdf",
            dt.date(2020, 1, 1),
            OFFICIAL,
            supports(CLUB_RENT, q("4800", "EUR/year")),
            supports(CLUB_END, dt.date(2025, 12, 31)),
        ),
        doc(
            "convention_entrepot",
            "lease",
            "pdf",
            dt.date(2020, 7, 1),
            OFFICIAL,
            supports(STORE_RENT, q("1500", "EUR/quarter")),
            supports(STORE_END, dt.date(2029, 6, 30)),
        ),
        doc(
            "convention_antenne",
            "lease",
            "pdf",
            dt.date(2019, 2, 1),
            OFFICIAL,
            stale(MAST_RENT, q("2000", "EUR/year")),
            scanned=True,
        ),
        doc(
            "avenant_antenne",
            "lease_amendment",
            "pdf",
            dt.date(2024, 2, 1),
            OFFICIAL,
            supports(MAST_RENT, q("2600", "EUR/year")),
        ),
        doc(
            "tableau_loyers",
            "rent_roll",
            "xlsx",
            dt.date(2026, 8, 31),
            OWNER,
            conflicts(TOTAL_RENT, q("13000", "EUR/year")),
        ),
        doc(
            "recapitulatif_surfaces",
            "area_schedule",
            "xlsx",
            dt.date(2026, 8, 31),
            OWNER,
            supports(BAY, q("420", "m2")),
            supports(UPPER, q("260", "m2")),
            supports(OFFICES, q("95", "m2")),
            conflicts(TOTAL_AREA, q("757", "m2")),
        ),
        doc(
            "courriel_notaire",
            "email",
            "eml",
            dt.date(2026, 9, 15),
            COMMERCIAL,
            supports(OWNER_KEY, _OWNER),
        ),
        doc("courriel_visite", "email", "eml", dt.date(2026, 7, 2), COMMERCIAL),
        doc("courriel_calendrier", "email", "eml", dt.date(2026, 9, 28), COMMERCIAL),
    ),
    traps=(
        Trap(TrapType.UNIT, STORE_RENT, ("convention_entrepot",)),
        Trap(TrapType.CONTRADICTION, FLOOD, ("dossier_agence", "etat_risques")),
        Trap(TrapType.SUPERSEDED, MAST_RENT, ("convention_antenne", "avenant_antenne")),
        Trap(TrapType.DISTRACTOR, FOOTPRINT, ("reglement_zone_ua", "reglement_zone_uc")),
        Trap(TrapType.BURIED, HEIGHT, ("reglement_zone_ub",)),
        Trap(TrapType.BURIED, SETBACK, ("reglement_zone_ub",)),
        Trap(TrapType.DATE_LOGIC, CERTIFICATE, ("certificat_urbanisme",)),
        Trap(TrapType.DATE_LOGIC, CLUB_END, ("convention_association",)),
        Trap(TrapType.MISSING, SOIL, ()),
        Trap(TrapType.MISSING, POLLUTION, ()),
        Trap(TrapType.ARITHMETIC, TOTAL_RENT, ("tableau_loyers",), RENTS),
        Trap(TrapType.ARITHMETIC, TOTAL_AREA, ("recapitulatif_surfaces",), (BAY, UPPER, OFFICES)),
    ),
)


def _regulation(zone: str) -> str:
    return f"Règlement du plan local d'urbanisme intercommunal, zone {zone}. {_FICTION}"


SCENARIO = Scenario(
    spec=SPEC,
    totals={
        TOTAL_RENT: RENTS,
        TOTAL_AREA: (BAY, UPPER, OFFICES),
    },
    wording=Wording(
        site=f"Ancienne caserne des pompiers, 12 rue des Tanneurs à Saint-Aubin-du-Val. {_FICTION}",
        labels={
            "lease:association": "Convention de l'association de secourisme",
            "lease:entrepot": "Location de l'entrepôt",
            "lease:antenne": "Convention d'antenne relais",
            "loyers": "Total des loyers",
            "floor:remise": "Remise des véhicules",
            "floor:etage": "Étage",
            "floor:bureaux": "Bureaux",
            "batiment": "Total du bâtiment",
        },
        intros={
            "reglement_zone_ua": _regulation("Ua"),
            "reglement_zone_ub": _regulation("Ub"),
            "reglement_zone_uc": _regulation("Uc"),
        },
        doc_labels={
            "reglement_zone_ua": "Zone Ua",
            "reglement_zone_ub": "Zone Ub",
            "reglement_zone_uc": "Zone Uc",
        },
        lengths={
            "reglement_zone_ua": (70, 30),
            "reglement_zone_ub": (70, 30),
            "reglement_zone_uc": (70, 30),
        },
        style=draw(SEED),
    ),
)
