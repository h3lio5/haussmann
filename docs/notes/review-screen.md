# The review screen

Status: written and implemented 2026-11-14; open to revision.

## Where this fits

The screen is the reviewer's desk: the memo on the left, the evidence for whatever is selected on the right. It reads and writes only through the HTTP API (`docs/notes/review-api.md`).

```
web/src/api.ts      the API's JSON shapes and one function per route
web/src/App.tsx     the bar, the memo pane, the evidence pane, the reviewer's actions
web/src/PdfPage.tsx one PDF page drawn by PDF.js, with the quote marked on it
web/src/text.ts     text comparison, the same rule as the verifier's: case, accents, punctuation ignored
```

- **Run it**: `cd web && npm install && npm run build`, then `uv run python -m feasibility_fr.app.demo` and open `http://127.0.0.1:8000`. For development, `npm run dev` serves the screen and forwards `/api` to the demo.
- **Needs**: no model key. The demo replays recordings; an action that would need a new model call is refused with a message that says which actions are recorded.

## What a reviewer does

1. **Select a sentence.** It is marked in the memo. The right pane shows each fact the sentence states: the value kept, every other value found with its standing, and for each value its sources.
2. **Open a source.** A PDF page is drawn with the quoted words marked and scrolled into view; a spreadsheet is shown as its cells with the cited cell marked; an email as its text with the quote marked. The mark in the source and the mark on the sentence are the same colour, the only use of that colour on the screen.
3. **Set another value** for a fact, with a reason. The memo is rebuilt and the pane lists what changed: the value, the sentences removed and added, and how many sections were left alone.
4. **Approve a section, request changes, or ask for a rewording.** A rewording comes back as a proposal to accept or to leave.

Each section's review state is in the memo's left margin, where a proofreader would put it. A value the memo flags as needing a check carries the mark the memo prints and a wavy underline.

## Decisions

- **A sentence is the unit of selection**, because a sentence is what records its facts. The screen never guesses which words of a sentence hold a value.
- **The quote is found by text comparison, not by coordinates.** The ledger stores the quote and the page; the screen finds the words on the page with the verifier's own comparison rule. Nothing about layout is stored.
- **On a PDF the mark covers whole text runs** that the quote touches, so it can be wider than the quote by a few words on the same line.
- **The interface is in English and the memo in French**, as the deliverable is.

## Known limits

- No automated test drives the screen. It is type-checked, built in CI, and was exercised by hand on the three dev files: selection, evidence, the PDF mark, an edit with its diff.
- The rewording flow was exercised through the API's tests, not yet by hand on the screen.
- A scanned page has no text layer, so nothing is marked on its image; the transcribed text below it carries the mark.
- Fonts are loaded from a public font service; offline, the screen falls back to system fonts.

## The evals view

- **Reached by**: the "Evals" link in the bar (`#evals`); `main.tsx` chooses between the two views by the address.
- **Needed because**: the results, the regression cases and the experiment log are the evidence for every claim about the engine, and they were readable only as Markdown files.
- **In**: `GET /api/evals`, which reads three committed files (the experiment log, the benchmark report, the state of the cases) and returns their tables as `{heading, header, rows}`. The reading is `evalkit.tables.read_tables`, pure, with no knowledge of what the tables hold.
- **Out**: the report's tables for each split, kept apart and labelled dev or held-out; the cases with their standing; the experiments newest first, each row opening to what was expected before the run, before, after, and what was seen.

The files stay the record. The view computes nothing: a number on the screen is a cell of a committed file, so the screen cannot disagree with the log.

Rejected: a scores-by-commit chart. The log has one row per experiment, not per commit, and its metrics are written as text with counts; plotting them would need a second, structured copy of the log to keep in step with the first.

