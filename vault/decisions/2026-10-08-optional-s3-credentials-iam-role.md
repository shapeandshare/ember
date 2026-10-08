---
title: "AWS S3 credentials made optional: support IAM-role-based auth (no static keys)"
type: decision
tags:
  - type/decision
  - domain/models
  - domain/cli
code-refs:
  - ember/cfg/anaconda_s3.py
  - ember/cfg/config.py
  - tests/test_model_integrity.py
created: "2026-10-08"
updated: "2026-10-08"
status: draft
---

# AWS S3 credentials made optional: support IAM-role-based auth (no static keys)

Part of [[ember]]. `ember/cfg/anaconda_s3.py::s3_client()` no longer requires
`EMBER_ANACONDA_S3_ACCESS_KEY_ID`/`_SECRET_ACCESS_KEY` to be set. When unset, no credential
kwargs are passed to `boto3.client("s3", ...)` at all, and boto3's own default credential
chain applies — the expected case for a hosted deployment with an IAM role attached to the
compute (e.g. an Outerbounds execution environment), matching `../model-foundry`'s own
Metaflow-managed S3 access pattern (`METAFLOW_DATASTORE_SYSROOT_S3` + Metaflow's own
credential handling, not static keys baked into deployment config).

## Context

Direct maintainer statement: "our deployment will operate much like the model foundry, i
have s3 pathing, but i dont think i need to provide s3 creds." Checked `../model-foundry`'s
actual deployment pattern (`deployment/deploy.dev.yaml`): its R2 access (`src/api/storage/
_base.py`) does use explicit static keys, but those are injected by a CI/Vault pipeline, not
typed by a developer — a different mechanism from what the maintainer is describing.
Deployment-time credentials for Metaflow's own S3 Datastore
(`METAFLOW_DATASTORE_SYSROOT_S3`) are handled separately and don't require explicit
`aws_access_key_id`/`aws_secret_access_key` in the app's own code — consistent with an
IAM-role-based execution environment, where `boto3`'s default credential chain (environment
→ shared config files → instance/container metadata service) resolves credentials
automatically with zero explicit configuration.

ember's `s3_client()` previously raised `RuntimeError: Anaconda-hosted S3 access is not
configured` immediately whenever `EMBER_ANACONDA_S3_ACCESS_KEY_ID`/`_SECRET_ACCESS_KEY` were
unset — this would have broken exactly the IAM-role deployment model described, since ember
would refuse to even attempt the S3 call.

## Decision

- `s3_client()` passes `aws_access_key_id`/`aws_secret_access_key` explicitly only when
  **both** are configured; otherwise it constructs `boto3.client("s3", region_name=...)`
  with no credential kwargs, letting boto3 resolve credentials itself.
- A partially-configured pair (only one of the two keys set) is treated as fully
  unconfigured — falls back to the default chain rather than passing a half-explicit,
  confusing combination to boto3.
- `region_name` is passed unconditionally (even as `None`) since `None` is itself a valid,
  meaningful value to boto3 (falls back to its own region resolution — environment, config
  file, or an S3-specific default).
- No change to `EMBER_MODEL_S3_URI`'s own behavior (`ember/serving/hosted.py`) — it already
  calls through `anaconda_s3.s3_client()`/`download_prefix()`, so it inherits the same
  optional-credentials behavior automatically with no separate change needed.
- Documentation (README.md, COMPATIBILITY.md, `specs/002-anaconda-models-provider/
  quickstart.md`, `ember/cfg/config.py`'s inline comment) updated to describe credentials as
  optional, naming the IAM-role case as the expected default for a hosted deployment rather
  than an edge case.

## Consequences

- An Outerbounds (or any IAM-role-attached) deployment sets only `EMBER_MODEL_S3_URI` (or
  pulls an `anaconda-*` REGISTRY entry) and gets working S3 access with zero credential
  configuration — matching the "I have S3 pathing, I don't think I need to provide S3 creds"
  expectation directly.
- A local developer machine (no attached role) still works exactly as before by setting
  `EMBER_ANACONDA_S3_ACCESS_KEY_ID`/`_SECRET_ACCESS_KEY` explicitly.
- If neither an attached role nor explicit credentials exist, the failure now surfaces later
  and from boto3 itself (e.g. `NoCredentialsError`, already wrapped as `RuntimeError` by the
  existing `ClientError`/`BotoCoreError` handling in `download_prefix()`) rather than
  immediately and explicitly from ember's own pre-check. This is an acceptable trade-off: the
  error is still a clean, actionable `RuntimeError` via the existing wrapping, just raised
  slightly later in the call chain (at the actual S3 request) instead of at client
  construction.
