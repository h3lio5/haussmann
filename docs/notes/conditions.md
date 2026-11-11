# Conditions: facts that hold only when another fact has a given value

Status: written and implemented 2026-11-11; open to revision.

## Where this fits

Some statements in a file are true for a case, not for the file. A zoning regulation gives a maximum height for each zone; only one of them is the height for the site, and which one depends on another fact, the site's zone. Today the ledger cannot say this. The finder records four heights under one key, settling sees four values of equal standing, and the key is escalated (E007: 9 of 9 such facts lost).

A condition lets a fact carry the case it is true for, so that code, not a model, picks the applicable one once the deciding fact is settled.

```
finder ── record_fact(value, applies_to) ──> ledger: fact + condition
                                                │
verify:  settle deciding keys ──> set aside facts under another condition ──> settle dependent keys
```

- **Called by**: `record_fact` in the workload's finder writes conditions; `verify` in the platform reads them, once per run, where it settles keys today.
- **Needed because**: the alternative is to let the finder choose the applicable rule, which removes the evidence for the choice and cannot be tested without a model.

## Structures

```python
# ledger
@dataclass(frozen=True, slots=True)
class Condition:
    key: FactKey      # the deciding fact, for example site/zone
    value: str        # the case as the document writes it, for example "Zone Ua"

NewFact(key, value, citations, method, holds_when: Condition | None = None)
Fact(..., holds_when: Condition | None)
Status.SET_ASIDE      # verified at its source, but stated for another case

# verify
verify(ledger, elements, cards, schema, keys, totals, renderings,
       depends_on: Mapping[FactKey, FactKey] = {})   # dependent key -> deciding key

# workload
RequiredFact(key, text, sum_of=(), depends_on: FactKey | None = None)
record_fact(..., applies_to: str = "")   # tool argument, only offered for dependent facts
```

Input and output of `verify` keep their shape: a ledger in, the same ledger with more records out. The only new records are `Assess(fact_id, Status.SET_ASIDE, "stated for <value>; <key> is <settled value>")`.

## Behaviour

1. **Recording.** For a fact with `depends_on`, the finder may give `applies_to`. It leaves it empty when the document states the value for the property itself, as a planning certificate does. A non-empty `applies_to` must have the form the workload declares for the deciding fact (for a zone: the word "zone" and its name) and must appear in the cited document; otherwise the tool refuses the record and says why.
2. **Order.** `verify` settles deciding keys before the keys that depend on them.
3. **Setting aside.** Before a dependent key is settled, each verified fact with a condition is compared with the settled value of its deciding key. If they do not match, the fact is marked `SET_ASIDE` and takes no part in grouping, conflicts or totals.
4. **Matching.** Both texts are case-folded and their spaces collapsed. They match if they are equal or if the settled value occurs in the condition as a whole word: "Uc" matches "Zone Uc" and does not match "Zone Ua".

## Invariants

- A fact without a condition is never set aside.
- If the deciding key has no settled fact (nothing found, or its own conflict was escalated), no fact is set aside and the dependent key behaves as it does today. An uncertain case never removes evidence.
- A set-aside fact stays in the ledger with its citation and the reason; `settled` returns it in `set_aside`, apart from the supporting facts, so a reviewer sees the rule of every zone and why one applies, and a memo never cites a rule that was not used.
- A deciding key may not itself depend on another key. `verify` refuses such a mapping. One level is all the workload has; chains are not built until one exists.
- The citation check is unchanged and runs first: a fact must be verified at its source before its condition is looked at.
- No domain vocabulary in the platform: it knows keys and conditions. The workload declares that height, storeys, footprint and setback depend on the zone.

## What the model does and does not decide

The model reads which case a sentence is written for and copies it. Code checks that text is in the cited document, and code decides which case applies. The model never chooses between the rules.

## Known limits

- If the finder leaves `applies_to` empty for a rule of another zone, that rule is not set aside and the key escalates, as today. The failure is soft and visible in the ledger.
- If the finder copies the wrong zone from a document that names several, a correct rule can be set aside. The check that the text is in the document does not catch this. In E008 it did not happen: all 20 facts set aside on the large scenario carried the zone their document is written for.
- E008 showed the finder sometimes fills `applies_to` with other words from the page ("alignement", "R+6"). They were in the cited document, so the tool accepted them, and the facts were set aside. The set of cases is not known before the documents are read, but the way a case is written is: the workload now declares a form per deciding fact (`CASE_FORMS`), and the tool refuses anything else. A text of the right form that names no real case can still pass.
- Matching is textual. Two spellings of the same case that share no whole word ("zone urbaine centrale" and "Uc") do not match, and the dependent key then escalates.

## Tests

- Facts under another condition are set aside; the one under the settled case, and facts without a condition, are settled as before.
- Deciding key missing, or escalated: nothing is set aside.
- A set-aside fact is excluded from conflicts and from a computed total, and is returned in `set_aside`, not as supporting.
- A mapping with a chain is refused.
- `record_fact`: `applies_to` absent from the cited document is refused; empty is accepted.
- Matching: equal, whole word, different case and spacing, near miss ("Uc" against "Zone Ucb").

## Alternatives rejected

- **Tell the finder the settled zone and ask for that zone's rules only.** Less code, but the choice moves into the model, the other zones' rules never reach the ledger, and the two earlier attempts to steer the finder by instruction (E005, E006) each moved unrelated traps.
- **One key per case (`zone:Ua/max_height`).** The cases are not known before the documents are read, and the answer would still need a step that maps the site to one of them.
- **Rank by document authority.** All zone documents are the same kind of document with the same standing; authority cannot separate them.
- **Remove other-case documents at ingest.** E006 showed that removing a document on an uncertain judgment costs more than it saves; a regulation for another zone is also still evidence a reviewer may want.
- **Reuse `REJECTED` for set-aside facts.** A set-aside fact is true at its source; a separate status keeps "wrong" and "true for another case" apart in review.
