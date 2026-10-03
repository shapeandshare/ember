---
title: Eval harness for ember_advise
type: session-log
tags:
  - type/session-log
  - domain/mcp
  - domain/agent-kit
  - domain/tooling
created: 2026-10-03
updated: 2026-10-03
---

# Eval harness for ember_advise

Part of [[ember]]. Added a calibration eval suite (`tests/test_advise_evals.py`) that
exercises all five SKILL.md recipes through the real MCP stdio path, with both positive
and negative cases, runnable directly via `make test-evals`.

## What happened

1. **Explored the test harness** — read `tests/conftest.py`, `tests/test_mcp_tool.py`,
   `tests/test_http_api.py`, `ember/agent_kit/ember-advise/SKILL.md`, and
   `ember/agent_kit/instructions.md` to understand the existing patterns.

2. **Wrote `tests/test_advise_evals.py`** (822 lines, 22 tests) covering:
   - **Recipe 1 — Intent & readiness** (4 tests): vague request → implement but not
     specific; precise imperative → implement + specific; explanation → question; failing
     tests investigation → investigate. Bounds calibrated from SKILL.md observed values.
   - **Recipe 2 — Failure triage** (3 tests): connection refused → environment, no retry;
     wrong assertion → logic_bug, no retry; intermittent timeout → flaky, retry likely.
   - **Recipe 3 — Change-risk** (3 tests): trivial rename → risk ≤ 1.0/3, no review;
     auth bypass → risk ≥ 2.0/3, needs_review ≥ 0.85; score gap ≥ 1.0 between trivial
     and dangerous changes.
   - **Recipe 4 — Routing** (4 tests): DB error → storage; React hydration error → ui;
     GitHub OIDC error → infra; thin state → unclear or confidence < 0.60.
   - **Recipe 5 — Effort & approach** (3 tests): one-line fix → effort ≤ 1.0/3 +
     minimal_patch; multi-service feature → effort ≥ 2.0/3; repeated pattern extraction
     → refactor approach.
   - **Anti-patterns** (5 tests): verdict-in-state biases output (distributions differ);
     identical requests are deterministic (bit-identical answers); score separates cases
     even when confidences sit close (pins SKILL.md warning); vague requests fail the
     specificity gate (P ≤ 0.30 for 4 vague phrases); malformed choice question surfaces
     actionable ToolError with "criteria" in the message.

3. **Registered `evals` marker** in `pyproject.toml`.

4. **Added `test-evals` target** to `shared/testing.mk`:
   `make test-evals` runs `pytest -m evals -v tests/test_advise_evals.py`.

5. All 22 tests collect cleanly; file passes ruff lint and compiles.

## Decisions and discoveries written back

None requiring a separate decision or discovery note — this is purely an addition to the
test harness and does not change the agent contract, kit, or model.

## Follow-ups

- Run `make test-evals 2>&1 | tee evals.log` to measure actual observed values against
  the calibrated bounds; tighten or loosen bounds based on results.
- If any bound fails consistently, it is a signal that the model revision or question set
  has drifted — update SKILL.md observed values and the test bounds together.
- The `test_small_refactor_uses_refactor_approach` and routing tests use looser bounds
  (0.65–0.70) as they are templates, not pinned recipes — measure and tighten once
  project-specific option sets are stable.
