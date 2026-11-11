# llmkit: the tool loop

Status: written and implemented 2026-11-11; open to revision.

## Where this fits

A single model call can only answer from what is already in its prompt. A fact-finder has to look things up: search the documents, open a page, then decide what to look at next. The tool loop is what lets it do that. It calls the model, runs the tools the model asks for, feeds the results back, and repeats until the model answers or a limit is hit.

```
            ┌────────────────────────────────────────────┐
request ──> │ call model ──> tool calls? ──no──> answer  │ ──> LoopResult
            │      ^              │ yes                   │
            │      └── results <──┴── run each tool      │
            └────────────────────────────────────────────┘
                   stops on: answer, turn limit, token limit
```

Every agent in the system (fact-finders now, the resolver and reviser later) is this loop with a different prompt and a different set of tools. There is no other agent machinery.

## Boundaries

```python
ToolSpec(name: str, description: str, parameters: Mapping[str, object])    # shown to the model
Tool(spec: ToolSpec, run: Callable[[Mapping[str, object]], Awaitable[str]])
ToolError(Exception)                                    # a tool's way to say "bad call" to the model

Budget(max_turns: int, max_tokens: int)                 # tokens: input plus output, all calls

run_tools(client, request, tools, budget, *, sample=0) -> LoopResult

LoopResult(answer: str, stop: Stop, messages: tuple[Message, ...],
           steps: tuple[Step, ...], responses: tuple[Response, ...])
Stop = ANSWERED | TURN_LIMIT | TOKEN_LIMIT
Step(call: ToolCall, result: str, failed: bool)
```

Example: the model asks for `search({"query": "hauteur maximale"})`; the loop runs it, appends the result as a tool message, and calls the model again; the model then answers in text and the loop returns `ANSWERED` with one step.

## Decisions

**Three ways to stop, all explicit.** The model answers; the turn limit is reached; or the token limit is reached. The caller always learns which. A loop without hard limits is how an agent run becomes an unbounded bill.

**A repeated call is refused, not fatal.** A call with the same tool and arguments as an earlier one is not run again; the model is told so and the loop goes on. The first version ended the loop on a repeat. In the first engine run that ended 8 of 27 finder runs early, each with facts still unrecorded, so the rule cost more than the calls it saved. A model that only repeats itself now runs into the turn limit.

**The loop holds no findings.** It returns messages and steps, and that is all. An agent that must not lose its work writes it through a tool as it goes, into the ledger. If a run stops on a limit, what was written stays written.

**A tool's mistake goes back to the model; a program's mistake does not.** An unknown tool name, arguments that are not valid JSON, or a `ToolError` raised by the tool become the text of the tool result, marked failed, so the model can correct itself. Any other exception is a bug and propagates.

**Tool calls in one reply run in order, one at a time.** Tools write to the ledger, and ordered writes keep a run reproducible.

**Each model call is an ordinary `complete`.** The loop adds nothing to the client contract beyond tool fields on the request, message and response. Replay therefore works unchanged: every call in a loop has its own recording, and a request that uses no tools keeps the cache key it had before tools existed.

**The token limit is checked between calls.** The loop cannot stop a call in flight, so it can overshoot by one call. The limit is a brake, not a ceiling.

## Tests

- Stops with the answer when the model answers at once, and after tool calls.
- Stops on the turn limit and on the token limit, each reported as such, with no further model call.
- A repeated call is not run again, is reported to the model as a failed step, and does not end the loop.
- Tool results are fed back in order, each answering its call id; the next request contains them.
- An unknown tool, invalid JSON arguments and a `ToolError` become failed steps the model sees; another exception propagates.
- Runs end to end on recordings: record a loop once, replay it with no inner client.

## Alternatives rejected

- **An agent framework.** The loop is about a hundred lines; a framework would add its own message types, state and retries around the one part of the system that most needs to be legible.
- **Ending the loop on a repeated call.** Tried first and dropped on evidence, as described above.
- **Running tool calls concurrently.** Faster, but writes would land in a different order from run to run.
- **Letting the loop own a scratchpad or memory.** State would then live in the conversation, which is what the ledger exists to avoid.
