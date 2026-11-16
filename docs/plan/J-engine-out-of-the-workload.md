# Slice J: engine steps and review session out of the workload

Status: approved 2026-11-15. J1 to J4 done 2026-11-16.

## Why

The platform is domain-free, but the steps of a run (`engine/ingest.py`, `finder.py`, `memo.py`, `run.py`, about 1,100 lines) and the review session and API (`app/`, about 700 lines) live in `feasibility_fr`. A second domain would have to copy them. After this slice a workload is its declarations, its prompts and its benchmark; everything else is imported.

## Constraint

The engine is frozen at `engine-freeze-m3` (`docs/notes/heldout.md`, rule 1). This slice may not change what any model is sent or what the ledger settles. The proof is the replay cache: every recorded request is keyed by its hash, so the benchmark and the demo must replay with no missing recording and the report must reproduce byte for byte, dev and held-out.

## Tasks

| ID | Task | Done when |
|---|---|---|
| J1 | Design note `docs/notes/workload-definition.md`: one `Workload` record holding the schema, required facts, document types and authority, date rules, language functions and prompt texts; who builds it, who reads it | approved |
| J2 | New platform package `haussmann.engine` (above `buildkit`, below `review`): ingest, find, write and run, taking a `Workload`; `feasibility_fr` keeps a thin module that builds its `Workload` | all gates green; report reproduces identically from recordings |
| J3 | Review session and HTTP API into the platform as `haussmann.app`, above `engine` (the design note places it there: opening a session runs the engine); the workload keeps `demo.py` | the demo serves the three dev files from recordings; app tests pass unchanged |
| J4 | Import contract and vocabulary test extended to the new package; README section on another domain rewritten with the new line counts | gates green |

## Not in this slice

A second workload. It becomes cheap after J and is the natural next step, in the domain of whichever company is being written to.

## Risks

- A prompt assembled in a different order changes a request hash; the replay check catches it at once and costs nothing.
- The French prompts contain domain words. They move as data owned by the workload, not into the platform, so the vocabulary test still holds.

## Cost

No live model call. Any recording that would need to be made again means the constraint was broken, and the change is reverted.
