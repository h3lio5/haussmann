# Submission contract and scorer

Status: approved 2026-11-10. Needed by M1 tasks B5, B6, B7, B8.

## Purpose

Why the benchmark uses synthetic documents at all is in `benchmark-rationale.md`.

Every system under test, baseline or engine, is reduced to one `Submission`. The scorer compares it with a manifest and nothing else, with no model and no human in the loop, so two systems can only differ in score by differing in what they reported.

## Contract

Types and `score` live in `haussmann.evalkit`.

```python
Citation(doc_id: str, locator: str | None)
ReportedFact(key: FactKey, value: Value, citations: tuple[Citation, ...], flagged: bool)
Submission(facts: tuple[ReportedFact, ...], open_questions: tuple[FactKey, ...], memo_text: str)

Outcome = CORRECT | BAIT | INVENTED | ABSTAINED | OMITTED | UNASKED
FactResult(key, outcome, answerable: bool, well_cited: bool)
Rate(count: int, total: int)                    # .value is None when total is 0
TrapResult(type, key, passed: bool)
Score(facts: tuple[FactResult, ...], traps: tuple[TrapResult, ...])   # metrics are properties

score(manifest: Manifest, schema: Schema, submission: Submission) -> Score
```

- **Closed question list.** Each system receives the scenario's gold keys without values and fills them in. A reported key outside that list is `UNASKED`: counted, shown in the report, and excluded from every rate.
- **One fact per key.** `score` raises `InvalidSubmission` on a repeated key; the runner records the run as failed and does not repair it.
- **`flagged`** means "this fact needs a human look": sources disagree, a total does not add up, a date cannot hold. One flag and one citation set per fact.
- **An open question** is a key in `open_questions` with no reported fact (`ABSTAINED`). A key in both counts as reported. An asked key that is neither reported nor listed is `OMITTED`.
- `memo_text` is carried for the prose rubric in M2 and is not scored in M1.
- `score` is pure. Cost and latency come from the run record and are joined in the report (B8), not here.

## Classifying a reported fact

The reported value is normalized with the workload schema, then compared in this order:

| Outcome | Condition |
|---|---|
| CORRECT | gold has a value and the reported value matches it |
| BAIT | it matches a STALE, CONFLICTS or DISTRACTOR statement for the same key |
| INVENTED | anything else, including any value for a fact whose gold is `None` |

Matching, per kind:

- **Quantity:** same canonical unit and `|reported - gold| <= tolerance`. A unit the schema cannot convert does not match.
- **Date:** equal.
- **Text:** equal after Unicode NFKD with accents removed, case folding, punctuation removed and whitespace collapsed. No fuzzy matching and no model.

Tolerance is absolute, per attribute, set by the workload: 1 for money amounts, 0.5 for areas, 0 otherwise. `validate` already guarantees every bait differs from gold by more than the tolerance, so CORRECT and BAIT cannot both apply.

## Citations

A citation is **valid** when the cited document states that key, and, if a locator is given, at that locator. A correct fact is **well cited** when it has at least one valid citation to a SUPPORTS statement and no invalid citation. The total of an ARITHMETIC trap has no supporting statement, so any valid citation counts for it. Locator format belongs to the generator note; the scorer compares locators as strings.

## Metrics

With `answerable` = gold facts that have a value, and `reported` = reported facts on asked keys:

| Metric | Definition |
|---|---|
| recall | CORRECT / answerable |
| precision | CORRECT / reported |
| bait rate | BAIT / reported |
| invented rate | INVENTED / reported |
| abstention | unanswerable facts left as open questions / unanswerable facts |
| citation correctness | well-cited CORRECT facts / CORRECT facts |
| traps passed | k / n per trap type, never averaged across types |

A rate with a zero denominator is reported as `None`, not as 0 or 1.

## Trap pass conditions

The table in `benchmark-ground-truth.md`, expressed on a submission:

| Type | Passes when |
|---|---|
| SUPERSEDED | CORRECT and a valid citation to a supporting document of the trap |
| BURIED | CORRECT and a valid citation whose locator equals the statement's |
| UNIT | CORRECT |
| DISTRACTOR | CORRECT and no citation to a document of the trap |
| CONTRADICTION | CORRECT, flagged, and every document of the trap cited |
| ARITHMETIC | CORRECT and flagged |
| DATE_LOGIC | flagged |
| MISSING | open question |

## Tests

- An oracle submission built from the manifest scores 1.0 on every rate and passes every trap.
- A bait-taker built from the manifest passes no trap and has recall 0 on trapped facts.
- Hypothesis: the order of facts, citations and open questions never changes the score; adding an INVENTED fact never raises precision; adding an UNASKED fact changes no rate.
- One case per row of each table above, and one per text-matching step.

## Known limits

- **Text matching is strict.** A correct paraphrase scores as INVENTED. Text attributes are therefore kept to short identifiers (a code, a name) and systems are told to copy them as written. The false-negative count on dev scenarios is checked by hand once and reported.
- **Flagging is not graded for its reason.** A flag raised for the wrong reason still passes. The reason lives in the memo and is judged in M2.
- **Unit factors are shared data.** The scorer and, later, the verifier both read the workload's unit table; their comparison code is separate, so they cannot share a comparison bug, only a wrong factor. The factors have their own tests.

## Alternatives rejected

- **Open extraction, no question list.** Precision would depend on how many unasked true facts a system volunteers, which the manifest cannot check.
- **A separate `conflicts` list with its own citations.** Two citation sets per fact turn every pass condition into a rule about which set counts. A flag on the fact carries the same information.
- **A model as the matcher for text.** It makes the grader non-deterministic, costs money per run and can share a failure mode with the system it grades.
- **Fuzzy text matching with a threshold.** The threshold becomes a tuned parameter of the benchmark, and a near-miss name is exactly the error a reviewer needs to see.
- **Relative tolerance.** Baits are planted at absolute distances; an absolute tolerance keeps "bait differs by more than tolerance" a simple check.
- **One aggregate trap score.** With about three instances per type, an average hides which behavior failed.
