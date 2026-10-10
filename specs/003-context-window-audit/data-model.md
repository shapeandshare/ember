# Data Model: Context Window Audit

**Feature**: `003-context-window-audit` | **Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

## Limits

### LimitSource (`ember/serving/limit_source.py`, StrEnum)

| Member | Value | Applies to | Meaning |
|--------|-------|------------|---------|
| `MODEL` | `model` | effective maximum | Declared by the loaded model's `config.json` |
| `FALLBACK` | `fallback` | both | Effective maximum: `config.json` unreadable. Cap: model not yet measured, or outside the registry |
| `OPERATOR` | `operator` | both | Set by flag, env, or config file (includes cap `0` = disabled) |
| `MEASURED` | `measured` | cap | The registry model's probe-measured default |

### GoverningLimit (`ember/serving/governing_limit.py`, StrEnum)

| Member | Value | Meaning |
|--------|-------|---------|
| `CAP` | `cap` | The per-request cap is the enforced limit |
| `MAXIMUM` | `maximum` | The effective maximum is the enforced limit (the cap is disabled, or set above it) |

### Limits (`ember/serving/limits.py`, frozen Pydantic model)

| Field | Type | Rule |
|-------|------|------|
| `max_length` | int | ≥ 1, and never above the model's declared maximum when it is known (operator values are clamped). When the declared maximum is unknown, an operator value is used as given |
| `max_length_source` | LimitSource | `model`, `fallback`, or `operator` |
| `max_request_length` | int | ≥ 0; `0` means the cap is disabled |
| `max_request_length_source` | LimitSource | `measured`, `fallback`, or `operator`; always `operator` when the value is `0` |

| Derived | Definition |
|---------|------------|
| `enforced` | `min(max_request_length, max_length)` if `max_request_length > 0`, else `max_length` |
| `governing` | `GoverningLimit.CAP` when the cap is enabled and ≤ `max_length`, else `GoverningLimit.MAXIMUM`. Selects `{limit_name}` and `{setting}` in the refusal message |

Construction:
- `resolve(...)` is a pure function of the declared maximum, the registry cap (if any),
  and the operator values. The rules are in [contracts/config.md](./contracts/config.md).
- `from_config(model_dir, registry_key)` reads `config.resolve()` and calls `resolve`.

Callers:
- The server builds `Limits` once, in `lifespan`.
- Doctor builds it to show configured values.
- The probe builds it with the cap disabled (`0`, `operator`).

### ModelSpec addition (`ember/models.py`)

| Field | Type | Rule |
|-------|------|------|
| `max_request_length` | `int \| None` = `None` | The cap the FR-010 rule chose for this model, set from the canonical probe run. `None` until measured. When set, 2,048 ≤ value ≤ declared maximum (a test checks this) |

`registry_key(name) -> str | None` returns the registry key unless `EMBER_MODEL_DIR`
overrides the directory. Callers pass `None` for a hosted (`EMBER_MODEL_S3_URI`) model.

## Request size and refusal

### RequestSize (`ember/serving/request_size.py`, frozen dataclass, internal to the engine)

| Field | Type | Definition (research R1) |
|-------|------|--------------------------|
| `total` | int ≥ 1 | `len(encode_record(full).input_ids)` with `max_length=sys.maxsize` |
| `media` | int ≥ 0 | `total − len(no-media encode)`; `0` without media |
| `fixed` | int ≥ 1 | `len(bare encode)`: prefix, schema, and suffix, with no state and no media |
| `state` | int ≥ 0 | `len(no-media encode) − fixed` |

Invariant: `state + media + fixed == total`.

### Over-limit refusal (`RequestTooLargeError`, `ember/serving/runtime.py`)

- Raised when `size.total > limits.enforced`.
- Carries `size`, `limits`, and the declared maximum.
- Its message is `refusal_message(...)`, formatted exactly as in
  [contracts/http-api.md](./contracts/http-api.md).
- The HTTP layer maps it to 413, with `detail` set to the message.

## Reporting

### Health `engine` (plain dict from `Engine.describe()`)

Fields: `model`, `device`, `dtype`, `max_length`, `max_length_source`,
`max_request_length`, `max_request_length_source`. The last three are new
([contracts/http-api.md](./contracts/http-api.md)).

### Limit report (`ember doctor`, printed only)

| Element | Values |
|---------|--------|
| provenance | `live` (health body has limit fields); `configured` (local endpoint, no server running, values from `from_config`); `unknown` (remote unreachable, no model loaded yet, or the health body has no limit fields) |
| origin | `local server`, or the endpoint URL (live only) |
| values | `enforced`; `max_length` with its source; `max_request_length` (or `disabled`) with its source |

The line format is in [contracts/cli.md](./contracts/cli.md).

## Long-context probe records (`evals/context/records/`, one class per file)

### Depth (StrEnum)

`start` (no filler before the evidence), `middle` (filler split evenly), `end` (no filler
after).

### RowStatus (StrEnum)

`ok`; `oom` (MPS out of memory, no answers); `error` (any other exception, with its
message kept).

### FailureReason (StrEnum)

| Member | Value | Meaning |
|--------|-------|---------|
| `MEMORY` | `memory` | Peak memory over the model's budget |
| `OOM` | `oom` | MPS ran out of memory |
| `ACCURACY` | `accuracy` | Accuracy more than the tolerance below the 2K result |
| `BRIER` | `brier` | Brier score more than the tolerance above the 2K result |
| `ERROR` | `error` | An inference at that length and depth raised an error, or nothing ran there, so the cell can't be scored |

### ProbeModel (Pydantic)

`name`, `repo`, `revision`, `params`, `memory_budget_bytes` (flash 32 GiB, full 64 GiB),
`recommended_max_memory_bytes` (from `torch.mps`; informational).

### ProbeManifest (Pydantic; `manifest.json`, written before the first inference)

| Field | Type / rule |
|-------|-------------|
| `run_id` | matches `^context_\d{8}T\d{6}Z$`, or the value given by `--run-id` |
| `created_at` | ISO 8601, UTC |
| `canonical` | bool; false for `--smoke`, `--items`, or `--lengths` subsets, and for a dirty tree |
| `git_hash`, `git_dirty`, `ember_version` | from `evals/eval/provenance.py` |
| `host` | platform, chip, RAM bytes, Python, pinned package versions |
| `device`, `dtype` | `mps`, `float16` |
| `models` | `dict[str, ProbeModel]` |
| `dataset_path`, `dataset_sha256` | `evals/clef-flash.jsonl` |
| `item_ids` | the included text-only items, in run order |
| `excluded` | `dict[item_id, reason]`: media item, or unpadded size > 2,048 − 64 |
| `filler_path`, `filler_sha256`, `filler_source`, `filler_licence` | the vendored corpus |
| `lengths` | ascending ints; the first is 2048 |
| `depths` | `[start, middle, end]` |
| `length_tolerance_tokens` | 32, so `total` ∈ [L − 32, L] |
| `tolerance_accuracy`, `tolerance_brier` | 0.02, 0.02 |
| `bootstrap_resamples`, `bootstrap_level`, `seed` | 10000, 0.95, 0 |
| `exploratory_items` | 48 (stratified by category, seeded) |
| `exploratory_item_ids` | the seeded subset itself: `exploratory_items` ids drawn from `item_ids`, stratified by category. Run at lengths after the first failure |
| `pilot_projected_half_width` | float; `None` before the pilot |
| `sizing_passed` | bool; `None` before the pilot |
| `reproduces` | the run id a reproduction re-runs, or `None`; a resumed reproduction still compares against it |

### ProbeRow (Pydantic; one line of `rows-<model>.jsonl`)

| Field | Type / rule |
|-------|-------------|
| `run_id`, `model`, `item_id`, `split`, `category` | str |
| `length` | int, one of the manifest's `lengths` |
| `depth` | Depth |
| `total_tokens`, `state_tokens`, `media_tokens`, `fixed_tokens` | int; the parts sum to the total; for an `ok` row, total ∈ [L − 32, L] |
| `answers` | `dict[question_id, SystemOne answer]`; empty unless the status is `ok` |
| `latency_ms` | float |
| `rss_start_bytes`, `driver_peak_bytes`, `peak_bytes` | int; `peak = rss_start + driver_peak` |
| `status` | RowStatus |
| `exploratory` | bool; true for lengths after the first failing length |
| `error` | str or `None` |

Uniqueness key: (`model`, `item_id`, `length`, `depth`) is unique within a run. A resumed
run skips keys that already exist. The memory check's three inferences at a length are the
first item's rows for that length, so the quality pass skips them by this key.

### CellResult (Pydantic; in `summary.json`)

Fields: `model`, `length`, `depth`, `exploratory`, `n_items`, `accuracy`, `brier`, `ece`,
`delta_accuracy`, `delta_accuracy_ci` (`[lo, hi]`), `delta_brier`, `delta_brier_ci`, and
`n_errors` (inferences that raised; any error makes the cell unscorable).

Deltas are paired: the same items at the same depth, compared against the 2K cell.
Baseline cells have deltas of 0.

### LengthVerdict (Pydantic)

| Field | Type / rule |
|-------|-------------|
| `model`, `length` | str, int |
| `peak_bytes`, `budget_bytes` | int |
| `latency_ms_median` | float; the median over the length's `ok` rows, or `None` when none ran |
| `memory_ok` | bool |
| `quality_ok` | bool; `None` when skipped for memory |
| `passes` | bool |
| `reason` | `FailureReason`; `None` when the length passes |
| `failed_depth` | `Depth` for an `accuracy`, `brier`, or `error` failure; otherwise `None` |

### ModelVerdict (Pydantic)

| Field | Type / rule |
|-------|-------------|
| `model` | str |
| `cap` | int; `None` when no length passes |
| `first_failure_length` | int or `None` |
| `first_failure_reason` | `FailureReason` or `None` |
| `first_failure_depth` | `Depth` or `None` |

### ProbeSummary (Pydantic; `summary.json`)

Fields:
- `run_id`, `canonical`
- `rule`: the tolerances, budgets, and lengths, copied from the manifest
- `cells`: `list[CellResult]`
- `lengths`: `list[LengthVerdict]`
- `verdicts`: `list[ModelVerdict]`
- `inputs_sha256`: `dict[file, sha256]`

Serialization is deterministic: sorted keys, indent 2, floats rounded to 6 decimals.

## State transitions

### Probe run

1. **created**: the manifest is written.
2. **pilot**: flash runs at 2K and 16K, middle depth.
3. **gate**: if the sizing gate fails, the run is **stopped** (exit 2). Otherwise it moves
   to **running**.
4. **running**: one worker process per model works through the lengths in ascending
   order. At each length:
   - A memory check runs first (first item, three depths).
   - If that check exceeds the budget or runs out of memory, this length and every longer
     one fail on memory, and no quality cells run.
   - Otherwise the quality cells run. Before the first failing length, every item runs;
     after it, only the exploratory subset.
5. **summarized**: `summary.json` is written.
6. **snapshotted** (optional): a copy goes to the tracked `evals/context/runs/`.

`--resume` re-enters **running**.

### Limit sources

- **fallback → measured**: when the registry model's `ModelSpec.max_request_length` is
  set from a canonical run.
- **→ operator**: any flag, env, or config value.
- **operator → default tier**: removing that value.
