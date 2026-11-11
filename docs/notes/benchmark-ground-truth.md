# Benchmark ground truth

Status: approved 2026-11-10. Needed by M1 tasks B1, B2, B5.

## Purpose

Why the benchmark uses synthetic documents at all is in `benchmark-rationale.md`.

A scenario must let a scorer decide, without a model and without a human, whether each thing a system reports is right, wrong because it fell for a planted trap, or invented. That requires knowing two things by construction: what is true, and everything the documents say, including what they say wrongly.

## Contract

Generic types live in `haussmann.evalkit`. The list of attributes and units is the workload's and is passed in.

```python
FactKey(subject: str, attribute: str)          # ("site", "max_height"), ("lease:acme", "annual_rent")
Value = Quantity | date | str                  # Quantity(amount: Decimal, unit: str)

AttributeDef(name, kind, canonical_unit, tolerance)   # workload-defined; units carry a factor
                                                      # to the canonical unit (ha -> m2, month -> year)

GoldFact(key, value: Value | None)             # None: the documents cannot establish it

StatementKind = SUPPORTS | STALE | CONFLICTS | DISTRACTOR
PlannedStatement(key, value, kind)             # in the spec
Statement(doc_id, locator, key, value, kind)   # in the manifest, once rendering fixed the locator

DocumentPlan(doc_id, source, format, date, authority: int, scanned: bool, states: [PlannedStatement])
    # source is a template to render, or an attached public file with hand-given locators

TrapType = CONTRADICTION | SUPERSEDED | BURIED | UNIT | ARITHMETIC | DATE_LOGIC | MISSING | DISTRACTOR
Trap(type, key, docs, parts: [FactKey] = ())   # parts: the rows of an ARITHMETIC total

ScenarioSpec(id, split, seed, gold: [GoldFact], documents: [DocumentPlan], traps: [Trap])
Manifest(scenario_id, split, gold, traps, files: [(doc_id, filename, sha256, statements)])
```

- A spec is written as a Python module in the workload. The manifest is JSON written by the generator.
- The manifest is self-contained: the scorer reads the manifest and a submission, nothing else.
- Types are frozen dataclasses; Pydantic is used only to read and write the manifest file.
- Amounts are `Decimal`, never `float`.
- `authority` is an integer the workload assigns from its ranking of document types. The platform compares integers and knows no document types.

## Trap semantics

What a trap expects is fixed by its type. There are three kinds of outcome: report the value, report the value and flag the fact, or abstain.

| Type | Planted as | Gold value | Passes when |
|---|---|---|---|
| SUPERSEDED | a STALE statement in an earlier document, a SUPPORTS statement in a later amendment | the amended value | value correct and the later document cited |
| BURIED | the only SUPPORTS statement sits deep in a long document | the value | value correct and that page cited |
| UNIT | the SUPPORTS statement uses a non-canonical unit or period | the value in canonical unit | value correct after normalization |
| DISTRACTOR | a DISTRACTOR statement in a document about another asset | the real value | value correct and the distractor document not cited for it |
| CONTRADICTION | a CONFLICTS statement in a lower-authority document | the higher-authority value | value correct, fact flagged, both documents cited |
| ARITHMETIC | a stated total (CONFLICTS) that differs from the sum of its rows | the sum of `parts` | value correct and fact flagged |
| DATE_LOGIC | dates that cannot hold together, or a validity that has expired | the date as stated | fact flagged |
| MISSING | no statement anywhere | `None` | no value asserted and the fact listed as an open question |

How a submission expresses "flagged", "cited" and "open question" is defined in the scorer note.

## Invariants

Checked by `validate(spec)`; each has a failing fixture in the tests.

1. Every gold key uses an attribute from the workload schema and a value of the right kind, in the canonical unit. Every statement is about a gold key and uses a unit the schema can convert.
2. A gold value is `None` exactly when a MISSING trap covers the key, and then no document states it.
3. Every other gold fact has at least one SUPPORTS statement, except the total of an ARITHMETIC trap: its true value is the sum of its parts and no document states it.
4. A SUPPORTS statement equals the gold value exactly after unit normalization. STALE, CONFLICTS and DISTRACTOR statements differ from it by more than the attribute's tolerance, so a scorer that accepts rounding can never accept a bait.
5. Every STALE, CONFLICTS or DISTRACTOR statement belongs to exactly one trap. A key has at most one trap.
6. Each trap has the shape its type requires: SUPERSEDED has the stale document dated before the supporting one; CONTRADICTION has the conflicting document at lower authority; UNIT has a non-canonical unit; ARITHMETIC has a gold total equal to the sum of its parts.
7. Document ids and gold keys are unique, and traps reference existing documents and gold keys. `split` is an enum, so it needs no check.

After generation the manifest adds two checks: every statement has a locator, and a BURIED statement is past a page threshold.

## Deliberately left out of M1

- **Contradictions between documents of equal authority.** The right answer is "escalate, assert nothing", which needs a second kind of gold. Added once the engine has a resolve step to test.
- **Tax basis (excluding versus including tax)** as a UNIT trap. It is a conversion that needs a rate, not a unit factor.
- **Two traps on one fact,** for example a buried amendment. A failure could not be attributed to either trap.
- **Facts computed from rules,** for example buildable area from height and footprint limits. Gold in M1 is what the documents state; computed quantities are scored once the calculators exist.
- **An `as_of` date on facts.** Nothing in M1 scoring uses it.

## Alternatives rejected

- **Gold facts only, no statements.** A wrong answer could not be split into "took the bait" and "made it up", and citations could not be checked.
- **Deriving ground truth from the rendered documents,** by a model or by hand labeling. It is circular and stops being ground truth by construction.
- **A free-form expected behavior per trap.** Fixing behavior by type keeps eight comparable pass conditions instead of one per trap instance.
- **Specs in YAML or TOML.** A parser and a validation layer for two scenarios; a Python module is checked by pyright for free. Worth revisiting when cases come from outside the repo.
- **Inferring statement kind from its value.** An explicit kind is validated against the value (invariant 4), which catches authoring mistakes that inference would silently accept.
