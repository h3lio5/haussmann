# Durable run report

Scenario `sainte_genevieve_gendarmerie`, from recordings. One run: 14 steps that call a model, 70 model calls.

## Killed with SIGKILL, then continued by a new process

Exit code -9 is the kill. A call is counted as sent when it reaches the client below the journal. Orphaned calls are calls the killed process paid for that the continued step never asked for.

| killed | before call | exit code | calls sent before | calls sent after | sent twice | orphaned | same ledger and memo |
|---|---|---|---|---|---|---|---|
| inside a finder step (find:3:pass1) | 35 of 70 | -9 | 34 | 36 | 0 | 0 | yes |
| between two steps (before find:5:pass1) | 49 of 70 | -9 | 48 | 22 | 0 | 0 | yes |
| inside the memo | 68 of 70 | -9 | 67 | 3 | 0 | 0 | yes |

## Time added by the journal

Median of 3 uninterrupted runs, engine and memo, model calls served from recordings on disk:

| journal | seconds |
|---|---|
| memory | 0.34 |
| Postgres, local | 0.58 |

## Cost per step

From the journal's record of calls: the cost the provider reported with each response, or list price times tokens when it reported none.

| step | calls | tokens in | tokens out | USD |
|---|---|---|---|---|
| find:0:pass1 | 4 | 23866 | 957 | 0.00227 |
| find:0:cross-check | 10 | 64826 | 953 | 0.00372 |
| find:1:pass1 | 9 | 76009 | 1005 | 0.00438 |
| find:1:cross-check | 3 | 24418 | 544 | 0.00232 |
| find:2:pass1 | 6 | 28100 | 271 | 0.00195 |
| find:3:pass1 | 4 | 14884 | 324 | 0.00160 |
| find:3:cross-check | 5 | 29161 | 646 | 0.00237 |
| find:4:pass1 | 4 | 20508 | 992 | 0.00224 |
| find:4:cross-check | 3 | 16100 | 597 | 0.00227 |
| find:5:pass1 | 7 | 53268 | 1153 | 0.00425 |
| find:5:cross-check | 3 | 14699 | 439 | 0.00184 |
| find:6:pass1 | 3 | 10725 | 344 | 0.00170 |
| find:6:cross-check | 3 | 19084 | 384 | 0.00287 |
| memo:4a3cf2c52d715784 | 6 | 2601 | 542 | 0.00058 |
| **total** | 70 | 398249 | 9151 | 0.03437 |

The same responses priced one by one as they were received, outside the journal: 0.03437 USD (equal). This checks that the journal stores and sums costs without loss; both figures use the same pricing function.
