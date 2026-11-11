# llmkit

Provider-agnostic model client with replay cache and cost accounting.

## Contract

One call interface over model providers, a replay cache keyed by request hash, usage and cost per call. Later: tool loop, structured outputs with repair, retry taxonomy, tracing.

## Status

`client` (`Request`, `Response`, `LLMClient`), `replay` (`ReplayClient`, `ReplayStore`, `request_key`), `chat_completions` (live client over httpx), `pricing` (`cost_usd`). Design: `docs/notes/llmkit-client-and-replay.md`. `embeddings` (`Embedder`, live client, replay). Tool loop not started.
