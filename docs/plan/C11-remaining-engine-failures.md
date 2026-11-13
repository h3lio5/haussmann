# C11 plan: the remaining engine failures on the large scenario

## Why

After E009 the engine misses 9 of 81 facts on the large scenario over three runs, fails 7 of 72 traps, and has 86 % of its citations counted correct. Replaying the three runs gives one cause for each loss.

| Loss | Runs | Cause, from the replay |
|---|---|---|
| Flood risk: wrong side of a disagreement reported | 3 of 3 | Both values are recorded and the conflict is seen. The agent's email is typed `sale_notice` by the model, so it ranks as an official document, ties with the risk report and wins on its later date. None of the 14 emails in the file is typed `email`: ten are typed by their content (`sale_notice`, `lease`, `zoning_regulation`) and four as `other`. (An earlier version of this plan said 13 of 15; the count was wrong.) |
| Four floor areas and their total | 1 of 3 | The finder quoted a label and a value from two spreadsheet cells as one passage ("... Surface de plancher 384 m²"). That text is not in the sheet, so the verifier rejects the facts, as it should. |
| Owner | not found 1 of 3; one side only 1 of 3 | Search for "propriétaire" never reaches "Le bien appartient à ...". Keyword search cannot bridge the two wordings. |
| One lease end | 1 of 3 | In the cross-check the finder was sent to another lease's page, which says "Le bail prend fin le ..." without naming the lease, and recorded that date under this lease's key. |
| Citations | every run | (a) A total recomputed from its parts cites the parts' documents; the benchmark counts a citation only where that fact is stated. Three facts per run. (b) A value found in a spreadsheet is cited at the sheet, not at its cell. |

## Where it fits

```
files ──> ingest: cards ──> finder: record_fact ──> ledger ──> verify ──> submission
            ▲ change 1         ▲ change 2                                   ▲ change 3
```

## Change 1: a document's form is known to code

An email is an email because the file is one. `docparse` already reads `.eml` files apart from PDFs and spreadsheets; it will report each document's file form, and the workload types a document read from an email file as `email` without asking the model. The model is still asked for the date and for the type of every other document.

- **Called by**: `build_cards`, once per document at ingest.
- **In / out**: gains a mapping `doc_id -> type` for documents whose type code knows; returns the same `DocumentCard`s.
- **Effect**: emails get the authority the workload gives an email (1), below an official report (3). With the scenario's own document types, the code half already passes every trap (the perfect-finder test).

## Change 2: `record_fact` checks the quote where it is cheap to correct

When a fact is recorded, the tool checks that the quote is in the cited page, with the function the verifier uses. If it is not, the tool refuses and says so; the finder has a turn to quote the text as written. This is the pattern of C10 (the amount must appear in the quote). The verifier is unchanged and remains the final check.

For a spreadsheet, when the quote lies within one cell, code sets the citation to that cell (`Sheet1!B7`) even if the model cited the sheet.

- **Called by**: the finder's `record_fact` tool.
- **Not touched**: the citation check in `verify`.

## Change 3: a recomputed total is reported with the place that declares it

In the benchmark adapter, a fact whose value was recomputed from its parts cites the documents that state the total, flagged, and no longer the documents of the parts. The parts and their sources stay in the ledger and in the memo's record. No model call changes, so this is checked on the existing recordings.

This changes what the engine reports to match what the benchmark counts as a citation. It is a change made after seeing the score and is logged as such.

## Left out, with the reason

- **Owner.** It needs search that matches meaning, not words. That is the open M2 decision on how the finder searches (keywords, embeddings or both); it gets its own plan and experiment, next.
- **The lease end taken from another lease.** The fix is to know which lease a document is about. The one attempt to judge a document's scope (E006) removed correct documents; this waits for a document card that carries its subject.
- **The zone citing the zone's regulation** (1 run): true at its source, not counted by the benchmark; left as it is.

## Tasks

| ID | Task | Done when |
|---|---|---|
| C11.1 | Change 3, on recordings | citation rate reported before and after; no other score moves; row E012 (code only) |
| C11.2 | Change 1: file form from `docparse`; emails typed by code | tests: an email file is typed `email` whatever the model answers; other documents unchanged |
| C11.3 | Change 2: quote check and cell citation in `record_fact` | tests: a quote joining two cells is refused; a quote within a cell is accepted and cited at the cell; a PDF quote not on the page is refused |
| C11.4 | Live run E013 (changes 1 and 2), row in `EXPERIMENTS.md`, findings in `docs/notes/engine.md` | large and small scenarios reported separately |

Changes 1 and 2 go in one live run because each run needs a person; what each contributed is read from the replay (which facts changed and why), as in E008.

## Expected outcome, stated before the runs

- **E012 (code only):** citations on the large scenario from 86 % to about 95 %; recall and traps unchanged.
- **E013, large scenario:** flood passes in every run where both sides are recorded, so contradiction from 4/9 to 7/9 (the owner still fails twice). Floor areas are not lost to a joined quote. Recall from 89 % to at least 93 %. Citations at or above 95 %.
- **E013, small scenarios:** nothing should move; every engine call is re-recorded, so a move of one or two facts is noise and is reported as such.

Risks: the new refusal may cost a finder turns and push a run to its turn limit; emails that are a fact's only source lose nothing, but an email on the right side of a disagreement with an official document now loses, which is the workload's stated ranking.

## Outcome

| | Before | Predicted | After |
|---|---|---|---|
| E012, citations, large scenario | 86% (62/72) | about 95% | 89% (64/72) |
| E013, recall, large scenario | 89% (72/81) | at least 93% | 100% (81/81) |
| E013, traps, large scenario | 90% (65/72) | contradiction 4/9 to 7/9 | 97% (70/72); contradiction 7/9, every other type 9/9 |
| E013, citations, large scenario | 89% (64/72) | at or above 95% | 98% (79/81) |
| E013, small scenarios | recall 96%, traps 69/72 | no move | recall 96% (95/99), traps 69/72; citations 93% to 100% |

E012 missed its prediction: the facts whose totals cited their parts were mostly the same facts that cite a sheet instead of a cell, and were counted twice in the estimate. E013 held on every line.

What each change did, read from the replay:

- **Emails typed by code.** Flood is reported from the risk report in all three runs, with the agent's email kept as the other side of the disagreement. Every card now has the authority its scenario declares.
- **Quote check.** 14 records were refused on the large scenario. 12 were floor areas quoted across two cells, in 2 of 3 runs (1 of 3 before); each was recorded again from a single cell and verified. 2 were a parcel reference quoted from a page that does not contain it.
- **Not attributable to the changes:** the owner was found in all three large runs and the stray lease end did not recur. Search and the cross-check were not changed; this is what a re-recording does, and recall of 100% on the large scenario should be read with that in mind.

What still fails: the owner. On the large scenario one side of the disagreement is found in 2 of 3 runs. On one small scenario the finder never reaches the sentence, and in 2 of 3 runs records "collectivité propriétaire" from a notice and the owner of the neighbouring lot. Both come from keyword search and from documents about another property; the next plan is about search.

## Cost

E012: none. E013: only the engine is re-recorded; about 0.15 USD, printed upper estimate about 0.95 USD. Measured: 0.15 USD for the engine, 0.002 USD for the three memos.

## No new dependency
