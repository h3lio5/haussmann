# C9 plan: one large dev scenario

## Why

The two dev scenarios hold 21 and 22 pages. At that size a single prompt reads everything, retrieval keeps most pages, and three trap instances per type move by chance between runs. A large scenario is where the three systems should separate and where a change to the finder becomes measurable.

## Where it fits

Nothing in the platform changes. The scenario is one more `Scenario` in the workload; the generator, scorer, runner and report take it as they take the other two.

```
Scenario(spec, wording, totals, filler)  ->  generate  ->  files/ + manifest.json  ->  run  ->  report
```

## Size and content

| | Current scenarios | Large scenario |
|---|---|---|
| Documents | 13 to 14 | about 45 |
| Pages | 21 to 22 | about 200 |
| Tokens | about 12,000 | about 200,000 (the model's window is 262,144) |
| Required facts | 14 to 19 | about 30 |
| Traps | 12 | 24, three of each type |
| Scanned pages | 2 | at most 15 |

- **Size comes from documents a real file has**, not from one long document: the zoning regulation split into one document per zone, four leases with amendments, a rent roll, an area schedule, surveys, notary notes, risk reports, notices, a brochure and about fifteen emails.
- **Difficulty comes from near misses.** The regulation documents for the other zones state the same rules with other values. Only the planning certificate says which zone the site is in, so the right height is two steps away. Those values are planted as distractor statements, so the scorer counts taking one as bait.
- **A larger pool of boilerplate.** The ten paragraphs used today would repeat about 250 times. The scenario carries its own pool of about 80 paragraphs.
- **Only the fourteen existing document types**, so the engine's document descriptions and every existing recording stay untouched.

## Tasks

| ID | Task | Done when |
|---|---|---|
| C9.1 | `Scenario.filler`, defaulting to the current pool | the two existing scenarios generate byte-identical files |
| C9.2 | Site and public data: parcel, zone, rules, risks, frozen with provenance | `public/` and `CARD.md` written; real values tested against the frozen data |
| C9.3 | The spec: facts, documents, traps, wording | it validates; 24 traps, three per type; about 200 pages |
| C9.4 | Generated files committed; scenario tests extended | all gates pass |
| C9.5 | Live run, row in `EXPERIMENTS.md` | the report shows the three systems on the large scenario next to the small ones |

## Expected outcome, stated before the run

- One prompt still fits but should lose recall on facts deep in the file.
- Retrieval keeps well under a quarter of the pages and should miss facts it does not retrieve.
- The engine's cost should grow with the number of facts, not with the number of pages.

If one prompt still scores as it does today, that is a result and is reported as one.

## Cost

About 0.15 USD for the first live run (three samples of each system, plus scan transcription and document cards). The printed upper estimate will be near 1 USD, under the 2 USD line.

## Open choice

The site. The two existing scenarios use a real parcel sold by a commune, with rules copied from the real regulation.

1. A third real site, found the same way. More varied facts; needs research into a public sale and its regulation.
2. The Metz site again with a full-size file. No research, but the same public facts appear in two scenarios.
