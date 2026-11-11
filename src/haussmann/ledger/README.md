# ledger

Append-only facts, citations and conflicts.

## Contract

Facts with citations are written in transactions by agents or experts and are never updated in place. Conflicts between facts are first-class records.

## Status

`ledger`: `Ledger` (in memory), the records a step appends (`NewFact`, `Assess`, `NewConflict`, `Resolve`, `Ask`) and what it reads back (`Fact`, `Conflict`, `Question`, `Status`). Design: `docs/notes/ledger.md`.
