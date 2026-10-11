# Contract: Run artifacts, resumability, and hashes

**Scope**: `evals/eval/run_evals.py`, `evals/eval/resume.py`, `evals/eval/client.py`,
`evals/eval/snapshot_evals.py`, `results/`, `benchmark/<run-id>/`.

## Files per run (`results/`, gitignored)

| File | When | Content |
| --- | --- | --- |
| `<run-id>_run.json` | before the first request | `run_id, model, deployment_label, settings{dtype,max_length,max_request_length}, dataset_sha256 (file), dataset_content_sha256 (version), recipe_sha256{}, register_sha256, split, category, started_at` |
| `<run-id>_dataset.jsonl` | start | copy of the dataset scored (unchanged) |
| `<run-id>_trace.jsonl` | appended per item (torn-line safe) | `score_item` record + `latency_ms`, `model`, `usage`, `answers`, **`tokens{total,state,fixed,media}`**, and the item annotations **`kind`, `tier`, `source_kind`, `parent_id`, `perturbation`** copied from the dataset |
| `<run-id>_results.json` | end | `config` (today's fields + `dataset_content_sha256`, `recipe_sha256`, `register_sha256`, `settings`, `policy`, `resumed`) and `summary` |

## Token split requirement

The harness reads `usage.state_tokens/fixed_tokens/media_tokens` from every `200`. If the
first response lacks them, the run stops before writing a trace row:

```text
error: the server at <label> (ember <version or "unknown">) does not return the token
split in usage; ember >= <min> is required for the benchmark.
```

No flag disables this.

## Resume

```text
ember eval run --resume <run-id> [--server ...]
```

Preconditions (all must hold, else exit 1 with the mismatch named): the manifest exists;
the live server's model, device, dtype, `max_length`, `max_request_length` equal the
manifest's; the dataset's content hash equals `dataset_content_sha256` (an annotation-only
edit since the run started is allowed; a gold or state edit is not); split and category
match. Behaviour: ids already present in the trace are skipped; new rows are appended;
`results.json` is written at the end with `resumed: true`.

## Snapshot bundle (`benchmark/<run-id>/`, tracked)

Unchanged files (`results.json` scrubbed, `trace.jsonl`, `dataset.jsonl`, `model.json`),
plus:

```text
ember eval snapshot --rebuild <run-id>
```

recomputes `results.json["summary"]` with the current `metrics.aggregate` from the bundle's
own `trace.jsonl` and `dataset.jsonl`, then rebuilds `model.json`. `config` is preserved;
`dataset_content_sha256` and `recipe_sha256` are computed from the bundle's dataset and
added when absent, `register_sha256: null` for pre-register runs. The bundle's
`dataset.jsonl` still carries string sources, so it is read through the legacy shim with
the bundle's own file `config.dataset_sha256` as the legacy `dataset_version`; trace rows
gain the item annotations (`kind`, `tier`, `source_kind`, `parent_id`, `perturbation`)
joined by id from that dataset. `model.json["meta"]` gains `dataset_content_sha256`,
`recipe_sha256`, `register_sha256`, `settings`, and `tokens_available: false` (these traces
predate the split; the report says the split is unavailable). Because the projection
excludes `source`, the rebuilt bundles' content hash equals the current dataset's, so they
sit on the current version. The privacy scrub (`_CONFIG_LOCATION_KEYS`,
`_ENGINE_LOCATION_KEYS`) is unchanged; the new config keys carry no locations.

## Gate check for Phase 0 (FR-012, SC-001)

For each committed bundle: `summary.categories` and `summary.questions` before and after
`--rebuild` are equal (rounded to four decimals as stored); `summary.overall` differs only
by the exclusion of vision recipes; `summary.capability` holds the vision figures;
`meta.dataset_content_sha256` equals `ember eval dataset hash`'s content hash of the
current dataset. The report's summary section states "Headline over coding recipes; vision
recipes in the capability panel."
