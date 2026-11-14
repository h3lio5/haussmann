"""Document templates for benchmark scenarios, keyed by `DocumentPlan.source`."""

import random
from collections.abc import Mapping
from dataclasses import dataclass, field

from feasibility_fr.french import format_date
from haussmann.evalkit.documents import Block, Body, Filler, Heading, Paragraph, Table, Template
from haussmann.evalkit.groundtruth import DocumentPlan, PlannedStatement

PHRASES: Mapping[str, str] = {
    "parcel_ref": "Le terrain est cadastré {}.",
    "zone": "Le terrain est classé en zone {} du plan local d'urbanisme.",
    "flood_risk": "Exposition au risque d'inondation : {}.",
    "pollution_study": "Diagnostic de pollution des sols : {}.",
    "max_height": "La hauteur maximale des constructions est fixée à {}.",
    "max_levels": "Le nombre de niveaux des constructions est limité à {}.",
    "footprint_limit": "L'emprise au sol des constructions ne peut excéder {} de la superficie "
    "du terrain.",
    "street_setback": "Les constructions s'implantent avec un recul minimal de {} par rapport "
    "à l'alignement.",
    "land_area": "La contenance du terrain est de {}.",
    "floor_area": "La surface de plancher s'établit à {}.",
    "planning_certificate_date": "Le certificat d'urbanisme a été délivré le {}.",
    "owner": "Le bien appartient à {}.",
    "occupancy": "Situation locative : {}.",
    "asking_price": "Le prix de vente demandé est de {}.",
    "annual_rent": "Le loyer s'élève à {}.",
    "lease_end": "Le bail prend fin le {}.",
    "soil_study": "Étude de sol : {}.",
}

ROW_LABELS: Mapping[str, str] = {
    "parcel_ref": "Référence cadastrale",
    "zone": "Zone",
    "flood_risk": "Risque d'inondation",
    "pollution_study": "Diagnostic de pollution",
    "max_height": "Hauteur maximale",
    "max_levels": "Nombre de niveaux maximal",
    "footprint_limit": "Emprise au sol maximale",
    "street_setback": "Recul sur rue",
    "land_area": "Contenance",
    "floor_area": "Surface de plancher",
    "planning_certificate_date": "Date du certificat d'urbanisme",
    "owner": "Propriétaire",
    "occupancy": "Occupation",
    "asking_price": "Prix demandé",
    "annual_rent": "Loyer",
    "lease_end": "Échéance du bail",
    "soil_study": "Étude de sol",
}


@dataclass(frozen=True, slots=True)
class Kind:
    """One document type: its title and framing, and how its statements are laid out."""

    title: str
    opening: str
    closing: str = ""
    table: bool = False
    filler_before: int = 0
    filler_after: int = 0


KINDS: Mapping[str, Kind] = {
    "planning_certificate": Kind(
        "Certificat d'urbanisme d'information",
        "Le maire certifie que les dispositions d'urbanisme applicables au terrain sont les "
        "suivantes.",
        "Le présent certificat ne vaut pas autorisation de construire.",
    ),
    "zoning_rules": Kind(
        "Plan local d'urbanisme - Règlement écrit",
        "Dispositions applicables à la zone.",
        filler_before=110,
        filler_after=14,
    ),
    "zoning_amendment": Kind(
        "Plan local d'urbanisme - Modification approuvée",
        "La présente modification remplace les dispositions antérieures de même objet.",
    ),
    "cadastral_extract": Kind(
        "Extrait du plan cadastral",
        "Informations issues du plan cadastral informatisé.",
    ),
    "risk_report": Kind(
        "État des risques",
        "Synthèse des risques recensés à l'adresse du terrain.",
    ),
    "title_note": Kind(
        "Note du notaire - Origine de propriété",
        "La présente note résume les énonciations du titre de propriété.",
    ),
    "survey": Kind(
        "Procès-verbal de bornage",
        "Le géomètre-expert soussigné a procédé à la reconnaissance des limites du terrain.",
    ),
    "sale_notice": Kind(
        "Avis de cession - cahier des charges",
        "La collectivité propriétaire porte à la connaissance des candidats les conditions de "
        "la cession.",
        "Les offres sont remises dans les formes prévues au règlement de la consultation.",
    ),
    "sales_memo": Kind(
        "Note de présentation du bien",
        "Document commercial non contractuel établi par le mandataire du vendeur.",
        "Les informations ci-dessus sont données à titre indicatif.",
    ),
    "lease": Kind(
        "Bail commercial",
        "Entre les soussignés, il a été convenu ce qui suit.",
        filler_before=6,
        filler_after=4,
    ),
    "lease_amendment": Kind(
        "Avenant au bail commercial",
        "Les parties conviennent de modifier le bail dans les conditions suivantes ; les autres "
        "clauses demeurent inchangées.",
    ),
    "area_schedule": Kind("Tableau des surfaces", "Surfaces par niveau.", table=True),
    "rent_roll": Kind("État locatif", "Situation locative à la date du document.", table=True),
    "email": Kind(
        "Dossier de cession - éléments complémentaires",
        "Bonjour, veuillez trouver ci-dessous les éléments demandés.",
        "Bien cordialement.",
    ),
}


@dataclass(frozen=True, slots=True)
class Style:
    """How a set of documents is worded: one phrase and one row label per attribute, one
    frame per document type, and the small fixed texts around them.

    `prefix` and `row` say how a subject's label is joined to a sentence and to a row label.
    """

    phrases: Mapping[str, str]
    row_labels: Mapping[str, str]
    kinds: Mapping[str, Kind]
    dated: str = "Document établi le {}."
    heading: str = "Dispositions"
    columns: tuple[str, str] = ("Désignation", "Valeur")
    prefix: str = "{} : "
    row: str = "{subject} - {name}"


@dataclass(frozen=True, slots=True)
class Wording:
    """Scenario-specific text: the site, a label per fact subject, and per-document openings.

    A document about another asset gets its own entry in `intros`. A document longer or
    shorter than its type gets an entry in `lengths`: boilerplate paragraphs before and after.
    A document whose statements all concern one thing, such as one zone of a regulation, gets
    an entry in `doc_labels`, which then replaces the subject label on every statement.

    `style` replaces how documents are worded as a whole: every phrase, row label, title and
    frame. Without one, documents use the wording of this module.
    """

    site: str
    labels: Mapping[str, str] = field(default_factory=dict[str, str])
    intros: Mapping[str, str] = field(default_factory=dict[str, str])
    lengths: Mapping[str, tuple[int, int]] = field(default_factory=dict[str, tuple[int, int]])
    doc_labels: Mapping[str, str] = field(default_factory=dict[str, str])
    style: "Style | None" = None


DEV_STYLE = Style(PHRASES, ROW_LABELS, KINDS)


def make_templates(wording: Wording) -> dict[str, Template]:
    style = wording.style or DEV_STYLE
    return {name: _template(kind, wording, style) for name, kind in style.kinds.items()}


def _template(kind: Kind, wording: Wording, style: Style) -> Template:
    def label(plan: DocumentPlan, statement: PlannedStatement) -> str:
        return wording.doc_labels.get(plan.doc_id) or wording.labels.get(statement.key.subject, "")

    def sentence(plan: DocumentPlan, statement: PlannedStatement) -> Paragraph:
        name = label(plan, statement)
        prefix = style.prefix.format(name) if name else ""
        return Paragraph(prefix + style.phrases[statement.key.attribute], (statement,))

    def row(plan: DocumentPlan, statement: PlannedStatement) -> tuple[str, PlannedStatement]:
        name = style.row_labels[statement.key.attribute]
        subject = label(plan, statement)
        return (style.row.format(subject=subject, name=name) if subject else name, statement)

    def template(plan: DocumentPlan, rng: random.Random) -> Body:
        blocks: list[Block] = [
            Paragraph(wording.intros.get(plan.doc_id, wording.site)),
            Paragraph(style.dated.format(format_date(plan.date))),
            Paragraph(kind.opening),
        ]
        before, after = wording.lengths.get(plan.doc_id, (kind.filler_before, kind.filler_after))
        if before:
            blocks.append(Filler(before))
        if kind.table:
            blocks.append(Table(style.columns, tuple(row(plan, s) for s in plan.states)))
        else:
            blocks.append(Heading(style.heading))
            blocks.extend(sentence(plan, s) for s in plan.states)
        if after:
            blocks.append(Filler(after))
        if kind.closing:
            blocks.append(Paragraph(kind.closing))
        return Body(kind.title, tuple(blocks))

    return template
