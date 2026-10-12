---
code-refs:
  - evals/dataset/
  - evals/context/
  - specs/006-benchmark-hygiene/
created: 2026-10-11
tags:
  - type/decision
  - domain/tooling
  - domain/server
  - status/draft
title: "Hygiene decisions: stability as a round record, the probe match key,
  annotation-only tags"
type: decision
updated: 2026-10-11
---
# Hygiene decisions: stability as a round record, the probe match key, annotation-only tags

Part of [[ember]]. Three design choices for Phase 1 of the benchmark programme ([[2026-10-10-benchmark-foundations-token-split-and-registries]] delivered Phase 0; `specs/006-benchmark-hygiene/` is Phase 1).

## 1. Label stability is a committed round record, not a per-item field

A stability round lives at `evals/dataset/stability/<round-id>.json`: one entry per re-labelled item (`id`, `category`, `question`, `original`, `relabel`, `agrees`, `labelled_on`). `ember eval dataset stability --emit` writes the **blinded sheet** (original labels withheld); `--ingest` validates it and writes the round; agreement is computed into the card's reserved `label_stability` key.

Rationale: the parent (`specs/004-benchmark-categories/spec.md`) requires the *publication* of label stability, and `Item` already reserves `second_review`/`second_pass` for a genuine second reviewer — reusing those for a self re-label would misrepresent them. Items stay untouched, so the content hash cannot move. A per-item boolean would also duplicate what the round record holds and lose the cooling-off/method provenance the report must state.

Alternatives rejected: a `stability` field on `Item`; writing the result straight into `card.json` with no round record (breaks "reproducible from committed evidence").

## 2. The probe joins a leaderboard row by (model, device, dtype, dataset content hash)

`ProbeManifest` gains `dataset_content_sha256`; `evals/context/link.py` matches a snapshotted probe run in `evals/context/runs/` to a row when `device`, `dtype`, and `dataset_content_sha256` are equal and the row's model (repo+revision) is in the manifest's `models`; `leaderboard._row()` exposes `probe` (`cap`/`first_failure_length`/`first_failure_depth` as `request_cap`/`first_drop_length`/`worst_depth`), or `None` rendered as "not measured".

Rationale: `ModelVerdict` already produces exactly those three figures; the only missing piece was a shared key. `deployment_key` already embeds the device and `settings_key` covers dtype, so the four-field match is precise. Matching by git hash was rejected (runs of the same model/device would miss each other); adding `deployment_label` to the probe manifest was rejected for now (FR-012 names model/device/settings, and the probe is device-level).

## 3. Kinds, tiers, anchors, and stability never move the content hash

The scoring projection is `id, category, split, state, images, videos, media_kwargs, questions, gold_labels` (`evals/dataset/hashes.py`). Everything else is an annotation: `kind`, `tier`, `source`, `rationale`, `acted*`, `second_review*`, and the new stability/round data. Only a human adjudication that changes a `gold_labels` value moves the hash — and then a new version is recorded in the append-only `versions.lock` and the item's pinned split is preserved (`splits.lock`).

Rationale: the parent's two-hash rule, already implemented and enforced (e.g. `ember eval dataset tier` refuses to write if tagging changed the hash). It is also why the stability tool can tag nothing on items and still publish.

## References

- `specs/006-benchmark-hygiene/` — spec, plan (R1/R6/R10), data-model, contracts
- `evals/dataset/hashes.py` — the projection
- `evals/context/records/model_verdict.py` — cap / first-drop / worst-depth
- `vault/decisions/2026-10-10-benchmark-foundations-token-split-and-registries.md` — Phase 0
