# ctxkit

Retrieval and context assembly under a token budget.

## Contract

Given a task and a budget, assemble the context for one model call from prioritized items and record a manifest of what went in.

## Status

`search` (`Index`, keyword search over elements) and `assemble` (`assemble`, `ContextItem`, the manifest). Design: `docs/notes/ctxkit.md`. Compaction and memory not started.
