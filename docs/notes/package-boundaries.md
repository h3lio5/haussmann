# Package boundaries

Status: approved 2026-11-10; revised the same day from nine platform distributions to one. Needed by M1 task A3.

## Contract

The platform is one installable package, `haussmann`, made of nine modules. Each workload is its own package on top.

```
workloads        feasibility_fr (later lease_abstract)      separate packages
-----------------------------------------------------------------------------
layer 4          haussmann.review
layer 3          haussmann.buildkit | haussmann.evalkit
layer 2          haussmann.ctxkit | haussmann.flow
layer 1          haussmann.llmkit | haussmann.docparse | haussmann.ledger
layer 0          haussmann.coretypes
```

- A module may import any module in a lower layer.
- Modules on the same layer do not import each other.
- Nothing in `haussmann` imports a workload. Workloads do not import each other.
- `coretypes` imports only the standard library.

## Invariants

1. **`coretypes` stays small.** A type moves there only when two modules on the same layer both need it, for example the `Locator` that `docparse` produces and `ledger` stores in a citation. It holds frozen dataclasses and identifiers, no behavior, no I/O, no Pydantic.
2. **Same-layer independence is real.** `evalkit` scores a submission and never reads `buildkit` internals; `ctxkit` and `flow` know nothing of each other. If two siblings need to talk, the wiring belongs in the layer above or in the workload.
3. **No domain vocabulary in `src/haussmann/`.** Source and READMEs there must not contain, as whole words and ignoring case: parcel, cadastre, zoning, PLU, lease, tenant, landlord, rent, deed, easement, dataroom. The platform says "document set", "fact", "subject". The list grows when a new workload brings new words.
4. **The platform/workload line is a package boundary.** A workload declares `haussmann` as a dependency; the reverse dependency cannot be declared.

## Enforcement

import-linter, run in CI as `uv run lint-imports`:

```toml
[tool.importlinter]
root_packages = ["haussmann", "feasibility_fr"]

[[tool.importlinter.contracts]]
name = "Platform layers"
type = "layers"
containers = ["haussmann"]
layers = ["review", "buildkit | evalkit", "ctxkit | flow",
          "llmkit | docparse | ledger", "coretypes"]

[[tool.importlinter.contracts]]
name = "Platform never imports a workload"
type = "forbidden"
source_modules = ["haussmann"]
forbidden_modules = ["feasibility_fr"]

# Added with the second workload:
# type = "independence", modules = ["feasibility_fr", "lease_abstract"]
```

The vocabulary rule is a pytest test that scans `src/haussmann/` for the banned terms, with a fixture proving it fails when a term is planted.

## Alternatives rejected

- **Nine platform distributions in a workspace** (the first layout, built and then dropped). It buys independent installation, which nothing here needs, at the cost of ten build configurations and a dependency declaration to maintain for every cross-module import. The layer rule is enforced by import-linter either way, so the extra packaging added ceremony without adding a guarantee.
- **Everything in one package, workloads included.** Removes the one boundary that carries the extensibility claim: a workload must be addable without touching the platform.
- **Modules share only a types module, with no layers.** Cannot hold: `evalkit` calls `llmkit`, `buildkit` reads `ledger`, `review` needs both.
- **Strict independence with all wiring in workloads.** Each workload would repeat the same composition code, which defeats the small-second-workload measure.
- **Naming the shared module `types`.** Confusing next to the standard library module of the same name.
