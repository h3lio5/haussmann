# verify

Checks facts against their sources, finds disagreements and settles them by rule.

## Contract

`citations`: does the passage a fact cites really state its value. `settle`: give each candidate fact a status, record a conflict when verified facts disagree on a key, resolve it by rule or escalate it, and compute declared totals from their settled parts. No model is called. Design: `docs/notes/verify.md`.
