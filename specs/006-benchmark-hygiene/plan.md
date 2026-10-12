# Implementation Plan: Benchmark Hygiene — Phase 1

**Branch**: `006-benchmark-hygiene` | **Date**: 2026-10-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-benchmark-hygiene/spec.md` — Phase 1 (Hygiene)
of the benchmark programme (`specs/004-benchmark-categories/spec.md`). Inherits the parent's
protocol, bars, shares, and gates unchanged.

## Summary

Phase 0 left slots for hygiene it did not fill. Phase 1 fills them and adds the three missing
mechanisms, grounded entirely in the code that already exists:

- **Label stability becomes real.** `Scale` has only two poles and no anchors; the card's
  per-recipe `label_stability` is hardcoded `None` and `rater_count` hardcoded `1`. Phase 1
  adds per-level **rubric anchors** to the scale registry (validated, always-enforced lint
  rule), a **stability tool** that emits a blinded re-label sheet and ingests the filled one,
  and computes agreement into the card's reserved `label_stability` field — with the existing
  single-rater disclosure (`leaderboard` rows already carry `single_rater: True`).
- **One controlled comparison is committed.** The AWS CUDA bundle for the current version
  exists; Phase 1 commits the matching **MPS** run and a build-visible gate test that a
  machine/CUDA pair shares the current dataset hash and settings-except-device. The comparison
  view already exists (`ember eval report --compare`).
- **Every item is tagged.** `Item.kind` (the `ItemKind` composition role) is schema-defined but
  unpopulated across all 475 items; the exemption mechanism
  (`RecipeSpec.exemptions: dict[ItemKind, str]`) is built but unused. Phase 1 tags kinds and
  populates exemptions where a kind is structurally absent. Tiers are already derived by
  `ember eval dataset tier` (`tier="easy"` from never-wrong-across-runs) and rendered by
  `metrics_phase0.tiers()`; Phase 1 runs it against the now-committed bundles and surfaces
  non-easy accuracy.
- **Every row carries the probe shape.** The probe's `ModelVerdict` already produces exactly
  `cap` / `first_failure_length` / `first_failure_depth`; nothing links it to a leaderboard row
  (the probe manifest lacks the dataset content hash). Phase 1 adds that key, a join in
  `leaderboard._row()`, a site cell, and "not measured" when no probe matches.
- **The capture pipeline exists.** `Source` already models `captured` with `session_id` +
  `redaction_sha256`; `Item` already carries `acted` / `acted_differs`. Phase 1 adds a converter
  from a consented, redacted session transcript to candidate items, with validation that refuses
  any session lacking a redaction record and any surviving live secret.
- **The card publishes the hygiene edition.** `card.json` already carries `kind_shares`,
  `easy_items`, `rubric_since`, and the register hash; Phase 1 fills `label_stability`, keeps
  `inter_source_agreement` null with a stated reason (no imports yet), states single-rater, and
  regenerates the committed card.

No new dependency. Nothing in `ember/` reaches the network. Kinds, tiers, and stability are
annotations: the dataset content hash is unchanged by them.

## Technical Context

**Language/Version**: Python 3.12 (uv).

**Primary Dependencies**: existing only — Pydantic v2 (`evals/dataset/records/`, `evals/context/records/`),
httpx and FastAPI (unchanged), pytest and pytest-cov. No new dependency.

**Storage**: Files — `evals/clef-flash.jsonl` (items carry `kind`, `tier` annotations),
`evals/dataset/records/` (new records one per file), `evals/dataset/scales.py` (anchors),
`evals/dataset/stability/` (new committed re-label round records), `evals/context/runs/<run_id>/`
(canonical probe snapshots — currently empty), `results/context/<run_id>/`, the tracked
`benchmark/<run>/` bundles (a new MPS bundle joins the CUDA one), `evals/dataset/card.json` +
`CARD.md`, `evals/dataset/versions.lock` (append-only).

**Testing**: pytest and pytest-cov. New unit files: `tests/test_dataset_stability.py`,
`tests/test_dataset_capture.py`, `tests/test_probe_linking.py`, `tests/test_dataset_anchors.py`,
`tests/test_benchmark_comparison.py` (the gate). Extended: `tests/test_dataset_tooling.py`,
`tests/test_dataset_lint.py`, `tests/test_dataset_card_check.py`, `tests/test_leaderboard.py`,
`tests/test_site_benchmark.py`, `tests/test_cli_eval_dataset.py`, `tests/test_context_probe.py`,
`tests/test_run_evals_phase0.py`. Model-backed: none new (the probe and harness already have
their own). The report fixtures stay in `tests/conftest.py`; no module over 400 lines grows.

**Target Platform**: the maintainer's Apple Silicon Mac (MPS) and the AWS CUDA deployment — the
two devices of the controlled comparison.

**Project Type**: Python library + CLI with a data/benchmark harness and a site renderer.

**Performance Goals**: none user-facing. The probe runs hours on MPS; the stability pass is a
one-off tool; the join is O(rows × snapshots).

**Constraints**: `evals/` follows Article X at full strictness (one class per file, Pydantic
records, enums for fixed sets, ≤ 400 lines, no new lazy imports). Tiers/kinds/stability are
annotations and MUST NOT enter the content hash (`hashes.PROJECTED`/`PROJECTED_REQUIRED`).
`no-live-secret` MUST NOT be relaxed. The card's `is_fresh()` comparison is byte-exact, so
`card.json`/`CARD.md` are regenerated in the same change.

**Scale/Scope**: 475 items (9 recipes), 3 scale entries today (`risk`, `effort`, `alert_level`),
1 dataset version recorded, 3 committed bundles (two older + the CUDA run just added).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Gate Results (pre-design)

| Article | Gate | Result |
|---------|------|--------|
| I Local or Remote, Never Silent | The stability tool, capture tool, and probe join run locally over files; only the runs themselves touch the configured endpoint; nothing in `ember/` reaches the network | ✅ PASS |
| II Typed decisions, not text | No new question types; the answer schema is unchanged | ✅ PASS |
| III Agent-legible contract | The kit is untouched (no new recipes, no threshold changes); the single-rater and stability facts are report-only | ✅ PASS |
| IV Non-interfering lifecycle | Tests use fixtures and random ports; the capture tool reads a transcript file, never a running agent; no opencode CLI in tests | ✅ PASS |
| V Model loading | Untouched; the comparison runs the same weights on two devices | ✅ PASS |
| VI Apple Silicon and CUDA | The comparison is exactly MPS vs CUDA at float16; the probe records `device`/`dtype` | ✅ PASS |
| VII Verification over assertion | Quickstart runs the stability tool, the capture converter, `dataset tier`, the probe join, and the site build for real | ✅ PASS |
| VIII Tooling | ruff, mypy strict (scope already covers `evals/dataset`), bandit, compile, tests; `no-live-secret` unchanged | ✅ PASS |
| IX Vault | A decision note for the stability-record shape and the probe-matching key lands with the implementation; `make vault-audit` | ✅ PASS |
| X Python conventions | New records one per file under `evals/dataset/records/` and `evals/context/records/`; enums for new fixed sets (stability outcome, capture refusal); Pydantic for anything crossing a file boundary; relative imports; every touched module under 400 lines | ✅ PASS |
| XI TDD and coverage | Red-green per task; tests land with code; the coverage floor 94% is unchanged or raised | ✅ PASS |
| XII Async-first | No new route and no new I/O in `ember/`; the harness and probe keep their existing sync/worker shapes | ✅ PASS |
| XIII Layers | Nothing crosses the MCP/HTTP/engine seam; `evals/` may import `ember.cfg`/`ember.models` only (as today); no torch in `evals/dataset` | ✅ PASS |
| XIV Pit of success | An untagged item reports as a named gap; a missing redaction record refuses with one message; a stale card names the fix; an unmatched row says "not measured" | ✅ PASS |
| XV Simplicity | Reuses the tier tool's `--from`/trace pattern, the `RecipeSpec.exemptions` mechanism, the card's reserved fields, `ModelVerdict`, `write_atomic`/`write_items`, and the `Scale.since` convention; no new dependency; no new abstraction beyond the three genuinely missing tools | ✅ PASS |

No violations. Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/006-benchmark-hygiene/
├── spec.md                  # Phase 1 specification (this feature)
├── plan.md                  # this file
├── research.md              # R1–R12 (Phase 0 output)
├── data-model.md            # stability record, anchors, kind/tier, probe link, capture (Phase 1)
├── quickstart.md            # validation run book
├── contracts/
│   ├── cli.md               # new `ember eval` commands and flags
│   ├── stability.md         # re-label round record + agreement, the blinded sheet
│   ├── kinds-and-tiers.md   # ItemKind tagging, exemptions, the tier tool run
│   ├── probe-shape.md       # probe manifest key + leaderboard join + site cell
│   ├── capture.md           # session transcript + redaction record → candidate items
│   └── card-and-report.md   # card hygiene edition + single-rater disclosure
├── checklists/requirements.md
└── tasks.md                 # Phase 2 (/speckit.tasks) — not created here
```

### Source Code (repository root)

```text
evals/
  dataset/
    stability.py                    # NEW: emit blinded sheet, ingest, compute agreement, publish
    capture.py                      # NEW: transcript + redaction -> candidate items (validation)
    anchors.py                      # NEW: validate per-level anchors (adjacent-distinct, length)
    records/
      stability_round.py            # NEW: one round's per-item re-label record
      stability_result.py           # NEW: computed per-recipe/label agreement
      session_transcript.py         # NEW: the capture input shape
      redaction_record.py           # NEW: session id + sha256 + method/date
      capture_outcome.py            # NEW: converted | refused + reason enum
    scales.py                       # MOD: Scale entries gain per-level anchors
    records/scale.py                # MOD: + anchors field, + validation
    lint.py                         # MOD: + scale-anchored rule (always enforced)
    card.py                         # MOD: fill label_stability, single-rater statement
    card.json / CARD.md             # MOD: regenerated (committed)
    clef-flash.jsonl                # MOD: kind + tier annotations written (content hash unchanged)
    recipes.py                      # MOD: populate exemptions where a kind is absent
  context/
    records/probe_manifest.py       # MOD: + dataset_content_sha256
    link.py                         # NEW: match a snapshotted probe to a leaderboard row
  leaderboard.py                    # MOD: _row() gains the probe block (or None)
ember/
  commands/parser.py                # MOD: `dataset stability`, `dataset kind`; top-level `capture`
  commands/eval.py                  # MOD: handlers + the dataset `modules` dispatch
  commands/parser_capture.py        # NEW (if capture is a top-level subcommand)
scripts/
  build_site_benchmark.py           # MOD: a probe column/cells in the leaderboard table
tests/
  test_dataset_stability.py         # NEW
  test_dataset_capture.py           # NEW
  test_probe_linking.py             # NEW
  test_dataset_anchors.py           # NEW
  test_benchmark_comparison.py      # NEW: the MPS/CUDA gate
benchmark/
  <new MPS run id>/                 # NEW: the MPS half of the controlled comparison (committed)
```

**Structure Decision**: everything numeric or tooling-related stays in `evals/` (which Article X
covers at full strictness); the only `ember/` change is CLI wiring (parser + handlers), which
keeps `evals/` checkout-only as today. New records follow the existing one-class-per-file
convention in `evals/dataset/records/` and `evals/context/records/`. The stability record is a
committed file under `evals/dataset/stability/` (not per-item, since a round covers many items),
so items carry no stability field — matching the parent's "publish as label stability" language
without inventing a per-item schema.

## Complexity Tracking

> No Constitution Check violations — this section is intentionally empty.

## Constitution Check — Post-Design Re-Evaluation

Re-checked after the Phase 0/1 design (research.md, data-model.md, contracts/, quickstart.md).

| Article | Result | Notes |
|---------|--------|-------|
| I | ✅ PASS | The stability, kind, tier, capture, and probe-join tools read files only; the runs use the configured endpoint; nothing in `ember/` gains a network path (R7's transcript file is the privacy boundary). |
| II | ✅ PASS | No question-type or answer-schema change; stability/tiers are reporting. |
| III | ✅ PASS | Kit untouched; the single-rater sentence is report-only. |
| IV | ✅ PASS | Capture reads a transcript, never a live store or process; tests never launch a harness CLI. |
| V | ✅ PASS | Untouched; the comparison runs identical weights on two devices. |
| VI | ✅ PASS | The comparison is MPS vs CUDA at float16; the probe keys on device+dtype. |
| VII | ✅ PASS | Quickstart steps 1–8 exercise the real commands and the site build. |
| VIII | ✅ PASS | No new dependency; ruff/mypy/bandit/compile/tests unchanged; `no-live-secret` intact. |
| IX | ✅ PASS | The stability-record and probe-key decisions land with a vault decision note; `make vault-audit` is in the run book. |
| X | ✅ PASS | New records one per file; `StrEnum` for the new fixed sets (`CaptureOutcome`, the round outcome); Pydantic for the new records; relative imports; each new module is small and none pushes a touched module past 400 lines. |
| XI | ✅ PASS | Each new tool ships with `tests/test_*.py` in the same commit; the coverage floor 94% is unchanged. |
| XII | ✅ PASS | No new route; no new I/O in `ember/`. |
| XIII | ✅ PASS | Everything lives in `evals/`; no torch; no MCP/HTTP/engine cross-import. |
| XIV | ✅ PASS | Untagged items, an unmatched probe ("not measured"), a refused capture, and a stale card each produce one actionable outcome, never a traceback. |
| XV | ✅ PASS | Reuses the tier pattern, `RecipeSpec.exemptions`, the card's reserved keys, `ModelVerdict`, `write_atomic`/`write_items`, `secret_guard`, and the site's existing cells (R12). No new package, abstraction, or configuration knob. |

