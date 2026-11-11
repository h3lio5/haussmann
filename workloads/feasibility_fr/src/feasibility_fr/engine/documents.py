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
