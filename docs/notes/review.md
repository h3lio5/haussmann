# review: an expert's correction, what it rebuilds, and what it leaves behind

Status: written and implemented 2026-11-13; open to revision.

## Where this fits

A run ends with a settled ledger and a memo. `review` is what lets a person change the outcome without losing the record: a correction is a ledger transaction, the memo is rebuilt from the ledger, the difference is shown, and the correction becomes a case the engine is checked against from then on.

```
expert ──edit(key, value, reason)──> ledger: an expert fact
                                        │
            verify again (settle, totals, cases of dependent keys, date rules)
                                        │
                     memo step ──> sections whose inputs changed are rewritten
                                        │
                diff(before, after) ──> what the reviewer sees
                                        │
                     case(run, key, value) ──> evalkit: checked on every later engine
```

- **Called by**: the workload's run, as a step of the same runner that ran the engine, and in M3's second slice by the HTTP API.
- **Needed because**: an edit made on the memo's text would be lost at the next build and would teach the system nothing. An edit made on a fact survives rebuilds, shows its effect, and is evidence about where the engine is wrong.
- **Imports**: `ledger`, `verify`, `buildkit`. It sits on top of the platform; nothing imports it.

## Structures

```python
# verify.settle
EXPERT = "expert"                        # a fact's method, beside "extracted" and "computed"
Standing(expert: int, computed: bool, authority: int, date: dt.date)   # expert is the fact's transaction number, 0 for others

# review.edits
edit(ledger, key, value, reason, author) -> str          # the new fact's id

# review.diff
@dataclass
class SectionDiff:
    section_id: str
    rewritten: bool                       # its hash changed
    values: tuple[ValueChange, ...]       # input name, text before, text after; None for added or removed
    removed: tuple[str, ...]              # sentences, as printed, no longer in the section
    added: tuple[str, ...]
diff(before: Sequence[Built], after: Sequence[Built], inputs_before, inputs_after, flag_mark) -> tuple[SectionDiff, ...]

# review.state
type Event = Approve | RequestChanges | Comment          # each names a section, the section's hash, an author
State = DRAFT | IN_REVIEW | CHANGES_REQUESTED | APPROVED
states(built: Sequence[Built], events: Sequence[Event]) -> Mapping[str, State]
approved(built, events) -> bool                          # every section is

# evalkit.cases
Case(scenario_id, sample, key, expected: Value, reason, author)
check(case, settled_value, schema) -> bool
```

## Behaviour

1. **An edit is a fact.** `edit` appends, in one transaction, a fact with method `expert`, the author's name and no citation, and its assessment as verified with the expert's reason. Nothing else in the ledger changes.
2. **Settling is run again, and may be.** `verify` is now idempotent: a key whose disagreement is already recorded with the same sides and the same outcome gets no new record, and a total whose recomputation gives the value already computed gets no new fact. After an edit it therefore adds records only for the keys the edit touches.
3. **The expert's fact wins.** The settling order becomes expert, computed, authority, date. Between two expert facts on one key the later transaction wins. The facts it overrules stay verified at their sources and stay in the conflict, so the reviewer and any later reader see what the documents said and that a person decided otherwise.
4. **What follows from the edit is recomputed by code.** A total that includes an edited part is recomputed; the earlier computed total is marked rejected with the reason. When the edited key decides a case (the zone), facts stated for the new case are restored and facts stated for the old one are set aside. The workload's date rules are applied to the new value.
5. **The memo is rebuilt by the runner.** The edit is a step; the memo is the next step, named after its sections' hashes, so a memo whose inputs changed is a new step. Sections whose inputs did not change send the requests they sent before and cost nothing.
6. **A value set by an expert is not printed as doubtful.** It carries no flag mark and is not listed among the points to resolve; date flags on it still are.
7. **Review state is derived, not stored.** A section that has inputs is in review once built. An approval or a request for changes names the section's hash; it counts only while the section still has that hash. A rebuild that changes a section returns it to review; one that does not leaves its approval in place.
8. **An edit becomes a case.** The case records the scenario, the sample, the key and the expert's value. `evalkit` replays the engine on recordings and compares what it settles with the case.

## Regression cases: held and open

A case the engine already satisfies is **held**: it must keep passing, and CI fails if it stops. A case the engine does not satisfy is **open**: it is a known error with a named expected value, listed in the report and not a CI failure, since an expert's correction of the engine is by definition something the engine gets wrong at that moment. When a change makes an open case pass, the next run of the cases command records it as held, and it gates from then on.

## In the workload

- `engine/run.py`: `apply_edit(runner, ...)` records the edit and settles again as one step named `edit:<n>:<key>`; `settle_ledger` is the settling the engine's own `settle` step runs.
- `engine/memo.py`: `bind` treats a value an expert set as decided: no flag mark and no entry among the points to resolve, unless a date rule flags it.
- `benchmark/cases.py` and `benchmark_data/cases.json`: the cases, the command that checks them (`python -m feasibility_fr.benchmark.cases`, `--update` to record standings) and `results/cases.md`. The gate is a test, so it runs wherever the tests run, CI included.

The first three cases: the owner on one small scenario (open: the engine settles on nothing), and two values the engine lost before E013, the flood exposure and a floor area on the large scenario (held).

What is not measured yet: the rebuild after a real edit on a real memo. The test does it on a scripted model. On a dev memo the rewritten section needs one model call that has no recording.

## Invariants

- An edit never changes or removes a fact, a citation, a conflict or a resolution written before it.
- After an edit the key settles on the expert's value, whatever the documents' standing.
- Running `verify` twice in a row appends nothing the second time.
- A section's approval never applies to text other than the text that was approved.
- A comment is attached to a section and to the facts a sentence uses, not to a position in the text, so it survives a rewrite that keeps those facts.
- `diff` of a build with itself is empty; every value change it reports is in a section it marks rewritten.

## Known limits

- An expert's fact has no citation. The reason and the author are its provenance; attaching a source to an edit comes with the screen, where the expert can point at one.
- An edit is checked for kind and unit against the schema and for nothing else. An expert can enter a wrong value.
- A chain of consequences is one level deep, as in settling: totals of parts and cases of one deciding key.
- Review events are held by the caller in this slice. Their storage comes with the API.

## Alternatives rejected

- **Editing the memo's text.** The next build would overwrite it, and the ledger would still say what the expert corrected.
- **Rejecting the facts the expert overrules.** They are true at their sources. Marking them wrong would destroy the evidence that a document and an expert disagree.
- **A separate table of overrides consulted when settling.** Two places would decide what a key's value is.
- **Storing a state per section.** It would have to be kept in step with builds; deriving it from the hash that was approved cannot drift.
- **Failing CI on every open case.** The gate would be red from the first correction and would be switched off.

## Tests

- An edit wins over a higher-authority, later and computed fact; the overruled facts keep their status; a second edit wins over the first.
- An edit of an open question settles it without a conflict.
- An edited part changes the recomputed total; an edited deciding key swaps which conditional facts apply.
- `verify` twice appends nothing; property test over ledgers.
- Through the runner on a scripted model: after one edit, only the sections that use the fact are rewritten, with one model call each, and the diff names the value and the sentences.
- Review state: approval, a request for changes, a rebuild that changes the section and one that does not.
- Cases: a held case that stops passing fails the check; an open case does not; a case round-trips through its file.
