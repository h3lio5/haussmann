# The review session and its HTTP API

Status: written and implemented 2026-11-14; open to revision.

## Where this fits

The review core (`docs/notes/review.md`) is functions over a ledger and a build. A screen needs one object that holds a run open and answers its questions, and a way to reach it over HTTP.

```
browser ──HTTP──> app/http.py: routes ──> app/session.py: Session ──> runner, ledger, memo
                                                 │                         (review core, engine)
                              app/demo.py: opens the dev scenarios from recordings
```

- **Called by**: the review screen. Until it exists, by the tests through the framework's test client.
- **Needed because**: every action of a reviewer has to go through the same runner as the engine, so that an edit, an approval and an accepted rewording are stored like any other step and survive a restart.
- **Lives in the workload** (`feasibility_fr/app`), not in the platform: each route needs the workload's schema, its formatter and its memo spec. The platform keeps the review core; with a second workload the routes move down over a session type that both provide.

## Structures

```python
Session.open(run_id, scenario_id, folder, runner, client, asked, pages, cards, as_of, model, rehearse)

session.view() -> {run, scenario, as_of, approved, sections[], inputs{}}
    section: {id, title, kind, state, version, sentences[{text, uses[]}], comments[]}
    input:   {label, text, flagged, attribute, citations[{doc_id, locator}]}
session.fact(name) -> {label, settled, settled_fact, reasons[], in_conflict[], facts[]}
    fact:    {id, value, status, method, author, stated_for, citations[{doc_id, locator, quote}]}
session.source(doc_id, locator) -> {doc_id, locator, cell, form, type, date, text}
session.file(doc_id) -> Path

await session.edit(name, value, unit, reason, author) -> changes[]     # settles again, rebuilds
await session.approve(section, author)
await session.request_changes(section, author, reason)
await session.comment(section, author, text, uses, to_agent) -> proposal | None
await session.accept(proposal_id, author)
session.cases() -> list[Case]                                          # one per expert fact
```

| Route | Method | Calls |
|---|---|---|
| `/api/runs` | GET | the open sessions |
| `/api/runs/{run}/memo` | GET | `view` |
| `/api/runs/{run}/facts/{name}` | GET | `fact` |
| `/api/runs/{run}/sources/{doc}/{locator}` | GET | `source` |
| `/api/runs/{run}/files/{doc}` | GET | the file itself, for a PDF viewer |
| `/api/runs/{run}/edits` | POST | `edit`; returns the changes and the new memo |
| `/api/runs/{run}/sections/{section}/approve` | POST | `approve` |
| `/api/runs/{run}/sections/{section}/request-changes` | POST | `request_changes` |
| `/api/runs/{run}/sections/{section}/comments` | POST | `comment`; returns the proposal if one was asked for |
| `/api/runs/{run}/proposals/{id}/accept` | POST | `accept` |
| `/api/cases` | GET | the committed cases and those made in review |

A request the run cannot satisfy is 404 for something that does not exist, 422 for a value or an action that does not fit, 409 for an action that needs a model call with no recording.

## Decisions

- **Review events are steps of the run.** An approval, a request for changes, a comment and an accepted rewording are each stored as a step named `review:<n>` whose result is the event. They go through the journal the run already has, in memory or in Postgres, and need no table of their own. The session reads them back from the runner's finished steps.
- **The memo shown is derived.** It is the memo the last memo step wrote, with each accepted rewording applied to its section as long as that section still has the inputs the rewording was written for.
- **A fact's name is its key**, `subject.attribute`, the name sentences already use. The screen goes from a sentence to its facts to their citations without an id that changes between runs.
- **Replay-only sessions rehearse an edit.** With no live model, an edit is first applied to a copy of the ledger and the memo rebuilt from it. If that needs a call with no recording, the edit is refused and nothing changes. A live session skips the rehearsal, which would pay for the same calls twice.
- **Cases made in review are derived from the ledger**: one per fact an expert set. They are returned beside the committed ones; adding them to the committed file is a deliberate act, not a side effect of a click.

## Invariants

- A refused request changes nothing: not the ledger, not the memo, not the review state.
- Every write is a step of the run's runner.
- The API never returns a value that is not printed from the ledger by the workload's formatter.

## Known limits

- No authentication and no notion of a user beyond the author's name in a request. The demo binds to localhost.
- Pending proposals are held in memory; one that was not accepted is lost on restart, and asking again costs nothing since its call is in the journal.
- The demo opens every dev scenario at start, on in-memory journals; edits are lost when it stops. Opening a run on the Postgres journal is the same call with another journal.
- One sample per scenario.
- The framework's test client warns that it prefers another HTTP library than the one installed; the tests pass and no dependency was added for it.

## Alternatives rejected

- **A table of review events.** A second store beside the journal, with its own transaction boundaries, for something the journal already orders and persists.
- **Routes in the platform now.** They would need an interface for "a run open for review" with one implementation.
- **Applying an edit, then failing on the rebuild.** The ledger would hold a fact the memo does not show.

## Tests

On the recorded dev scenario, through the test client: the memo, a fact and its source, the file; what is not there is 404; an edit rebuilds, returns the diff, keeps unrelated approvals and yields a case; an edit with no recording, a value that does not fit, an unknown fact and an empty reason change nothing; a comment to the agent returns a proposal that applies only once accepted and ends the section's approval; a plain comment and a request for changes are kept with the section.

## Evals

`GET /api/evals` returns the tables of the experiment log, the benchmark report and the regression cases, by name. `create_app` takes `evals`, a function giving each file's text; the route parses them with `evalkit.tables.read_tables`. It is read-only and involves no session.

