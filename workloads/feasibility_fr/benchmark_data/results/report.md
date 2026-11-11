# Benchmark report

## dev: metz_vigny, champagnole_ecole

| system | recall | precision | bait | invented | abstention | citations | recall spread | failed runs | cost USD | mean latency s |
|---|---|---|---|---|---|---|---|---|---|---|
| one_prompt | 88% (87/99) | 88% (87/99) | 12% (12/99) | 0% (0/99) | 100% (9/9) | 97% (84/87) | 87% to 89% | 0/6 | 0.0109 | 6.1 |
| naive_rag | 88% (87/99) | 88% (87/99) | 12% (12/99) | 0% (0/99) | 100% (9/9) | 100% (87/87) | 87% to 89% | 0/6 | 0.0094 | 6.5 |

Traps passed, by type:

| system | arithmetic | buried | contradiction | date_logic | distractor | missing | superseded | unit |
|---|---|---|---|---|---|---|---|---|
| one_prompt | 0% (0/9) | 100% (9/9) | 0% (0/9) | 33% (3/9) | 100% (9/9) | 100% (9/9) | 67% (6/9) | 100% (9/9) |
| naive_rag | 0% (0/9) | 100% (9/9) | 0% (0/9) | 33% (3/9) | 100% (9/9) | 100% (9/9) | 67% (6/9) | 100% (9/9) |
