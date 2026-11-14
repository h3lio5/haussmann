"""Held-out scenario: a former presbytery put up for sale by an invented commune.

Written after the engine was frozen, under the rules of docs/notes/heldout.md. The site is
fictional; see benchmark_data/heldout_presbytere/CARD.md.
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

SEED = 7101

PARCEL = FactKey("site", "parcel_ref")
AREA = FactKey("site", "land_area")
ZONE = FactKey("site", "zone")
HEIGHT = FactKey("site", "max_height")
LEVELS = FactKey("site", "max_levels")
FOOTPRINT = FactKey("site", "footprint_limit")
CERTIFICATE = FactKey("site", "planning_certificate_date")
FLOOD = FactKey("site", "flood_risk")
OWNER_KEY = FactKey("site", "owner")
PRICE = FactKey("site", "asking_price")
POLLUTION = FactKey("site", "pollution_study")
PRACTICE_RENT = FactKey("lease:cabinet", "annual_rent")
PRACTICE_END = FactKey("lease:cabinet", "lease_end")
GARAGE_RENT = FactKey("lease:garage", "annual_rent")
GARAGE_END = FactKey("lease:garage", "lease_end")
TOTAL_RENT = FactKey("loyers", "annual_rent")
GROUND = FactKey("floor:rdc", "floor_area")
FIRST = FactKey("floor:etage", "floor_area")
ATTIC = FactKey("floor:combles", "floor_area")
TOTAL_AREA = FactKey("batiment", "floor_area")

_FICTION = "Site et document fictifs, établis pour un banc d'essai."
_COMMUNE = "Commune de Villeneuve-les-Aulnes"

SPEC = ScenarioSpec(
    id="heldout_presbytere",
    split=Split.HELDOUT,
    seed=SEED,
    gold=(
        GoldFact(PARCEL, "AB 142"),
        GoldFact(AREA, q("2310", "m2")),
        GoldFact(ZONE, "UA"),
        GoldFact(HEIGHT, q("12", "m")),
        GoldFact(LEVELS, "R+2"),
        GoldFact(FOOTPRINT, q("60", "percent")),
        GoldFact(CERTIFICATE, dt.date(2023, 1, 16)),
        GoldFact(FLOOD, "non"),
        GoldFact(OWNER_KEY, _COMMUNE),
        GoldFact(PRICE, q("215000", "EUR")),
        GoldFact(POLLUTION, None),
        GoldFact(PRACTICE_RENT, q("9600", "EUR/year")),
        GoldFact(PRACTICE_END, dt.date(2028, 3, 31)),
        GoldFact(GARAGE_RENT, q("1500", "EUR/year")),
        GoldFact(GARAGE_END, dt.date(2030, 12, 31)),
        GoldFact(TOTAL_RENT, q("11100", "EUR/year")),
        GoldFact(GROUND, q("180", "m2")),
        GoldFact(FIRST, q("165", "m2")),
        GoldFact(ATTIC, q("70", "m2")),
        GoldFact(TOTAL_AREA, q("415", "m2")),
    ),
    documents=(
        doc(
            "certificat_urbanisme",
            "planning_certificate",
            "pdf",
            dt.date(2023, 1, 16),
            OFFICIAL,
            supports(ZONE, "UA"),
            supports(CERTIFICATE, dt.date(2023, 1, 16)),
        ),
        doc(
            "reglement_urbanisme",
            "zoning_rules",
            "pdf",
            dt.date(2024, 3, 11),
            OFFICIAL,
            supports(HEIGHT, q("12", "m")),
            supports(LEVELS, "R+2"),
            supports(FOOTPRINT, q("60", "percent")),
        ),
        doc(
            "releve_cadastral",
            "cadastral_extract",
            "pdf",
            dt.date(2026, 9, 14),
            OFFICIAL,
            supports(PARCEL, "AB 142"),
            supports(AREA, q("0.2310", "ha")),
        ),
        doc(
            "attestation_notaire",
            "title_note",
            "pdf",
            dt.date(2025, 2, 3),
            OFFICIAL,
            supports(OWNER_KEY, _COMMUNE),
            scanned=True,
        ),
        doc(
            "etat_risques",
            "risk_report",
            "pdf",
            dt.date(2026, 9, 14),
            OFFICIAL,
            supports(FLOOD, "non"),
        ),
        doc(
            "appel_candidatures_initial",
            "sale_notice",
            "pdf",
            dt.date(2025, 11, 3),
            OFFICIAL,
            stale(PRICE, q("240000", "EUR")),
        ),
        doc(
            "appel_candidatures_rectifie",
            "sale_notice",
            "pdf",
            dt.date(2026, 6, 22),
            OFFICIAL,
            supports(PRICE, q("215000", "EUR")),
        ),
        doc(
            "dossier_agence",
            "sales_memo",
            "pdf",
            dt.date(2026, 7, 6),
            COMMERCIAL,
            conflicts(FOOTPRINT, q("80", "percent")),
            conflicts(LEVELS, "R+3"),
        ),
        doc(
            "convention_cabinet",
            "lease",
            "pdf",
            dt.date(2019, 4, 1),
            OFFICIAL,
            supports(PRACTICE_RENT, q("800", "EUR/month")),
            supports(PRACTICE_END, dt.date(2028, 3, 31)),
        ),
        doc(
            "convention_garage",
            "lease",
            "pdf",
            dt.date(2022, 1, 1),
            OFFICIAL,
            stale(GARAGE_RENT, q("1200", "EUR/year")),
            supports(GARAGE_END, dt.date(2030, 12, 31)),
            scanned=True,
        ),
        doc(
            "avenant_garage",
            "lease_amendment",
            "pdf",
            dt.date(2025, 1, 1),
            OFFICIAL,
            supports(GARAGE_RENT, q("1500", "EUR/year")),
        ),
        doc(
            "tableau_loyers",
            "rent_roll",
            "xlsx",
            dt.date(2026, 9, 1),
            OWNER,
            conflicts(TOTAL_RENT, q("10800", "EUR/year")),
        ),
        doc(
            "recapitulatif_surfaces",
            "area_schedule",
            "xlsx",
            dt.date(2026, 9, 1),
            OWNER,
            supports(GROUND, q("180", "m2")),
            supports(FIRST, q("165", "m2")),
            supports(ATTIC, q("70", "m2")),
            supports(TOTAL_AREA, q("415", "m2")),
        ),
        doc(
            "courriel_mairie",
            "email",
            "eml",
            dt.date(2026, 9, 21),
            COMMERCIAL,
            supports(FLOOD, "non"),
        ),
        doc(
            "lot_b_certificat",
            "planning_certificate",
            "pdf",
            dt.date(2026, 5, 4),
            OFFICIAL,
            distractor(ZONE, "UC"),
        ),
        doc(
            "lot_b_releve_cadastral",
            "cadastral_extract",
            "pdf",
            dt.date(2026, 9, 14),
            OFFICIAL,
            distractor(PARCEL, "AB 977"),
        ),
    ),
    traps=(
        Trap(TrapType.UNIT, AREA, ("releve_cadastral",)),
        Trap(TrapType.UNIT, PRACTICE_RENT, ("convention_cabinet",)),
        Trap(TrapType.CONTRADICTION, FOOTPRINT, ("dossier_agence", "reglement_urbanisme")),
        Trap(TrapType.CONTRADICTION, LEVELS, ("dossier_agence", "reglement_urbanisme")),
        Trap(
            TrapType.SUPERSEDED,
            PRICE,
            ("appel_candidatures_initial", "appel_candidatures_rectifie"),
        ),
        Trap(TrapType.SUPERSEDED, GARAGE_RENT, ("convention_garage", "avenant_garage")),
        Trap(TrapType.DISTRACTOR, ZONE, ("lot_b_certificat",)),
        Trap(TrapType.DISTRACTOR, PARCEL, ("lot_b_releve_cadastral",)),
        Trap(TrapType.BURIED, HEIGHT, ("reglement_urbanisme",)),
        Trap(TrapType.DATE_LOGIC, CERTIFICATE, ("certificat_urbanisme",)),
        Trap(TrapType.MISSING, POLLUTION, ()),
        Trap(TrapType.ARITHMETIC, TOTAL_RENT, ("tableau_loyers",), (PRACTICE_RENT, GARAGE_RENT)),
    ),
)

_LOT_B = (
    f"Lot B : autre bien mis en vente par la commune, distinct de l'ancien presbytère. {_FICTION}"
)

SCENARIO = Scenario(
    spec=SPEC,
    totals={
        TOTAL_RENT: (PRACTICE_RENT, GARAGE_RENT),
        TOTAL_AREA: (GROUND, FIRST, ATTIC),
    },
    wording=Wording(
        site=f"Ancien presbytère, 4 place de l'Église à Villeneuve-les-Aulnes. {_FICTION}",
        labels={
            "lease:cabinet": "Convention du cabinet paramédical",
            "lease:garage": "Location du garage",
            "loyers": "Total des loyers",
            "floor:rdc": "Rez-de-chaussée",
            "floor:etage": "Étage",
            "floor:combles": "Combles aménagés",
            "batiment": "Total du bâtiment",
        },
        intros={
            "lot_b_certificat": _LOT_B,
            "lot_b_releve_cadastral": _LOT_B,
        },
        style=draw(SEED),
    ),
)
