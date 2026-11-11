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
