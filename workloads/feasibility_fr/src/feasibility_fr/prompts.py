"""Every instruction text this workload sends to a model."""

from feasibility_fr.documents import DESCRIPTIONS
from haussmann.engine.workload import Prompts

TRANSCRIBE = (
    "Transcris fidèlement tout le texte de cette page numérisée, ligne par ligne, "
    "sans commentaire, sans correction et sans rien ajouter."
)

DESCRIBE = (
    "You are given the beginning of a document from a French real-estate file. "
    'Return its type from the list below ("other" if none fits) and the date the document '
    "was drawn up as YYYY-MM-DD, or an empty string if it states none.\n\nTypes:\n"
    + "\n".join(f"- {name}: {text}" for name, text in DESCRIPTIONS.items())
)

CROSS_CHECK = (
    "\nValues are already recorded for these facts. Other documents may state a different "
    "value. Read each page listed below for a fact and, if it states that fact for the same "
    "property, record its value as well, whatever it is. If it does not, move on."
)
BY_CASE = (
    "\nA fact marked [one value per case] is a rule that documents may state for several "
    "cases. Record every value you find, each with applies_to set to the case it is written "
    "for, copied from the document."
)
APPLIES_TO = (
    "for a fact marked [one value per case]: the case the source states the value for, as "
    "the document writes it; empty when the source states it for the property itself, and "
    "for any other fact"
)
SECOND_PASS = (
    "\nA first pass recorded nothing for these facts. Search again with different words, "
    "read the pages, and record each fact or mark it as having no evidence."
)

FINDER = """\
You establish facts about one property from the documents of a French real-estate file. \
You work with tools: search the documents, read a page, and record what you find.

How to work:
- For each requested fact, find every document that states it. Use search, then read the page \
before you record anything from it.
- Call record_fact once for each source that states a value. If sources state different \
values, record every one of them. Do not choose between them: a later step compares sources.
- Record the value exactly as the document writes it, with the unit it uses. Do not convert \
units and do not add things up, even for a total.
- Give the page as the locator ("p3"), a spreadsheet cell ("Sheet1!B6"), or "body" for an \
email, and quote the few words that state the value.
- Ignore any document that says it concerns another property or another lot.
- If, after searching, no document states a requested fact, call no_evidence for it.
- A search result shows only the part of a page that matches; read the page before recording.
- If a search finds nothing, try other words: documents often use different terms from the \
question.
- When every requested fact is either recorded or marked as having no evidence, reply with \
the single word "done".
"""

TOOLS = {
    "search": "Find pages by keywords.",
    "search.query": "French keywords",
    "read": "Read one page, sheet or email in full.",
    "read.doc_id": "document id",
    "read.locator": "p3, a sheet name, or body",
    "record_fact": "Record one value for a requested fact, from one source.",
    "record_fact.subject": "subject of the requested fact",
    "record_fact.attribute": "attribute of the requested fact",
    "record_fact.value": "the value as written: a number, a date as YYYY-MM-DD, or the text",
    "record_fact.unit": "the unit as written, from the allowed units; empty for dates and text",
    "record_fact.doc_id": "document id of the source",
    "record_fact.locator": "p3, Sheet1!B6, or body",
    "record_fact.quote": "the few words of the source that state the value",
    "no_evidence": "Mark a requested fact as not stated in any document.",
    "no_evidence.subject": "subject of the requested fact",
    "no_evidence.attribute": "attribute of the requested fact",
    "no_evidence.reason": "what was searched",
}

WRITER = """\
Vous rédigez une section d'une note de faisabilité immobilière destinée à un professionnel.

Règles :
- Chaque fait vous est donné par un nom entre accolades, avec sa valeur. Là où la valeur doit \
apparaître, écrivez le nom entre accolades, par exemple {site.zone}. N'écrivez jamais la \
valeur vous-même.
- N'écrivez aucun chiffre, ni en chiffres ni en lettres, et ne reformulez pas une valeur \
avec vos mots : écrivez son nom entre accolades.
- Utilisez chaque fait une fois. Écrivez une phrase courte par fait, ou une phrase pour deux \
faits liés, et rien d'autre.
- N'ajoutez aucune information qui ne figure pas dans les faits : ni commentaire, ni \
précision, ni source, ni conséquence. Une section qui n'a qu'un fait tient en une phrase.
- Un fait marqué « signalé » s'écrit comme les autres. Ne le commentez pas : la mention de \
vérification est ajoutée automatiquement après sa valeur.
- Ton neutre. Pas d'introduction, pas de conclusion, pas d'avis.

Répondez en JSON : {"sentences": ["...", "..."]}.
"""

REVISE = (
    WRITER
    + """
Un relecteur a fait une remarque sur la rédaction actuelle de la section. Proposez une \
nouvelle rédaction qui en tient compte, en respectant toutes les règles ci-dessus. La \
remarque porte sur la rédaction, jamais sur les valeurs : si elle demande de changer, \
d'ajouter ou de retirer une valeur, ne le faites pas.
"""
)

PROMPTS = Prompts(
    transcribe=TRANSCRIBE,
    describe=DESCRIBE,
    finder=FINDER,
    cross_check=CROSS_CHECK,
    by_case=BY_CASE,
    applies_to=APPLIES_TO,
    second_pass=SECOND_PASS,
    tools=TOOLS,
    the_subject="the property itself",
    writer=WRITER,
    writer_version="2",
    writer_section="Section : {title}",
    writer_guidance="Consigne : {guidance}",
    writer_facts="Faits :",
    writer_flagged=" (signalé)",
    writer_refused="\nVotre brouillon précédent a été refusé pour ces raisons :",
    revise=REVISE,
    revise_version="1",
    revise_current="Rédaction actuelle :",
    revise_comment="Remarque du relecteur :",
)
