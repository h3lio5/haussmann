# flow

Durable step runner.

## Contract

A run is a sequence of named steps. Each step gets the run's ledger and a model client, and what it appends is stored together with its completion. A run that stops, for any reason, is opened again and continues at the first unfinished step; a model call the run has already paid for is served from the journal.

```python
runner = await open_run(journal, run_id, inputs_digest, client, prices, cap_usd)
result = await runner.step("verify", fn)  # fn(ledger, client) -> small JSON
runner.ledger  # as of the last finished step
await journal.costs(run_id)  # calls, tokens and cost per step
```

- `journal.py`: the `Journal` protocol and `MemoryJournal`.
- `postgres.py`, `schema.sql`: `PostgresJournal` and its four tables.
- `runner.py`: `Runner`, `open_run`, `SpendCapReached`.

Design and limits: `docs/notes/flow.md`.

## Status

Journal and runner implemented. Spans are not emitted yet; there is no queue and no retry.
