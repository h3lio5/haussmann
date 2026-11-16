"""The feasibility memo workload, as the engine receives it."""

import re
from collections.abc import Mapping

from feasibility_fr.documents import DOCUMENT_AUTHORITY, TYPE_OF_FORM
from feasibility_fr.french import UNIT_NAMES, format_date, format_value, parse_date
from feasibility_fr.prompts import PROMPTS
from feasibility_fr.schema import ATTRIBUTES
from haussmann.buildkit.spec import Section, Spec
from haussmann.coretypes.values import FactKey
from haussmann.engine.workload import (
    ISSUE,
    OPEN,
    CaseForm,
    DateRules,
    Deliverable,
    DocumentTypes,
    Language,
    Workload,
)

MAIN_SUBJECT = "site"
ZONE = FactKey(MAIN_SUBJECT, "zone")
ZONE_RULES = ("max_height", "max_levels", "footprint_limit", "street_setback")
DEPENDS_ON: Mapping[str, FactKey] = dict.fromkeys(ZONE_RULES, ZONE)
CASE_FORMS: Mapping[FactKey, CaseForm] = {ZONE: CaseForm(re.compile(r"zone \w+"), "Zone Ua")}

# A planning certificate is valid for 18 months from its date (code de l'urbanisme, art. L410-1).
DATES = DateRules(
    valid_for_months={"planning_certificate_date": 18},
    end_dates=frozenset({"lease_end"}),
)

FLAG_MARK = " (à vérifier, voir « Points à résoudre »)"

MEMO = Spec(
    "feasibility_memo",
    "1",
    (
        Section(
            "site",
            "Le site et sa propriété",
            "prose",
            ("parcel_ref", "land_area", "owner", "zone"),
            "Situer le terrain : sa référence, sa contenance, son propriétaire, son zonage.",
        ),
        Section(
            "rules",
            "Règles d'urbanisme",
            "prose",
            (
                "max_height",
                "max_levels",
                "footprint_limit",
                "street_setback",
                "planning_certificate_date",
            ),
            "Énoncer les règles applicables au terrain, puis le certificat d'urbanisme.",
        ),
        Section(
            "risks",
            "Risques et études",
            "prose",
            ("flood_risk", "soil_study", "pollution_study"),
            "Dire ce que le dossier établit sur les risques et les études disponibles.",
        ),
        Section(
            "occupancy",
            "Occupation et revenus",
            "prose",
            ("occupancy", "annual_rent", "lease_end"),
            "Présenter chaque occupation avec son loyer et son échéance, puis le total.",
        ),
        Section(
            "areas",
            "Surfaces",
            "prose",
            ("floor_area",),
            "Donner les surfaces par partie, puis le total.",
        ),
        Section(
            "price",
            "Prix",
            "prose",
            ("asking_price",),
            "Donner le prix par lot, puis le total.",
        ),
        Section("issues", "Points à résoudre", "listing", (ISSUE,)),
        Section("open", "Questions ouvertes", "listing", (OPEN,)),
    ),
)

REASONS: Mapping[str, str] = {
    "recomputed from its parts": "valeur recalculée à partir de ses composantes",
    "higher-authority source": "source de plus forte autorité",
    "later source": "source la plus récente",
    "ended before the review date": "échéance dépassée à la date de revue",
}

WORKLOAD = Workload(
    schema=ATTRIBUTES,
    main_subject=MAIN_SUBJECT,
    documents=DocumentTypes(DOCUMENT_AUTHORITY, TYPE_OF_FORM),
    dates=DATES,
    cases=CASE_FORMS,
    language=Language(
        format_date=format_date,
        format_value=format_value,
        parse_date=parse_date,
        unit_names=UNIT_NAMES,
        reasons=REASONS,
        expired="valable {months} mois, expiré le {date}",
    ),
    prompts=PROMPTS,
    deliverable=Deliverable(
        spec=MEMO,
        title="Note de faisabilité",
        review_date="Date de revue : {date}",
        flag_mark=FLAG_MARK,
        nothing="Aucun élément.",
        open_question="{label} : aucun document ne l'établit.",
        issue="{label} : {parts}.",
        separator=" ; ",
        stated="les documents donnent {values}",
        undecided="non tranché, à arbitrer par le relecteur",
        kept="valeur retenue : {value} ({reason})",
    ),
)
