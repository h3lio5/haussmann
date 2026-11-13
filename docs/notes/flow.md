# flow: a run as journaled steps

Status: approved 2026-11-13; open to revision.

## Where this fits

A run is a sequence of steps that read the ledger, call a model and append to the ledger. Today the sequence is a function in one process: a crash loses the ledger and every model call is paid again. `flow` puts a journal under that function, so that a run can be stopped at any point and continued, by the same process or another one.

```
workload run
   │  await runner.step("find:site:0", fn)
   ▼
Runner ── finished already? ──yes──> return the stored result
   │ no
   ▼
fn(ledger, client) ── client.complete(request) ──> journal has this call? ──yes──> stored response
   │                                                   │ no: check the cap, pay, store
   ▼
journal.commit(step, new ledger entries, result)        one database transaction
```

- **Called by**: the workload's run (`engine/run.py`, `engine/memo.py`). It names the steps; the platform does not know what they do.
- **Needed because**: a finder pass costs money and time, a file of several hundred pages has dozens of them, and a failure in step 30 should not cost steps 1 to 29 again. The same record answers what a run cost and where.
- **Imports**: `ledger`, `llmkit`, `coretypes`, psycopg. It sits in the layer above the ledger and the client and below `buildkit`.

## Structures

```python
type Json = None | bool | int | str | list[Json] | dict[str, Json]
type StepFn = Callable[[Ledger, LLMClient], Awaitable[Json]]

@dataclass(frozen=True, slots=True)
class RunState:
    run_id: str
    entries: tuple[Entry, ...]        # every ledger entry committed so far, in order
    done: Mapping[str, Json]          # finished step key -> its result

class Journal(Protocol):
    async def open(self, run_id: str, inputs_digest: str) -> RunState
    async def call(self, run_id: str, key: str) -> Response | None
    async def record_call(self, run_id: str, step: str, key: str, response: Response, cost_usd: Decimal) -> None
    async def commit(self, run_id: str, step: str, entries: Sequence[Entry], result: Json) -> None
    async def spent(self, run_id: str) -> Decimal

MemoryJournal()                       # tests, the benchmark
PostgresJournal(connection)           # everything else

class Runner:
    ledger: Ledger                    # the run's ledger, rebuilt from the journal when the run is opened
    async def step(self, key: str, fn: StepFn) -> Json

async def open_run(journal, run_id, inputs_digest, client, prices, cap_usd) -> Runner

class SpendCapReached(Exception): run_id, spent, cap
class InputsChanged(Exception): run_id
class StepRepeated(Exception): key
```

`Journal` is an interface because both implementations exist and are used: the benchmark and the tests run with no database, and the two must behave the same, which one shared test checks.

What the workload writes:

```python
runner = await open_run(journal, run_id, digest, client, PRICES, cap_usd=Decimal("0.50"))
for number, group in enumerate(plan(wanted)):
    await runner.step(f"find:{number}:pass1", lambda ledger, client: find(group, ..., ledger, client))
    ...
await runner.step("verify", ...)
```

Steps are named by the workload as it goes, not declared in advance, because which steps exist depends on the ledger: a second pass runs only if the first left facts untouched.

## Tables

```sql
runs           (id text primary key, inputs_digest text, created_at timestamptz)
steps          (run_id, key, seq int, result jsonb, done_at timestamptz,          primary key (run_id, key))
ledger_entries (run_id, tx int, position int, author text, step text, record jsonb, assigned_id text,
                                                                                  primary key (run_id, tx, position))
calls          (run_id, key text, step text, model text, input_tokens int, output_tokens int,
                cost_usd numeric, response jsonb, at timestamptz,                 primary key (run_id, key))
```

One SQL file with `create table if not exists`, applied when a journal is opened. No migration tool until a table has to change under existing data.

## Behaviour

1. **Opening.** `open` creates the run or loads it. A run that exists with another `inputs_digest` is refused: the digest covers the document hashes, the list of required facts, the model and the reference date, and a run resumed on other inputs would mix two files in one ledger. The Postgres journal takes a session advisory lock on the run id; a second process opening the same run is refused while the first lives.
2. **A step that is done** returns its stored result. Its function is not called.
3. **A step that is not done** gets the run's ledger and a client bound to the step. When the function returns, the entries it appended since the step began and its result are committed with the step row in one transaction. If the function raises, or the process dies, nothing of the step is stored and the in-memory ledger is discarded with the process.
4. **A model call** is looked up by `request_key(request, sample)`, the hash the replay cache already uses, within the run. A hit returns the stored response. A miss checks the cap, calls the inner client, and stores the response with its cost before returning it.
5. **The cap.** Before a call is paid, the run's total so far is compared with the cap. At or above it, `SpendCapReached` is raised, the step fails and nothing of it is committed. The run can be opened again with a higher cap and continues from the same step, with its earlier calls already paid and stored.

## Why a resumed step does not pay twice

A step that is run again starts from the same ledger, since nothing of its first attempt was committed, and the same inputs. If its code is deterministic it sends the same first request, finds the stored response, and so on down the same path until it reaches the call that was never made. The ledger entries it appends on the way are the same as the first time, including the ids the ledger assigns.

This puts one requirement on step functions: given the ledger and their inputs, they make the same requests. No clock, no random choice, no iteration over an unordered set. The reference date is an input of the run for this reason. A step that breaks the rule still runs correctly; it pays for the requests that differ, and the journal counts them, so the break shows as a cost and not as a wrong ledger.

## Invariants

- A step's ledger entries and its done row are committed together or not at all.
- A finished step's function is never called again in that run, and its entries are never written twice (primary keys on both tables).
- The ledger loaded from a journal is equal to the ledger that was committed: same facts, ids, statuses, conflicts, questions and transaction numbers.
- A model call recorded in a run is never sent to the provider again by that run.
- The cap is checked before every paid call; a run's recorded cost can exceed its cap by at most the cost of one call.
- The two journals give the same results for the same sequence of operations.
- No ledger rule is written in SQL. The `Ledger` class is the only code that decides whether an append is valid; the database stores entries it has already accepted.

## Changes to the ledger

`Entry` becomes public and gains nothing: `(tx, author, record, assigned_id)`. Two additions: `ledger.since(tx) -> tuple[Entry, ...]` for the runner to collect a step's appends, and `Ledger.load(entries)` which replays entries through the same checks as `append`, so a corrupted store is refused and not trusted. A JSON codec for records lives next to them.

## Known limits

- **Paid twice in one window.** A call that returns as the process dies, before its row is written, is paid again on resume. Closing the window would need the provider to accept an idempotency key.
- **One process per run.** There is no queue and no worker pool. The advisory lock makes a second process fail fast; it does not hand the run over.
- **No retry.** A step that raises fails the run. Opening the run again is the retry, and it is manual.
- **A step is the unit of loss.** Ledger appends made by a finder before a kill are redone, at no model cost, when the step is run again.
- **Results must be small JSON.** A step that produces something large writes it to the ledger or to a file and returns a reference.

## Alternatives rejected

- **A second ledger implementation in SQL.** Every invariant of the ledger would exist twice and have to be kept equal. Storing accepted entries and replaying them through the one class gives durability without a second set of rules.
- **Write each ledger append to the database as it happens.** A killed step would leave half its facts behind, and running it again would record them twice. Undoing them would mean deleting from an append-only store.
- **Journal steps only, not calls.** A step killed after nine of ten calls would pay for all ten again; the finder is the expensive step and the one most likely to be interrupted.
- **The replay cache as the call journal.** It is a folder of files shared by all runs and committed to the repository for tests. A run's record of what it paid belongs to the run, in the same transaction scope as its steps, and is what cost is summed over.
- **A workflow engine (Temporal, DBOS).** The right answer at scale and the named replacement behind this interface. For one process and four tables it would add a server or a framework's execution model to explain, where the mechanism here fits on a page.
- **Declaring the steps as a graph.** The steps depend on what earlier steps found; a static graph would need conditional nodes to say what a loop says.

## Tests

- Contract, run on both journals: open, record calls, commit steps, open again; the state loaded equals the state committed. Property: for any sequence of valid ledger appends split into steps, the loaded ledger equals the in-memory one.
- A finished step is not run again and returns its stored result.
- A step that raises leaves no entry and no step row; its recorded calls remain.
- A step killed after n calls and run again sends only the calls after n to the inner client, and commits the same entries as an uninterrupted run.
- Committing a step twice is refused and changes nothing.
- A run opened with another inputs digest is refused; a second connection opening a locked run is refused.
- The cap stops a run before the call that would pass it; reopening with a higher cap continues.
- A step that makes a request it did not make the first time pays for it, and the divergence is counted.
- Codec: any ledger record round-trips through JSON.

Database tests carry the `db` marker and run when `HAUSSMANN_DB_URL` is set, as it is in CI; each test uses its own run ids and leaves the schema in place.
