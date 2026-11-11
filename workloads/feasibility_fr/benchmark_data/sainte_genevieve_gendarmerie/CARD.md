# Scenario card: sainte_genevieve_gendarmerie (dev, large)

A former gendarmerie that the commune owning it offered for sale through a call for expressions of interest. The site and its public facts are real. Every document in `files/` is synthetic and says so in its first paragraph; the occupancy agreements, rents, dates and the split of floor areas are invented.

This is the large scenario: 38 documents, 193 pages, about 516,000 characters, 30 required facts and 24 traps, three of each type.

## Site

Former gendarmerie, 1 Terres de la Bonne Dame, Sainte-Geneviève-des-Bois (Loiret), parcel AC 198, 4,838 m². The seller is the commune of Châtillon-Coligny, which owns a site located in the neighbouring commune, so no private owner is involved.

- Notice: https://www.chatillon-coligny.fr/wp-content/uploads/2025/04/16-2025-Cahier_des_Charges_Appel_Manifestation_Gendarmerie.pdf (read 2026-11-11, sha256 `6a63d64ee543ec6a4d84f9ca38fc5fde1fde72891af0a4733a9c50d5e469d9ca`)

## Real facts and where they come from

| Fact | Value | Source |
|---|---|---|
| Parcel reference, land area | AC 198, 4,838 m² | land registry, `public/cadastre.json`; also the notice |
| Owner | Commune de Châtillon-Coligny | the notice |
| Zone | Uc | zoning portal, `public/zone.json`; the notice does not name the zone |
| Street setback | 5 m minimum | regulation PDF, zone Uc, article 2.1.1, PDF page 52 |
| Footprint limit | 30 % | regulation PDF, zone Uc, article 2.1.4, PDF page 53 |
| Maximum height | 8 m at the ridge, stated as ground floor + 1 storey + attic | regulation PDF, zone Uc, article 2.1.5, PDF page 54 |
| Valuation of buildings and parcel | 332,345 EUR | the notice, as the State valuation |
| Valuation of the buildable land | 26,000 EUR for 2,000 m² | the notice |
| Total floor area | 604 m², of which 429 m² housing | the notice |
| Flood risk | "oui" | risk report, `public/risks.json`, field `inondation.present` |

Rules of the other zones, used as near misses, read in the same PDF:

| Zone | Height | Storeys | Footprint | PDF page |
|---|---|---|---|---|
| Ua | 12 m | ground floor + 2 + attic | not regulated | 19 |
| Ub | 9 m | ground floor + 1 + attic | 40 % | 36 |
| Uh | 7 m | ground floor + attic | 30 % | 70 |

Regulation PDF (not stored here, 6.0 MB, 201 pages): `200067676_reglement_20250923.pdf` from https://data.geopf.fr/annexes/gpu/documents/DU_200067676/0d0387a7b857a7876f84d8fdb3f6dfbb/200067676_reglement_20250923.pdf, sha256 `1f1d988641742bdb9f4f4f34c803284af0a4a9f0fb49262d79f5469be51ec917`, downloaded 2026-11-11.

## Things a reader should know

- **The regulation is split by zone.** The real regulation is one PDF. Here each zone is its own document, and every rule sentence starts with its zone ("Zone Ua : …"). Only the planning certificate and one email say the site is in zone Uc, so the applicable height is two steps away.
- **Rules of other zones that equal the site's are left out.** Zone Ub also has a 5 m setback and the same storeys, and zone Uh the same footprint; a bait may not equal the true value.
- **Height is the ridge height.** The article also gives 6 m at the parapet for flat roofs; the answer key uses the ridge figure.
- **The valuation stands in for an asking price.** The notice's sentence leaves open whether the 26,000 EUR is part of the 332,345 EUR. The answer key treats them as two lots and their sum, 358,345 EUR, as the total.
- **The real buildings are disused.** The notice describes them as disused, in poor condition and containing asbestos. The five occupancy agreements are invented to carry rent and date facts.
- **The split of floor area is invented.** Only the 604 m² total, the 429 m² of housing and a 45 m² dwelling in a separate building come from the notice.
- **Rules are simplified to one value each.** The real articles carry exceptions that the answer key leaves out.

## Invented

All five occupancy agreements and their three amendments, the rent roll, the split of floor areas, the planning certificate and its date, the brochure, the fourteen emails, the survey and the notary note as documents, the consultation rules, and all boilerplate. No soil study, no pollution study and no end date for the antenna agreement exist in the file on purpose.

## Traps

| Type | Fact | Documents |
|---|---|---|
| Unit | land area in hectares; workshop rent per quarter; dwelling rent per month | `extrait_cadastral`; `bail_atelier`; `bail_logement` |
| Buried | street setback (page 15 of 20); association agreement end (page 5 of 7); garage rent, in a scanned lease (page 5 of 5) | `reglement_zone_uc`; `bail_association`; `bail_garage` |
| Contradiction | flood risk, "non" in an agent's email against "oui"; owner, the wrong commune in a brochure; price, 345,000 against 332,345 | `courriel_agence` with `etat_risques`; `plaquette` with `note_notaire`; `plaquette` with `avis_cession` |
| Superseded | association rent, 4,200 raised to 4,800; workshop lease end, extended to June 2028; antenna rent, 6,800 raised to 7,500 | lease to amendment, three times |
| Date logic | planning certificate of February 2024, expired; dwelling lease ended September 2025; garage agreement ended March 2026 | `certificat_urbanisme`; `bail_logement`; `bail_garage` |
| Arithmetic | total price, 358,435 stated against 358,345 summed; total rent, 24,840 against 25,440; total floor area, 640 against 604 | `avis_cession`; `etat_locatif`; `tableau_surfaces` |
| Distractor | height, storeys and footprint of other zones | `reglement_zone_ua`, `reglement_zone_ub`, `reglement_zone_uh` |
| Missing | soil study; pollution study; end of the antenna agreement | none |

## Public data and licences

`public/sources.json` lists each frozen file with its URL, date, hash and licence as stated by the publisher. All three publishers state an open licence (Licence Ouverte / Open Licence) without giving a version.
