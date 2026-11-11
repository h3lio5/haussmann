# Baselines

Status: written 2026-11-11 and implemented in the same change at the owner's request; open to revision.

## Where this fits

The baselines are the first contestants in the benchmark. Each reads a scenario's files, answers a fixed list of questions, and returns a `Submission` for the scorer. Their scores are the bar the engine has to clear in M2 on the same files and the same model.

```
files/ (PDF, scan, XLSX, EML) ──> read ──> pages of text ──┐
question list (fact keys) ─────────────────────────────────┼──> baseline ──> Submission ──> scorer
                                                           │    (a) everything in one prompt
                                                           │    (b) retrieve pages, then one prompt
```

A baseline never sees the scenario spec or the manifest. The question list is the manifest's fact keys with their values removed, handed over by the runner.

## Boundaries

```python
# reading: files in, text out
Page(doc_id: str, locator: str, text: str)             # locator: "p3", "Sheet1", "body"
read_folder(folder, client, model) -> tuple[Page, ...]

# the answer contract shared by both baselines
answer_schema(schema) -> dict                          # JSON Schema sent to the model
parse_answer(text, schema) -> Submission               # raises InvalidAnswer

# the two baselines
one_prompt(pages, questions, schema, client, model, sample) -> Attempt
naive_rag(pages, questions, schema, client, embedder, model, embedding_model, sample) -> Attempt

Attempt(submission: Submission | None, failure: str | None, responses: tuple[Response, ...])
```

The model returns JSON of this shape, constrained by the provider:

```json
{"facts": [{"subject": "site", "attribute": "max_height", "value": "9", "unit": "m",
            "citations": [{"doc_id": "reglement_zone", "locator": "p8"}], "flagged": false}],
 "open_questions": [{"subject": "site", "attribute": "soil_study"}]}
```

## Decisions

**Both baselines read the same text.** Reading is one shared step, so the comparison between baselines, and later with the engine, is about what is done with the text and not about who has the better PDF reader. A PDF page with a text layer is extracted locally. A page without one is rendered to an image and transcribed by one model call, recorded like any other call. Spreadsheets become one line per cell with its cell reference; emails become their body.

**Values travel as strings and are parsed against the schema.** Every fact carries `value` and `unit` as strings. The attribute's kind decides how `value` is read: a quantity as a decimal number, a date as ISO, text as is. A value that cannot be read as its attribute's kind is kept as text, which the scorer classes as invented. Only JSON that does not match the shape at all fails the run. This keeps the schema free of nullable and union types, which providers support unevenly.

**The model writes numbers here, on purpose.** The project rule that a model never types a number applies to the engine. A baseline is the naive approach, and letting the model report values directly is what makes it naive.

**Baseline (a): one prompt.** All pages, in file order, with a marker before each page giving its document id and locator, then the question list. One call.

**Baseline (b): retrieve, then one prompt.** One chunk per page. Each question becomes a short French query built from its subject and attribute label. Queries and pages are embedded with one multilingual embedding model through the same provider, and the three most similar pages per question are kept. The union, in file order, goes into the same prompt as baseline (a). One call. No reranking, no query rewriting, no second attempt.

**Same instructions, same model, same settings for both.** Temperature 0 and a seed equal to the sample number. Three samples per scenario measure what variation remains.

**Prompts live in code and are versioned by the experiment log.** Changing a prompt changes the request, so it shows up as cache misses and needs a new row in `EXPERIMENTS.md`.

## Tests

- Reading: text PDF pages, a scanned page going through the transcription call, spreadsheet cells with references, email body.
- Answer: a valid answer parses to the expected `Submission`; French-formatted and ISO values; an unreadable value stays text; malformed JSON raises.
- Baselines against a scripted client: baseline (a) sends every page and all questions; baseline (b) sends only retrieved pages; an invalid answer becomes a failed attempt, not an exception.
- Retrieval is deterministic for fixed vectors and keeps file order.

## Known limits

- Page-sized chunks are coarse. A finer splitter would be a fairer retrieval baseline on long pages; the scenarios' long document has short pages, so this is left.
- The transcription model is the same model as the contestant. A stronger reader would lift every system equally.
- Queries for baseline (b) use the question's own words. A real naive system would not have such clean queries, so this favours baseline (b).

## Alternatives rejected

- **Native PDF input.** Not available through the provider-neutral client, and it would make the reading step differ between systems.
- **A local embedding model.** A model download and a large runtime dependency for forty vectors per scenario. See ADR-0005.
- **Keyword-only retrieval.** Cheaper still, but a retrieval baseline without embeddings would be dismissed as a strawman.
- **Nullable typed value fields.** Cleaner to read, but schema-constrained output with unions is not reliably supported across providers.
