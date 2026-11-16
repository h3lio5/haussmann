# Haussmann

Haussmann turns a folder of messy documents into a written deliverable that an expert can check line by line.

Documents go in: PDFs, scans, spreadsheets, emails, some of them wrong, out of date or about something else. A deliverable comes out in which every sentence names the facts it rests on and every fact names the page, cell or line it was read from. An expert reviews it, corrects a fact, sees what was rebuilt, and the correction becomes a test.

The model finds and words; code checks, settles and computes. The model never types a number.

The platform knows nothing about any domain. The first workload on it is a feasibility memo for a French development site, written from a seller's dataroom; [what another domain needs](#another-domain) is below.

## Results

Three systems on the same model (`mistralai/mistral-small-2603`), three runs each, scored by code against an answer key that is known because the documents were generated from it. Each scenario plants eight kinds of trap: two documents that disagree, a value replaced by an amendment, a total that does not add up, a unit to convert, a date past its validity, a fact that is in no document, another property's document, a fact deep in a long document.

- **one_prompt**: every document in one prompt, one call.
- **naive_rag**: chunks, embeddings, top-k, one call.
- **engine**: this project.

### Dev: three scenarios the engine was built against

| System | Recall | Precision | Traps passed | Citations correct | Cost per run | Time per run |
|---|---|---|---|---|---|---|
| one_prompt | 85% (153/180) | 92% | 62% (89/144) | 96% | 0.008 USD | 11 s |
| naive_rag | 86% (154/180) | 81% | 56% (81/144) | 99% | 0.003 USD | 8 s |
| engine | 98% (176/180) | 98% | 97% (139/144) | 99% | 0.017 USD | 94 s |

### Held-out: two scenarios written after the engine was frozen, run once

| System | Recall | Precision | Traps passed | Citations correct | Cost per run | Time per run |
|---|---|---|---|---|---|---|
| one_prompt | 97% (113/117) | 97% | 74% (53/72) | 100% | 0.002 USD | 13 s |
| naive_rag | 99% (116/117) | 99% | 74% (53/72) | 100% | 0.002 USD | 15 s |
| engine | 88% (103/117) | 95% | 85% (61/72) | 94% | 0.013 USD | 94 s |

The rules for the held-out scenarios and a prediction were committed before the scenarios were written, and the scenarios before the run ([docs/notes/heldout.md](docs/notes/heldout.md)). Nothing was tuned on them.

### What the held-out run says

The dev numbers overstate the engine.

- **Its advantage on traps carries over, smaller**: 11 points ahead of both baselines, against 35 on dev. One scenario of the two was complete in every run (60/60 facts, 36/36 traps). On the other the engine passed fewer traps than one_prompt (25/36 against 27/36).
- **Its advantage on recall does not**: on small files a model that reads everything misses almost nothing, and the engine's search is a way to lose facts.
- **What code checks held on new documents**: arithmetic, date rules, missing facts, superseded values and unit conversion passed 9 of 9 each. Both baselines passed 0 of 9 contradictions and 3 of 9 date rules, on dev as on held-out: they report one value where two documents disagree.

### What still fails

| Failure | Where | Cause |
|---|---|---|
| Values taken from another property's documents | held-out, 3 of 3 runs on one scenario | Ignoring such documents is an instruction to the model; no code enforces it. |
| A limit of the regulation never found | held-out, 3 of 3 runs | The finder searches by keyword; it looked for "niveau" where the document writes "R+2". |
| The owner left open or wrong | dev and held-out | The sentence uses a verb where the model searches a noun; a neighbouring lot's document is offered as a second source. |
| A rewrite rewords sentences whose facts did not change | review | A section is rewritten whole, so the diff shows more than what moved. |

Limits of the measurement: five scenarios, generated documents, one model, and the held-out scenarios were written by the engine's author. Every experiment, with what was expected before the run and what came out, is in [EXPERIMENTS.md](EXPERIMENTS.md); the full reports are in [`benchmark_data/results`](workloads/feasibility_fr/benchmark_data/results).

## Try it

No model key is needed. Every model call the demo and the benchmark make is replayed from recordings in the repository.

```bash
uv sync
```

```bash
cd web && npm ci && npm run build && cd ..
```

```bash
uv run python -m feasibility_fr.app.demo
```

Open http://127.0.0.1:8000.

- **Evidence**: select a sentence of the memo. Its facts appear with their status, and the source opens at the cited place with the quote marked: the PDF page, the spreadsheet cell or the email line.
- **Edit**: on the `champagnole ecole` file, select the line about the owner among the points to resolve and set its value. Two sections of eight are rebuilt, the diff shows what changed, and the six other approvals stay valid.
- **Evals**: the link in the bar shows both result tables, the regression cases and the experiment log.

An action that would need a model call that was never recorded is refused and says so.

Reproduce the report from recordings:

```bash
uv run python -m feasibility_fr.benchmark.run --include-heldout
```

## How it works

```mermaid
flowchart TD
    D[Documents: PDF, scans, XLSX, EML] --> P[Parse into pages and cells]
    P --> C[Describe each document: type and date]
    C --> F[Find: one agent per group of facts<br/>search, read, record a value with its quote]
    F --> V[Check each quote against the cited page]
    V --> L[(Ledger: append-only facts,<br/>citations, conflicts)]
    L --> S[Settle: expert, computed, authority, date<br/>recompute totals, apply date rules]
    S --> L
    L --> W[Write each section around bound facts]
    W --> K[Check: no typed number, every fact stated]
    K --> B[Build: hash each section's inputs,<br/>reuse what did not change]
    B --> M[Memo: sentence to facts to citations]
    M --> R[Review: evidence, edit, approve, comment]
    R -- an edit is a fact --> L
    R -- a comment --> X[Propose a rewording]
    X --> K
    R -- an edit becomes a case --> E[Regression cases, checked in CI]

    classDef model fill:#ffe9c7,stroke:#b36b00,color:#3d2600
    classDef code fill:#dbe8fb,stroke:#2d5fa3,color:#17284a
    class C,F,W,X model
    class D,P,V,L,S,K,B,M,R,E code
```

Orange steps call the model; blue steps are code. A step hands the next one typed records in the ledger, never a transcript.

- **The ledger is the centre.** Facts are appended, never changed. A disagreement between documents is a record with both sides. An expert's correction is one more fact, which outranks the others without deleting them.
- **Numbers come from code.** The model writes sentences with placeholders; values are bound from the ledger, and a draft that contains a digit is refused.
- **Runs are durable.** Each step commits its ledger entries and its completion in one Postgres transaction. A run killed at any point resumes without sending a model call twice.
- **Rebuilds are incremental.** A section is rebuilt only when the facts it uses change, so an approval lasts as long as the text it was given for.
- **Everything is replayable.** Model calls are recorded by a hash of the request; tests and CI never call a live model.

## Layout

One platform package and one workload. Import rules are enforced by `import-linter`, and a test keeps real-estate vocabulary out of the platform.

| Package | What it does |
|---|---|
| `haussmann.coretypes` | Values, units, fact keys |
| `haussmann.llmkit` | Model client, tool loop, replay cache, cost, trace spans |
| `haussmann.docparse` | PDFs, scans, spreadsheets and emails into pages and cells |
| `haussmann.ledger` | Append-only facts, citations, conflicts |
| `haussmann.ctxkit` | Assembles what a model call is shown, within a budget |
| `haussmann.flow` | Durable runner, journal in Postgres, spend cap |
| `haussmann.verify` | Citation check, settling order, totals |
| `haussmann.buildkit` | Sections as targets, hashed and reused |
| `haussmann.evalkit` | Scenario generator, scorer, report, regression cases |
| `haussmann.review` | Edits, diffs, review state, proposals |
| `haussmann.engine` | The steps of a run: ingest, find, settle, write, for any workload |
| `haussmann.app` | A run open for review, and the HTTP API the screen calls |
| `feasibility_fr` | The workload: schema, language, prompts, deliverable, benchmark, demo command |
| `web/` | The review screen (React, TypeScript, PDF.js) |

No agent framework. Each third-party dependency has a one-paragraph decision record in [docs/adr](docs/adr); each core module has a design note in [docs/notes](docs/notes) with its contract, its invariants and the alternatives rejected. [ARCHITECTURE.md](ARCHITECTURE.md) has the rules.

## Another domain

The same steps apply wherever a decision rests on a file of documents that disagree: comparing bids against a specification, abstracting leases, summarising a claims file, preparing a credit memo. None of these is built; this section says what the code would ask of one.

A workload hands the engine one record, 436 lines in `feasibility_fr`:

| Part | File | What it says |
|---|---|---|
| Fact schema | `schema.py` | The attributes, their kinds and units, the tolerance for calling two values equal |
| Document types | `documents.py` | The kinds of document and how much each counts when two disagree |
| Language | `french.py` | How dates, numbers and units are written and read |
| Instruction texts | `prompts.py` | Every text a model is sent |
| The record | `workload.py` | Date rules, the sections of the deliverable and its fixed wording, and the record that gathers all of the above |

The platform, about 6,000 lines, is used unchanged: parsing, the ledger, the citation check, settling, the durable runner, the incremental build, the steps of a run (`haussmann.engine`), the scorer and the benchmark generator, the review core, the review session and its HTTP API (`haussmann.app`). The platform holds no instruction text; the recordings prove that moving the engine under it changed no request.

Beside the record, a workload writes the command that opens its files and serves the screen (159 lines here) and, to be measured, its own scenarios and answer keys. The record has one implementation so far: its shape is fitted to this workload and is expected to change when a second one is written.

## Development

```bash
uv run ruff check && uv run pyright && uv run pytest && uv run lint-imports
```

The database tests need Postgres and run when `HAUSSMANN_DB_URL` is set; without it they are skipped:

```bash
docker compose up -d
```

```bash
HAUSSMANN_DB_URL=postgresql://haussmann:haussmann@127.0.0.1:5432/haussmann uv run pytest
```

To look at a run as a trace (run, steps, model calls with tokens and cost), start the viewer and pass its address to the demo, then open http://127.0.0.1:16686:

```bash
docker compose --profile traces up -d
```

```bash
uv run python -m feasibility_fr.app.demo --traces http://127.0.0.1:4318
```

A live run needs `OPENROUTER_API_KEY`, prints its estimated cost first and refuses above a cap. The whole benchmark, five scenarios and three systems, costs about 0.35 USD.
