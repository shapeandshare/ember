---
title: "Article V redefined: Model Loading replaces Reproducibility by Pinning"
type: decision
tags:
  - type/decision
  - domain/models
  - domain/runtime
  - domain/server
  - domain/cli
  - domain/governance
  - status/draft
created: "2026-10-08"
updated: "2026-10-08"
code-refs:
  - ember/models.py
  - ember/serving/runtime.py
  - ember/serving/hosted.py
  - ember/serving/server.py
  - ember/serving/process.py
  - ember/commands/doctor.py
  - shared/release.mk
---

# Article V redefined: Model Loading replaces Reproducibility by Pinning

Part of [[ember]]. Constitution Article V's mandatory `REGISTRY` SHA-256 schema/head
hash-verification requirement is removed (constitution 2.1.0 → 3.0.0, MAJOR). ember now
supports any model that fits its loader contract, not a hand-maintained allowlist of
individually pinned, hash-verified weights. `ember/serving/integrity.py` is deleted;
`ModelSpec.schema_sha256`/`head_sha256` fields are gone; `revision` is now optional
(`str | None`) — a download-targeting convenience, not a verified pin. This supersedes the
same-day [[2026-10-08-outerbounds-hosted-s3-model-location]] note's narrower "Unverified
hosted-deployment exception" (`EMBER_MODEL_S3_UNVERIFIED=1` gate), which is now redundant.

## Context

Direct maintainer direction, a few hours after the Outerbounds hosted-S3 decision above
shipped with its own narrow Article V exception (requiring `EMBER_MODEL_S3_UNVERIFIED=1`
alongside `EMBER_MODEL_S3_URI`): "we do not need pinned models as we will support any that
can run and will likely not be able to manage/pin them all." This generalizes the same
underlying reasoning the hosted-path exception already acknowledged (an operator-supplied
S3 location has no pre-computed hash to verify against) to every model path: `REGISTRY`
entries (`flash`, `full`, `anaconda-flash`, `anaconda-clef`) included, not just
`EMBER_MODEL_S3_URI`.

Flagged the scope question explicitly before implementing, since this reverses meaningful
parts of the same day's earlier work (the hosted-only exception, several hash-mismatch
"safety feature" tests) rather than extending it — confirmed via direct questions:

- Scope: broader relaxation across `REGISTRY`, not just the hosted path.
- `ModelSpec.schema_sha256`/`head_sha256`: removed entirely (not made optional).
- `revision`: kept, made optional — it has a distinct, non-security purpose
  (`huggingface_hub.snapshot_download(revision=...)` download targeting), separate from
  hash verification, and remains useful for the still-tested `flash`/`full`/`anaconda-*`
  entries.
- `verify_model_dir`: removed entirely, not reduced to a structural-files-only check — per
  explicit direction, no verification of any kind remains before
  `joint_schema_model.py` is imported and executed.
- Existing tests asserting hash-mismatch/tamper-detection as a safety property: updated to
  match the new policy, not preserved as conditional/dead-code-adjacent tests.

## Decision

- **Article V retitled "Model Loading"** (was "Reproducibility by Pinning"). The mandatory
  pinning/hash-verification sentence is replaced with: ember supports any model that can run
  under its loader contract; `REGISTRY` is a directory for discoverability, not a security
  gate. Dependency-range pinning (`uv.lock`, `uv sync --locked`) is explicitly carved out as
  unchanged — this redefinition is scoped to model weights only.
- **`ember/serving/integrity.py` deleted** in full: `verify_model_dir`, `_sha256_file`,
  `_REQUIRED_FILES`. Nothing replaces it; no structural (file-presence) check remains either,
  per explicit direction to drop verification entirely rather than keep a reduced form.
- **`ember/serving/runtime.py` simplified**: `_classify_dir` (the official/custom
  classification helper `verify_model_dir` needed) is deleted entirely —
  `joint_module(model_dir)` now just imports from the directory, no `spec`/`skip_integrity`
  parameters. `load_clef`/`Engine.__init__` lost the same two parameters; `Engine.describe()`
  lost its `"integrity"` field (nothing left to report — every load is the same, not
  "verified" vs "unverified").
- **`ModelSpec` loses `schema_sha256`/`head_sha256`**; `revision: str` becomes
  `revision: str | None = None`. All four current `REGISTRY` entries keep their real,
  previously-pinned `revision` values (download-targeting convenience, unaffected) but no
  longer carry hash fields at all.
- **`ember/serving/hosted.py` simplified**: the `EMBER_MODEL_S3_UNVERIFIED` env var and its
  required-acknowledgment gate are removed. `EMBER_MODEL_S3_URI` alone is now sufficient —
  resolution still happens once at process startup (unchanged timing), still fails fast on a
  malformed URI or missing credentials, just without the extra flag. `HostedModelSource` loses
  its `skip_integrity` field (always implicitly true now, for every model, so no longer worth
  naming).
- **`ember/commands/doctor.py`/`ember/serving/server.py`/`ember/serving/process.py`**:
  dropped `skip_integrity`/"unverified" framing from docstrings and the `Engine(...)`
  construction call sites; `doctor`'s hosted-URI report line no longer says "unverified."
- **Test suite**: `tests/test_model_integrity.py` reduced from ~1220 to ~690 lines — removed
  every hash-well-formedness, pinned-hash-value, `verify_model_dir`-behavior,
  `_classify_dir`-classification, and `Engine`-spec-threading test group; kept registry-
  structure tests (`source`, `s3_bucket`/`s3_prefix`, `kind`) and the S3-download-dispatch
  tests (disk-space checks, bucket/prefix resolution, boto3 error wrapping — a separate,
  still-valid concern unrelated to hash verification). `tests/test_hosted.py` lost its
  flag-requirement tests. `tests/test_runtime_unit.py` lost its `_classify_dir` tests and
  had its pinned-revision test relaxed to `revision is None or <full SHA>` instead of a
  hard requirement.
- **`shared/release.mk`'s `spec.revision` usage is unaffected** — `flash`'s `revision` is
  still a real pinned value, so `make download` continues to target that exact commit; this
  was always a download-targeting use, never a verification one.

## Consequences

- Any future `REGISTRY` entry can omit `revision` entirely (fetches the repo's default
  branch) and never needs `schema_sha256`/`head_sha256` at all — adding a new model is pure,
  minimal data, with no hash-measurement step required before it can be used.
- `joint_schema_model.py` is imported and executed from any resolved model directory with
  zero pre-flight integrity check, for every source (`HUGGING_FACE`, `ANACONDA_S3`,
  `EMBER_MODEL_S3_URI`) — a real, accepted security posture change: ember trusts the
  configured location, full stop, for all model loading, not just the hosted-URI path.
  Operators providing their own `EMBER_MODEL_S3_URI`/`EMBER_ANACONDA_S3_*` credentials are
  responsible for trusting those locations themselves.
- `ember doctor`/`GET /health` no longer report an `"integrity"` field at all — there is
  nothing left to distinguish ("verified" vs "unverified" is no longer a meaningful
  distinction when nothing is ever verified).
- The two same-day constitution amendments (2.0.3 → 2.1.0 → 3.0.0) are both kept in the
  Sync Impact Report history for an honest record, even though 2.1.0's "Unverified
  hosted-deployment exception" paragraph is now fully removed from Article V's live text —
  this is why the governance log shows two Article V changes in one day rather than one.
