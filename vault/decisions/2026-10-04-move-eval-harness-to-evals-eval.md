---
title: "Move benchmark harness scripts from scripts/ into evals/eval/"
type: decision
tags:
  - type/decision
  - domain/tooling
  - domain/governance
  - status/reviewed
created: "2026-10-04"
updated: "2026-10-04"
code-refs:
  - evals/eval/run_evals.py
  - evals/eval/report_evals.py
  - evals/eval/snapshot_evals.py
  - evals/eval/run_agent_evals.py
  - ember/cli.py
  - shared/testing.mk
---

# Move benchmark harness scripts from scripts/ into evals/eval/

Part of [[ember]]. Four benchmark harness scripts moved from `scripts/` into a
new `evals/eval/` sub-package. `scripts/` now contains only make-invoked dev
tools with no package coupling.

## Context

`scripts/` contained ten files split across two distinct roles:

1. **Benchmark harness** (`run_evals.py`, `report_evals.py`, `snapshot_evals.py`,
   `run_agent_evals.py`) — these four are already imported by `ember/cli.py` to
   implement `ember eval run/report/export/snapshot/agent`. They belong with the
   eval domain, not in a sibling non-package directory.

2. **Make-only dev tools** (`smoke_mps.py`, `test_mcp_client.py`, `vault_audit.py`,
   `check_provenance.py`, `build_site_docs.py`, `build_site_benchmark.py`) — purely
   invoked by `make` targets, no package coupling.

The harness scripts importing into `ember/cli.py` from `scripts/` was a
cross-boundary smell: an application package importing from a sibling
non-package directory. Peer repos (anvil, wellspring) place CLI-reachable
logic under the package, not in `scripts/`.

## Decision

- Created `evals/eval/` sub-package with a bare `__init__.py` marker.
- Moved the 4 harness scripts into `evals/eval/`.
- `run_agent_evals.py` inter-dependency on `run_evals._git_hash/_host` updated
  from `from scripts.run_evals import` → `from .run_evals import` (relative).
- `ember/cli.py` 5 deferred imports updated from `scripts.*` → `evals.eval.*`;
  error message and docstring updated.
- `shared/testing.mk` 6 invocation paths updated from `scripts/*.py` →
  `evals/eval/*.py`.
- All docstrings, `evals/report_text.py` architecture text, AGENTS.md, README.md,
  and the vault decision note `2026-10-03-measure-ember-through-the-agent.md`
  code-ref updated.
- `scripts/` retains the 6 make-only tools: no callers changed.

## Consequences

- `ember eval run/report/export/snapshot/agent` still work; now they import
  cleanly from `evals.eval.*` within the package tree.
- `scripts/` is now unambiguously "make-only dev tooling with no package
  coupling" — no file in `scripts/` is ever imported by application code.
- `evals/` root has 7 modules + 4 sub-packages (`render/`, `sections/`,
  `charts/`, `eval/`, `agent/`) — at or near §10.3's threshold; `agent/`
  and `eval/` are each ≤4 modules.
- `make pr-ready` and `make vault-audit` pass clean.
