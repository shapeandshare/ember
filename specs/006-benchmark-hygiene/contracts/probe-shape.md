# Contract: Probe Shape in Leaderboard Rows (Phase 1)

Makes the long-context probe's result visible on every leaderboard row. Files:
`evals/context/records/probe_manifest.py` (+1 field), `evals/context/records/probe_shape.py`
(new), `evals/context/link.py` (new), `evals/leaderboard.py` (`_row()` + probe),
`scripts/build_site_benchmark.py` (cells). Prerequisite: a snapshotted probe run.

---

## Manifest addition

`ProbeManifest` gains:

| Field | Type | Meaning |
|-------|------|---------|
| `dataset_content_sha256` | `str` | `hashes.dataset_content_sha256(read_items(<the scored dataset>))` at probe start. The join key. |

Existing fields (`run_id`, `device`, `dtype`, `models`, `lengths`, `depths`) are unchanged. The
probe already records the `device` and `dtype` the leaderboard matches on.

## The projection

`ProbeShape` (new record) is derived from the probe summary's `ModelVerdict`:

| Field | From `ModelVerdict` | Meaning |
|-------|---------------------|---------|
| `request_cap` | `cap` | The request cap. |
| `first_drop_length` | `first_failure_length` | First-drop length. |
| `worst_depth` | `first_failure_depth` | Worst depth (`start`/`middle`/`end`). |

## Match rule

`evals/context/link.py::probe_shape(row, snapshots) -> ProbeShape | None`:

1. Read each `evals/context/runs/<run_id>/summary.json` (the canonical snapshots).
2. Keep those whose `manifest.device`, `manifest.dtype`, and
   `manifest.dataset_content_sha256` equal the row's `device`/`dtype`/`dataset_content_sha256`,
   and whose `models` include the row's model (repo + revision).
3. Take the newest match; return its `ModelVerdict` as a `ProbeShape`. Return `None` when no
   snapshot matches.

`evals/leaderboard.py::_row()` sets `probe` to that value (or `None`).

## Row and site

- The leaderboard row dict gains `probe: {request_cap, first_drop_length, worst_depth} | None`.
  The site serialises row fields verbatim into `site/_data/benchmark.json`, so no data-file change
  is needed.
- `scripts/build_site_benchmark.py` adds one table column with a cell rendering
  `cap / first-drop / worst-depth`, following the `_risk_cell`/`_recipe_cell` pattern.
- A row with `probe = None` renders **"not measured"** — never blank, never omitted (FR-012,
  SC-005).

## Prerequisite and current state

`evals/context/runs/` is empty today, so **every row shows "not measured"** until a probe is run
and snapshotted: `ember eval context --models flash` then
`ember eval context --snapshot <run_id>`. The probe is bound by the memory rule it measures, so a
tight GPU records an honest cap (a low `first_failure_length`, or `worst_depth` from an `oom`); a
row is never given a figure from a probe whose key does not match.

## Out of scope

Running the probe is not part of this contract; the join, the field, and the cells are. Recording
a measured cap into `ModelSpec.max_request_length` remains the probe's own documented follow-up.
