# ledger: facts, their sources and their standing

Status: written and implemented 2026-11-11; open to revision.

## Where this fits

The ledger is the engine's memory. Fact-finders write candidate facts into it; the verifier records what it thinks of each; the resolve step records which fact wins a disagreement; the memo and the benchmark submission are read from it. Steps never pass each other text: a step reads the ledger, does its work, and appends.

```
fact-finders ──append facts──┐
verifier ──append assessments, conflicts──┤──> ledger ──read──> resolve, compute, memo, submission
resolve ──append resolutions──┘
```

## Boundaries

What a step appends, in one transaction:

```python
NewFact(key: FactKey, value: Value, citations: tuple[Citation, ...], method: str)
Assess(fact_id: str, status: Status, reason: str)
NewConflict(key: FactKey, fact_ids: tuple[str, ...], kind: str)
Resolve(conflict_id: str, chosen: str | None, reason: str)      # None: escalated to a person
Ask(key: FactKey, reason: str)                                  # an open question

Citation(doc_id: str, locator: str | None, quote: str = "")
Status = CANDIDATE | VERIFIED | UNVERIFIED | REJECTED

ledger.append(author: str, records) -> int                      # the transaction number
```

What comes back out:

```python
Fact(id, key, value, citations, method, author, tx)             # immutable once written
ledger.facts(key=None) -> tuple[Fact, ...]
ledger.fact(fact_id) -> Fact
ledger.status(fact_id) -> Status                                # CANDIDATE until assessed
ledger.conflicts() -> tuple[Conflict, ...]                      # each with its resolution, if any
ledger.questions() -> tuple[Question, ...]
ledger.at(tx) -> Ledger                                         # the ledger as it was after tx
```

Example: a fact-finder appends `NewFact(("site", "max_height"), 9 m, [Citation("plu_2020", "p3")], "extracted")` and gets `f1`. The verifier later appends `Assess("f1", VERIFIED, "value found at p3")`. Nothing about `f1` itself changes.

## Decisions

**Nothing is ever changed or deleted.** A fact is written once. Its standing is a separate record appended later, and the latest one wins. This is what lets a section of the memo be rebuilt only when the facts it used are different facts, and lets a reviewer see who said what and when.

**Several facts may share a key.** Two documents that disagree produce two facts. Choosing between them is the resolve step's job and is itself a record, so the losing fact and the reason stay visible.

**A transaction is all or nothing.** Every record in an append is checked first: a status for a fact that does not exist, or a resolution that picks a fact outside the conflict, rejects the whole append and leaves the ledger as it was.

**Ids are assigned by the ledger,** in order (`f1`, `c1`), so a record cannot name something that has not been written.

**An in-memory ledger for this slice.** It is a list of records and a few lookups. The Postgres implementation arrives with the durable runner and will have to pass the same tests; the interface is introduced then, when there are two.

**The ledger makes no judgements.** It does not decide that two facts conflict or which one is right. It stores what the steps decide.

## Invariants (property-tested)

1. Appending never changes an earlier fact, conflict or question.
2. `at(tx)` gives the same answers after any number of later appends.
3. A rejected append leaves the ledger identical.
4. Ids are unique and increase with the transaction number.
5. `status` is the status of the latest assessment of that fact, or CANDIDATE.

## Alternatives rejected

- **A mutable table of current facts.** Simpler to query, but an edit would erase what it replaced, and incremental rebuild would have nothing stable to hash.
- **Status as a field on the fact.** It would make a fact change when it is verified.
- **Postgres from the first slice.** Every test would need a database before any step exists to use it.
