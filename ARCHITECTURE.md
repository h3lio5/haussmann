# Haussmann architecture

PROJECT.md says what and why. This file says how the code is organized. The platform knows nothing about real estate; workloads sit on top.

## 1. Modules (one platform package `haussmann`; each workload is its own package)

| Module | Responsibility | Key types |
|---|---|---|
| `llmkit` | Provider-agnostic client, tool loop, structured outputs with validate-and-repair, retry taxonomy, replay cache, cost ledger, OTel spans | `LLMClient`, `Tool`, `Message`, `Usage` |
| `docparse` | Any file -> elements with provenance; parser adapters; document cards (type, date, parties, summary, relations) | `Element`, `Locator`, `DocumentCard`, `Parser` |
| `ctxkit` | Retrieval (FTS + vector + rerank), context assembly under a token budget with priority tiers, compaction, memory, tool-output shaping, a manifest per model call | `Retriever`, `ContextItem`, `Assembler`, `ContextManifest`, `Memory` |
| `ledger` | Append-only facts, citations, conflicts, versions, transactions by agents or experts | `Fact`, `Citation`, `Conflict`, `Tx` |
| `flow` | Durable step runner: journal in Postgres, queue (SKIP LOCKED), idempotency keys, resume, spend caps | `Runner`, `Step`, `RunState` |
| `buildkit` | Deliverable spec (sections, required facts, calculations) and content-hashed incremental build | `Spec`, `Target`, `BuildResult` |
| `evalkit` | Dataset registry, scorers, calibrated judges, async runner on replay cache, regression gate, online sampling | `Case`, `Scorer`, `Judge`, `Report` |
| `review` | Annotations, edits, approvals, versions, diffs: API and UI | `Annotation`, `Edit`, `ReviewState` |

Workloads:
- `workloads/feasibility_fr`: spec, fact schema, domain tools (cadastre, zoning, risks, regulation reader, comparables, calculators), benchmark scenarios.
- `workloads/lease_abstract`: second, deliberately tiny workload (lease abstraction table from a dataroom). Reuses the whole platform. Its line count is reported in the README as the measure of extensibility.

## 2. Rules

- Dependencies point one way: workloads -> platform. Platform modules follow a fixed layer order over a small `coretypes` module (see `docs/notes/package-boundaries.md`). Enforced in CI with import-linter.
- An interface exists only where two implementations exist (parsers, model providers, workloads). No speculative abstraction.
- Pure core, I/O at the edges. Pydantic at boundaries only. No global state.
- Each module: one-page README stating its contract, its own tests, no domain vocabulary.
- Adopt what is not the differentiator; record each choice as an ADR in `docs/adr/`.

## 3. The run (multi-step, multi-agent)

Workflow where the steps are known; an agent only where the path depends on what is found.

1. Plan (code): spec -> fact groups.
2. Find (agents, parallel, isolated contexts): bounded tool loop per group: search, read, follow references, stop on filled facts or budget.
3. Verify (code): citation match, arithmetic, units, cross-source consistency, completeness.
4. Resolve (agent): per conflict, read both sources, check dates and authority, resolve or escalate.
5. Compute (code): calculators over verified facts.
6. Write + critique (LLM): one call per section around bound facts; critic pass, max two rounds.
7. Build (code): hash targets, reuse unchanged sections.
8. Revise (agent): triggered by a reviewer comment; proposes a diff for approval.

Handoffs between steps are typed artifacts in the ledger, never chat transcripts.

## 4. Context engineering (`ctxkit`)

- State lives in the ledger; every agent starts from a fresh assembled context.
- Assembler: priority tiers (instructions, task, required-fact schema, memory, retrieved elements, prior findings), hard budget, deterministic ordering, stable prefix for prompt caching.
- Just-in-time retrieval: agents hold references (document ids, locators) and pull content through tools.
- Long loops: clear stale tool results first, then compact; findings are written to the ledger as they are made.
- Summaries: a document card per file; hierarchical summaries for long documents.
- Memory: expert corrections stored as retrievable notes scoped by client, document type, or source.
- Conversation state: one review thread per deliverable; state = ledger + compacted thread; old turns summarized, decisions pinned.
- ContextManifest: for every model call, the list of items, sources and token counts. Enables diffing two runs and context ablation evals (remove a tier, measure the score).

## 5. Review model (`review`)

- Annotation: anchored to a sentence, a fact, or a source span; threaded; resolvable; can be addressed to the agent.
- Edit: a ledger transaction by an expert, with reason; triggers incremental rebuild and a diff.
- ReviewState per section: draft -> in_review -> changes_requested -> approved. A deliverable is approved when all sections are.
- Version history: every build is a version; diffs at fact and prose level.
- Provenance display: sentence -> facts -> citations -> highlighted source (PDF region, sheet cell, email line).
- Every action emits an event consumed by `evalkit` (gold label, regression case) and `ctxkit` (memory).

## 6. Build versus adopt (one ADR each)

| Concern | Decision | Production alternatives noted |
|---|---|---|
| PDF/layout parsing | Adopt PyMuPDF + Docling + vision-model fallback behind `Parser` | Reducto, LlamaParse, Unstructured, cloud document APIs |
| Retrieval store | Postgres FTS + pgvector + reranker | Elasticsearch/OpenSearch, Qdrant, Vespa |
| Durable execution | Build a small Postgres step journal behind `Runner` | DBOS (first swap), Temporal at larger scale |
| Agent framework | None; `llmkit` tool loop | LangGraph, Pydantic AI (compared in an ADR) |
| Structured outputs | Native structured outputs + Pydantic + repair loop | Instructor, BAML |
| Eval harness | Build `evalkit` (domain scorers, planted-trap benchmark) | Braintrust, Inspect, promptfoo |
| Traces | Emit OpenTelemetry; view in self-hosted Langfuse or Phoenix | LangSmith, Datadog |
| Review UI | Build (provenance and diffs are the product) | Label Studio, Argilla, platform annotation queues |
| Prompt optimization | DSPy/GEPA, offline only | — |

## 7. Tests

Unit tests per package on recorded responses; Hypothesis property tests for calculators, build hashing and ledger invariants; contract tests for each `Parser` and `LLMClient` implementation; end-to-end benchmark run as the regression gate.
