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

## Tests

- Each tool: what it returns, and each way it refuses.
- A scripted finder run: search, read, record two values, mark one as having no evidence, stop.
- Planning, the date rules, and an empty run.
- With a perfect finder (every statement about the property entered as a candidate), the code half passes every trap on both dev scenarios with full recall. This isolates the finder as the only source of failure in a real run.

## Known limits

- **Everything depends on the finder recording both sides.** If it records only one value, no conflict exists to resolve.
- **A document about another property is excluded by instruction only.** Nothing in code stops a finder recording from it; the document card does not yet say what a document is about.
- **Totals computed from parts cite the parts' documents,** which is true provenance but is not what the benchmark counts as citing the total.
- **Finders run one after another.** Running them in parallel waits for the durable runner.

## Alternatives rejected

- **One finder for all facts.** Its context would grow with every tool result until the budget ended the run.
- **Letting the finder resolve conflicts it sees.** That is the baselines' failure moved into a loop.
- **A final structured answer instead of a record tool.** A run that stops on a limit would lose everything it had found.
