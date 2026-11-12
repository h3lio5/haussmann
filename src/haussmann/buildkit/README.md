# buildkit

Deliverable spec and content-hashed incremental build.

## Contract

A deliverable is a pure function of the inputs it is given. Sections are build targets hashed over those inputs; an unchanged hash is a cache hit and no author is called.

```python
targets(spec, inputs, environment) -> tuple[Target, ...]
await build(targets, authors, cache) -> tuple[Built, ...]
fill(sentence, inputs, flag_mark) -> str
prose_author(ask, label, refused) -> Author      # model draft, checked by code, plain list as fallback
```

The package never reads a ledger and never formats a value: the caller prepares each `Input` with its printed text and a digest of its value and sources.

Design: `docs/notes/buildkit.md`, `docs/notes/writer.md`.
