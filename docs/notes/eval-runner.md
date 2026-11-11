# Benchmark runner and report

Status: written 2026-11-11 and implemented in the same change at the owner's request; open to revision.

## Where this fits

The runner is the command that produces every number the project reports. It takes each system (the two baselines now, the engine from M2), runs it on each scenario several times, scores each attempt, and writes one report.

```
scenarios (files + manifest) ─┐
systems (baseline a, b, …) ───┼──> runner ──> RunRecord per attempt ──> report.md, EXPERIMENTS.md row
recordings (replay cache) ────┘
```

By default it only replays recordings, so it needs no key, costs nothing and always gives the same report. With `--live` it calls the provider for whatever is not yet recorded.

## Boundaries

```python
RunRecord(system: str, scenario: str, split: Split, sample: int,
          score: Score | None, failure: str | None, cost_usd: Decimal, latency_s: float)

render_report(records: Sequence[RunRecord]) -> str            # pure, markdown
experiment_row(id, date, change, hypothesis, records, decision) -> str   # one EXPERIMENTS.md row
```

```
python -m feasibility_fr.benchmark.run                 # replay only
python -m feasibility_fr.benchmark.run --live          # record what is missing
    [--samples 3] [--cap-usd 2.0] [--include-heldout] [--report PATH]
```

## Decisions

**Replay by default.** A missing recording stops the run with a message naming the system and scenario, instead of silently calling the provider.

**Spend cap before the first live call.** The runner estimates input tokens from the character count of what it will send (one token per three characters, which overstates), prices it from the table, prints the estimate, and refuses to start above the cap. The provider's billed cost is recorded per call afterwards and is what the report shows.

**Held-out scenarios need a flag.** They are skipped unless `--include-heldout` is given, and held-out results are always reported in their own table.

**A failed attempt is a result.** An attempt whose answer could not be parsed is kept as a failed run with its cost. It counts as zero correct facts in recall, and the report shows the number of failed runs.

**What the report shows.** Per split, one row per system: recall, precision, bait rate, invented rate, abstention, citation correctness, each pooled over scenarios and samples as counts; the lowest and highest recall across attempts as the spread; failed runs; total cost; mean latency. A second table gives traps passed per type as k of n. Rates with nothing to count are shown as a dash.

**The experiment row is written by the runner, the judgement by a person.** The runner fills the metrics and cost; the change, hypothesis and decision are passed in.

## Tests

- Report snapshot from hand-made records, including a failed run and an empty rate.
- Replay-only run on recorded fixtures reproduces the same report twice.
- A live run above the cap refuses before any call; a held-out scenario is skipped without the flag.

## Alternatives rejected

- **Averaging rates across attempts.** Pooled counts weight every fact equally and keep k of n visible.
- **One overall trap score.** With about three instances per type, a single number hides which behaviour failed.
- **Asking the provider to count tokens.** Not available through the provider-neutral client; an overestimate is enough for a cap.
