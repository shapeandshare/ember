---
title: Adopt peer Python conventions as Article X
type: decision
tags:
  - type/decision
  - domain/governance
  - status/draft
created: 2026-10-03
updated: 2026-10-03
code-refs:
  - .specify/memory/constitution.md
  - AGENTS.md
  - CONTRIBUTING.md
---

# Adopt peer Python conventions as Article X

Part of [[ember]]. We harvested the opinionated Python style rules from the sibling
repositories and adopted them as constitution Article X, applied prospectively to new and
modified code.

## Context

ember's agent-facing style rules were thin compared with its siblings. A survey of the peer
`AGENTS.md` and `.specify/memory/constitution.md` files — anvil, wellspring, heretic, conjure,
sonarqube-standalone, gh-runner-standalone, infrastructure, k8s.platform, darkfactory,
specworks, and the fired-up-pizza reference project — found a converging family convention
(one class per file, `__init__.py` ownership, top-of-file imports with named exceptions, coded
type suppressions, enums over magic strings, Pydantic over dataclasses, Protocol over ABC,
NumPy docstrings) alongside two genuine tensions: the single "God Class" façade (mandated by
anvil/wellspring, rejected by darkfactory/fired-up-pizza) and async-first versus
async-at-boundaries.

## Decision

Adopt the converged rules as **Article X — Python Conventions**, scoped to new and modified
code. Resolve the tensions in ember's favour and record the divergence: ember keeps its
MCP / HTTP / CLI seam instead of a God class, and keeps synchronous MPS inference behind the
engine lock instead of async-first. Existing violations (the 445-line `ember/cli.py`,
function-oriented modules, missing NumPy docstrings and `py.typed`) are recorded as migration
debt in Article X §10.18 rather than fixed in this change.

## Consequences

- `AGENTS.md` and `CONTRIBUTING.md` mirror the rules; the constitution is authoritative.
- New code must satisfy the rules; touching a file means paying down its debt, but untouched
  files must not be reformatted.
- Both enforcement follow-ups landed with this decision: `ember/py.typed` (PEP 561) and ruff
  pydocstyle (NumPy) over `ember/` (tests and scripts exempt). The remaining Article X debt is
  the `ember/cli.py` line ceiling plus the one-class-per-file / function-oriented gap.
