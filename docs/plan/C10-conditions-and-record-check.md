# C10 plan: facts that hold under a condition, and a check when a fact is recorded

## Why

On the large scenario (E007) the engine has the lowest recall of the three systems, 68 % against 75 %. Two causes account for 15 of its 26 misses.

| Loss | Misses | Cause |
|---|---|---|
| Height, storeys, footprint | 9 of 9 | The finder records the rule of every zone. Settling sees several values of equal standing and escalates. Nothing ties a rule to the zone of the site, although the zone is found. |
| Rents per quarter or per month, and the total rent | 6 of 9 | The finder records 6 000 EUR per year and quotes "1 500 € par trimestre". The verifier rejects it, as it should. The schema already converts a quarterly rent; the finder was told not to convert and did anyway. |

The other misses (owner never found, an agent's email typed as a sale notice) are not in this slice.

## Where it fits

```
finder --record_fact--> ledger --verify--> settled facts --> submission
          ^ change 2              ^ change 1
```

- Change 1 is in the ledger record, the `record_fact` tool and the settling code. It is called by `verify`, once per run, as today.
- Change 2 is in the `record_fact` tool only. The verifier is unchanged and stays the final check.

## Change 1: a fact may hold under a condition

A zoning rule is true for a zone, not for the file. The ledger should say so, and code should use it.

| Piece | Where | Structure |
|---|---|---|
| Condition on a fact | `ledger` | `NewFact.holds_when: Condition \| None`, with `Condition(key: FactKey, value: str)`: "this value holds when `key` is `value`" |
| Which facts depend on which | workload, `engine/spec.py` | `RequiredFact.depends_on: FactKey \| None`; height, storeys, footprint and setback depend on `site/zone` |
| Recording | `engine/finder.py` | for a dependent fact, `record_fact` takes an optional `applies_to`, the condition's value as the document writes it; code refuses it if that text is not in the cited document |
| Settling | `verify/settle.py` | keys are settled in dependency order; before a dependent key is settled, verified facts whose condition differs from the settled value of the condition's key are marked set aside and left out |

- **Input and output of settling are unchanged**: a ledger in, a ledger with more records out. Facts set aside stay in the ledger with their reason, so a reviewer can see the rule of zone Ua and why it was not used.
- **When the condition's key is not settled** (zone missing or in conflict), nothing is set aside and the key escalates as it does today.
- **No domain vocabulary in the platform**: the platform knows conditions and keys; the workload says that a height depends on a zone.

## Change 2: `record_fact` checks the number against the quote

When the finder records a quantity, the tool checks that the amount appears in the quote, with the same function the verifier uses. If it does not, the tool returns an error: record the value as the document writes it, with its unit. The finder then has a turn to correct itself, instead of the fact being lost after the run.

The model still never produces a converted number that is kept: the conversion from 1 500 EUR per quarter to 6 000 EUR per year is done by the schema's factor.

## Tasks

| ID | Task | Done when |
|---|---|---|
| C10.1 | Design note: `docs/notes/conditions.md` (contract, invariants, alternatives rejected); update `docs/notes/engine.md` | approved |
| C10.2 | `Condition` on ledger facts; a `SET_ASIDE` status | round-trip and status tests pass |
| C10.3 | Settling in dependency order, setting aside facts under another condition | tests: other-zone facts set aside; unsettled condition changes nothing; a chain of dependencies is refused |
| C10.4 | `depends_on` on required facts; `applies_to` in `record_fact`, checked against the cited document | tests: `applies_to` absent from the cited document is refused; empty is accepted |
| C10.5 | Amount-in-quote check in `record_fact` | tests: converted amount refused; amount as written accepted, including hectares |
| C10.6 | Live run E008, row in `EXPERIMENTS.md` | large and small scenarios reported separately |

The perfect-finder test for each scenario must still pass every trap.

## Expected outcome, stated before the run

On the large scenario: distractor from 0/9 toward 9/9, unit from 5/9 toward 9/9, arithmetic from 6/9 toward 9/9, recall from 68 % to above the baselines' 75 %. On the small scenarios nothing should move, since they have no dependent rules in other zones; if they move, that is the replay noise recorded in E006 and is reported as such.

Risks: the finder may name the wrong zone for a rule, or loop on the new error. Both show in the ledger and are reported.

## Cost

Only the engine is re-recorded; the baselines replay. About 0.15 USD, printed upper estimate about 0.95 USD.

## Alternative rejected

Tell the finder the site's zone and ask it to record only that zone's rules. Simpler, but it leaves the choice to the model, and the two earlier attempts to steer the finder by instruction (E005, E006) each moved other traps. Recording every rule with its zone and letting code choose keeps the evidence and makes the choice testable.

## Outcome

Engine, three samples per scenario; the baselines replayed unchanged.

| | Recall before | Recall after | Traps before | Traps after |
|---|---|---|---|---|
| Large scenario | 68% (55/81) | 89% (72/81) | 68% (49/72) | 90% (65/72) |
| Small scenarios | 91% (90/99) | 96% (95/99) | 92% (66/72) | 96% (69/72) |

On the large scenario: distractor 0/9 to 9/9, unit 5/9 to 9/9, arithmetic 6/9 to 8/9. The engine now leads both baselines on recall (89 % against 75 %) and on traps (65 against 39 and 31 of 72). Cost per run 0.031 USD, about 120 seconds.

On the large scenario every set-aside fact was a rule of another zone, recorded with that zone's name: 20 over three runs, none wrong.

The small scenarios were expected not to move and did; with every engine call re-recorded, the gain is not attributed. The run also showed a defect. In one small scenario the finder filled `applies_to` with words that are not a case at all ("alignement", "R+6", "reconstruction à l'identique"), in 4 records over two runs. Those texts are in the cited document, so the tool accepted them, and since none names the site's zone the facts were set aside. Three of the four were correct values from the regulation and one was a brochure's. No answer changed, because each correct value had also been recorded once without a condition; with a single record, a correct fact would have been lost. E009 made the tool refuse an `applies_to` that does not have the form of a zone name: no such condition was recorded afterwards, and every score stayed the same, so the defect had no part in the E008 gain. One finder run in a small scenario stopped on its turn limit; whether the new error caused it was not established. Remaining failures are listed in `docs/notes/engine.md`.
