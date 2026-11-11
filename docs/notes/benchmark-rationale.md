# Why the benchmark is built from synthetic documents

Status: working record. Read this before `benchmark-ground-truth.md`, `scorer.md` and the generator note.

## The problem

The system reads a set of private project documents and reports facts with citations. To know whether a change made it better or worse, each reported fact has to be checked against the truth, automatically, on every commit.

Real private documents cannot serve as that test set, for two separate reasons:

1. **They are not available.** A seller's document set is confidential. None can be obtained, and none could be published in this repository.
2. **They have no answer key.** Even with access, nobody has written down what is true in them, which document is outdated, or which figure is a typo. Producing that key means an expert reading every page of every case, and the key is itself unverified.

The second reason holds for anyone, including a team that owns thousands of real cases. Access solves availability, not measurement.

## The approach

Write the truth first, then generate documents that state it, and plant known errors on purpose. The answer key exists by construction, so a program can grade a run with no model and no human.

| Piece | What it is | Why it exists |
|---|---|---|
| Scenario spec | the true facts, the documents to produce, the planted errors | the answer key, written before any document |
| Traps | eight kinds of planted error: a contradiction, an outdated value, a buried value, a unit change, a wrong total, impossible dates, a missing fact, a document about something else | each one is a way real document sets mislead a reader; a system that only copies the first value it finds fails them |
| Invariants and `validate` | checks that a spec is consistent | a wrong answer key silently corrupts every score computed from it, so it is checked before use |
| Generator | renders the spec into PDF, scanned PDF, spreadsheet and email files, plus a manifest | turns the answer key into inputs that look like the real thing |
| Manifest | what each file states and where | lets the scorer tell "took the planted bait" from "made it up", and check citations |
| Scorer | compares a system's reported facts with the manifest | the measurement itself; pure and deterministic |
| Baselines | one prompt with everything; naive retrieval | the system has to beat the obvious approaches on the same documents and model, or its design is not justified |

## What is real and what is not

| Data | Real or synthetic |
|---|---|
| Site and public facts in a scenario (location, zone, risks, sale prices) | real open data, frozen with source, date and hash |
| Private facts and documents (ownership, occupancy, prices, studies) | synthetic |
| Regulation text and public registries queried by the workload's tools | real, fetched live or from a frozen copy |
| A full real private document set | not available |

## Limits

- Synthetic documents are cleaner and more regular than real ones. A high score here does not prove the same score on real cases.
- The traps cover the failure types we thought of. Real cases will contain others.
- Mitigations: held-out scenarios with different templates, results reported separately for dev and held-out, and a generator that accepts a real anonymized case if one becomes available. A small hand-labeled set of real public documents is a possible later check on real mess; it cannot replace the benchmark because its key would be partial.

## Where this code lives

The eval harness is part of the product, not test scaffolding: the same scorer gates CI, and expert edits in review become new regression cases. It therefore lives in the importable `evalkit` module.

The layer contract already keeps it out of the run path: `evalkit` sits above the modules that find and store facts, so none of them can import it. Synthetic templates and scenarios are workload data under `<workload>/benchmark/`. Rendering libraries used only by the generator go in an optional dependency group, decided in the rendering ADR.

## Alternatives rejected

- **Label a few real cases by hand and use them as the benchmark.** Small, slow to extend, unpublishable if private, and the labels are unverified.
- **Use a model to judge fact correctness.** The grader would then share failure modes with the system it grades, and scores would move when the judge changes.
- **Public question-answering datasets.** They test reading one document, not reconciling many that disagree.
