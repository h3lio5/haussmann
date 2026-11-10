# ADR-0001: Toolchain

Status: accepted, 2026-11-10

Python 3.12 in a uv workspace: one lockfile, one environment. The platform is a single package at the repo root and each workload under `workloads/` is its own package. Packages build with hatchling from a `src/` layout. Quality gates are ruff (lint and format), pyright in strict mode, pytest with Hypothesis, and import-linter for the package boundaries. Pydantic v2 is used at I/O boundaries and httpx for HTTP. These are the tools named in PROJECT.md section 7 and they are covered by this single record; any dependency outside that list gets its own ADR. Alternatives considered: Poetry or pip-tools (no workspace support as direct as uv's), mypy (pyright strict is faster and stricter on inference), one distribution per platform module (rejected in `docs/notes/package-boundaries.md`).
