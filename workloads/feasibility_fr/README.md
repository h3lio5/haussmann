# feasibility_fr

Feasibility memo for a French development site, written from a seller's dataroom. The first workload on the platform.

## Contract

Imports the platform; nothing in the platform imports it.

| Part | What it holds |
|---|---|
| `schema.py`, `french.py`, `documents.py` | The fact attributes with their units; how values are written and read in French; the document types with their authority |
| `prompts.py` | Every instruction text sent to a model |
| `workload.py` | Date rules, the memo's sections and wording, and the `Workload` record handed to `haussmann.engine` and `haussmann.app` |
| `app/demo.py` | The command that opens the dev files from recordings and serves the review screen |
| `benchmark/` | Scenarios, templates, baselines and the benchmark runner |
| `benchmark_data/` | Generated files, answer keys, recordings and results |

## Commands

`uv run python -m feasibility_fr.app.demo` serves the review screen from recordings. `uv run python -m feasibility_fr.benchmark.run --include-heldout` reproduces the report.
