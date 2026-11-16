# engine

The steps of a run, for any workload.

## Contract

A workload passes one `Workload` record: its schema, document types, date rules, language and every instruction text. The engine owns the order of the steps and the shape of each model request; it holds no instruction text of its own.

```python
ingest(workload, folder, client, model, skip) -> Ingested                  # ingest.py
run_engine(workload, wanted, elements, cards, runner, model, as_of)        # run.py
apply_edit(workload, runner, wanted, elements, cards, as_of, key, value, reason, author)
memo_step(workload, runner, asked, model, cache) -> Memo                   # memo.py
revise_step(workload, runner, memo, section_id, comment, model) -> Proposal
render(workload, memo, as_of) -> str
```

`find` (finder.py) is one bounded tool loop on one group of facts; what it finds is written to the ledger. `flag_dates` (dates.py) applies the workload's date rules to settled facts.

Called by a workload's entry points: its review session, its demo command, its benchmark.

Design: `docs/notes/workload-definition.md`, `docs/notes/engine.md`, `docs/notes/writer.md`.
