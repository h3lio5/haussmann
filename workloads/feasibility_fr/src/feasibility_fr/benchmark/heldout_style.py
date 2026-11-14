"""Document wording for the held-out scenarios.

Nothing here repeats the wording of `templates.py`. Each attribute has two phrasings and two
row labels, written as the document that states the fact would write it; `draw` picks one of
each with a scenario's seed, so the author does not choose (docs/notes/heldout.md, rule 7).
"""

import random
from collections.abc import Mapping

from feasibility_fr.benchmark.templates import Kind, Style

PHRASES: Mapping[str, tuple[str, str]] = {
    "parcel_ref": (
        "Référence cadastrale du terrain, section et numéro : {}.",
        "Le bien figure au cadastre sous la référence {}.",
    ),
    "zone": (
        "Le terrain relève de la zone {} du règlement d'urbanisme en vigueur.",
        "Zonage applicable au terrain : zone {}.",
    ),
    "flood_risk": (
        "Le terrain est-il exposé à un risque d'inondation : {}.",
        "Risque d'inondation recensé à l'adresse du bien : {}.",
    ),
    "pollution_study": (
        "Étude de la pollution des sols disponible au dossier : {}.",
        "Diagnostic relatif à la pollution du sol : {}.",
    ),
    "max_height": (
        "Les constructions ne peuvent dépasser une hauteur de {}.",
        "Hauteur des constructions : {} au plus.",
    ),
    "max_levels": (
        "Le gabarit autorisé est de {} au maximum.",
        "Les constructions comptent au plus {}.",
    ),
    "footprint_limit": (
        "Le coefficient d'emprise au sol est plafonné à {}.",
        "L'emprise bâtie est limitée à {} de l'unité foncière.",
    ),
    "street_setback": (
        "Un retrait d'au moins {} est imposé par rapport à la voie.",
        "Implantation des constructions en retrait de {} au minimum depuis la rue.",
    ),
    "land_area": (
        "Superficie cadastrale : {}.",
        "Le terrain développe une superficie de {}.",
    ),
    "floor_area": (
        "Surface de plancher relevée : {}.",
        "La surface de plancher mesurée est de {}.",
    ),
    "planning_certificate_date": (
        "Certificat d'urbanisme délivré en date du {}.",
        "Date de délivrance du présent certificat : {}.",
    ),
    "owner": (
        "Le propriétaire actuel est {}.",
        "Le bien est la propriété de {}.",
    ),
    "occupancy": (
        "État d'occupation du bien : {}.",
        "À ce jour, le bien est {}.",
    ),
    "asking_price": (
        "Le prix attendu par le vendeur est fixé à {}.",
        "Mise à prix : {}.",
    ),
    "annual_rent": (
        "Le loyer est fixé à {}.",
        "Redevance d'occupation : {}.",
    ),
    "lease_end": (
        "Le contrat arrive à échéance le {}.",
        "Terme du contrat : {}.",
    ),
    "soil_study": (
        "Étude géotechnique : {}.",
        "Reconnaissance de sol : {}.",
    ),
}

ROW_LABELS: Mapping[str, tuple[str, str]] = {
    "parcel_ref": ("Section et numéro", "Référence au cadastre"),
    "zone": ("Zonage", "Zone du règlement"),
    "flood_risk": ("Inondation", "Exposition aux inondations"),
    "pollution_study": ("Pollution des sols", "Étude de pollution"),
    "max_height": ("Hauteur autorisée", "Hauteur limite"),
    "max_levels": ("Gabarit", "Niveaux autorisés"),
    "footprint_limit": ("Coefficient d'emprise", "Emprise bâtie"),
    "street_setback": ("Retrait sur voie", "Marge de recul"),
    "land_area": ("Superficie", "Superficie du terrain"),
    "floor_area": ("Surface relevée", "Surface (plancher)"),
    "planning_certificate_date": ("Certificat délivré le", "Délivrance du certificat"),
    "owner": ("Titulaire du droit de propriété", "Détenteur du bien"),
    "occupancy": ("État d'occupation", "Occupation actuelle"),
    "asking_price": ("Prix attendu", "Mise à prix"),
    "annual_rent": ("Montant du loyer", "Redevance"),
    "lease_end": ("Terme", "Fin du contrat"),
    "soil_study": ("Étude géotechnique", "Reconnaissance de sol"),
}

KINDS: Mapping[str, Kind] = {
    "planning_certificate": Kind(
        "Certificat d'urbanisme (article L. 410-1 a)",
        "Vu la demande présentée, il est certifié ce qui suit quant aux règles applicables.",
        "Ce certificat est délivré à titre d'information.",
    ),
    "zoning_rules": Kind(
        "Règlement du plan local d'urbanisme intercommunal",
        "Règles applicables dans la zone.",
        filler_before=90,
        filler_after=20,
    ),
    "zoning_amendment": Kind(
        "Modification simplifiée du plan local d'urbanisme",
        "Les dispositions ci-après se substituent aux dispositions antérieures de même objet.",
    ),
    "cadastral_extract": Kind(
        "Relevé de propriété et extrait cadastral",
        "Données extraites de la documentation cadastrale.",
    ),
    "risk_report": Kind(
        "État des risques et pollutions",
        "Récapitulatif des risques auxquels le bien est exposé.",
    ),
    "title_note": Kind(
        "Attestation notariée de propriété",
        "Le notaire soussigné atteste ce qui suit au vu du titre.",
    ),
    "survey": Kind(
        "Plan de bornage et de reconnaissance de limites",
        "Les limites du terrain ont été reconnues contradictoirement avec les riverains.",
    ),
    "sale_notice": Kind(
        "Appel à candidatures pour la cession d'un bien",
        "Le vendeur fait connaître ci-après les conditions de la mise en vente.",
        "Les candidatures sont adressées au service indiqué dans le règlement.",
    ),
    "sales_memo": Kind(
        "Dossier de commercialisation",
        "Présentation établie par l'agence mandatée, sans valeur contractuelle.",
        "Informations communiquées sans garantie.",
    ),
    "lease": Kind(
        "Convention d'occupation",
        "Il est convenu entre les parties ce qui suit.",
        filler_before=8,
        filler_after=5,
    ),
    "lease_amendment": Kind(
        "Avenant n° 1 à la convention d'occupation",
        "Les parties modifient la convention comme suit, le surplus restant inchangé.",
    ),
    "area_schedule": Kind("Récapitulatif des surfaces", "Surfaces relevées par local.", table=True),
    "rent_roll": Kind(
        "Tableau des occupations et loyers",
        "Occupations en cours à la date d'établissement.",
        table=True,
    ),
    "email": Kind(
        "Vente du bien - compléments",
        "Bonjour, voici les informations complémentaires.",
        "Cordialement.",
    ),
}

DATED = ("Fait le {}.", "Date du document : {}.")
HEADINGS = ("Renseignements", "Éléments du dossier")
PREFIXES = ("{} - ", "{}. ")
ROWS = ("{name} ({subject})", "{subject}, {name}")
COLUMNS = (("Rubrique", "Donnée"), ("Poste", "Montant ou mention"))


def draw(seed: int) -> Style:
    """The wording of one scenario: for each choice, one of the two written, by its seed."""
    rng = random.Random(seed)
    return Style(
        phrases={name: rng.choice(options) for name, options in sorted(PHRASES.items())},
        row_labels={name: rng.choice(options) for name, options in sorted(ROW_LABELS.items())},
        kinds=KINDS,
        dated=rng.choice(DATED),
        heading=rng.choice(HEADINGS),
        columns=rng.choice(COLUMNS),
        prefix=rng.choice(PREFIXES),
        row=rng.choice(ROWS),
    )
