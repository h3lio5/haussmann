# llmkit: single-call client and replay cache

Status: approved 2026-11-10. Needed by M1 tasks B4, B6, B7, B8.

## Where this fits

Every part of the system that needs a model goes through one function, `complete`. In M1 the callers are the two baselines; from M2 they are the fact-finder agents, the writer and the judges.

```
baselines (M1) ─┐
fact-finders ───┤                      ┌─ hit ──> recorded response (no network, no key, no cost)
writer, judges ─┴─> ReplayClient ──────┤
                     (wraps)           └─ miss ─> live client ──> provider API
                                                   └─ response saved as a recording
```

- **Live client:** sends the request to a real provider over the network. It costs money, needs a key, and gives a different answer each time.
- **Replay client:** a wrapper that first looks for a saved recording of the same request. Tests, CI and the public demo run with recordings only, so they are free, fast and repeatable. A benchmark run records once and is then reproducible by anyone from the repository.
- **Why it matters downstream:** the scorer's numbers are only trustworthy if a run can be repeated exactly. The experiment log compares "before" and "after" on the same recordings, and a prompt change shows up as cache misses on exactly the calls it affected.

Scope is one request, one response. The tool loop, the repair loop, the retry taxonomy and tracing are later slices that call this primitive.

## Contract

```python
Message(role: Literal["system", "user", "assistant"], text: str)

Request(model: str, messages: tuple[Message, ...], max_tokens: int,
        temperature: float | None = None, seed: int | None = None,
        output_schema: Mapping[str, object] | None = None)

Usage(input_tokens: int, output_tokens: int,
      cached_input_tokens: int | None = None,        # None: the provider does not report it
      reported_cost_usd: Decimal | None = None)      # None: the provider does not report it
Response(text: str, stop_reason: str, model: str, usage: Usage, latency_s: float)

class LLMClient(Protocol):
    async def complete(self, request: Request, *, sample: int = 0) -> Response: ...

ChatCompletionsClient(base_url: str, api_key: str, http: httpx.AsyncClient,
                      seed_param: str = "seed",
                      extra_body: Mapping[str, object] | None = None)       # live
ReplayClient(store: ReplayStore, inner: LLMClient | None = None)
ReplayMiss(KeyError)

request_key(request, sample) -> str
cost_usd(model: str, usage: Usage) -> Decimal
```

- Types are frozen dataclasses. HTTP is confined to one file, the live client.
- `ReplayClient` looks the key up. On a hit it returns the recording. On a miss it raises `ReplayMiss` when `inner` is `None`, otherwise it calls `inner`, stores the response and returns it. Replay-only and record are the same class with and without an inner client.
- The protocol exists because there are two implementations today.

## Decisions

**No provider SDK.** The live client is about 150 lines over `httpx` that speak the chat-completions wire format: a list of role and text messages in, choices and token usage out. The provider is configuration (base URL, key, model id), not code. A provider whose format differs gets its own adapter file behind the same protocol. Reasons and alternatives are in ADR-0004.

**Text-only messages.** The client sends text. Turning a PDF or a scanned page into text is a separate, cached step owned by the baselines in M1 and by `docparse` from M2, so every system under test reads the same text and the comparison is about reasoning, not about one provider's PDF reader.

**Async from the start.** `complete` is a coroutine. The fact-finders in M2 run in parallel and the benchmark runner issues several samples at once, and changing a sync protocol to async later would touch every caller. M1 tests drive it with `asyncio.run`; no test plugin is added.

**Cache key.** `sha256` of a version tag, the sample index and the request as canonical JSON (sorted keys, no whitespace). The model id is part of the request, so it is part of the key. Base URL, credentials and timeouts are not.

**Sample index.** Run-to-run spread is measured by sending the same request several times. The sample index makes sample 0, 1 and 2 separate recordings instead of one overwritten entry. `temperature` and `seed` are plain request fields; what the baselines set them to is decided in the baselines note.

**Store.** One JSON file per key under a directory, committed with the benchmark results. Each file holds the request and the response. Files diff and merge in git, and reading them needs no database.

**Structured output: constrained by the provider, validated by the caller.** The caller passes a JSON Schema in `output_schema`; the client asks the provider to constrain its output to it. `Response.text` is the raw string the model produced. Turning that string into a typed object is one Pydantic call, `Model.model_validate_json(text)`, made by the caller. It stays outside `complete` for two reasons: the recording must hold exactly what the model said, including bad output, so that failures can be counted and validation can change without paying for the call again; and the client would otherwise depend on every caller's types. In M1 an output that is truncated, refused or invalid is recorded as a failed run. The repair loop in M2 wraps the same two steps: call, validate, and on failure send the error back.

**Optional usage fields.** Providers report different things. A field the provider does not report is `None`, never 0, so "no cache hit" and "unknown" stay distinct and adding a provider does not change the type.

**Cost.** When the provider reports what it billed for the call, that figure is recorded and used. Otherwise `cost_usd` is arithmetic over recorded usage and a price table in code, in `Decimal`; each row carries its source and the date it was read, and a wrong price is fixed in one place. The table ignores cache discounts, so it can only overstate.

**Aggregator as the configured provider.** M1 runs go through a model aggregator: one key and one endpoint for models from several vendors, in the same wire format, with billed cost and cached tokens in the reply. `extra_body` carries its routing options, for example requiring an upstream that honours the output schema. These options are not part of the cache key; a recording is tied to the model id, not to which upstream served it.

**Errors.** One retry policy is not designed here. The client raises on a non-success status or a timeout and stores nothing. The retry taxonomy arrives with the tool loop.

**Testing the live client.** `httpx` accepts a mock transport, so the request the client builds and the response it parses are tested with canned HTTP exchanges and no network. One test marked `live` makes a single real call and is never selected by default.

## Tests

- Key: equal requests give equal keys; changing any field or the sample index changes it; key order inside `output_schema` does not.
- Record then replay returns an identical `Response`; a miss without an inner client raises `ReplayMiss` naming the key; a hit never calls the inner client.
- Store: an entry round-trips; a corrupt file raises instead of being treated as a miss.
- Cost: arithmetic; an unknown model raises; a reported cost wins over the table.
- Live client against a mock transport: request body snapshot (messages, `output_schema`, temperature, seed, extra body), usage and stop reason mapped, cached tokens and cost read when present and `None` when absent, an error status raises and stores nothing.

## Open points

- **Provider differences inside the common format.** Request and response field names were checked against the first provider's published API specification. The one difference found between providers is the name of the seed field, which is a constructor argument. Whether prompt tokens include cached tokens is not stated by the aggregator's documentation; nothing in M1 depends on it.
- **Live test.** Passed on 2026-11-10 against the configured aggregator and model: schema-constrained JSON came back, with token usage and billed cost. It is rerun by hand when the provider or model changes.
- **Estimating cost before a run.** Without a provider tokenizer, the runner (B8) estimates input tokens from character count with a safety margin and enforces the spend cap on that estimate.

## Alternatives rejected

- **A provider's official SDK.** Typed and convenient, but every caller-visible type would be that provider's, and switching provider would be a rewrite instead of a configuration change.
- **A multi-provider library.** See ADR-0004.
- **An HTTP-level cassette (VCR-style).** It keys on the wire format, so a change of provider or header invalidates every recording, and it stores request headers unless scrubbed.
- **SQLite or Postgres as the store.** A binary file does not diff or merge in git; Postgres would make unit tests need a database.
- **Storing cost with the recording.** A mistake in the price table would then be frozen into every recording.
- **Sync now, async later.** Rejected for the retrofit cost described above.
