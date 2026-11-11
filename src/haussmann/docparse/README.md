# docparse

Files to elements with provenance.

## Contract

Any supported file in, a list of elements out, each with a locator back to its source (page and box, sheet and cell, or message id), plus a document card per file.

## Status

`elements` (`Element`, `parse_file`, `parse_folder`, `transcribe`) and `cards` (`DocumentCard`, `build_cards`). Design: `docs/notes/docparse.md`.
