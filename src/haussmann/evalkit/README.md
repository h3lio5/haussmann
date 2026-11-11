# evalkit

Scenarios, scorers and benchmark runner.

## Contract

Scenarios with known answers, pure scorers over a submission, and a runner that replays recorded model responses by default.

Background: `docs/notes/benchmark-rationale.md`.

## Status

`groundtruth` (scenario types, unit normalization), `validation` (`validate(spec, schema)`), `manifest` (JSON read and write), `scorer` (`score(manifest, schema, submission)`). `generator` (`build`, `write`) with `documents`, `render` and `scan`. `report` (`RunRecord`, `render_report`, `experiment_row`). The run command lives in the workload.
