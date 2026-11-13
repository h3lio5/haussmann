# Benchmark report

## dev: metz_vigny, champagnole_ecole, sainte_genevieve_gendarmerie

| system | recall | precision | bait | invented | abstention | citations | recall spread | failed runs | cost USD | mean latency s |
|---|---|---|---|---|---|---|---|---|---|---|
| one_prompt | 85% (153/180) | 92% (153/166) | 8% (13/166) | 0% (0/166) | 89% (16/18) | 96% (147/153) | 74% to 100% | 0/9 | 0.0705 | 10.9 |
| naive_rag | 86% (154/180) | 81% (154/189) | 12% (23/189) | 6% (12/189) | 50% (9/18) | 99% (153/154) | 74% to 100% | 0/9 | 0.0249 | 8.3 |
| engine | 93% (167/180) | 97% (167/172) | 2% (3/172) | 1% (2/172) | 100% (18/18) | 91% (152/167) | 74% to 100% | 0/9 | 0.1597 | 88.9 |

Traps passed, by type:

| system | arithmetic | buried | contradiction | date_logic | distractor | missing | superseded | unit |
|---|---|---|---|---|---|---|---|---|
| one_prompt | 28% (5/18) | 78% (14/18) | 6% (1/18) | 44% (8/18) | 100% (18/18) | 89% (16/18) | 83% (15/18) | 67% (12/18) |
| naive_rag | 28% (5/18) | 100% (18/18) | 0% (0/18) | 39% (7/18) | 100% (18/18) | 50% (9/18) | 50% (9/18) | 83% (15/18) |
| engine | 94% (17/18) | 94% (17/18) | 72% (13/18) | 100% (18/18) | 83% (15/18) | 100% (18/18) | 100% (18/18) | 100% (18/18) |
