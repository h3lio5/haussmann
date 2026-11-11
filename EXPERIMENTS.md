# Experiment log

Every change to prompts, context assembly, retrieval or model choice gets a row: rerun the benchmark on the replay cache, record the numbers, keep or revert. Dev and held-out results are separate rows and are never mixed. Failures are logged as plainly as wins.

## Columns

| Column | Content |
|---|---|
| id | `E` plus a running number, never reused |
| date | ISO date of the run |
| change | what was changed, with the commit hash |
| hypothesis | what the change was expected to do, written before the run |
| split | `dev` or `heldout` |
| before | headline metrics before the change |
| after | the same metrics after, as k/n where they are counts |
| cost_usd | live model spend for the run; 0 when replayed |
| decision | `kept`, `reverted` or `baseline` |

Headline metrics, in this order: fact recall, fact precision, traps passed, citation correctness, invented-claim rate, abstention correctness. Full reports per run live next to the replay cache.

## Log

| id | date | change | hypothesis | split | before | after | cost_usd | decision |
|---|---|---|---|---|---|---|---|---|
| E001 | 2026-11-11 | First baselines on two dev scenarios | Sets the bar for the engine; one prompt may already pass most traps | dev | - | one_prompt: recall 88% (87/99), traps 58% (42/72); naive_rag: recall 80% (79/99), traps 54% (39/72) | 0.0199 | kept |
| E002 | 2026-11-11 | Documents state their date and the prompt gives the review date | Superseded and date-logic traps were not judgeable without dates; expect both to rise | dev | one_prompt: recall 88% (87/99), traps 58% (42/72); naive_rag: recall 80% (79/99), traps 54% (39/72) | one_prompt: recall 88% (87/99), traps 62% (45/72); naive_rag: recall 88% (87/99), traps 62% (45/72) | 0.0203 | kept |
| E003 | 2026-11-11 | Engine added as a third system; all systems are told which facts are declared totals | The engine recomputes totals and reports conflicts with both sources, so it should pass the arithmetic and contradiction traps both baselines fail | dev | one_prompt: recall 88% (87/99), traps 62% (45/72); naive_rag: recall 88% (87/99), traps 62% (45/72); no engine | one_prompt: recall 93% (92/99), traps 69% (50/72); naive_rag: recall 94% (93/99), traps 69% (50/72); engine: recall 76% (75/99), traps 65% (47/72) | 0.0503 | kept |
