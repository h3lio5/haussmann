# Haussmann — an evidence-first deliverable engine

Messy dataroom + open data in. A feasibility memo out, where every sentence traces to evidence, an expert can correct it in seconds, and every correction makes the system measurably better.

## 1. Problem

Early-stage real-estate decisions run on deliverables (feasibility studies, investment memos) assembled from fragmented sources: a seller's dataroom of scanned deeds, leases, amendments, spreadsheets and email threads, plus public data and regulations. Three things make automating this hard:

- Sources disagree, go stale, and bury the critical fact in an annex. A plausible-sounding memo is easy; a correct one is not.
- There is no ground truth for real datarooms, so quality is hard to measure and regressions go unnoticed.
- Experts must validate every output. If review is slow, automation saves nothing.

Haussmann treats all three as first-class: every claim is bound to evidence, quality is measured against a benchmark with known answers, and the review loop is designed around expert minutes.

## 2. Core ideas

1. Evidence ledger. Agents write facts to an append-only ledger; state lives there, not in chat history. Every agent gets a fresh, assembled context.
2. Deliverable as a build. The memo is a pure function of the ledger. Sections are content-hashed build targets; an expert edit rebuilds only dependents and yields the diff.
3. Benchmark with planted traps, built first. Ground truth by construction.
4. Review by edit or by comment. Evidence on click; edits are ledger transactions; comments trigger an agent revision shown as a diff.
5. Experiment log. Every change: hypothesis, metrics before/after, cost, kept or reverted.

Rule throughout: the LLM reads and writes prose; deterministic code computes and verifies. The model never types a number.

## 3. Architecture

### Ingest (deterministic)
- File router: digital PDF, scanned PDF (OCR / vision fallback), DOCX, XLSX, email, images.
- Elements with provenance: doc sha256, page + bbox, or sheet + cell, or message id.
- Document card per file: type, date, parties, language, and relations (amends, supersedes, duplicates).
- Authority ranking by document type (deed > lease > teaser > email), used in conflict resolution.

### Deliverable spec (data, not code)
Declares sections, the typed facts each section requires, the calculations, and writing guidance. The spec is the program the agents execute. A new deliverable type (investment memo, dataroom summary) is a new spec, not new orchestration code.

### Fact-finder agents (LLM, bounded)
- The orchestrator plans from the spec: required facts are grouped; each group goes to a worker with an isolated context.
- Context assembler: hybrid retrieval (BM25 + dense, RRF) with document-type priors, structure-aware chunks, hard token budget, tool-output compaction, shared prefix prompt-cached.
- Tools: dataroom search/read, spreadsheet reader, GIS (parcel, zone, overlays, risks), regulation reader, market comparables.
- Output: candidate facts with citations and confidence. Multiple candidates per attribute are kept.
- Missing facts become open questions for the client, never guesses.

### Evidence ledger (Postgres, append-only)
Fact(subject, attribute, value, unit, as_of, citations[], method, confidence, status, author). Conflict(fact_a, fact_b, kind, resolution). Authors are agents or experts; every write is a transaction with a run id. Tables also cover Source, Element, Run, Step, Deliverable, SectionVersion, ExpertEdit, EvalCase, Memory.

### Verifier (deterministic first, LLM judge as fallback)
- Citation check: the cited span contains the value (string/number match), else entailment judge.
- Arithmetic: recompute totals (rent roll, areas), unit normalization.
- Cross-source consistency: detect contradictions; apply authority + recency policy or escalate.
- Completeness against the spec.
- Status per fact: verified / conflict / unverified / missing.

### Build (deterministic orchestration)
- Calculators: capacity estimate, yield, simple residual land value; every assumption is a fact.
- Writer: prose around placeholders bound to fact ids; conflict and open-question sections generated from ledger state; FR + EN.
- Each section target hashed over (spec version, input fact versions, prompt version, model id). Unchanged hash = cache hit.

### Review UI
- Memo view: click a sentence, see its facts and the source highlighted (PDF region, spreadsheet cell, email line). Status colors.
- Edit a fact: ledger transaction, incremental rebuild, diff shown, approve.
- Comment to agent: bounded agent run, proposed diff, approve or reject.
- Version history, approvals per section, review timer.
- Annotations anchored to sentences, facts or source spans; review states per section (draft, in review, changes requested, approved); one review thread per deliverable with managed conversation state.
- Traces: emitted as OpenTelemetry and viewed in self-hosted Langfuse or Phoenix (no custom trace viewer).
- Evals view: score by commit, by trap type; cost and latency over time.

### Flywheel
ExpertEdit -> gold label for that scenario -> regression case in CI (replay cache) -> Memory entry retrieved in later runs (e.g. "in this seller's rent rolls, amounts are before tax").

### Harness and ops
Thin LLMClient interface; tool loop; structured outputs with validate-and-repair; retry taxonomy with backoff; replay cache keyed by request hash; prompt registry; cost ledger; OpenTelemetry spans; durable job runner on a Postgres queue (SKIP LOCKED), resumable after a kill; per-run spend caps; model routing. DSPy/GEPA only in an offline optimization module. No agent framework.

## 4. The benchmark (build this first)

- Scenario spec: a real parcel (real zone, real risks from open data) plus an invented private fact sheet: regulatory and site facts as documents state them (zone, height and footprint limits, setbacks, land area) and ownership and financial facts (owner, occupancy, asking price).
- Generator: renders 12-20 documents from the fact sheet via templates + LLM styling, in mixed formats, some degraded to look scanned; adds distractors and outdated versions; includes real public documents.
- Typed traps, each with an expected behavior: CONTRADICTION, SUPERSEDED, BURIED, UNIT, ARITHMETIC, DATE_LOGIC, MISSING, DISTRACTOR.
- Scores: fact recall and precision; traps handled by type; citation correctness; invented-claim rate; abstention correctness; cost; latency. Prose rubric judge calibrated on ~50 hand-labeled claims.
- Rigor: dev vs held-out scenarios; held-out uses different templates; the generator model differs from the system-under-test model.
- Stated limits: private documents are synthetic; real datarooms are messier. The generator accepts real anonymized cases.

Baselines: (a) everything in one prompt, one call; (b) naive RAG + one call. Haussmann must beat both, and the README shows by how much and at what cost.

## 5. Metrics for the README

Results table (baselines vs Haussmann, dev and held-out), traps by type, cost and latency per deliverable, cache-hit rate on rebuild after an edit, seconds from expert edit to updated memo, error analysis of remaining failures. EXPERIMENTS.md holds the full log.

## 6. Regulation and GIS tools (kept small in the first release)

API Carto cadastre (parcel geometry, EPSG:2154), GPU zone and overlays, risk data, DVF comparables; regulation reader that extracts the rules for the parcel's zone with citations and flags legally void COS mentions; simple capacity estimate (footprint ratio x height). Jurisdiction sits behind an interface (rule sources, CRS, language, connectors) so a second country is a plugin.

## 7. Stack and layout

Python 3.12, uv, ruff, pyright strict, pytest + Hypothesis, Pydantic v2, httpx, Postgres + PostGIS + pgvector, FastAPI; UI in React + TypeScript + Vite with PDF.js and MapLibre.

One platform package `haussmann` with modules `llmkit docparse ctxkit ledger flow buildkit evalkit review`, workloads `feasibility_fr` and `lease_abstract`, plus `docs/` and `EXPERIMENTS.md`. Module boundaries, contracts and build-versus-adopt decisions are in ARCHITECTURE.md.

## 8. Milestones

- M1 Benchmark first: scenario spec, generator, 2 dev scenarios, scorer, both baselines, first numbers.
- M2 Engine: ingest, ledger, fact-finders, verifier, build, traces and cost, durable runner. Beat the baselines; log every change.
- M3 First release: review UI (evidence click, edit -> rebuild -> diff, comment-to-agent), flywheel into CI, evals view, 2 held-out scenarios, GIS/regulation tools, second workload (`lease_abstract`) as the extensibility proof, minimal online scoring, hosted read-only demo served from the replay cache, README, architecture diagram, demo video.
- M4 Next: auto-accept triage with a risk-coverage curve; GEPA on fact-finder prompts with held-out delta; 50 scenarios concurrently with kill/resume; full commune regulation compiler and 3D envelope; second jurisdiction; online quality monitoring with drift alerts.

Cut order if short on time: EN output, market comparables, evals view polish. Never cut: benchmark, baselines, evidence click, edit -> rebuild -> diff, experiment log, held-out results.

## 9. Demo

Hosted demo: read-only, precomputed runs replayed from cache (fast, free, deterministic).

README order: demo video, one-paragraph thesis, results table, architecture diagram, core ideas, error analysis, how to run, ADRs.

## 10. Technical risks

- Synthetic private documents may read as artificial: use templates modeled on real public examples, keep scenarios few and careful, state limits plainly.
- Benchmark overfitting: held-out templates, different generator model, report dev and held-out separately.
- Scope creep: follow the cut order; M3 is the first release.
