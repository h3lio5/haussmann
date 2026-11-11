"""How benchmark values and boilerplate are written in French documents."""

import datetime as dt
from collections.abc import Mapping
from decimal import Decimal

from haussmann.evalkit.groundtruth import AttributeDef, Quantity, Value

UNIT_TEXT: Mapping[str, str] = {
    "m": "m",
    "m2": "m²",
    "ha": "ha",
    "percent": "%",
    "EUR": "€",
    "kEUR": "k€",
    "MEUR": "M€",
    "EUR/year": "€ par an",
    "EUR/month": "€ par mois",
    "EUR/quarter": "€ par trimestre",
}

_MONTHS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def format_number(amount: Decimal) -> str:
    """French convention: spaces between thousands, a comma before decimals."""
    sign = "-" if amount < 0 else ""
    whole, _, fraction = f"{abs(amount).normalize():f}".partition(".")
    groups: list[str] = []
    while whole:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    return sign + " ".join(groups) + (f",{fraction}" if fraction else "")


def format_date(date: dt.date) -> str:
    day = "1er" if date.day == 1 else str(date.day)
    return f"{day} {_MONTHS[date.month - 1]} {date.year}"


def format_value(value: Value, attribute: AttributeDef) -> str:
    if isinstance(value, Quantity):
        return f"{format_number(value.amount)} {UNIT_TEXT[value.unit]}"
    if isinstance(value, dt.date):
        return format_date(value)
    return value


FILLER: tuple[str, ...] = (
    "Les dispositions du présent règlement s'appliquent sans préjudice des prescriptions prises "
    "au titre des législations spécifiques concernant les servitudes d'utilité publique affectant "
    "l'utilisation du sol, lesquelles sont reportées en annexe du plan local d'urbanisme.",
    "Les constructions, aménagements et installations doivent, par leur situation, leur "
    "architecture, leurs dimensions ou l'aspect extérieur des bâtiments ou ouvrages à édifier ou à "
    "modifier, ne pas porter atteinte au caractère ou à l'intérêt des lieux avoisinants.",
    "Tout terrain doit être desservi par une voie publique ou privée dont les caractéristiques "
    "correspondent à la destination des constructions projetées et permettent l'approche du "
    "matériel de lutte contre l'incendie ainsi que la collecte des déchets ménagers.",
    "Le raccordement au réseau public de distribution d'eau potable est obligatoire pour toute "
    "construction ou installation nouvelle qui requiert une alimentation en eau, selon les "
    "prescriptions techniques du gestionnaire du réseau.",
    "Les eaux pluviales sont gérées à la parcelle par infiltration lorsque la nature du sol le "
    "permet ; à défaut, le débit de fuite rejeté au réseau collecteur est limité conformément au "
    "zonage d'assainissement en vigueur.",
    "Les aires de stationnement des véhicules correspondant aux besoins des constructions et "
    "installations doivent être réalisées en dehors des voies publiques, sur le terrain d'assiette "
    "du projet ou dans son environnement immédiat.",
    "Les espaces libres de toute construction font l'objet d'un traitement paysager de qualité ; "
    "les plantations existantes sont maintenues ou remplacées par des plantations équivalentes "
    "d'essences locales.",
    "Les clôtures, lorsqu'elles sont édifiées, participent à la qualité de l'espace public ; leur "
    "hauteur et leur aspect sont définis en cohérence avec les clôtures avoisinantes et le "
    "caractère de la rue.",
    "Les ouvrages techniques nécessaires au fonctionnement des services publics ou d'intérêt "
    "collectif peuvent déroger aux règles d'implantation et de hauteur lorsque leurs "
    "caractéristiques techniques l'imposent.",
    "En cas de sinistre, la reconstruction à l'identique d'un bâtiment régulièrement édifié est "
    "autorisée dans un délai de dix ans, nonobstant toute disposition contraire du présent "
    "règlement, sauf si un plan de prévention des risques en dispose autrement.",
)
