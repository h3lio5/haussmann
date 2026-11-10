# Package boundaries

Status: approved 2026-11-10. Needed by M1 task A3.

## Contract

The repo is a uv workspace of nine platform packages and the workloads on top. Imports are allowed in one direction only, down this list:

```
workloads        feasibility_fr (later lease_abstract)
layer 4          review
layer 3          buildkit | evalkit
layer 2          ctxkit | flow
layer 1          llmkit | docparse | ledger
layer 0          coretypes
```

- A package may import any package in a lower layer.
- Packages on the same layer do not import each other.
- No platform package imports a workload. Workloads do not import each other.
- `coretypes` imports only the standard library.

## Invariants

1. **`coretypes` stays small.** A type moves there only when two packages on the same layer both need it, for example the `Locator` that `docparse` produces and `ledger` stores in a citation. It holds frozen dataclasses and identifiers, no behavior, no I/O, no Pydantic.
2. **Same-layer independence is real.** `evalkit` scores a submission and never reads `buildkit` internals; `ctxkit` and `flow` know nothing of each other. If two siblings need to talk, the wiring belongs in the layer above or in the workload.
3. **No domain vocabulary in `packages/`.** Source and READMEs under `packages/` must not contain, as whole words and ignoring case: parcel, cadastre, zoning, PLU, lease, tenant, landlord, rent, deed, easement, dataroom. The platform says "document set", "fact", "subject". The list grows when a new workload brings new words.
4. **Each package installs alone** with only its lower-layer dependencies declared in its own `pyproject.toml`.

## Enforcement

import-linter, run in CI as `uv run lint-imports`, with three contracts in the root `pyproject.toml`:

```toml
[tool.importlinter]
root_packages = ["coretypes", "llmkit", "docparse", "ledger", "ctxkit",
                 "flow", "buildkit", "evalkit", "review", "feasibility_fr"]

[[tool.importlinter.contracts]]
name = "Platform layers"
type = "layers"
layers = ["review", "buildkit | evalkit", "ctxkit | flow",
          "llmkit | docparse | ledger", "coretypes"]

[[tool.importlinter.contracts]]
name = "Platform never imports a workload"
type = "forbidden"
source_modules = ["coretypes", "llmkit", "docparse", "ledger", "ctxkit",
                  "flow", "buildkit", "evalkit", "review"]
forbidden_modules = ["feasibility_fr"]

# Added with the second workload:
# type = "independence", modules = ["feasibility_fr", "lease_abstract"]
```

The vocabulary rule is a pytest test that scans `packages/` for the banned terms, with a fixture file proving it fails when a term is planted.

## Alternatives rejected

- **Platform packages share only a types module** (the original wording in ARCHITECTURE.md). It cannot hold: `evalkit` judges and baselines call `llmkit`, `buildkit` reads `ledger`, `review` needs both. Keeping the rule would push every protocol into the shared module until it stopped being small.
- **Strict independence with all wiring in workloads.** Clean on paper, but each workload would repeat the same composition code, which defeats the small-second-workload measure.
- **One package with sub-modules.** Simpler to set up, but loses "each installable on its own" and makes the boundary a convention rather than a dependency declaration.
- **Naming the shared module `types`.** It shadows the standard library module.

## Consequence for existing docs

ARCHITECTURE.md section 2, first rule, changes from "Platform packages share only a small `types` module" to a pointer to this layer order.
