---
title: "Outerbounds hosted deployment: operator-supplied S3 model location, Article V amended"
type: decision
tags:
  - type/decision
  - domain/models
  - domain/runtime
  - domain/server
  - domain/cli
  - domain/governance
  - status/stale
created: "2026-10-08"
updated: "2026-10-08"
code-refs:
  - ember/serving/hosted.py
  - ember/serving/runtime.py
  - ember/serving/server.py
  - ember/serving/process.py
  - ember/commands/doctor.py
  - ember/cfg/anaconda_s3.py
  - ember/cfg/paths.py
---

# Outerbounds hosted deployment: operator-supplied S3 model location, Article V amended

> **SUPERSEDED same day (2026-10-08) by [[2026-10-08-article-v-redefined-model-loading]].**
> This note's `EMBER_MODEL_S3_UNVERIFIED=1` acknowledgment-gate design was removed a few
> hours later when the maintainer generalized the reasoning: "we do not need pinned models
> as we will support any that can run and will likely not be able to manage/pin them all."
> Article V was redefined again (2.1.0 → 3.0.0, MAJOR this time) to drop the hash-
> verification requirement for every model path, not just the hosted-S3 one — making the
> acknowledgment flag redundant (there is no longer a verified default for it to be an
> exception to). `EMBER_MODEL_S3_URI` still works exactly as described below; only the
> now-removed `EMBER_MODEL_S3_UNVERIFIED` env var and the "narrow exception" framing are
> stale. Kept below, unedited, for an honest record of the first (now-superseded) design —
> see the linked note for what actually shipped.

Part of [[ember]]. When ember runs as an Outerbounds-deployed app, the platform supplies the
model's location as a single `s3://bucket/prefix` URI at start time (`EMBER_MODEL_S3_URI`),
not a `REGISTRY` key — matching `model-foundry`'s own S3-URI deployment convention. Because a
URI-only location has no pinned revision/hash to verify in advance, constitution Article V was
amended (2.0.3 → 2.1.0, MINOR) with a narrow, explicit "Unverified hosted-deployment
exception": the URI alone is never sufficient — `EMBER_MODEL_S3_UNVERIFIED=1` must also be set,
or ember fails fast at startup.

## Context

Direct maintainer requirement: "we will run as an outerbounds deployment when running hosted
we will start we provide the s3 location of the model to load." Investigated
`../model-foundry` (a sibling Anaconda repo deployed the same way) for the actual convention:
`deployment/deploy.dev.yaml` is the Outerbounds app deployment contract (`outerbounds app
deploy --config-file ...`), and `src/install_config.py`'s `InstallConfig` is the pattern for
process-wide, read-once-at-startup deployment config (a frozen dataclass populated from
`os.environ` at import time, failing before `uvicorn` binds if a required value is missing).
`src/api/storage/_base.py` confirms the `s3://bucket/key` URI shape as the standard way an S3
location is referenced throughout that codebase.

This is architecturally different from `specs/002-anaconda-models-provider/`'s existing
`ANACONDA_S3` registry-entry design (per-entry `s3_prefix` + a shared `anaconda_s3_bucket`
config fallback, both still requiring a matching `REGISTRY` key with pinned
`schema_sha256`/`head_sha256`): an Outerbounds-supplied URI names an arbitrary location with
no `REGISTRY` entry at all, so there is nothing to look up a pinned hash against. Loading it
unconditionally would violate constitution Article V's "Model weights MUST be pinned... in
REGISTRY" as written, and `ember/serving/runtime.py::joint_module()` would import and execute
`joint_schema_model.py` from that directory with zero integrity check — a real security
regression (arbitrary code execution from whatever is at the configured S3 path), not just a
reproducibility one.

Flagged this conflict explicitly rather than silently implementing a bypass. Per Governance
("principle changes are human-approved amendments"), asked for and received explicit direction
to amend Article V with a narrow, visible, opt-in exception rather than reinterpret or weaken
the existing rule for every other path.

## Decision

- **Constitution Article V amended** (2.0.3 → 2.1.0, MINOR — a new exception added, the core
  rule unchanged for every other path): `EMBER_MODEL_S3_URI` MAY name an S3 location to load
  without a `REGISTRY` entry or hash verification, but ONLY when `EMBER_MODEL_S3_UNVERIFIED=1`
  is also set. The URI alone MUST fail fast at startup, never silently fall back to a pinned
  entry or silently skip verification.
- **New module `ember/serving/hosted.py`**: `resolve()` is the single entry point, read once
  at process startup (not lazily per `config.resolve()` call, matching `model-foundry`'s
  `InstallConfig` timing) — returns `None` when `EMBER_MODEL_S3_URI` is unset (zero side
  effects on the normal path), raises `RuntimeError` for the missing-acknowledgment/malformed-
  URI cases, or returns a `HostedModelSource(uri, model_dir, skip_integrity=True)` once
  downloaded (or already cached).
- **`skip_integrity: bool = False` threaded through `joint_module()`/`load_clef()`/
  `Engine.__init__()`** (`ember/serving/runtime.py`) — when `True`, `verify_model_dir()` is not
  called at all. Defaults to `False` everywhere else; no other call site sets it.
- **`Engine.describe()` gained `"integrity": "unverified"|"verified"`**, surfaced automatically
  through `GET /health`'s existing `engine` field — never indistinguishable from a normal
  pinned load, per the amendment's explicit visibility requirement.
- **`ember/commands/doctor.py::_doctor_check_models()` checks `hosted.resolve()` first**: when
  active, reports `model <uri>: unverified (EMBER_MODEL_S3_URI, constitution Article V
  exception): <local dir>` instead of the normal `REGISTRY`-based line.
- **`ember/serving/process.py::start()` and `ember/serving/server.py::lifespan()` both check
  `hosted.resolve()` before the normal path** — `process.start()` so a misconfigured URI fails
  fast in the parent `ember start` process before spawning a server subprocess that would
  otherwise crash during its own startup; `lifespan()` so `ember serve`/the spawned subprocess
  itself resolves correctly when launched directly (e.g. by Outerbounds' own `commands:`
  startup line, not through `ember start`).
- **Download mechanics reused, not duplicated**: `ember/cfg/anaconda_s3.py::download()` (the
  existing `ANACONDA_S3` registry-entry path) was refactored to extract a lower-level
  `download_prefix(bucket, prefix, dest, label)` primitive with no `ModelSpec` dependency;
  `hosted.resolve()` calls this directly, `download()` becomes a thin `ModelSpec`-resolving
  wrapper around it. Same credentials (`EMBER_ANACONDA_S3_ACCESS_KEY_ID`/
  `_SECRET_ACCESS_KEY`/`_REGION`) serve both paths.
- **New cache location `ember/cfg/paths.py::hosted_model_cache(uri)`**: keyed by a SHA-256
  hash of the URI (truncated to 16 hex chars) rather than a `REGISTRY` `dir_name`, since there
  is no registry entry to key by — `<cache>/ember/hosted-models/<hash>`. Idempotent: an
  unchanged URI resolves to the same local path and is not re-downloaded.

## Consequences

- `EMBER_MODEL` and the `model` config key are completely ignored when `EMBER_MODEL_S3_URI`
  is set — there is no interaction between the two paths; `EMBER_MODEL_S3_URI` is a full
  override, not an additional selector.
- Every other model-loading path (`flash`, `full`, `anaconda-flash`, `anaconda-clef`, any
  future `REGISTRY` entry) is completely unaffected — `skip_integrity` defaults to `False`
  everywhere, and `hosted.resolve()` is a pure no-op when the env var is unset.
- An operator choosing this path explicitly accepts that `joint_schema_model.py` is imported
  and executed from an unverified directory — this is a real, documented security trade-off,
  not a convenience default. Prefer a pinned `REGISTRY` entry whenever one is available.
- `ember doctor`/`GET /health` always say "unverified" when this path is active; a future
  reviewer or on-call engineer can never mistake this state for a normal, pinned, verified
  load by reading either surface.
- The `EMBER_MODEL_S3_URI`/`EMBER_MODEL_S3_UNVERIFIED` env vars are a new, narrow, Outerbounds-
  shaped addition to the existing `anaconda_s3_*` config surface from
  `specs/002-anaconda-models-provider/` — they share the same AWS S3 credentials
  (`anaconda_s3_access_key_id`/`_secret_access_key`/`_region`) but are a structurally distinct
  mechanism (startup-time URI override vs. `REGISTRY`-entry-based pull), not a replacement for
  it.
