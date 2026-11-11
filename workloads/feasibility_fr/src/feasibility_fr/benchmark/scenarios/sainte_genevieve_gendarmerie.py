"""Large dev scenario: a former gendarmerie offered for sale by the commune that owns it.

38 documents and about 200 pages. The regulation is split by zone, so the rules of the
other zones sit next to the ones that apply. What is real and what is invented is recorded
in benchmark_data/sainte_genevieve_gendarmerie/CARD.md.
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
from feasibility_fr.benchmark.wording import LONG_FILLER
from haussmann.coretypes.values import FactKey
from haussmann.evalkit.groundtruth import GoldFact, ScenarioSpec, Split, Trap, TrapType

PARCEL = FactKey("site", "parcel_ref")
AREA = FactKey("site", "land_area")
ZONE = FactKey("site", "zone")
HEIGHT = FactKey("site", "max_height")
LEVELS = FactKey("site", "max_levels")
FOOTPRINT = FactKey("site", "footprint_limit")
SETBACK = FactKey("site", "street_setback")
CERTIFICATE = FactKey("site", "planning_certificate_date")
FLOOD = FactKey("site", "flood_risk")
OWNER_KEY = FactKey("site", "owner")
SOIL = FactKey("site", "soil_study")
POLLUTION = FactKey("site", "pollution_study")

BUILT_PRICE = FactKey("lot:bati", "asking_price")
LAND_PRICE = FactKey("lot:terrain", "asking_price")
TOTAL_PRICE = FactKey("ensemble", "asking_price")

CLUB_RENT = FactKey("lease:association", "annual_rent")
CLUB_END = FactKey("lease:association", "lease_end")
WORKSHOP_RENT = FactKey("lease:atelier", "annual_rent")
WORKSHOP_END = FactKey("lease:atelier", "lease_end")
DWELLING_RENT = FactKey("lease:logement", "annual_rent")
DWELLING_END = FactKey("lease:logement", "lease_end")
GARAGE_RENT = FactKey("lease:garage", "annual_rent")
GARAGE_END = FactKey("lease:garage", "lease_end")
MAST_RENT = FactKey("lease:antenne", "annual_rent")
MAST_END = FactKey("lease:antenne", "lease_end")
TOTAL_RENT = FactKey("loyers", "annual_rent")
RENTS = (CLUB_RENT, WORKSHOP_RENT, DWELLING_RENT, GARAGE_RENT, MAST_RENT)

DWELLINGS = FactKey("floor:logements", "floor_area")
LODGE = FactKey("floor:pavillon", "floor_area")
OFFICES = FactKey("floor:bureaux", "floor_area")
TOTAL_AREA = FactKey("batiment", "floor_area")

_FICTION = "Document fictif établi pour un banc d'essai."
_SELLER = "Commune de Châtillon-Coligny"
_EMPTY_EMAILS = tuple(f"courriel_{number:02d}" for number in range(1, 13))
_EMAIL_DATES = (
    dt.date(2025, 5, 6),
    dt.date(2025, 5, 19),
    dt.date(2025, 6, 3),
    dt.date(2025, 6, 24),
    dt.date(2025, 9, 9),
    dt.date(2025, 11, 17),
    dt.date(2026, 1, 12),
    dt.date(2026, 2, 26),
    dt.date(2026, 4, 8),
    dt.date(2026, 6, 15),
    dt.date(2026, 8, 31),
    dt.date(2026, 9, 22),
)
_REGULATION_DATE = dt.date(2025, 9, 23)

SPEC = ScenarioSpec(
    id="sainte_genevieve_gendarmerie",
    split=Split.DEV,
    seed=45278,
    gold=(
        GoldFact(PARCEL, "AC 198"),
        GoldFact(AREA, q("4838", "m2")),
        GoldFact(ZONE, "Uc"),
        GoldFact(HEIGHT, q("8", "m")),
        GoldFact(LEVELS, "R+1+C"),
        GoldFact(FOOTPRINT, q("30", "percent")),
        GoldFact(SETBACK, q("5", "m")),
        GoldFact(CERTIFICATE, dt.date(2024, 2, 12)),
        GoldFact(FLOOD, "oui"),
        GoldFact(OWNER_KEY, _SELLER),
        GoldFact(SOIL, None),
        GoldFact(POLLUTION, None),
        GoldFact(BUILT_PRICE, q("332345", "EUR")),
        GoldFact(LAND_PRICE, q("26000", "EUR")),
        GoldFact(TOTAL_PRICE, q("358345", "EUR")),
        GoldFact(CLUB_RENT, q("4800", "EUR/year")),
        GoldFact(CLUB_END, dt.date(2029, 12, 31)),
        GoldFact(WORKSHOP_RENT, q("6000", "EUR/year")),
        GoldFact(WORKSHOP_END, dt.date(2028, 6, 30)),
        GoldFact(DWELLING_RENT, q("6240", "EUR/year")),
        GoldFact(DWELLING_END, dt.date(2025, 9, 30)),
        GoldFact(GARAGE_RENT, q("900", "EUR/year")),
        GoldFact(GARAGE_END, dt.date(2026, 3, 31)),
        GoldFact(MAST_RENT, q("7500", "EUR/year")),
        GoldFact(MAST_END, None),
        GoldFact(TOTAL_RENT, q("25440", "EUR/year")),
        GoldFact(DWELLINGS, q("384", "m2")),
        GoldFact(LODGE, q("45", "m2")),
        GoldFact(OFFICES, q("175", "m2")),
        GoldFact(TOTAL_AREA, q("604", "m2")),
    ),
    documents=(
        # Planning
        doc(
            "certificat_urbanisme",
            "planning_certificate",
            "pdf",
            dt.date(2024, 2, 12),
            OFFICIAL,
            supports(ZONE, "Uc"),
            supports(CERTIFICATE, dt.date(2024, 2, 12)),
            scanned=True,
        ),
        doc("reglement_dispositions_generales", "zoning_rules", "pdf", _REGULATION_DATE, OFFICIAL),
        doc(
            "reglement_zone_ua",
            "zoning_rules",
            "pdf",
            _REGULATION_DATE,
            OFFICIAL,
            distractor(HEIGHT, q("12", "m")),
            distractor(LEVELS, "R+2+C"),
        ),
        doc(
            "reglement_zone_ub",
            "zoning_rules",
            "pdf",
            _REGULATION_DATE,
            OFFICIAL,
            distractor(HEIGHT, q("9", "m")),
            distractor(FOOTPRINT, q("40", "percent")),
        ),
        doc(
            "reglement_zone_uc",
            "zoning_rules",
            "pdf",
            _REGULATION_DATE,
            OFFICIAL,
            supports(SETBACK, q("5", "m")),
            supports(FOOTPRINT, q("30", "percent")),
            supports(HEIGHT, q("8", "m")),
            supports(LEVELS, "R+1+C"),
        ),
        doc(
            "reglement_zone_uh",
            "zoning_rules",
            "pdf",
            _REGULATION_DATE,
            OFFICIAL,
            distractor(HEIGHT, q("7", "m")),
            distractor(LEVELS, "R+C"),
        ),
        doc("reglement_zone_a", "zoning_rules", "pdf", _REGULATION_DATE, OFFICIAL),
        # Land and title
        doc(
            "extrait_cadastral",
            "cadastral_extract",
            "pdf",
            dt.date(2026, 10, 12),
            OFFICIAL,
            supports(PARCEL, "AC 198"),
            supports(AREA, q("0.4838", "ha")),
        ),
        doc(
            "bornage",
            "survey",
            "pdf",
            dt.date(2011, 5, 19),
            OFFICIAL,
            supports(PARCEL, "AC 198"),
        ),
        doc(
            "note_notaire",
            "title_note",
            "pdf",
            dt.date(2025, 3, 18),
            OFFICIAL,
            supports(OWNER_KEY, _SELLER),
            scanned=True,
        ),
        doc(
            "etat_risques",
            "risk_report",
            "pdf",
            dt.date(2026, 10, 12),
            OFFICIAL,
            supports(FLOOD, "oui"),
        ),
        # Sale
        doc(
            "avis_cession",
            "sale_notice",
            "pdf",
            dt.date(2025, 4, 22),
            OFFICIAL,
            supports(PARCEL, "AC 198"),
            supports(OWNER_KEY, _SELLER),
            supports(BUILT_PRICE, q("332345", "EUR")),
            supports(LAND_PRICE, q("26000", "EUR")),
            conflicts(TOTAL_PRICE, q("358435", "EUR")),
        ),
        doc("reglement_consultation", "sale_notice", "pdf", dt.date(2025, 4, 22), OFFICIAL),
        doc(
            "plaquette",
            "sales_memo",
            "pdf",
            dt.date(2025, 5, 12),
            COMMERCIAL,
            conflicts(OWNER_KEY, "Commune de Sainte-Geneviève-des-Bois"),
            conflicts(BUILT_PRICE, q("345000", "EUR")),
        ),
        # Occupancy
        doc(
            "bail_association",
            "lease",
            "pdf",
            dt.date(2019, 1, 1),
            OFFICIAL,
            stale(CLUB_RENT, q("4200", "EUR/year")),
            supports(CLUB_END, dt.date(2029, 12, 31)),
        ),
        doc(
            "avenant_association",
            "lease_amendment",
            "pdf",
            dt.date(2023, 1, 1),
            OFFICIAL,
            supports(CLUB_RENT, q("4800", "EUR/year")),
        ),
        doc(
            "bail_atelier",
            "lease",
            "pdf",
            dt.date(2017, 7, 1),
            OFFICIAL,
            supports(WORKSHOP_RENT, q("1500", "EUR/quarter")),
            stale(WORKSHOP_END, dt.date(2026, 6, 30)),
        ),
        doc(
            "avenant_atelier",
            "lease_amendment",
            "pdf",
            dt.date(2026, 5, 4),
            OFFICIAL,
            supports(WORKSHOP_END, dt.date(2028, 6, 30)),
        ),
        doc(
            "bail_logement",
            "lease",
            "pdf",
            dt.date(2019, 10, 1),
            OFFICIAL,
            supports(DWELLING_RENT, q("520", "EUR/month")),
            supports(DWELLING_END, dt.date(2025, 9, 30)),
        ),
        doc(
            "bail_garage",
            "lease",
            "pdf",
            dt.date(2020, 4, 1),
            OFFICIAL,
            supports(GARAGE_RENT, q("900", "EUR/year")),
            supports(GARAGE_END, dt.date(2026, 3, 31)),
            scanned=True,
        ),
        doc(
            "bail_antenne",
            "lease",
            "pdf",
            dt.date(2015, 4, 1),
            OFFICIAL,
            stale(MAST_RENT, q("6800", "EUR/year")),
        ),
        doc(
            "avenant_antenne",
            "lease_amendment",
            "pdf",
            dt.date(2022, 4, 1),
            OFFICIAL,
            supports(MAST_RENT, q("7500", "EUR/year")),
            scanned=True,
        ),
        doc(
            "etat_locatif",
            "rent_roll",
            "xlsx",
            dt.date(2026, 9, 30),
            OWNER,
            supports(CLUB_RENT, q("4800", "EUR/year")),
            supports(MAST_RENT, q("7500", "EUR/year")),
            conflicts(TOTAL_RENT, q("24840", "EUR/year")),
        ),
        doc(
            "tableau_surfaces",
            "area_schedule",
            "xlsx",
            dt.date(2026, 9, 30),
            OWNER,
            supports(DWELLINGS, q("384", "m2")),
            supports(LODGE, q("45", "m2")),
            supports(OFFICES, q("175", "m2")),
            conflicts(TOTAL_AREA, q("640", "m2")),
        ),
        # Correspondence
        doc(
            "courriel_urbanisme",
            "email",
            "eml",
            dt.date(2026, 10, 14),
            COMMERCIAL,
            supports(ZONE, "Uc"),
        ),
        doc(
            "courriel_agence",
            "email",
            "eml",
            dt.date(2026, 10, 15),
            COMMERCIAL,
            conflicts(FLOOD, "non"),
        ),
        *(
            doc(doc_id, "email", "eml", date, COMMERCIAL)
            for doc_id, date in zip(_EMPTY_EMAILS, _EMAIL_DATES, strict=True)
        ),
    ),
    traps=(
        Trap(TrapType.UNIT, AREA, ("extrait_cadastral",)),
        Trap(TrapType.UNIT, WORKSHOP_RENT, ("bail_atelier",)),
        Trap(TrapType.UNIT, DWELLING_RENT, ("bail_logement",)),
        Trap(TrapType.BURIED, SETBACK, ("reglement_zone_uc",)),
        Trap(TrapType.BURIED, CLUB_END, ("bail_association",)),
        Trap(TrapType.BURIED, GARAGE_RENT, ("bail_garage",)),
        Trap(TrapType.CONTRADICTION, FLOOD, ("courriel_agence", "etat_risques")),
        Trap(TrapType.CONTRADICTION, OWNER_KEY, ("plaquette", "note_notaire")),
        Trap(TrapType.CONTRADICTION, BUILT_PRICE, ("plaquette", "avis_cession")),
        Trap(TrapType.SUPERSEDED, CLUB_RENT, ("bail_association", "avenant_association")),
        Trap(TrapType.SUPERSEDED, WORKSHOP_END, ("bail_atelier", "avenant_atelier")),
        Trap(TrapType.SUPERSEDED, MAST_RENT, ("bail_antenne", "avenant_antenne")),
        Trap(TrapType.DATE_LOGIC, CERTIFICATE, ("certificat_urbanisme",)),
        Trap(TrapType.DATE_LOGIC, DWELLING_END, ("bail_logement",)),
        Trap(TrapType.DATE_LOGIC, GARAGE_END, ("bail_garage",)),
        Trap(TrapType.ARITHMETIC, TOTAL_PRICE, ("avis_cession",), (BUILT_PRICE, LAND_PRICE)),
        Trap(TrapType.ARITHMETIC, TOTAL_RENT, ("etat_locatif",), RENTS),
        Trap(TrapType.ARITHMETIC, TOTAL_AREA, ("tableau_surfaces",), (DWELLINGS, LODGE, OFFICES)),
        Trap(
            TrapType.DISTRACTOR,
            HEIGHT,
            ("reglement_zone_ua", "reglement_zone_ub", "reglement_zone_uh"),
        ),
        Trap(TrapType.DISTRACTOR, LEVELS, ("reglement_zone_ua", "reglement_zone_uh")),
        Trap(TrapType.DISTRACTOR, FOOTPRINT, ("reglement_zone_ub",)),
        Trap(TrapType.MISSING, SOIL, ()),
        Trap(TrapType.MISSING, POLLUTION, ()),
        Trap(TrapType.MISSING, MAST_END, ()),
    ),
)


def _regulation(part: str) -> str:
    return f"Plan local d'urbanisme intercommunal - règlement écrit, {part}. {_FICTION}"


SCENARIO = Scenario(
    spec=SPEC,
    totals={
        TOTAL_PRICE: (BUILT_PRICE, LAND_PRICE),
        TOTAL_RENT: RENTS,
        TOTAL_AREA: (DWELLINGS, LODGE, OFFICES),
    },
    filler=LONG_FILLER,
    wording=Wording(
        site=(
            "Ancienne gendarmerie, 1 Terres de la Bonne Dame à Sainte-Geneviève-des-Bois "
            f"(Loiret). {_FICTION}"
        ),
        labels={
            "lot:bati": "Bâtiments et parcelle",
            "lot:terrain": "Terrain constructible détachable",
            "ensemble": "Total de la cession",
            "lease:association": "Convention avec l'association sportive",
            "lease:atelier": "Bail de l'atelier",
            "lease:logement": "Bail du logement",
            "lease:garage": "Location du garage",
            "lease:antenne": "Convention d'antenne relais",
            "loyers": "Total des loyers",
            "floor:logements": "Logements du bâtiment principal",
            "floor:pavillon": "Pavillon indépendant",
            "floor:bureaux": "Bureaux et locaux techniques",
            "batiment": "Total des bâtiments",
        },
        intros={
            "reglement_dispositions_generales": _regulation("dispositions générales"),
            "reglement_zone_ua": _regulation("zone Ua"),
            "reglement_zone_ub": _regulation("zone Ub"),
            "reglement_zone_uc": _regulation("zone Uc"),
            "reglement_zone_uh": _regulation("zone Uh"),
            "reglement_zone_a": _regulation("zone A"),
        },
        doc_labels={
            "reglement_zone_ua": "Zone Ua",
            "reglement_zone_ub": "Zone Ub",
            "reglement_zone_uc": "Zone Uc",
            "reglement_zone_uh": "Zone Uh",
        },
        lengths={
            "certificat_urbanisme": (4, 4),
            "reglement_dispositions_generales": (300, 40),
            "reglement_zone_ua": (240, 100),
            "reglement_zone_ub": (240, 100),
            "reglement_zone_uc": (240, 100),
            "reglement_zone_uh": (240, 100),
            "reglement_zone_a": (260, 0),
            "bornage": (24, 10),
            "note_notaire": (8, 4),
            "etat_risques": (30, 20),
            "avis_cession": (40, 50),
            "reglement_consultation": (80, 0),
            "plaquette": (20, 20),
            "bail_association": (70, 40),
            "bail_atelier": (60, 40),
            "bail_logement": (40, 30),
            "bail_garage": (70, 10),
            "bail_antenne": (60, 50),
            **dict.fromkeys(_EMPTY_EMAILS, (4, 2)),
        },
    ),
)
