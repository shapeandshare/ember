---
code-refs:
  - evals/dataset/
  - specs/006-benchmark-hygiene/
  - benchmark/
created: 2026-10-11
tags:
  - type/session-log
  - domain/tooling
  - domain/server
  - status/draft
title: "Session: benchmark-hygiene implementation (Phase 1, partial)"
type: session-log
updated: 2026-10-11
---
# Session: benchmark-hygiene implementation (Phase 1, partial)

Part of [[ember]]. Executed `/speckit.implement` on `specs/006-benchmark-hygiene/` — Phase 1 of the benchmark programme. **Both phase gates' machinery is done; the stability publication awaits the maintainer's blinded re-label.** 26 of 55 tasks landed, all committed and green.

## What shipped

- **Setup + Foundational (T001–T004)** — baseline verified, new `evals/dataset/stability/`, `evals/dataset/candidates/`, `tests/fixtures/` directories, and [[2026-10-11-hygiene-stability-records-and-probe-key]] recording the three design decisions.
- **US1 label stability (T005–T013)** — `evals/dataset/stability.py`: emit writes a **blinded sheet** (the gold level travels only as a SHA-256 commitment, so a gold change between emit and ingest is detected), ingest validates unknown/duplicate items, unfilled or out-of-range re-labels, and commitment mismatches (nothing written on refusal), compute publishes per-recipe agreement / per-label agreement / unstable ids, and the render states the single-rater rule. Three records one per file; the `ember eval dataset stability` subcommand (the `dataset` dispatch pattern); the card's reserved `label_stability` is filled and `CARD.md` carries the single-rater sentence. The first round's sheet was emitted (168 scoped items, `change_risk`/`risk` + `effort_approach`/`effort`); **ingest is pending the maintainer's cooling-off second sitting** (T012).
- **US2 controlled comparison (T014–T018)** — the MPS full run (82.0% over 811 questions, 475 items, 0 errors, float16, `Local (MPS)`) committed as `benchmark/flash_20261012T014702Z/` beside the AWS CUDA bundle on the same content hash; `tests/test_benchmark_comparison.py` is the phase gate (float16 + per-recipe hashes, settings identical, devices differ, the compare view renders, both leaderboard rows). MPS and CUDA agree metric-for-metric.
- **US3 anchors (T019–T025)** — `Scale` gains per-level anchors (non-empty entries), `evals/dataset/anchors.py` validates count/blanks/adjacent-duplicates against the question's criteria, a new always-enforced `scale-anchored` lint rule wires it in, and `risk`, `effort`, `alert_level` carry written anchors that distinguish each level.
- **Tier run (T031)** — `ember eval dataset tier` marked **353 of 475** items easy from the committed bundles; the content hash is unchanged (annotations only) and the card's `easy_items` are real.

## What remains

- **T012 (human)** — fill the emitted sheet after the cooling-off window and `--ingest`; then `ember eval dataset card` publishes the agreement. This is the last piece of the stability gate.
- **US4 remainder** — the 475-item `ItemKind` tagging (editorial) and the resulting exemptions; the `kind` audit command and lint tests.
- **US5 probe shape** — `ProbeManifest.dataset_content_sha256`, `ProbeShape`, `evals/context/link.py`, the leaderboard `probe` field, the site column; the probe snapshot itself takes hours and may land last ("not measured" until then).
- **US6 capture** — the transcript→candidate pipeline; **US7** — the card's remaining hygiene edition; **Polish** — README, the quickstart walk-through, the coverage ratchet.

## Relevance

The two-hardest design points are now settled in code and covered by tests: a stability round is a committed record keyed by a commitment (never a per-item field), and every published figure stays annotation-only — kinds, tiers, and stability never move the content hash. The controlled comparison shows MPS and CUDA agreeing exactly, so a deployment change does not change what the benchmark measures.

## References

- `specs/006-benchmark-hygiene/` — spec, plan, tasks (status per task)
- `evals/dataset/stability.py`, `evals/dataset/anchors.py` — the two new tools
- `benchmark/flash_20261012T014702Z/` (MPS) + `benchmark/17f0b0ad…_20261012T012758Z/` (CUDA) — the comparison
- Commits `a633844`…`b8912c0` — the implementation arc
