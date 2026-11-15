# Workload definition

Status: proposed 2026-11-15, for slice J (`docs/plan/J-engine-out-of-the-workload.md`). Nothing is implemented.

## Where this fits

Today the steps of a run and the review session live in `feasibility_fr` and import its declarations as module constants. This note defines the one record through which those steps receive everything that belongs to a domain, so that the steps can move under the platform and a second domain supplies a record instead of a copy of the code.

- **Built by**: the workload, once, as a module constant (`feasibility_fr.workload.WORKLOAD`).
- **Read by**: ingest, the finder, the run, the memo steps, the review session and its HTTP API.
- **Passed by**: the workload's entry points (the demo command, the benchmark's engine system), which already pass the documents, the required facts, the runner and the model name.

## Contract

Two new platform packages, above `review`:

```
haussmann.app       review session and HTTP API           (from feasibility_fr.app)
haussmann.engine    ingest, find, run, memo steps         (from feasibility_fr.engine)
haussmann.review    unchanged
```

`engine` sits above `review` because the step that answers a reviewer's comment builds a `review.Proposal`. `app` sits above `engine` because opening a session runs the engine.

`RequiredFact` (key, text, `sum_of`, `depends_on`) moves to `haussmann.engine`; it has no domain content. The list of required facts stays a per-run argument, as now: it comes from the scenario or the file being opened, not from the workload.

The record, in `haussmann.engine.workload`, as frozen dataclasses:

| Field | Type | What it carries | Today |
|---|---|---|---|
| `schema` | `Schema` | Attributes, kinds, units, tolerances | `schema.ATTRIBUTES` |
| `main_subject` | `str` | The subject whose facts are grouped in chunks by the planner | `"site"` in `run.py` |
| `documents` | `DocumentTypes` | `authority` by type, `type_of_form` (file form that decides a type), `descriptions` shown to the describer | `engine/documents.py` |
| `dates` | `DateRules` | `valid_for_months` by attribute, `end_dates` | `engine/rules.py` |
| `cases` | `Mapping[FactKey, CaseForm]` | How a case of a deciding fact is written | `spec.CASE_FORMS` |
| `language` | `Language` | `format_date`, `format_value`, `parse_date`, `unit_names`, `reasons` (settling reasons as printed) | `french.py`, `_RULES_FR`, `_reason` |
| `prompts` | `Prompts` | Every instruction text: transcribe, describe, finder instructions and its three notes, tool and parameter descriptions, writer instructions, revise instructions, and their versions | constants in `ingest.py`, `finder.py`, `memo.py` |
| `deliverable` | `Deliverable` | The `buildkit.Spec` of sections, the title, the flag mark, the text of an empty section | `memo.MEMO`, `FLAG_MARK`, `NOTHING`, `render` |

Input and output of the moved functions do not change except for this one argument, which replaces `schema` where it was passed and the module constants where they were imported: `run_engine(workload, wanted, elements, cards, runner, model, as_of, sample)`, `ingest(workload, folder, client, model, skip)`, `memo_step(workload, runner, asked, model, cache)`, `Session.open(workload, ...)`, `create_app(...)` unchanged.

What stays in `feasibility_fr`: `schema.py`, `french.py`, `workload.py` (the record, with the prompts and the deliverable), `app/demo.py`, and the benchmark.

## Invariants

1. **No request changes.** The engine is frozen (`docs/notes/heldout.md`, rule 1). Every prompt text moves as a string, unedited, and is assembled in the same order. The check is the replay cache: the benchmark report reproduces byte for byte on dev and held-out and the demo opens its three files, with no missing recording. One miss means the move changed a request, and the change is reverted, not re-recorded.
2. **No journal changes.** Step names, author names and the inputs digest are unchanged, so a stored run resumes after the move.
3. **The platform holds no instruction text.** System prompts, notes, and tool and parameter descriptions come from `Prompts`. What the engine itself answers to a tool call (a confirmation, a refusal and its reason) is engine behaviour and stays in code.
4. **The record is data plus plain functions.** No base class, no protocol, no registry. `Language` is a dataclass of four callables and two mappings.
5. **The record is not global.** It is passed down from the entry point; no module in `haussmann` imports a workload, and the import contract and the vocabulary test cover the two new packages.
6. **Tuning constants are not workload data.** Group size, passes, loop and context budgets stay constants of the engine. They were tuned on one workload; a second one may show that some belong in the record, and they move then.

## Alternatives rejected

- **Leave it, and copy the engine for a second domain.** Two copies of the finder and the writer would drift, and the claim that a workload is small would be false in the code.
- **Generic English prompts in the platform with slots for domain words.** It changes every request, so the frozen engine and the held-out result would no longer describe the code. It would also be a prompt change with no measurement behind it.
- **Hooks by subclassing (a base `Engine` with methods to override).** Nothing the workload supplies needs to call back into the engine. A record is enough and is easier to read than an inheritance chain.
- **Declarations in a configuration file.** The language functions are code, and fact keys and attribute names are checked by the type checker and the tests when they are Python values.
- **Moving the steps into existing packages** (`find` into `ctxkit`, memo into `buildkit`, session into `review`). The steps import across those packages; placed inside them they would break the layer rule that same-layer packages do not import each other.

## Open point

Invariant 4 passes an interface (the record) with one implementation. `ARCHITECTURE.md` names workloads as one of the three places where an interface is allowed; until a second workload exists, the record's shape is fitted to one case and is expected to change when the second one is written.
