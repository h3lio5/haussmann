# Slice D plan: the memo as a build

## Why

The engine ends at a ledger of settled facts. The product is a memo an expert can read, check and correct. This slice turns the ledger into that memo, so that no number in it comes from the model and a corrected fact rebuilds only the sections that use it.

## Where it fits

```
ledger (settled facts, conflicts, open questions)
   │
   ├─ spec: sections and the facts each needs          (D1, buildkit; declared by the workload)
   ├─ target hash per section                          (D2, buildkit)
   ├─ writer: one model call per changed section       (D3, buildkit mechanism, workload prompt)
   └─ deliverable: sections -> sentences -> fact ids -> citations
```

- **Called by**: the workload's run, after `verify` and the date rules. The benchmark `Submission` is unchanged and still read from the ledger.
- **Read by**: the review interface in M3 (click a sentence, see its facts and sources) and the rebuild after an expert edit.

## Structures

```python
# buildkit (no domain vocabulary)
Section(id, title, attributes: tuple[str, ...], guidance: str, kind: "prose" | "disagreements" | "open")
Spec(id, version, sections)

Input(name, attribute, text, digest, flagged)       # a settled fact, its value already formatted by code
Target(section, inputs, hash)

Sentence(text, uses: tuple[str, ...])                # the inputs it names
Built(section_id, hash, sentences, reused: bool)

build(targets, authors, cache) -> sections
```

A section selects facts by attribute, not by key, because subjects differ between files (one file has two leases, another five).

## D1: the spec

The feasibility memo is declared in the workload as data:

| Section | Facts | Kind |
|---|---|---|
| Site and ownership | parcel, land area, owner, zone | prose |
| Planning rules | height, storeys, footprint, setback, planning certificate | prose |
| Risks and studies | flood risk, soil study, pollution study | prose |
| Occupancy and income | rents, lease ends, total rent | prose |
| Floor areas | areas, total area | prose |
| Price | lot prices, total price | prose |
| Points to resolve | every disagreement, escalation and date flag | from the ledger, by code |
| Open questions | every required fact with nothing settled | from the ledger, by code |

The facts a run must establish become the union of the sections' attributes, so the spec is what drives the finders.

## D2: target hashing

A section's hash covers everything its text depends on: spec version, section id and guidance, prompt version, model id, and for each bound fact its key, canonical value, flag reasons and citations. Fact ids are left out, so the same fact found again in a new run does not force a rewrite.

- Same hash: the stored section is reused and no model is called.
- An edited fact changes the hash of the sections that select its attribute, and no other.

## D3: the writer

1. Code formats every bound value (French number and date forms) and gives the model a list: `{site.land_area}` = "4 838 m²", flagged or not. Placeholders are named after the fact's key, not its ledger id, so they are the same from one run to the next.
2. The model writes sentences that use the placeholders. It never sees a task that needs arithmetic.
3. Code checks the draft: every placeholder is bound; every bound fact is used; no digit appears outside a placeholder. A failed check is returned to the model once. A flagged fact is printed with a fixed mark by code, so the warning does not depend on the model's wording.
4. If the second draft fails, the section is written by code as a plain list of facts. A section always builds.
5. Code substitutes the values and records, per sentence, the fact ids it uses.

The two ledger-driven sections are written by code only.

## Left out of this slice

- **A second model as critic.** The checks in step 3 are code. A rubric judge for prose quality needs hand-labelled claims and is planned with the review interface.
- **English.** French first; a second language is a second prompt and formatter.
- **Storage.** The cache is in memory or a folder of files; Postgres comes with Slice E.

## Tasks

| ID | Task | Done when |
|---|---|---|
| D0 | Design notes: `docs/notes/buildkit.md` (spec, hashing, build) and `docs/notes/writer.md` | approved |
| D1 | `Spec`, `Section`; the memo spec in the workload; required facts derived from it | the engine's fact list comes from the spec and the benchmark recordings still replay |
| D2 | `Target`, hashing, `build` with a cache | property tests: order of facts never changes a hash; changing one fact changes exactly the sections that select it |
| D3 | Writer: bind, check, retry once, fall back, substitute | tests on recorded drafts: an unbound placeholder, an unused fact and a stray digit are each refused; a flagged fact is always printed with its mark; the fallback builds |
| D4 | Memo output: Markdown, plus the sentence-to-fact-to-citation record | one memo per dev scenario committed with its recordings |
| D5 | Live run E010 and a rebuild measurement | row in `EXPERIMENTS.md` |

## What is measured

| Measure | How |
|---|---|
| Numbers not bound to a fact | count in final memos; must be 0 by construction, reported with the retry and fallback rates |
| Coverage | settled facts that appear in the memo, out of all settled facts |
| Rebuild after one edited fact | sections rewritten and model calls, out of the total |
| Cost and time per memo | from recorded usage |

Prose quality is not scored in this slice and is not claimed.

## Expected outcome, stated before the run

No unbound number in any memo. Fallback on fewer than one section in ten. One edited fact rewrites one or two sections of six. A memo costs under 0.01 USD.

## Cost

Six short calls per memo, three dev scenarios: about 0.02 USD for the first live run, well under the 2 USD line. The engine's own recordings replay and are not re-recorded.

## No new dependency

Standard library only (`hashlib`, `json`).
