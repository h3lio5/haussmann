# Retrieval report

For each fact that some page states, the rank of the first such page when the pages are ranked for the fact's wording. A fact counts when that rank is 5 or better, the number of results the finder's search returns.

| scenario | pages | facts | keywords | embeddings | fused |
|---|---|---|---|---|---|
| metz_vigny | 21 | 15 | 14/15 | 13/15 | 14/15 |
| champagnole_ecole | 22 | 18 | 17/18 | 16/18 | 15/18 |
| sainte_genevieve_gendarmerie | 193 | 27 | 25/27 | 22/27 | 22/27 |

## Facts that a ranking leaves below the first results

| scenario | fact | query | keywords | embeddings | fused |
|---|---|---|---|---|---|
| metz_vigny | site/parcel_ref | Le bien objet du dossier - Référence cadastrale | 12 | 4 | 5 |
| metz_vigny | site/zone | Le bien objet du dossier - Zone | 5 | 16 | 9 |
| metz_vigny | site/street_setback | Le bien objet du dossier - Recul sur rue | 2 | 6 | 3 |
| champagnole_ecole | site/parcel_ref | Le bien objet du dossier - Référence cadastrale | 15 | 3 | 6 |
| champagnole_ecole | site/zone | Le bien objet du dossier - Zone | 2 | 18 | 10 |
| champagnole_ecole | site/street_setback | Le bien objet du dossier - Recul sur rue | 3 | 12 | 6 |
| sainte_genevieve_gendarmerie | site/parcel_ref | Le bien objet du dossier - Référence cadastrale | 9 | 34 | 9 |
| sainte_genevieve_gendarmerie | site/land_area | Le bien objet du dossier - Contenance | 1 | 119 | 21 |
| sainte_genevieve_gendarmerie | site/max_height | Le bien objet du dossier - Hauteur maximale | 4 | 9 | 6 |
| sainte_genevieve_gendarmerie | site/street_setback | Le bien objet du dossier - Recul sur rue | 1 | 188 | 29 |
| sainte_genevieve_gendarmerie | site/owner | Le bien objet du dossier - Propriétaire | 67 | 61 | 70 |
