# Durable run report

Scenario `sainte_genevieve_gendarmerie`, from recordings. One run: 14 steps that call a model, 68 model calls.

## Killed with SIGKILL, then continued by a new process

Exit code -9 is the kill. A call is counted as sent when it reaches the client below the journal. Orphaned calls are calls the killed process paid for that the continued step never asked for.

| killed | before call | exit code | calls sent before | calls sent after | sent twice | orphaned | same ledger and memo |
|---|---|---|---|---|---|---|---|
| inside a finder step (find:2:pass1) | 24 of 68 | -9 | 23 | 45 | 0 | 0 | yes |
| between two steps (before find:5:pass1) | 45 of 68 | -9 | 44 | 24 | 0 | 0 | yes |
| inside the memo | 66 of 68 | -9 | 65 | 3 | 0 | 0 | yes |

## Time added by the journal

Median of 3 uninterrupted runs, engine and memo, model calls served from recordings on disk:

| journal | seconds |
|---|---|
| memory | 0.35 |
| Postgres, local | 0.60 |

## Cost per step

From the journal's record of calls: the cost the provider reported with each response, or list price times tokens when it reported none.

| step | calls | tokens in | tokens out | USD |
|---|---|---|---|---|
| find:0:pass1 | 5 | 33501 | 1496 | 0.00284 |
| find:0:cross-check | 4 | 25241 | 1127 | 0.00206 |
| find:1:pass1 | 7 | 46410 | 865 | 0.00261 |
| find:1:cross-check | 3 | 24319 | 496 | 0.00231 |
| find:2:pass1 | 9 | 43961 | 290 | 0.00217 |
| find:3:pass1 | 3 | 13208 | 438 | 0.00112 |
| find:3:cross-check | 2 | 6457 | 869 | 0.00127 |
| find:4:pass1 | 9 | 71288 | 1095 | 0.00397 |
| find:4:cross-check | 2 | 6554 | 1088 | 0.00116 |
| find:5:pass1 | 9 | 81423 | 871 | 0.00479 |
| find:5:cross-check | 3 | 14791 | 500 | 0.00161 |
| find:6:pass1 | 3 | 10674 | 344 | 0.00104 |
| find:6:cross-check | 3 | 19051 | 402 | 0.00153 |
| memo:a56f3a4d443a6b7f | 6 | 2605 | 550 | 0.00062 |
| **total** | 68 | 399483 | 10431 | 0.02911 |

The same responses priced one by one as they were received, outside the journal: 0.02911 USD (equal). This checks that the journal stores and sums costs without loss; both figures use the same pricing function.
