# feasibility_fr

Feasibility memo for a French development site, written from a seller's dataroom. The first workload on the platform.

## Contract

Imports the platform; nothing in the platform imports it.

| Part | What it holds |
|---|---|
| `schema.py`, `french.py` | The fact attributes with their units; how dates, numbers and units are written and read in French |
| `engine/spec.py`, `engine/documents.py`, `engine/rules.py` | The facts a run must establish, the document types with their authority, the date rules |
| `engine/ingest.py`, `engine/finder.py`, `engine/memo.py`, `engine/run.py` | The steps of a run: parse and describe documents, find facts, write sections, and the run that orders them |
| `app/` | The review API and the demo served from recordings |
| `benchmark/` | Scenarios, templates, baselines and the benchmark runner |
| `benchmark_data/` | Generated files, answer keys, recordings and results |

## Commands

`uv run python -m feasibility_fr.app.demo` serves the review screen from recordings. `uv run python -m feasibility_fr.benchmark.run --include-heldout` reproduces the report.
