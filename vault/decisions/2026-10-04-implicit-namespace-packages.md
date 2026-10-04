---
title: "Adopt PEP 420 implicit namespace packages"
type: decision
tags:
  - type/decision
  - domain/governance
  - domain/tooling
  - status/reviewed
created: "2026-10-04"
updated: "2026-10-04"
code-refs:
  - ember/agent_kit/api.py
  - pyproject.toml
  - .specify/memory/constitution.md
---

# Adopt PEP 420 implicit namespace packages

Part of [[ember]]. No `__init__.py` file exists anywhere under `ember/` — Python 3.3+
discovers all sub-packages from the filesystem (PEP 420). Constitution amended to v1.3.3.

## Context

Article X §10.1 (added 2026-10-03) required a bare, docstring-only `__init__.py` at every
fully-owned package level — the "ownership policy" style also used by the anvil, wellspring,
and darkfactory peer repos. The maintainer requested a shift to pure PEP 420 implicit
namespaces, aligning ember with the infrastructure and k8s.platform peers instead.

Two `__init__.py` files existed in the codebase:

- `ember/__init__.py` — a bare docstring-only marker with no public API. Pure noise.
- `ember/agent_kit/__init__.py` — real API code (`instructions()`, `skill()`, `snippet()`,
  `skill_path()`, `install_skill()`, `SKILL_NAME`, `GUIDE_URI`, `AGENTS`). Callers used
  `from ember import agent_kit` then `agent_kit.X`.

The build backend is hatchling with `packages = ["ember"]` in `pyproject.toml` — an explicit
package list that does not rely on `__init__.py` for discovery. `importlib.resources.files()`
works on namespace packages (returns a `MultiplexedPath`), verified empirically.

Anvil tried pure PEP 420 (Article VI v1.4.0) and reversed it (ADR-021), citing namespace
collision risk and developer confusion. Those objections don't apply here: ember is a
single-package codebase with no namespace-split distribution, and the mandatory `explicit_package_bases = true` mypy setting makes the toolchain fully aware of the implicit structure.

## Decision

- All `__init__.py` files removed from `ember/`.
- `ember/agent_kit/__init__.py` API code moved to `ember/agent_kit/api.py`; `_read()` updated
  to use `files("ember.agent_kit")` (explicit package name, resolves to the same directory).
- All import sites updated: `from ember import agent_kit` →
  `from ember.agent_kit import api as agent_kit` (6 files: `ember/cli.py`,
  `ember/mcp_server.py`, `tests/test_agent_kit.py`, `tests/test_mcp_tool.py`,
  `tests/test_cli.py`, `evals/agent/sandbox.py`).
- `pyproject.toml` `[tool.mypy]` gains `explicit_package_bases = true` so mypy resolves
  relative imports in namespace packages correctly.
- Constitution amended to v1.3.3 (PATCH); AGENTS.md §10.1 bullet updated.

## Consequences

- No `__init__.py` files exist anywhere under `ember/`. This is now the constitutional rule
  (§10.1) and MUST NOT be violated.
- When a sub-package needs a public API, the code goes in a named module inside the
  sub-package (e.g. `api.py`) and callers import from that module explicitly.
- `mypy --strict` requires `explicit_package_bases = true`; this is set in `pyproject.toml`
  and MUST stay there.
- `make pr-ready` passes: ruff, mypy (12 files, no issues), bandit, compile, 127 tests.
