# docparse: files to elements

Status: written and implemented 2026-11-11; open to revision.

## Where this fits

Ingest is the first step of a run and the only place files are opened. Everything after it works on elements: the fact-finders search and read them, the verifier checks a cited value against them, and the review screen will highlight them.

```
folder of files ──> parse ──> elements (some image-only) ──> transcribe ──> elements with text
                                                       └──> describe ──> one card per document
```

In M1 the two baselines had their own copy of this step. They now use `docparse`, so the baselines and the engine read exactly the same text.

## Boundaries

```python
Element(doc_id: str, locator: str, text: str, image: bytes | None = None)
    # locator: "p3" for a PDF page, a sheet name, or "body"; image is set when a page has no text

parse_file(filename: str, data: bytes) -> tuple[Element, ...]             # pure
parse_folder(folder: Path, skip: Collection[str] = ()) -> tuple[Element, ...]

Transcriber = Callable[[bytes], Awaitable[str]]
transcribe(elements, transcriber) -> tuple[Element, ...]                  # fills text, drops image

DocumentCard(doc_id: str, type: str, date: date | None, authority: int)
Describer = Callable[[str], Awaitable[Description]]                       # Description(type, date)
build_cards(elements, describe, authority: Mapping[str, int]) -> tuple[DocumentCard, ...]
```

Example: `releve.pdf` with two text pages gives `Element("releve", "p1", "…")` and `Element("releve", "p2", "…")`; a spreadsheet gives one element per sheet whose text has one line per cell, `[Sheet1!B6] 310 m²`.

## Decisions

**`docparse` calls no model.** Reading a scanned page and describing a document both need one, but `docparse` and `llmkit` sit in the same layer and may not import each other. So `docparse` takes a function for each. The workload passes one built on the model client. Parsing stays pure and testable without recordings.

**An element is a page, a sheet or an email body.** That is the unit a citation points at and the unit the benchmark's locators use. Finer structure (paragraphs, table cells with bounding boxes) is added when the review screen needs to highlight a region.

**A spreadsheet cell keeps its reference in the text.** A system can then cite `Sheet1!B6`, and the verifier can find the value there.

**A scanned page keeps its original image.** The image embedded in the PDF page is passed on as it is, with no re-rendering, so the bytes sent to the model, and therefore the recording key, do not depend on the machine.

**A card is the workload's reading of a document.** Its type comes from a list the workload supplies, and its authority from the workload's ranking of those types. The platform compares integers and knows no document types. A document whose type is not recognised gets authority 0, the lowest.

**No parser interface yet.** There is one way to read each file type, so the dispatch is a table of functions. A second PDF reader would be the reason to introduce one.

## Tests

- Each file type: text PDF pages with locators, an image-only page with its image and no text, spreadsheet cells with references, email subject, date and body; an unknown extension raises.
- `transcribe` calls the function once per image-only element and leaves the others untouched.
- `build_cards` passes the start of each document to the describer once, maps type to authority, and gives an unrecognised type authority 0.
- The M1 report still reproduces from its recordings after the baselines switch to `docparse`.

## Alternatives rejected

- **Importing the model client into `docparse`.** It would break the layer rule and make every parsing test need recordings.
- **A layout-aware parser now.** No M2 task uses regions inside a page. See ADR-0006.
- **Describing documents with rules on titles.** It would work on the benchmark's templates and nowhere else.
