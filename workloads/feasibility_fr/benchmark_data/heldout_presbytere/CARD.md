# Scenario card: heldout_presbytere (held-out)

A former presbytery offered for sale by a public owner. **Everything here is invented**: the commune, the address, the parcel, the owner and every document. No real place, person or body is described; any resemblance to one is unintended. Every document says in its first paragraph that the site and the document are fictional.

This scenario was written after the engine was frozen (tag `engine-freeze-m3`), under the rules in `docs/notes/heldout.md`. The engine was never run on it before the single measured run.

## Content

Site: "Ancien presbytère, 4 place de l'Église à Villeneuve-les-Aulnes". Seller and owner: "Commune de Villeneuve-les-Aulnes". Parcel AB 142, 2,310 m², zone UA.

16 documents, 20 facts, 12 traps: unit 2 (land area in hectares, a rent per month), contradiction 2 (a brochure against the regulation on footprint and on storeys), superseded 2 (a rectified notice, a lease amendment), distractor 2 (the certificate and the cadastral record of another lot), buried 1, date logic 1 (an expired planning certificate), missing 1 (no pollution study), arithmetic 1 (a rent total that does not add up).

## Wording

The documents use none of the dev wording: other sentences for each fact, other row labels, other titles and frames. For each fact two phrasings were written and one was drawn with the scenario's seed (`benchmark/heldout_style.py`). The questions asked of the systems are worded as in dev.

## What it is not

It does not stand on a real parcel or on public data, unlike the dev scenarios. Its layouts and its boilerplate paragraphs come from the same generator as dev.
