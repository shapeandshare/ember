---
title: "Leaderboard-style benchmark reporting across models and deployments"
type: decision
tags:
  - type/decision
  - domain/tooling
  - status/draft
created: "2026-10-10"
updated: "2026-10-10"
code-refs:
  - evals/leaderboard.py
  - scripts/build_site_benchmark.py
  - evals/analysis.py
  - evals/eval/run_evals.py
  - evals/eval/provenance.py
---

# Leaderboard-style benchmark reporting across models and deployments

Part of [[ember]]. The benchmark site moves from always rendering the single most
recently snapshotted run to a leaderboard of every tracked model and deployment, each
with its own full detail report, in anticipation of running the same benchmark against
`flash`, `full`, and other future models, across multiple deployments (local MPS, and
Outerbounds hosted CUDA, soon split into separate per-model deployments).

## Context

Running the first hosted benchmark ([[2026-10-10-eval-harness-health-probe-also-sent-no-auth-header]])
surfaced that `scripts/build_site_benchmark.py` picked exactly one "latest" tracked
`benchmark/<run-id>/` bundle and rendered only that run's 17-section report; every other
tracked run was invisible on the site. That design assumed one model on one deployment
forever. It stopped holding the moment a second model (and, soon, a second hosted
deployment split by model) needed its own comparable results, and the direct ask was to
track component versions and datetimes per run and support comparing multiple models.

## Decision

- **Leaderboard grouping key**: `(model_key, deployment_key)` in the new `evals/leaderboard.py`.
  `model_key` prefers the registry name (`meta.model_spec.name`, e.g. `"flash"`) over the
  raw recorded model string, so a local run (`clef-flash`) and a hosted/S3 run
  (`Cloudflare__clef-flash`) of the same model group together; it falls back to the raw
  string for a model outside the registry. `deployment_key` is `"{server}|{device}"` — the
  server URL alone is not enough, since different devices could in principle sit behind
  the same URL over time.
- **Latest-run-wins per group**: `leaderboard.build()` keeps only the run with the latest
  `meta.run_at` for each `(model, deployment)` pair; older runs for the same pair stay in
  `benchmark/` (nothing is deleted) but drop off the leaderboard. Every group's survivor
  still gets its own full detail report — nothing is summarized away.
- **Per-run detail pages, now namespaced**: `scripts/build_site_benchmark.py` renders
  every leaderboard row's full 17-section report under `/results/<run-id>/<anchor>/`
  (previously the single global `/results/<anchor>/`). The leaderboard index moves to
  `/results/` itself. `site/_data/benchmark.json` changes shape:
  `{"leaderboard": {"rows": [...]}, "runs": {"<run-id>": {"sections": [...], ...}},
  "headline": {...}}`; `headline` is computed from the top (highest-accuracy) row, for the
  landing page's existing "Measured, not promised" section.
- **Version provenance, so leaderboard rows are comparable**: a hosted deployment's client
  (running the benchmark) and server (running the model) can run different `ember-advise`
  versions. `evals/eval/run_evals.py::_health()` (renamed from `_engine()`) now captures
  the server's top-level `version` field from `/health` into `config.server_version`;
  `evals.analysis.build()` surfaces it as `meta.server_version`; the "System under test"
  section's "Software" fact shows both when they differ (`server X, client Y`) and one
  version when they match. `evals/eval/provenance.py::model_spec_info()` also now matches
  a hosted/S3-derived name (`<owner>__<repo>`, e.g. `Cloudflare__clef-flash`) against the
  registry's `repo` field, not only `dir_name`/`revision` — without this, every hosted run's
  `model_spec` was `{}` and the leaderboard could not group it with the matching local run.
- **No new abstraction for "deployment" as a first-class entity** (Article XV): a
  deployment is identified by `(server, device)` computed on demand, not stored as its own
  registry or config object. The two upcoming Outerbounds deployments (one per model) will
  each get a distinct `server` URL, which is sufficient to key them apart; nothing here
  needs to change when that split happens.

## Consequences

- `scripts/build_site_benchmark.py`'s `_latest_model()` (picked one bundle by directory
  name, then by `meta.run_at`) is gone; `build()` now loads every bundle and delegates
  grouping to `evals.leaderboard.build()`.
- Existing deep links to `/results/<anchor>/` (e.g. `/results/summary/`) break; nothing
  outside `site/` linked them (checked: README, index.md, nav includes all go through
  `bench_url`/`relative_url`, now pointing at `/results/`), so this is a clean cut, not a
  redirect-requiring migration.
- A run snapshotted before this change has `server_version: None` in its `model.json`
  (the field didn't exist yet) and degrades to showing only the client's `ember-advise`
  version on the leaderboard and in its report — expected, not a bug; re-running refreshes it.
- Adding a new model to `ember/models.py::REGISTRY` or a new hosted deployment needs no
  leaderboard code change: the next snapshot with a new `model_key`/`deployment_key` simply
  adds a new row.

## References

- `evals/leaderboard.py` — grouping and row-selection logic, with tests in
  `tests/test_leaderboard.py`.
- `scripts/build_site_benchmark.py` — per-run page rendering and the leaderboard index,
  with tests in `tests/test_site_benchmark.py`.
- `evals/sections/sections_front.py::_software_fact` — the client/server version display,
  with tests in `tests/test_sections_front_system.py`.
- [[2026-10-10-eval-harness-health-probe-also-sent-no-auth-header]] — the auth-header and
  `model_spec_info` fixes this decision builds on.
- [[2026-10-03-publish-a-pages-site]] — the original single-run site design this supersedes.
