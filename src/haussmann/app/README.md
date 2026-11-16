# app

A run open for review, and the HTTP API the review screen calls. For any workload.

## Contract

```python
Session.open(workload, run_id, scenario_id, folder, runner, client, asked, pages, cards,
             as_of, model, rehearse) -> Session                            # session.py
create_app(sessions, held, screen, evals) -> FastAPI                       # http.py
```

`Session.open` runs the engine and writes the deliverable, or loads them when the run has them already. A session then answers what the screen reads (`view`, `fact`, `source`, `file`, `cases`) and what a reviewer does (`edit`, `approve`, `request_changes`, `comment`, `accept`). Each action is one step in the run's journal, so a review resumes with the run.

`create_app` maps each route to one call on a session and each refusal to a status: 404 for an unknown run or source, 422 for a value that does not fit, 409 for an action that needs a model call with no recording.

- **Called by**: a workload's entry point, which opens one session per run and serves the app (`feasibility_fr.app.demo`).
- **Receives**: the `Workload` record, the parsed pages and document cards, the required facts, a runner and a model client.
- **Returns**: JSON-ready dictionaries; the screen in `web/` is the only reader.

FastAPI is needed only here; install it with the `api` extra.

Design: `docs/notes/review-api.md`, `docs/notes/workload-definition.md`.
