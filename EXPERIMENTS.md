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
| E004 | 2026-11-11 | Finder fixes: repeats refused not fatal, search shows the matching passage, common date forms accepted, document types described, second pass for untouched facts | The first run's failures were the finder not finding or recording facts; these five fixes should raise engine recall above 90 % and traps above the baselines' 69 % | dev | engine: recall 76% (75/99), traps 65% (47/72); baselines unchanged | one_prompt: recall 93% (92/99), traps 69% (50/72); naive_rag: recall 94% (93/99), traps 69% (50/72); engine: recall 95% (94/99), traps 90% (65/72) | 0.0493 | kept |
| E005 | 2026-11-11 | Cross-check pass: code sends the finder to matching pages of documents a fact does not cite yet; units accepted as documents spell them | Remaining failures were one-sided: only one source recorded. Contradiction should rise from 4/9 toward 9/9 without losing distractor traps | dev | engine: recall 95% (94/99), traps 90% (65/72); baselines unchanged | one_prompt: recall 93% (92/99), traps 69% (50/72); naive_rag: recall 94% (93/99), traps 69% (50/72); engine: recall 91% (90/99), traps 92% (66/72) | 0.0799 | kept; contradiction 9/9 and superseded 9/9, but distractor fell from 8/9 to 3/9 and 3 values were invented: the cross-check led the finder into documents about another property. Follow-up in E006 |
