---
title: "Constitution consistency audit (2.0.0 → 2.0.1)"
type: discovery
tags:
  - type/discovery
  - domain/governance
  - domain/tooling
  - status/draft
created: "2026-10-06"
updated: "2026-10-06"
code-refs:
  - .specify/memory/constitution.md
  - ember/serving/process.py
  - evals/export.py
  - evals/eval/run_evals.py
  - evals/eval/run_agent_evals.py
  - evals/eval/snapshot_evals.py
---

# Constitution consistency audit (2.0.0 → 2.0.1)

Part of [[ember]]. The constitution had drifted from the code and docs. It contradicted itself
on coverage, CI, async rules, and layers, and its §10.18 debt list understated reality. The
docs had drifted less than the constitution had.

## What was tested

Each Article was read against `ember/`, `evals/`, `tests/`, `.github/workflows/`, `shared/*.mk`,
`pyproject.toml`, and the satellite docs. Line counts were taken with `wc -l`. Imports, route
handlers, prints, and writes were grepped.

## Finding

- **The code is clean on Articles I, IV, XII, XIII, and XIV.** No layer leaks, no untagged
  sync handlers, no kill-by-port, and no test binds 8765 or launches opencode.
- **Constitution text was stale or self-contradictory:**
  - Article VIII said coverage was "not yet gated, 60%" (XI and `pyproject.toml` say 71,
    gated) and named a `ci-check.yml` that never existed.
  - §12.1 and §12.2 conflicted, §12.2 recommended the deprecated `get_event_loop`, and
    §12.3 described a sync MCP tool.
  - The Article XIII diagram put `server.py` in two layers.
  - §14.1 described only the 503 path, not the lifecycle refusal.
  - The 2.0.0 report cited the wrong task IDs (T020–T022 instead of T023–T025).
- **§10.18 was broken.** `ember/cli.py` grew from 929 (recorded) to 1086 lines. Nine other
  modules over 400 lines were never recorded, and two `evals/` magic-string sets
  (conditions, tones) were unrecorded.
- **Two code violations were fixed:** `process._append_audit_log` used `print` (§10.13), and
  the eval result and snapshot writes were not atomic (§10.17).
- **Docs:**
  - AGENTS.md and README undercounted the CI jobs (no SonarCloud).
  - AGENTS.md called `make test-cov` the full suite; it is the unit suite.
  - SECURITY.md omitted `ember/cfg/endpoint.py`.
  - The `ci.yml` sonar comment still says `make test-cov` runs "the local full suite". It
    was left alone because pushing workflow changes needs the `workflow` token scope.

## Relevance

Re-run this audit after any amendment. The debt list must be re-measured, not copied
forward. Splitting `cli.py` and adding the evals `StrEnum`s remain open.

## References

- `.specify/memory/constitution.md` (2.0.1 Sync Impact Report)
- [[2026-10-04-constitutional-articles-xi-xv]]
