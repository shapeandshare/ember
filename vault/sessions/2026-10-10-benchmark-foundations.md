---
title: "Benchmark foundations: Phase 0 of the benchmark categories programme"
type: session-log
tags:
  - type/session-log
  - domain/tooling
  - domain/server
  - domain/governance
created: "2026-10-10"
updated: "2026-10-10"
---

# Benchmark foundations: Phase 0 of the benchmark categories programme

Part of [[ember]]. This session ran the spec-kit pipeline for `specs/004-benchmark-categories/`
(specify, clarify, plan, tasks, analyze) and then implemented all 93 tasks of Phase 0,
"Foundations": the dataset, run, report, and leaderboard plumbing every later benchmark
phase builds on.

## What happened

- **Spec and plan.** The benchmark categories programme was written as a delivery series
  (Phase 0 here; Phases 1–12 get their own specs) after the maintainer asked for an
  exhaustive benchmark that stays practical for a single maintainer, draws on freely usable
  external data where licences allow, and tracks provenance for everything. Clarifications
  fixed two hashes (content and file), pinned splits, mirrors outside the repo, the
  reviewed choice as gold, and resumable runs with per-recipe leaderboard assembly.
- **Dataset tooling** (`evals/dataset/`): one Pydantic record per file; a structured
  `source` with seven kinds (`authored`, `mined`, `captured`, `perturbed`, `templated`,
  `drafted`, `imported`); the content hash as the dataset version
  (`1e1bb88d47f0…`, unchanged by the source migration) plus per-recipe hashes and the
  register hash; `splits.lock` (append-only, deterministic `assign_new`); lint with one
  enforced rule (`no-live-secret`, vendor-documented examples in `example_secrets.json`);
  the data card; the provenance check; the tier tool; `ember eval dataset
  {lint,card,hash,check,tier}`.
- **Data-source register** (`register.json`, 105 rows: 38 excluded, 26 conditional, 23
  candidate, 18 unconfirmed; none `used` yet) and `scripts/audit_data_sources.py`
  (`make audit-sources`).
- **Server API.** `usage` now carries `state_tokens`/`fixed_tokens`/`media_tokens`
  alongside `input_tokens`; the harness requires the split (`MIN_SERVER_VERSION = "0.12.0"`).
  `AdmissionError` and `RequestTooLargeError` moved out of `runtime.py` to keep it under
  400 lines.
- **Harness.** Run manifests, `ember eval run --resume`, per-row `tokens` and annotations,
  hashes and `settings` in `results.json`; `ember eval snapshot --rebuild` re-renders a
  bundle from its trace. `evals/eval/client.py` and `evals/eval/resume.py` were split out.
- **Report.** Scales definitions and legends; a coding-only headline with a capability panel
  for vision; dangerous-option recall (`risk_metrics.py`); token, consistency,
  by-source-kind, and tier blocks (`metrics_phase0.py`, `sections_phase0.py`,
  `charts_tokens.py`). `analysis.py` (826 lines) became `analysis.py` (300) plus
  `analysis_design/findings/policies/calibration.py`; `metrics.py`, `report_text.py`,
  `sections_results.py`, and `run_evals.py` were split under the ceiling too.
- **Leaderboard and site.** `evals/leaderboard.py` groups runs by dataset version, one row
  per model, deployment, and settings, and assembles each recipe column from the latest run
  that scored it at the version's recipe hash; a row has a headline only when every coding
  recipe is scored. `scripts/build_site_benchmark.py` renders one table per version, links
  recipe cells to their producing runs, and the landing headline names its scope and the
  capability panel.
- **Bundles rebuilt.** `Cloudflare__clef-flash_20261010T192756Z`: headline 0.8268 → 0.8200
  (843 → 811 coding questions), capability 1.000 over 32. `clef-flash_20261003T203810Z`:
  0.8443 → 0.8325 (456 → 424); it scored the earlier 264-item dataset, so it is its own
  version (`913e1b65…`). Per-recipe and per-question figures were unchanged.
- **Governance.** Constitution 3.2.0 → 3.2.1: five §10.18 size-debt entries resolved
  (`analysis.py` had grown 793 → 826 unrecorded; `run_evals.py` was at 416 unrecorded), and
  the coverage floor ratcheted 81% → 94% (measured 94.50%). `make typecheck` now runs mypy
  over the `files` list (ember, `evals/dataset`, `evals/risk_metrics.py`), not `ember` alone.
  `release-ember.yml` writes `Benchmark dataset: <content hash>` into each release's
  changelog section (and so its notes). README, AGENTS.md, COMPATIBILITY.md updated.
- **Validation.** `make pr-ready` green; `make test` 1075 passed, 1 skipped (model-backed);
  `make test-cov` 94.50%; `uvx zizmor .github/` clean. Quickstart steps 1–9 ran end to end
  with a live server: the token split summed on the wire; a `--category routing` run was
  interrupted after 37 items and resumed to 75 items, each exactly once, with `resumed:
  true`; the snapshot produced an incomplete local-MPS row (headline `—`, four unscored
  recipes named) and the tier tool tagged 353 of 475 items easy in a scratch copy without
  changing the content hash. The scratch bundle was removed afterwards.
- **Bugs found by the quickstart.** A bare `ember eval run --resume RUN_ID` refused its own
  run (`category: manifest 'routing', requested None`); the resume now inherits the
  manifest's split and category, and an explicitly different filter still mismatches. A
  pre-existing crash in the coverage figure on runs with no `noul` questions
  (`min() iterable argument is empty`) was guarded.

## Decisions and discoveries written back

- [[2026-10-10-benchmark-foundations-token-split-and-registries]]

- **Convergence pass** (`/speckit.converge`, then "address all fully"): the generated
  dataset card is now rendered per recipe in the report's design section; protocol rules
  (`evals/dataset/protocol.py`) and scale rubric anchors carry `since`, the dataset version
  they first apply to, recorded in the append-only `evals/dataset/versions.lock` that
  `ember eval dataset card` appends to and `ember eval dataset check` verifies (FR-046); the
  Limitations bullet reads "Single rater"; the report states the policy text in force; an
  empty non-easy subset is stated rather than tabulated; enum members replace value-string
  comparisons; `tests/test_run_evals.py` split into `test_run_evals.py` and
  `test_run_evals_phase0.py`; `write_atomic`/`copy_atomic` moved to the leaf `evals/atomic.py`
  to break the `export → analysis → dataset → export` import cycle. Both bundles rebuilt
  again (per-recipe figures unchanged).
- **Second convergence pass**: three test modules over the 400-line ceiling were split by
  responsibility (`test_dataset_hashes.py`, `test_site_leaderboard.py`,
  `test_leaderboard_versions.py`); every new or touched module is now under 400 lines.
- **Critical review pass** ("double check, review critically"): `ember eval report
  --compare` compared runs by *file* hash, so an annotation-only edit between two runs
  (a tier tag, a rationale) would have warned "different item sets" while two genuinely
  different versions with the same file would not; it now compares the content hash and
  falls back to the file hash for pre-Phase-0 runs (`evals/eval/report_compare.py`, split
  out of `report_evals.py`, which also names the dataset *version* in its header). The
  leaderboard's dangerous-recall cell now says "(not met)" plainly (FR-006); the version
  heading counts "coding items" rather than implying the whole dataset; the headline note
  states that vision items counted toward earlier headlines (FR-012); the card computes the
  `acted_differs` share of captured items instead of hard-coding `None` (FR-033); an
  assembled row takes its latency and recipe hashes from the newest *contributing* run;
  dead code (`report_text.PROTOCOL`, `run_evals.ANNOTATIONS`, an unused lint parameter)
  removed. A new test pins that the harness (raw records) and the card/CLI (`Item`s) hash
  identically, which the leaderboard's version grouping depends on.

## Follow-ups

- Phase 1 of the programme (its own spec): controlled runs per version, tier tagging proper,
  the first `used` register rows, and the risk recipe's dangerous options so the
  `risk` block stops reporting empty.
- Re-measure the agent kit's thresholds once Phase 1's larger recipes land.
