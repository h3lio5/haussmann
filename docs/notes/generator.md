# Benchmark document generator

Status: approved 2026-11-10. Needed by M1 tasks B2, B3.

## Where this fits

A scenario spec is the answer key: true facts, the documents to produce, the planted errors. The generator turns that key into the files a system under test reads, and a manifest recording what each file states and where.

```
scenario spec ──> validate ──> generator ──┬─> files (PDF, scanned PDF, XLSX, EML) ──> baselines, engine
 (answer key)                              └─> manifest ─────────────────────────────> scorer
```

Nothing else writes scenario files, and nothing downstream sees the spec. The baselines and the engine read only the files; the scorer reads only the manifest. Why the documents are synthetic at all is in `benchmark-rationale.md`.

## Contract

Orchestration, renderers and scan degradation live in `haussmann.evalkit`. Document wording lives in the workload.

```python
# what a template returns: a layout-neutral document
Heading(text: str)
Paragraph(text: str, states: tuple[PlannedStatement, ...] = ())    # text has one "{}" slot per statement
Table(header: tuple[str, ...], rows: tuple[Row, ...])              # a cell is text or a PlannedStatement
Filler(paragraphs: int)                                            # boilerplate, for long documents
Body(title: str, blocks: tuple[Block, ...])

Template = Callable[[DocumentPlan, random.Random], Body]           # workload
Formatter = Callable[[Value, AttributeDef], str]                   # workload: how a value is written

Generated(files: Mapping[str, bytes], manifest: Manifest)

build(spec, schema, templates: Mapping[str, Template], format_value: Formatter,
      filler: Sequence[str] = (), buried_from_page: int = 5) -> Generated   # pure
GeneratorError(ValueError)
write(generated: Generated, out_dir: Path) -> None                 # the only I/O
```

- `build` refuses a spec that `validate` rejects.
- `DocumentPlan.source` names the template; `DocumentPlan.format` picks the renderer (`pdf`, `xlsx`, `eml`); `scanned` applies to PDFs.

## Decisions

**Templates return blocks, not bytes.** A template says what the document contains; a renderer decides where it lands. The renderer therefore knows the page or cell of every statement as it lays it out, and reports it. The alternative, rendering first and searching the output for each value, breaks when a value is split across lines or appears twice.

**Values are written by the generator, not by the template.** A template leaves a `{}` slot and attaches the planned statement; `build` fills the slot with `format_value(statement.value)`. A template cannot mistype or alter a planted value, for the same reason no model writes these documents.

**Locators.** `p<N>` for a PDF page (1-based), `<sheet>!<cell>` for a spreadsheet, `body` for an email. The scorer compares them as strings. A paragraph carrying a statement is kept on one page.

**Scanned PDFs.** The text PDF is rendered first, then each page is rasterized, converted to grayscale, rotated by a fraction of a degree, given noise and JPEG compression, and reassembled as an image-only PDF with no text layer. Locators are taken before degradation, so they stay exact. What the scan does to a number is left to whatever reads it, as with a real scan.

**Buried statements.** `Filler` adds seeded boilerplate paragraphs supplied by the workload. After generation, a BURIED statement must sit on page 5 or later; the threshold is a parameter, reviewed at the difficulty check in B8.

**Determinism.** Each document gets its own random generator seeded from the scenario seed and the document id, so adding a document does not change the others. Timestamps written into spreadsheets, emails and scans come from `DocumentPlan.date`; text PDFs are written in the library's invariant mode, which fixes them; spreadsheet archives are rewritten with fixed entry times and without the save time the library inserts; PDFs use the library's built-in fonts. The guarantee is: same spec, same locked dependencies, same platform gives identical bytes. Across platforms the committed files and manifest are the reference, and the check is that each committed file matches its recorded hash.

**Public data enters through templates.** Real public facts for a site are frozen in the scenario and rendered by templates like any other fact. Attaching an existing public file with hand-written locators is not in this slice.

**Rendering libraries are an optional extra.** They are needed to regenerate scenarios, not to run the engine or the scorer. See ADR-0003.

## Tests

- Two builds of the same spec give identical files and manifests; changing the seed changes filler but no statement value or kind.
- For every statement in a text PDF, the formatted value appears in the text extracted from the page its locator names. For a spreadsheet, the cell at the locator holds the value. For an email, the parsed body contains it.
- A scanned PDF has the same page count as its source and no extractable text.
- Every trap and every planned statement of the spec appears in the manifest with a locator; a BURIED statement before the threshold fails the build.
- A template whose text has the wrong number of slots, or names a missing template or an unknown format, fails with a clear error.
- An invalid spec is refused.

## Known limits

- Emails have fixed placeholder sender and recipient addresses; who wrote to whom is carried by the body text.
- A scanned page is about 150 KB, so a scenario with forty scanned pages adds about 6 MB of committed files.
- The workload's templates, value formatter and filler text are written with the scenarios (B3); this slice is tested with small templates of its own.
- Documents built from blocks and built-in fonts look plainer and more regular than real ones. This is the main way the benchmark is easier than reality.
- Scan degradation is mild and uniform: no stamps, handwriting, folds or skewed photographs.
- One layout per format. Held-out scenarios get different templates in M3, not different renderers.

## Alternatives rejected

- **HTML to PDF (WeasyPrint or a headless browser).** Better-looking documents, but system libraries or a browser in CI, no direct way to learn which page a block landed on, and output that varies across versions.
- **LaTeX or Typst.** An external binary to install everywhere the generator runs.
- **A model writing or restyling the documents.** It can change a planted value, and it adds cost and nondeterminism. Kept as a possible later stage that never touches value slots.
- **Finding locators by searching the rendered file.** Rejected above.
- **A document-augmentation library for scans.** A large dependency for five image operations.
