# Benchmark report

## dev: metz_vigny, champagnole_ecole

| system | recall | precision | bait | invented | abstention | citations | recall spread | failed runs | cost USD | mean latency s |
|---|---|---|---|---|---|---|---|---|---|---|
| one_prompt | 93% (92/99) | 93% (92/99) | 7% (7/99) | 0% (0/99) | 100% (9/9) | 100% (92/92) | 87% to 100% | 0/6 | 0.0098 | 6.7 |
| naive_rag | 94% (93/99) | 94% (93/99) | 6% (6/99) | 0% (0/99) | 100% (9/9) | 100% (93/93) | 87% to 100% | 0/6 | 0.0085 | 6.7 |
| engine | 76% (75/99) | 94% (75/80) | 4% (3/80) | 2% (2/80) | 100% (9/9) | 91% (68/75) | 60% to 89% | 0/6 | 0.0319 | 33.0 |

Traps passed, by type:

| system | arithmetic | buried | contradiction | date_logic | distractor | missing | superseded | unit |
|---|---|---|---|---|---|---|---|---|
| one_prompt | 56% (5/9) | 100% (9/9) | 0% (0/9) | 33% (3/9) | 100% (9/9) | 100% (9/9) | 67% (6/9) | 100% (9/9) |
| naive_rag | 56% (5/9) | 100% (9/9) | 0% (0/9) | 33% (3/9) | 100% (9/9) | 100% (9/9) | 67% (6/9) | 100% (9/9) |
| engine | 78% (7/9) | 44% (4/9) | 22% (2/9) | 67% (6/9) | 67% (6/9) | 100% (9/9) | 44% (4/9) | 100% (9/9) |
