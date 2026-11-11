# Scenario card: metz_vigny (dev)

A bare plot that the city of Metz offered for sale through a call for projects. The site and its public facts are real. Every document in `files/` is synthetic and says so in its first paragraph; prices, dates, occupancy history and the proposed building are invented.

## Site

8 rue Alfred de Vigny, Metz (Moselle), parcel RK 357, 1,138 m². The city's notice states that the parcel belongs to the city's private domain, so no private owner is involved.

- Notice: https://metz.fr/fichiers/2025/05/12/AAP_Alfred_de_Vigny_printemps_2025.pdf (read 2026-11-11)

## Real facts and where they come from

| Fact | Value | Source |
|---|---|---|
| Parcel reference, land area | RK 357, 1,138 m² | land registry, `public/cadastre.json` |
| Owner | Ville de Metz | the city's notice |
| Zone | UIL27 (zone UI) | zoning portal, `public/zone.json` |
| Street setback | 4 m minimum | regulation PDF, article 6, PDF page 47 |
| Footprint limit | 30 % of the land unit | regulation PDF, article 9.1, PDF page 49 |
| Maximum height | 9 m at the eaves (R+2) in sector UIL27 | regulation PDF, article 10, PDF page 51 |
| Flood risk | "oui" | risk report, `public/risks.json`, field `inondation.present` |

Regulation PDF (not stored here, 4.2 MB): `57463_reglement_20260921.pdf`, "P.L.U. de Metz, version 20260921", from https://data.geopf.fr/annexes/gpu/documents/DU_57463/8062eb05c0a5291d0a6a31e8ee3e9c6e/57463_reglement_20260921.pdf, sha256 `601fa92430e6ff9ebdbdfd23a5239404075912915d906326ce470f140daeddb4`, downloaded 2026-11-11.

## Things a reader should know

- **Two plans disagree.** The city's notice of May 2025 cites a metropolitan plan, zone "UILd", with a 40 % footprint limit. The regulation published on the national zoning portal is the city plan, sector UIL27, with 30 %. Which one is legally in force was not determined. The answer key follows the portal's document, and the 40 % figure is used as the value in the low-authority sales brochure.
- **Rules are simplified to one number each.** The real articles carry exceptions (existing buildings, corner plots, a ridge height, a 24 m building band) that the answer key leaves out.
- **Flood risk mirrors one flag.** The risk report says the risk exists at commune level and is "not known" at the address.

## Invented

Asking prices and both sale notices' wording, the 2024 email, the planning certificate and its date, the survey and notary notes as documents, the proposed building's floor areas, and both "lot 2" documents. No soil or pollution study exists in the file on purpose.

## Traps

| Type | Fact | Documents |
|---|---|---|
| Unit | land area, written only in hectares | `extrait_cadastral`, `bornage` |
| Buried | maximum height, street setback | `reglement_zone` (page 8 of 9) |
| Contradiction | footprint limit, 40 % in a brochure against 30 % in the regulation | `plaquette`, `reglement_zone` |
| Date logic | planning certificate dated March 2023, long expired | `certificat_urbanisme` |
| Superseded | asking price; occupancy | `avis_initial` to `avis_modificatif`; `courriel_2024` to `avis_modificatif` |
| Arithmetic | proposed floor area total, 330 stated against 310 summed | `tableau_surfaces` |
| Distractor | zone; parcel reference | `lot2_certificat`; `lot2_cadastre` |
| Missing | soil study; pollution study | none |

## Public data and licences

`public/sources.json` lists each frozen file with its URL, date, hash and licence as stated by the publisher. The risk report's licence could not be confirmed on 2026-11-11 because the service's licence pages returned errors; confirm before redistributing `public/risks.json` elsewhere.
