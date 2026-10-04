---
title: "Reinstate explicit __init__.py ownership policy with root-only re-export"
type: decision
tags:
  - type/decision
  - domain/governance
  - domain/tooling
  - status/reviewed
created: "2026-10-04"
updated: "2026-10-04"
code-refs:
  - ember/__init__.py
  - ember/agent_kit/__init__.py
  - ember/agent_kit/api.py
  - pyproject.toml
  - .specify/memory/constitution.md
---

# Reinstate explicit __init__.py ownership policy with root-only re-export

Part of [[ember]]. Every owned package level under `ember/` carries an `__init__.py`;
sub-package markers are bare and docstring-only; only `ember/__init__.py` (the root) may
re-export symbols. Constitution amended to v1.3.4.

## Context

Constitution v1.3.3 (2026-10-04) mandated pure PEP 420 implicit namespaces — no
`__init__.py` anywhere. The maintainer reversed this immediately in the same session,
specifying the rule:

- **Every authoritative package level MUST have an `__init__.py`.**
- **Sub-package markers are bare and docstring-only** (no imports, no re-exports).
- **Only the package root `ember/__init__.py` may re-export symbols** (and MAY carry
  `__version__`).

This is the same "ownership policy" used by the anvil, wellspring, and darkfactory peer
repos, with one clarification the peers don't make explicit: re-exports are the exclusive
right of the package root, not of sub-package `__init__.py` files.

The PEP 420 reversal mirrors anvil's own ADR-021 trajectory (anvil tried pure PEP 420,
then reversed it citing namespace collision risk and developer confusion).

## Decision

- `ember/__init__.py` restored: docstring + `from __future__ import annotations`. MAY
  carry `__version__` and root-level re-exports in future.
- `ember/agent_kit/__init__.py` restored: bare docstring + `from __future__ import
  annotations`. No imports, no re-exports.
- `ember/agent_kit/api.py` retained: the named module is where the agent-kit public API
  lives; callers import `from ember.agent_kit import api as agent_kit`.
- `explicit_package_bases = true` removed from `pyproject.toml` `[tool.mypy]` — no
  longer needed with explicit `__init__.py` markers present.
- Constitution amended to v1.3.4 (PATCH); AGENTS.md and CONTRIBUTING.md updated.

## Consequences

- Every owned package level under `ember/` MUST have an `__init__.py`. Absence = a bug.
- Sub-package `__init__.py` files are bare docstring-only markers. No imports, no
  re-exports. Violating this = a bug.
- `ember/__init__.py` is the single permitted re-export surface. Future public API
  additions go there if they need top-level access (`import ember; ember.X`).
- `ember/agent_kit/api.py` remains the right way to expose the agent-kit API; the
  sub-package `__init__.py` intentionally does NOT re-export from it.
- `make pr-ready` passes: ruff, mypy (12 files, 0 issues), bandit, compile, 127 tests.
