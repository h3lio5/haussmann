# Scenario card: champagnole_ecole (dev)

A former school that the commune of Champagnole offered for sale through a call for expressions of interest. The site and its public facts are real. Every document in `files/` is synthetic and says so in its first paragraph; the occupancy agreements, rents, dates and floor areas are invented.

## Site

Former Hubert Reeves school, rue du Colonel Gruyer, Champagnole (Jura), parcel AI 308, 6,615 m². The commune is the seller, so no private owner is involved.

- Notice: https://www.champagnole.fr/content/uploads/2025/09/Cahier-des-charges-2.pdf (read 2026-11-11)

## Real facts and where they come from

| Fact | Value | Source |
|---|---|---|
| Parcel reference, land area | AI 308, 6,615 m² | land registry, `public/cadastre.json` |
| Owner | Commune de Champagnole | the commune's notice |
| Zone | UB | zoning portal, `public/zone.json`; also the notice |
| Street setback | 6 m minimum | regulation PDF, article UB-6, PDF page 31 |
| Maximum height | R+4+C (storeys, not metres) | regulation PDF, article UB-10, PDF page 32 |
| Asking price | 128,000 EUR | the notice, as the State valuation |
| Flood risk | "non" | risk report, `public/risks.json`, field `inondation.present` |

Regulation PDF (not stored here, 5.1 MB): `39097_reglement_20230928.pdf` from https://data.geopf.fr/annexes/gpu/documents/DU_39097/fe2845643938a599697bf7be285f8789/39097_reglement_20230928.pdf, sha256 `b7c0e4d295d3fdb866da68bb443c541d1b5aae4669d3dd68db390c4515f9f352`, downloaded 2026-11-11.

## Things a reader should know

- **No footprint limit.** Article UB-9 imposes none, so this scenario has no footprint fact.
- **Height is in storeys.** The regulation gives no figure in metres, so the fact is a text value.
- **The sale covers part of the parcel.** The notice sells 5,125 m² to be split from the 6,615 m² parcel. The answer key uses the whole parcel as registered.
- **The valuation stands in for an asking price.** The notice gives a State valuation of 128,000 EUR, with a margin, not a fixed price.
- **The real building is vacant.** The notice says it is free of occupation. The two occupancy agreements here are invented to carry rent and date facts.
- **Rules are simplified to one value each.** The real articles carry exceptions that the answer key leaves out.

## Invented

Both occupancy agreements, the amendment, the rent roll, all floor areas (the ground floor uses the roughly 1,240 m² footprint the notice mentions), the planning certificate and its date, the brochure, the email, the notary notes as documents, and the "lot 2" document. No soil study exists in the file on purpose.

## Traps

| Type | Fact | Documents |
|---|---|---|
| Unit | land area in hectares; workshop rent per month | `extrait_cadastral`; `bail_atelier` |
| Buried | street setback | `reglement_zone` (page 8 of 9) |
| Contradiction | storeys, R+6 in a brochure against R+4+C; price, 150,000 against 128,000 | `plaquette` with `reglement_zone`; `plaquette` with `avis_cession` |
| Date logic | planning certificate of November 2022, long expired; workshop agreement ended June 2024 | `certificat_urbanisme`; `bail_atelier` |
| Superseded | club rent, 3,000 raised to 3,600 by amendment | `bail_club` to `avenant_club` |
| Arithmetic | total rent, 5,400 stated against 6,000 summed; total floor area, 2,270 against 2,170 | `etat_locatif`; `tableau_surfaces` |
| Distractor | owner | `lot2_note_notaire` |
| Missing | soil study | none |

## Public data and licences

`public/sources.json` lists each frozen file with its URL, date, hash and licence as stated by the publisher. The risk report's licence could not be confirmed on 2026-11-11 because the service's licence pages returned errors; confirm before redistributing `public/risks.json` elsewhere.
