# ctxkit: search and context assembly

Status: written and implemented 2026-11-11; open to revision.

## Where this fits

A model only knows what is in its prompt. `ctxkit` decides what goes in. It has two jobs in this slice: finding the pages worth showing (`search`), and packing the chosen pieces into one prompt that fits a size limit, in a fixed order, with a record of what was kept and what was left out (`assemble`).

```
elements ──> Index ──search("hauteur maximale")──> best pages
                                                      │
instructions, task, document list, pages ──> assemble(budget) ──> prompt text + manifest
```

Every fact-finder starts from a prompt built this way, and uses `search` as a tool while it works.

## Boundaries

```python
Index(elements).search(query: str, k: int) -> list[Hit(element, score)]

ContextItem(tier: str, source: str, text: str)
assemble(items, tiers, budget, required=(), count=estimate_tokens) -> Assembled
Assembled(text: str, items, manifest: tuple[Entry, ...], tokens: int)
Entry(tier, source, tokens, included: bool)
```

Example: with tiers `("instructions", "task", "documents", "elements")` and a budget of 4,000 tokens, the instructions and task always go in; document summaries next; then pages, best first, until one does not fit. The manifest lists every item with its size and whether it made it.

## Decisions

**Search is by keywords, ranked with BM25.** A page scores higher when it contains the query's words, more so for rare words and short pages. It needs no model, no stored vectors and no network, and it is exact for the codes, names and numbers these documents are full of. Whether adding embeddings helps is decided by measurement on the large scenario, not assumed.

**Words are compared without case or accents,** so `GENERALES` finds `générales`.

**Tiers give the order and the priority.** The caller names the tiers from most to least important. Items are placed in that order, so the top of every prompt (instructions, task) is the same from call to call, which is what lets a provider cache it.

**A hard budget, enforced per item.** An item goes in only if it fits what is left. An item that does not fit is skipped and the next one is tried, so one long page cannot crowd out several short ones. Items in a tier marked required must fit or the call fails: a prompt without its instructions is a bug, not a degraded mode.

**Token counts are an overestimate,** one token per three characters, unless the caller supplies a counter. The budget is then a safe upper bound without a tokenizer.

**The manifest is part of the result.** For any model call it says exactly what the model saw and what was dropped. Two runs can be compared item by item, and the effect of removing a tier can be measured.

**Same inputs, same prompt.** Nothing in assembly depends on time, randomness or iteration order of a set.

## Tests

- Search: matches by shared words; accents and case; a rare word outranks a repeated common one; no match gives nothing; stable order.
- Assembly: tier order then given order; skip-and-continue when an item does not fit; required overflow fails; unknown tier is an error; adding lower-tier items never changes the text before them; a property test that the budget is never exceeded and the result is deterministic.

## Not in this slice

Compaction of long tool results, memory of expert corrections, reranking and embeddings. Each is added when a measured run shows the need.

## Alternatives rejected

- **Embeddings as the only search.** They blur exactly what matters here: `UB` against `UC`, 9 against 19.
- **Truncating the prompt at the budget.** It cuts an item in half and can cut the instructions.
- **Filling by relevance alone, ignoring tiers.** The order of the prompt would change from call to call and nothing could be cached.
