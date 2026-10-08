# Contract: Model Registry Entry (Anaconda)

**Feature**: `002-anaconda-models-provider`
**Scope**: The contract a new Anaconda `REGISTRY` entry in `ember/models.py` must satisfy to
be listed, pulled, selected, and removed indistinguishably from an existing Clef entry
(spec FR-001, FR-004; data-model.md `ModelSpec`).

## Contract

1. **Registration**: The entry MUST be a `ModelSpec` instance added to the `REGISTRY` dict in
   `ember/models.py`, keyed by a unique, lowercase-comparable `name` distinct from existing
   keys (`flash`, `full`).
2. **Revision (optional, download-targeting only)** (constitution Article V, "Model
   Loading"): `revision` MAY name a Hugging Face commit/branch/tag to target for
   `snapshot_download` — a convenience, not a verified pin. When set (as for every current
   entry, per research R1), it SHOULD be a concrete commit SHA rather than a floating tag or
   branch, for reproducible download targeting; `None` is also valid and fetches the repo's
   default branch. ember does not verify downloaded weights against any hash — a `REGISTRY`
   entry is a directory of known-good sources (name, download location, size) for
   discoverability, not a security gate.
3. **Listability**: `list_models()` MUST return the entry with accurate `cached`/`path`/
   `bytes` status via the existing `resolve_dir()`/`size_on_disk()` functions, unmodified.
4. **Pullability**: `pull(name)` MUST download (or return the already-present directory for)
   the entry using the same disk-space-checked flow as any Clef entry. For a
   `ModelSource.ANACONDA_S3` entry, `pull()` dispatches to a direct AWS S3 download
   (`ember/cfg/anaconda_s3.py`) using the entry's own `s3_prefix` (data-model.md — per-entry,
   not shared global config) and a bucket resolved as the entry's own `s3_bucket` if set,
   else the shared `anaconda_s3_bucket` config, plus shared connection credentials/region. An
   entry for which no bucket is resolvable, or whose `s3_prefix` is unset, MUST raise a clear,
   actionable `RuntimeError` naming the entry — never silently fall back to a different
   entry's location.
5. **Self-describing prefix, shared-bucket fallback**: each `ModelSource.ANACONDA_S3` entry
   MUST carry its own `s3_prefix` on the `ModelSpec` itself, the same way a `HUGGING_FACE`
   entry carries its own `repo`. The bucket may be shared via the `anaconda_s3_bucket` config
   (the common case — one hosted-platform bucket holds every model) or set per-entry via
   `ModelSpec.s3_bucket` when an entry's files genuinely live elsewhere. No two Anaconda
   entries may share a `s3_prefix` value — this is the contract point the "many others to
   follow" requirement turns on: adding a new entry must never require changing another
   entry's prefix or forcing every entry into one hardcoded bucket.
6. **Selectability**: The entry MUST be selectable via the existing `model` config key,
   `EMBER_MODEL` env var, and `--model`/equivalent CLI flag, through the unchanged
   `config.resolve("model")` precedence chain (flag > env > config file > `DEFAULT`).
7. **Removability**: `remove(name)` MUST delete the entry's local files (checkout `.models/`
   dir or HF/catalog cache) using the existing generic removal logic, unmodified.
8. **Loadability**: `Engine`/`load_clef`/`joint_module` in `ember/serving/runtime.py` MUST
   load the entry's local directory without any code change, per research R2 (identical
   artifact shape to existing Clef entries). No integrity verification occurs before the
   load (constitution Article V, "Model Loading").
9. **Unknown-name errors**: Attempting to pull/start/remove an unregistered name MUST produce
   the existing clear error listing valid registered names (unchanged behavior, spec FR-004
   acceptance scenario 3) — now including the new Anaconda key in that listing.
10. **Default behavior**: When no explicit model preference is configured (flag, env, config
    file all absent), `config.resolve("model")` MUST resolve to `models.DEFAULT`, which this
    feature changes from `"flash"` to the new Anaconda entry's key (spec FR-002).
11. **Explicit override wins**: A user who explicitly configures any registered model
    (Anaconda or Clef) by any of the three channels MUST get exactly that model, never the
    default, regardless of which entry is currently `DEFAULT` (spec FR-003, FR-011).
12. **Actionable failure, never a raw traceback**: any underlying exception from the AWS S3
    client (`botocore.exceptions.ClientError`/`BotoCoreError`, or a `ValueError` from client
    construction itself, e.g. an invalid region) MUST be caught and re-raised as `RuntimeError`
    (chained via `from exc`) before it can propagate past `ember/cfg/anaconda_s3.py` —
    `ember/cli.py`'s top-level handler only prints a clean `error: ...` message for
    `RuntimeError`/`KeyError` (spec FR-009; found and fixed during critical review,
    research R5).

## Out of scope for this contract

- A generic multi-vendor provider abstraction (explicitly rejected, spec Clarification 2).
- Automatic default-selection among multiple Anaconda entries (deferred, research R4) — the
  single explicit `DEFAULT` constant continues to name one entry even as more are added.
