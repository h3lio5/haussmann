# Traces and cost

Status: approved 2026-11-13; open to revision.

## Where this fits

Two questions about a run are asked after it: what did it cost and where, and what happened inside the step that went wrong. The first is answered from the journal's `calls` table, by a sum. The second is answered by a trace: one span per run, step and model call, sent to whatever viewer is configured.

```
runner.span() ──span "run"
   └─ Runner.step ──span "step find:3:pass1"
         └─ step client ──span "chat <model>"── journal, else provider
journal.calls ──sum──> cost per step
exporter: none by default; in memory in tests; OTLP when a process configures one
```

- **Called by**: the workload opens the run span with `runner.span()`; `Runner.step` opens a step span; the client a step receives opens one span per call, with the helpers in `llmkit.tracing`, where the attribute names live. Cost per step is `Journal.costs(run_id)`, called by the workload's commands.
- **Needed because**: the benchmark report gives one cost per run. It cannot say that the cross-check pass is half of it, or show the requests of the one finder that hit its turn limit.

## Structures

```python
# llmkit.tracing
call_span(tracer, request, key, provider) -> context manager yielding the span
record_response(span, response, cost_usd, paid) -> None

# flow
open_run(..., provider: str = "unknown", tracer: Tracer | None = None)   # the global tracer when none is given
runner.span() -> context manager                                         # the run span for this process

# flow, returned by Journal.costs(run_id) in the order steps first paid for a call
@dataclass(frozen=True, slots=True)
class StepCost:
    step: str
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
```

Cost of a call is `cost_usd(model, usage)`, the function the benchmark report uses: the cost the provider reported with the response, or the price table applied to the token counts when it reported none. It is computed once when the call is recorded and stored. A report is a sum of stored numbers; no model is involved and nothing is recomputed from token counts later, so a price change does not rewrite the cost of past runs.

## Spans

| Span | Name | Attributes |
|---|---|---|
| Run | `run` | `haussmann.run.id`; one per process, so a resumed run has two |
| Step | `step <key>` | `haussmann.run.id`, `haussmann.step.key`, `haussmann.step.reused` (true when the stored result was returned) |
| Model call | `chat <model>` | `gen_ai.operation.name` = `chat`, `gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.response.finish_reasons`, `haussmann.cost_usd`, `haussmann.call.paid`, `haussmann.call.key` |

`haussmann.call.paid` is false when the response came from the journal, so the trace of a resumed run shows every call the step made and which of them were paid in this process. The span is opened before the journal is consulted for that reason.

A failed step or call sets the span status to error with `error.type`.

Prompts and responses are not put on spans. They are in the journal, keyed by the same request hash, which the span carries as `haussmann.call.key`. A trace backend is then never a second copy of dataroom text.

## Invariants

- With no SDK installed or no exporter set, tracing does nothing and costs nothing measurable.
- Every paid call of a run has exactly one row in `calls`, and the run's cost is the sum of those rows.
- Every model call made through a runner has a span whose parent is its step's span, whose parent is the run's.
- Attribute names from the generative AI conventions are written in one module.

## Known limits

- The generative AI conventions are at Development status; names may change. One module to edit.
- Tool calls inside a finder are not spans of their own. They run in microseconds on local data, and the model call that asked for them and the one that received their result are both in the trace.
- Embedding calls are not journaled or traced in this slice; the engine makes none.
- Cost is what the provider reported per call, or list price times tokens; it is not the provider's invoice.

## Alternatives rejected

- **Cost as a span attribute only, summed in the viewer.** Cost would then depend on a tracing backend being up and retaining data; the spend cap needs the number inside the run.
- **Content on spans.** Convenient in a viewer, and it sends every page a finder read to a second system with its own retention.
- **A span per tool call.** Several hundred spans per run that say nothing the ledger and the journal do not.
- **Spans opened inside the provider client.** The journal is consulted above it, so a stored call would have no span.
- **A tracing client that wraps any client.** It cannot know whether a call was paid; the step client can, and no other caller needs spans yet.

## Tests

- With the in-memory exporter: a run of two steps and three calls gives one run span, two step spans and three call spans with the right parents and attributes.
- A reused step has a span marked reused and no child.
- A call served from the journal is marked not paid.
- No span name or attribute contains request or response text.
- With no SDK configured, the same run completes and exports nothing: every other test in the suite runs that way.
- `costs` equals the sum of what was recorded, by step, on both journals.

## What was measured

`benchmark_data/results/durable.md`: on the large scenario, 70 model calls in 14 steps cost 0.034 USD, of which the memo is 0.0006 USD and the most expensive finder step (a first pass over nine calls) 0.0044 USD; cross-check passes are 0.015 USD, 45 % of the finding cost. The total equals the same responses priced one by one outside the journal. The benchmark report pools scenarios, so it has no per-scenario figure to compare with.
