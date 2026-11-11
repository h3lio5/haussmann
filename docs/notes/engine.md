# The thin engine: find, verify, settle, report

Status: written and implemented 2026-11-11; open to revision.

## Where this fits

This is the first complete path through the product: files in, settled facts with sources out. It chains the pieces built so far, and it enters the benchmark as a third contestant beside the two baselines, on the same files, model and question list.

```
required facts ──plan──> groups ──┐
elements, cards ──────────────────┼──> one finder per group ──> candidate facts in the ledger
                                  │     (tool loop: search, read, record_fact, no_evidence)
                                  └──> verify ──> date rules ──> settled facts
                                                                    │
                                              benchmark: to_submission ──> scorer
```

The split is the point of the design: the model reads and reports what documents say; code decides what is true. A finder never compares sources, converts a unit or adds anything up.

## Boundaries

```python
RequiredFact(key: FactKey, text: str, sum_of: tuple[FactKey, ...] = ())

run_engine(wanted, elements, cards, schema, client, model, as_of, sample=0) -> EngineRun
EngineRun(ledger: Ledger, findings: tuple[Finding, ...])

# a finder's tools
search(query) -> up to five lines "doc_id | locator | type, date | start of the page"
read(doc_id, locator) -> the whole page
record_fact(subject, attribute, value, unit, doc_id, locator, quote) -> "recorded as f7"
no_evidence(subject, attribute, reason) -> "noted as an open question"

to_submission(ledger, asked, schema) -> Submission       # benchmark side only
```

Example: asked for the maximum height, a finder searches "hauteur maximale", reads the regulation's page 8 and a brochure, and records `9 m` from the first and `15 m` from the second. `verify` checks both quotes, sees two values, and keeps the regulation's because its document type ranks higher. The submission reports 9 m, flagged, citing both documents.

## Decisions

**Finders record; they do not decide.** The instructions tell a finder to record every value it finds with its source, including values that disagree, exactly as written. Everything the baselines got wrong (choosing silently, copying a wrong total) is taken out of the model's hands.

**A fact is recorded through a tool, as it is found.** If a finder hits its turn or token limit, what it recorded stays in the ledger. The loop's final text is ignored.

**The record tool refuses what cannot be a fact.** A key that was not requested, a quantity that is not a number, or a unit outside the attribute's list is returned to the model as an error it can correct, and nothing is written.

**Groups keep each finder's job small.** Facts about the main subject go five at a time; the others are grouped by attribute, so the rows of a table and its total are looked for together. Each group starts from a fresh prompt: the task, the list of documents with type and date, and the two best pages for each fact.

**Totals are declared by the spec.** A required fact can say it is the sum of others. The engine computes it from the settled parts and compares it with any stated total. All three systems receive the same declaration in their question list, so the comparison stays fair.

**Date rules are workload code.** A planning certificate is flagged once 18 months have passed since its date, and an agreement once its end date is before the review date.

**The benchmark adapter reads the ledger and nothing else.** A settled key becomes a reported fact, flagged if it had a disagreement or a date rule fired, citing every verified source of its value and both sides of a disagreement. A key with no verified fact, or an escalated disagreement, becomes an open question.

## What the first real run changed

The first run scored below both baselines: recall 76 % against 93 %, traps 65 % against 69 %. Replaying it showed the checking code never failed; the finder did. Five causes were visible in the recordings and each got a fix:

| Seen in the recordings | Fix |
|---|---|
| 8 of 27 finder runs ended on a repeated call with facts unrecorded | the loop refuses a repeat and continues |
| Search results showed the start of a page, so a buried sentence was invisible | results show the passage that matches the query |
| Dates written as 31/08/2027 or "31 août 2027" were refused by the record tool | common date forms are accepted |
| Four of thirteen documents were typed "other" and got the lowest authority | each document type has a short description in the prompt |
| A finder said "done" with facts neither recorded nor marked | one more pass for exactly those facts |

That run (E004) put the engine ahead: recall 95 % against 93 to 94 %, and 90 % of traps against 69 %. Every remaining failure had one cause: the finder recorded the first source it found and stopped looking, so a disagreement was never seen. The fix is a cross-check pass. After a group is done, code looks up, for each fact with a recorded value, the best-matching pages of documents that fact does not cite yet, and sends the finder to read exactly those pages and record what they say. Finding where a second opinion might be is a search, which code does better than a model deciding when it has looked enough.

Units copied from a document in its own spelling ("m²", "%") are now understood by the record tool; they were refused sixteen times in that run.

One cause is not fixed: keyword search cannot connect a question about "occupation" to a document that says "situation locative". That is the case for adding meaning-based search, to be measured next.

That run (E005) confirmed the mechanism and showed its price. Contradiction traps went from 4 of 9 to 9 of 9 and superseded from 8 to 9, so every disagreement now reaches the ledger. But distractor traps fell from 8 of 9 to 3 of 9, recall from 95 % to 91 %, and three values were invented. Replay shows three causes:

- The cross-check handed the finder pages of documents about another property, with an instruction to record what they say. It did, and code then saw a disagreement between the property and its neighbour.
- Told to record "whatever" a listed page says, the finder recorded things that are not the fact: the address line of an email as the parcel reference, an email's own date as the certificate date.
- It recorded the same value from the same document twice, once by cell and once by sheet, and the coarser citation counts as a wrong one.

Cost and latency also doubled (0.06 USD and 72 s per six runs). The pass is kept because it fixes the failure it was built for; the three causes above are the next change.

A first attempt at them (E006) was reverted. It had the model that describes each document at ingest also say whether the document is about another property, and had code set those documents aside before any search. The check found the three documents it should have and three it should not have, out of 27: a model reading one document cannot know which property the file is about. Losing a planning certificate, a risk report and a cadastral extract cost more than the distractors did: recall fell to 81 % and traps to 83 %. Two things follow. Scope cannot be judged from a document alone; the judge needs a description of the subject, which the run does not take as input today. And removing a document is the wrong response to an uncertain judgment; marking it, and keeping it out of the cross-check only, would fail softly.

These runs also show the limit of the measurement. A small change to one prompt shifts every later model call, so two scenarios with three samples each move by several traps between runs for reasons unrelated to the change. Further finder tuning waits for more scenarios.

## Tests

- Each tool: what it returns, and each way it refuses.
- A scripted finder run: search, read, record two values, mark one as having no evidence, stop.
- Planning, the date rules, and an empty run.
- With a perfect finder (every statement about the property entered as a candidate), the code half passes every trap on both dev scenarios with full recall. This isolates the finder as the only source of failure in a real run.

## Known limits

- **A disagreement is seen only if both sides are recorded.** The cross-check pass covers documents that match the fact's wording; a second source that uses other words is still missed.
- **A document about another property is excluded by instruction only.** Nothing in code stops a finder recording from it; the document card does not yet say what a document is about.
- **Totals computed from parts cite the parts' documents,** which is true provenance but is not what the benchmark counts as citing the total.
- **Finders run one after another.** Running them in parallel waits for the durable runner.

## Alternatives rejected

- **One finder for all facts.** Its context would grow with every tool result until the budget ended the run.
- **Letting the finder resolve conflicts it sees.** That is the baselines' failure moved into a loop.
- **A final structured answer instead of a record tool.** A run that stops on a limit would lose everything it had found.
