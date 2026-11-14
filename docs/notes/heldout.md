# Held-out scenarios: rules fixed before they are written

Status: written 2026-11-14, before any held-out scenario exists. The engine is frozen at the tag `engine-freeze-m3`.

## Where this fits

Every score so far is on three dev scenarios that the engine was built against: thirteen experiments read their failures and changed the engine in answer. A held-out scenario is one the engine has never been run on. It answers one question: do the dev scores describe the engine, or the fit between the engine and those three files?

- **Run by**: `python -m feasibility_fr.benchmark.run --live --include-heldout`, once.
- **Read by**: the report, which already separates splits, and the README.

## The problem with writing them now

The scenarios are written by the same author who built the engine and read every one of its failures. A choice made while writing a scenario can favour the engine or the baselines without intent. The rules below are fixed first, and the places where a choice remains are settled by a seeded draw, not by the author.

## Rules

1. **The engine does not change.** No file under `feasibility_fr/engine` or `haussmann` changes between the tag and the run, except a change that cannot alter what a model is sent or what the ledger settles, and each such change is named in the run's row. The benchmark's own code (generator, templates, runner, report) may change to carry the new scenarios; the three dev scenarios must still regenerate identically.
2. **One run.** Three samples per system, the three systems, the dev model. Whatever comes out is reported. A second run is allowed only if the first exposes a defect in the scenario files themselves (a statement the generator misplaced, an answer key that contradicts its own documents), the defect is described in the row, and both runs are kept.
3. **Nothing is tuned on them, ever.** After the run the held-out results may be read and described. A change to the engine made afterwards is measured on dev, and the held-out scenarios are run again only as a new, logged measurement.
4. **Two scenarios, sized like the small dev ones**: 14 to 24 documents each, 15 to 22 facts each. One of them has a regulation split by zone with the rules of other zones present, as real plans are.
5. **Traps: the dev floor.** Across the two, three traps of each of the eight types, twenty-four in all, twelve in each scenario, each scenario holding at least one of each type.
6. **Sites are invented.** The dev scenarios stand on real parcels and frozen public data; these do not. Their communes, parcels and addresses are fictional and every document says so. What is held out is the documents and their wording, not a real place.
7. **Wording differs from dev everywhere a document speaks.** Every sentence that states a fact, every table row label, every document title, opening and closing is different from the dev templates. For each fact attribute two phrasings are written, both as the kind of document that states it would write it; which one a scenario uses is drawn with the scenario's seed. The author does not pick.
8. **The questions do not change.** What a system is asked (the label of each required fact) is the deliverable's wording, the same as in dev. Only the documents change.
9. **Document types stay within the workload's list.** The engine's type list is frozen with it; a held-out file contains the same kinds of documents as a real file of this sort.
10. **Values are new**, and each trap is built by the same construction as in dev (a brochure against an official document, a lease against its amendment, a total that does not add up, a unit to convert, a date past its validity, a missing fact, another property's document, a fact deep in a long document).
11. **Validity is checked by code before the run**, as in dev: the spec validates, the files match their manifest, and the code half of the engine, fed every true statement, passes every trap. That last check uses the settling rules, which are the benchmark's stated policy (authority, then date); it does not involve a model.

## What is predicted, before the scenarios are written

On held-out the engine stays ahead of both baselines on traps, by a smaller margin than on dev. Recall falls by a few points against dev's 98 %: the wording of facts is new, the finder searches by keywords, and the owner failure shows what a wording the model does not guess costs. A fall of more than ten points in recall, or the engine behind a baseline on traps, would mean the dev results overstate the engine.

## What this does not establish

Two scenarios, six engine runs. The generator, the filler paragraphs and the document layouts are the dev ones, so the files are new in content and wording and not in form. The author knows the engine. A held-out set written by someone else, on real files, would be a stronger test; this is the one that can be made now.

## What was written (2026-11-14, after the rules above were committed)

| Scenario | Documents | Pages | Facts | Traps | Seed |
|---|---|---|---|---|---|
| `heldout_presbytere` | 16 | 25 | 20 | 12 | 7101 |
| `heldout_caserne` | 19 | 43 | 22 | 12 | 8233 |

Three traps of each type across the two. The seeds were chosen before the wording was drawn and were not changed afterwards. Tests hold the scenarios to rules 4, 5 and 7: sizes, trap counts, no phrase, label or frame shared with the dev wording, and a wording that is a function of the seed.

Checked by code before the run (rule 11): both specifications validate; the files match their manifests; with every true statement outside the scanned pages entered as a candidate, the settling rules pass all 24 traps, and the only facts not recovered are the three whose sole statement is on a scanned page, which that check cannot read without a model. The full check, with transcribed scans, is a test that passes once the run has recorded the transcriptions.

No file of the engine or of the platform differs from the tag `engine-freeze-m3`. The benchmark's templates gained a `Style`, so that a scenario can carry its own wording; the three dev scenarios regenerate identically.

## What the run measured (2026-11-14, E016)

One run, three samples, three systems, the dev model, about 0.10 USD. No engine or platform file differs from the tag.

| | recall | traps | citations |
|---|---|---|---|
| one_prompt | 97% (113/117) | 74% (53/72) | 100% (113/113) |
| naive_rag | 99% (116/117) | 74% (53/72) | 100% (116/116) |
| engine | 88% (103/117) | 85% (61/72) | 94% (97/103) |

By scenario, engine / one_prompt / naive_rag:

| Scenario | recall | traps |
|---|---|---|
| `heldout_caserne` | 60/60, 56/60, 59/60 | 36/36, 26/36, 29/36 |
| `heldout_presbytere` | 43/57, 57/57, 57/57 | 25/36, 27/36, 24/36 |

For comparison, the two small dev scenarios, which these are sized like: engine 96% (95/99) recall and 96% (69/72) traps; one_prompt 93% and 69%; naive_rag 94% and 69%.

### Against the prediction

- **Traps, pooled: held.** The engine is ahead of both baselines by 11 points, against 35 on dev and 27 on the small dev scenarios.
- **Recall: at the stated limit.** Down 10 points from dev's 98%, 8 from the small dev scenarios.
- **Not predicted: the engine's recall is below both baselines**, and on one scenario of the two it is behind one_prompt on traps.

By the criterion written beforehand, the dev results overstate the engine. Its advantage on recall does not carry over to new documents. Its advantage on traps does, pooled, and is carried by one scenario.

### Where the engine lost

All of it is on `heldout_presbytere`.

| Fact | Runs lost | What happened |
|---|---|---|
| zone, parcel reference | 3 of 3 each | The finder recorded values from two documents headed as another lot. The zone settled on the other lot's value, the later document; the parcel on nothing, two official documents disagreeing. Distractor is 0/6 on this scenario and 15/18 on dev. The rule that such documents are ignored is an instruction to the model and nothing in code enforces it. |
| limit on storeys | 3 of 3 | Never found. The model searched for "niveau"; the regulation writes "R+2". This is the cost of wording the prediction named. |
| height limit | 2 of 3 | Stated on page 7 of 8 of a regulation whose filler paragraphs use the word on most pages. |
| owner | 3 of 3 | Left open twice; once the word "vendeur" was recorded as the name and won as the later source. The same failure as on dev. |
| certificate date | 1 of 3 | Taken from the other lot's certificate. |

`heldout_caserne`, with the regulation split by zone and the rules of other zones present, was complete in every run.

### What held

By type on held-out the engine passes 9/9 on arithmetic, date rules, missing facts, superseded values and units. Both baselines pass 0/9 contradictions and 3/9 date rules, as on dev: they report one value where two documents disagree and do not check a date against its validity. These are the checks done by code, and they do not depend on the wording of the documents.

The baselines find more on these scenarios than on dev. With sixteen to nineteen short documents, reading everything in one prompt misses almost nothing; the engine's search is a way to lose facts that a full read does not have.

### What follows, and what does not

Nothing in the engine changes in answer to this run (rule 3). Two changes are candidates for a later experiment measured on dev: deciding in code, from the document's card, that a document concerns another property; and giving the finder the full text of a short document instead of search results. Either would be run on these scenarios again only as a new, logged measurement, and these two scenarios would then no longer be untouched.
