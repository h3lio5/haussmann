# Slice E plan: a run that survives a kill, and says what it cost

## Why

Today a run lives in one process. The ledger is a Python object, a crash loses everything, and every model call made so far is paid again on the next attempt. Cost is known only to the benchmark report. This slice stores the run in Postgres, lets a killed run resume without paying twice, and reports cost and traces per step.

## Where it fits

```
workload run ──> runner.step(key, fn) ──> fn(ledger, client) ──> appends to the ledger, calls the model
                      │                              │
                      │                              └─ client wrapper: looks the call up in the journal
                      │                                 before paying; records it after; checks the spend cap
                      ▼
                   journal (Postgres): runs, steps, ledger entries, model calls
```

- **Called by**: the workload's run (`engine/run.py`), which becomes a sequence of named steps: one per finder pass, then verify, date rules, and one per memo section.
- **Read by**: the cost report, the trace viewer, and in M3 the review interface, which reads the ledger of a run from Postgres.
- **Unchanged**: the `Ledger` class, `verify`, the finder, the benchmark scores. The benchmark and the tests keep running without a database, on an in-memory journal.

## The idea in three rules

1. **A step commits all at once.** A step works on the ledger in memory. When it finishes, its new ledger entries and the "step done" row are written in one database transaction. A kill mid-step leaves nothing of that step behind.
2. **A paid call is recorded when it returns.** Each model response is stored under the run and the hash of its request (the same hash the replay cache uses). A step that is run again finds its earlier calls there and does not pay for them.
3. **On resume, finished steps are skipped.** The ledger is rebuilt from the stored entries; the run continues at the first step that is not done.

Rule 2 needs steps to be deterministic given the ledger and their inputs: a re-run step must ask the same questions. A request that is not in the journal is paid and counted as a divergence, so a break of this rule is visible.

Known gap: a call that returns just as the process dies, before its row is written, is paid twice. The window is one insert.

## Structures

```python
# flow
class Journal(Protocol):                    # two implementations: memory, Postgres
    async def open(run_id, cap_usd) -> RunState          # ledger entries so far, keys of finished steps
    async def call(run_id, key) -> Response | None
    async def record_call(run_id, step, key, response, cost_usd) -> None
    async def commit(run_id, step, entries, result) -> None   # one transaction
    async def spent(run_id) -> Decimal

RunState(run_id, ledger: Ledger, done: frozenset[str])

class Runner:
    async def step(key: str, fn: Callable[[Ledger, LLMClient], Awaitable[Json]]) -> Json
    # finished step: returns the stored result, runs nothing
    # otherwise: runs fn, commits, returns

SpendCapReached(run_id, spent, cap)         # raised before a paid call; the run can resume with a higher cap
```

Tables: `runs(id, status, cap_usd)`, `steps(run_id, key, result, done_at)`, `ledger_entries(run_id, tx, author, step, records)`, `calls(run_id, key, step, model, usage, cost_usd, response, at)`. One SQL file, applied at start; no migration tool.

The `calls` table is also the cost record: cost per run and per step is a sum over it.

## Traces

One span per run, per step and per model call, with model, token counts and cost as attributes, emitted through the OpenTelemetry API. The platform depends on the API only, which does nothing until an exporter is configured. Tests read spans from an in-memory exporter.

## Decisions for the notes and ADRs

| Decision | Proposal | Why |
|---|---|---|
| Postgres driver (ADR-0007) | psycopg 3 | One driver with both an async and a sync interface, typed; LGPL, used as a library. asyncpg is faster and async-only; speed is not the constraint here. |
| Tracing (ADR-0008) | `opentelemetry-api` in the platform; SDK and exporter in the dev group | The platform stays free of a tracing backend. |
| Ledger storage | The `Ledger` class stays the only implementation of the rules; Postgres stores its entries | Two copies of the invariants, one in Python and one in SQL, would have to be kept equal. The contract test is: any sequence of appends, stored and loaded, gives a ledger equal to the one in memory. |
| Database tests | Marked `db`; run when `HAUSSMANN_DB_URL` is set, which CI does | The default test run stays free of Docker. |

## Left out of this slice

- **Several workers and a queue.** One process per run. Claiming runs with `SKIP LOCKED` comes with running many scenarios at once (M4).
- **A trace viewer service.** Spans are emitted and tested; adding Phoenix or Langfuse to `compose.yaml` is the first thing cut if time is short, and otherwise the last task.
- **Retries with backoff.** A failed step fails the run; resume is manual.

## Tasks

| ID | Task | Done when |
|---|---|---|
| E0 | ADR-0007, ADR-0008; `docs/notes/flow.md`, `docs/notes/traces-and-cost.md`; storage section added to `docs/notes/ledger.md` | approved |
| E1 | JSON codec for ledger records; schema file; connection helper | property test: any record round-trips |
| E2 | `Journal`: memory and Postgres | one contract test passes on both; stored-and-loaded ledger equals the in-memory one for any sequence of appends |
| E3 | `Runner`, the journal client, the spend cap | tests: a finished step is not run again; a step killed mid-way leaves no entry; its calls are not paid again; the cap stops a run before the call that would exceed it |
| E4 | The engine run and the memo as steps | the benchmark report and the three committed memos reproduce unchanged |
| E5 | Spans for run, step and model call | span tree and attributes asserted from the in-memory exporter |
| E6 | Kill-and-resume measurement and cost report; section cache stored in Postgres | results file committed |
| E7 | Trace viewer in `compose.yaml` (cut first) | a run's trace opens in the viewer |

None of the four owner-authored files is touched: the tool loop is wrapped, not changed.

## What is measured

On the large scenario, from the replay cache, so no model is paid:

| Measure | How |
|---|---|
| Paid calls repeated after a kill | process killed with SIGKILL at three points (mid-finder, between steps, mid-memo), then resumed; calls reaching the inner client twice |
| Same result | ledger and memo of the resumed run compared with an uninterrupted run |
| Time added by the journal | run time with the memory journal and with Postgres |
| Cost per step | sum over `calls`, checked against the benchmark report's total |

## Expected outcome, stated before the run

No call repeated at any of the three kill points. The resumed ledger and memo are identical to the uninterrupted ones. The journal adds under one second to a run on a local database. Cost per run from the `calls` table equals the benchmark report's figure to the cent of a cent.

## Cost

No live model call. Everything runs on existing recordings. No prompt, context, retrieval or model change, so no benchmark rerun is due; the scores must reproduce unchanged, and that is a test.

## New dependencies

`psycopg[binary]` and `opentelemetry-api` in the platform; `opentelemetry-sdk` in the dev group. One ADR each for the first two.
