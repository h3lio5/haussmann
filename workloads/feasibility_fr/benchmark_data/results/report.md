# Benchmark report

## dev: metz_vigny, champagnole_ecole

| system | recall | precision | bait | invented | abstention | citations | recall spread | failed runs | cost USD | mean latency s |
|---|---|---|---|---|---|---|---|---|---|---|
| one_prompt | 88% (87/99) | 87% (87/100) | 12% (12/100) | 1% (1/100) | 89% (8/9) | 100% (87/87) | 87% to 89% | 0/6 | 0.0127 | 7.4 |
| naive_rag | 80% (79/99) | 82% (79/96) | 16% (15/96) | 2% (2/96) | 100% (9/9) | 100% (79/79) | 72% to 87% | 0/6 | 0.0072 | 7.2 |

Traps passed, by type:

| system | arithmetic | buried | contradiction | date_logic | distractor | missing | superseded | unit |
|---|---|---|---|---|---|---|---|---|
| one_prompt | 0% (0/9) | 100% (9/9) | 0% (0/9) | 11% (1/9) | 100% (9/9) | 89% (8/9) | 67% (6/9) | 100% (9/9) |
| naive_rag | 0% (0/9) | 67% (6/9) | 0% (0/9) | 0% (0/9) | 100% (9/9) | 100% (9/9) | 67% (6/9) | 100% (9/9) |
