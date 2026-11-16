"""The document types this workload recognises and how much each counts in a disagreement."""

from collections.abc import Mapping

OFFICIAL = 3
OWNER = 2
COMMERCIAL = 1

DOCUMENT_AUTHORITY: Mapping[str, int] = {
    "planning_certificate": OFFICIAL,
    "zoning_regulation": OFFICIAL,
    "cadastral_extract": OFFICIAL,
    "survey": OFFICIAL,
    "notary_note": OFFICIAL,
    "risk_report": OFFICIAL,
    "sale_notice": OFFICIAL,
    "lease": OFFICIAL,
    "lease_amendment": OFFICIAL,
    "rent_roll": OWNER,
    "area_schedule": OWNER,
    "sales_brochure": COMMERCIAL,
    "email": COMMERCIAL,
}
OTHER = "other"
EMAIL = "email"
TYPE_OF_FORM: Mapping[str, str] = {"eml": EMAIL}

DESCRIPTIONS: Mapping[str, str] = {
    "planning_certificate": "certificat d'urbanisme",
    "zoning_regulation": "règlement ou modification d'un plan local d'urbanisme",
    "cadastral_extract": "extrait du plan cadastral",
    "survey": "procès-verbal de bornage, plan de géomètre",
    "notary_note": "note de notaire, origine de propriété, titre",
    "risk_report": "état des risques",
    "sale_notice": "avis de cession, cahier des charges ou appel à projets publié par le vendeur",
    "lease": "bail ou convention d'occupation",
    "lease_amendment": "avenant à un bail ou à une convention",
    "rent_roll": "état locatif",
    "area_schedule": "tableau des surfaces",
    "sales_brochure": "plaquette ou note de présentation commerciale d'un mandataire",
    "email": "courriel",
}
