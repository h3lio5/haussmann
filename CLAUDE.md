# Haussmann

Evidence-first deliverable engine: messy dataroom + open data in, a cited feasibility memo out, with expert review and an eval harness.

Read before planning anything:
- `PROJECT.md`: what and why, milestones M1 to M4, cut order.
- `ARCHITECTURE.md`: packages, contracts, rules, build-versus-adopt decisions.
- `EXPERIMENTS.md`: the experiment log.

## How we work
- Plan first. For each milestone slice, write `docs/plan/<slice>.md` (tasks, contracts, tests) and wait for approval before writing code.
- Design notes first. Before each core module, write `docs/notes/<module>.md`: contract, invariants, alternatives rejected. Wait for approval, then implement.
- Small steps. One package or one behavior per change, with its tests. Summarize each change in three lines: what, why, how verified.
- Done means: `uv run ruff check`, `uv run pyright`, `uv run pytest`, and the import-linter contract all pass.
- Put reasoning in design notes and change summaries, not in code comments.

## Architecture rules (details in ARCHITECTURE.md)
- Workloads import the platform; platform packages never import a workload. No real-estate vocabulary in platform packages.
- An interface only where two implementations exist. No speculative abstraction.
- Pure core, I/O at the edges. Pydantic at boundaries only. No global state.
- No agent framework. New third-party dependencies need a one-paragraph ADR in `docs/adr/`.
- The LLM never computes or types a number; calculators and bound facts do.
- Handoffs between steps are typed ledger artifacts, never chat transcripts.

## Experiment discipline
- Any change to prompts, context assembly, retrieval, or model choice: rerun the benchmark on the replay cache and add a row to `EXPERIMENTS.md` (change, hypothesis, metrics before/after, cost, kept or reverted).
- Never tune on held-out scenarios. Report dev and held-out separately.
- Report failures as plainly as wins.

## Cost discipline
- Tests never call a live model; they run on recorded responses.
- Live runs use the cheapest adequate model. State the estimated cost first and ask before any run above 2 USD.

## Commands
`uv sync` · `uv run pytest` · `uv run pyright` · `uv run ruff check` · `uv run lint-imports` · `docker compose up -d` (Postgres with PostGIS + pgvector)

## Language
Code, comments and docs in English. Generated deliverables may be French and English.
