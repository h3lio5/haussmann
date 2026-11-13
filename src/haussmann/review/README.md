# review

Expert review of a deliverable.

## Contract

An expert's correction is a ledger transaction; the deliverable is rebuilt from the ledger; the difference between two builds is reported by value and by sentence; each section's review state is derived from the decisions made on its current text.

```python
edit(ledger, key, value, reason, author, schema) -> fact id      # edits.py
diff(before, after, inputs_before, inputs_after, flag_mark)      # diff.py
states(built, events), approved(built, events), comments(...)    # state.py
```

Settling after an edit is `verify.settle.verify`, which may be run again at any time. Regression cases made from edits are in `evalkit.cases`.

Design and limits: `docs/notes/review.md`.

## Status

Core implemented, no storage of review events and no HTTP API yet.
