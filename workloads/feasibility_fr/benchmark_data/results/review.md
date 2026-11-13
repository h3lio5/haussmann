# Review report

Scenario `champagnole_ecole`. An expert sets `site/owner`, which the engine had left as an open question; then a comment asks for a rewording.

## After the edit

| measure | value |
|---|---|
| sections rewritten | 2 of 8 (site, open) |
| model calls for the rebuild | 1 |
| cost of the rebuild, USD | 0.00011 |
| approvals still valid | 6 of 8 |
| digits typed by the model | 0 |

| section | value | before | after |
|---|---|---|---|
| site | site.owner | absent | Commune de Champagnole |
| open | site.owner#open | Le bien objet du dossier - Propriétaire : aucun document ne l'établit. | absent |

Section `site`:

- removed: Sa référence cadastrale est AI 308.
- removed: Il est situé en zone UB.
- added: Le propriétaire du terrain est la Commune de Champagnole.
- added: La référence cadastrale du terrain est AI 308.
- added: Le terrain est situé en zone UB.

Section `open`:

- removed: Le bien objet du dossier - Propriétaire : aucun document ne l'établit.

## After the comment

Comment on `site`: Regroupez la référence cadastrale et la contenance dans une seule phrase.

| measure | value |
|---|---|
| proposal | holds, accepted |
| model calls | 1 |
| cost, USD | 0.00013 |
| digits typed by the model | 0 |
| facts stated in the memo | 18 of 18 |

- Le terrain objet du dossier, d'une contenance de {site.land_area}, porte la référence cadastrale {site.parcel_ref}.
- Le propriétaire du terrain est la {site.owner}.
- Le terrain est situé en zone {site.zone}.
