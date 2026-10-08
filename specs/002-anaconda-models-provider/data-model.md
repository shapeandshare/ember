# Phase 1 Data Model: Anaconda Models as a First-Class Preferred Provider

**Feature**: `002-anaconda-models-provider`
**Date**: 2026-10-07
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

This feature extends one existing value object (`ModelSpec`) with a new field (`source`) and
a new supporting enum (`ModelSource`), plus new *instances* in `REGISTRY`. It reuses the
remote-endpoint entities already defined in
`specs/001-remote-inference-servers/data-model.md` unchanged.

## Entity: `ModelSource` (new, `ember/models.py`)

A `StrEnum` per constitution Article X §10.7 ("a value drawn from a fixed, known set is an
Enum, not a bare string constant"), distinguishing where a registry entry's weights are
downloaded from:

| Member | Value | Meaning |
|--------|-------|---------|
| `HUGGING_FACE` | `"hugging_face"` | Downloaded via `huggingface_hub.snapshot_download` against a public HF Hub repo (existing `flash`/`full` behavior, unchanged) |
| `ANACONDA_S3` | `"anaconda_s3"` | Downloaded directly from a plain AWS S3 bucket (bucket, prefix, credentials) made available when ember runs on Anaconda's hosted platform, per research R3-addendum-3 |

## Entity: `ModelSpec` (existing, `ember/models.py`, extended)

**Contract note**: ember will support Clef and Clef-Flash initially, with "many others to
follow" (user direction, 2026-10-07) — both from Cloudflare's public Hugging Face repos and
from a plain AWS S3 bucket made available when ember runs on Anaconda's hosted platform
(research R3-addendum-3). The object-key *prefix* is part of `ModelSpec` itself, not shared
global config, since each entry's files live at their own path — the same way `repo` already
names each Hugging-Face-sourced entry's own location. The *bucket* is usually shared across
every `ANACONDA_S3` entry in a given deployment (one hosted bucket holding every model), so
it is resolved from shared config by default, with a per-entry `ModelSpec.s3_bucket`
override available for the rare case a specific entry's files live elsewhere. Only the S3
*connection* details (credentials, region) are always shared, global config.

Three new fields (`source`, `s3_bucket`, `s3_prefix`), all defaulted so existing `flash`/`full`
entries need no change beyond adding the defaults:

| Field | Type | Anaconda entry value | Existing entries (`flash`/`full`) |
|-------|------|----------------------|-------------------------------------|
| `name` | `str` | `"anaconda-flash"` / `"anaconda-clef"` | unchanged |
| `repo` | `str` | A descriptive identifier (e.g. `"anaconda-clef-flash"`), not a Hugging Face repo id — unused as a download argument for `ANACONDA_S3` entries (see `s3_bucket`/`s3_prefix`) | unchanged |
| `dir_name` | `str` | `"anaconda-clef-flash"` / `"anaconda-clef"` | unchanged |
| `params` | `str` | `"9B"` / `"27B"` (identical models to `flash`/`full`) | unchanged |
| `approx_bytes` | `int` | `18 * 2**30` / `55 * 2**30` (identical weights to `flash`/`full`) | unchanged |
| `revision` | `str \| None` | Same commit as the matching `flash`/`full` entry — identical upstream artifact, per research R1 (download-targeting only; not verified — constitution Article V, "Model Loading") | unchanged |
| `kind` | `str` | `"decision"` (unchanged category) | unchanged |
| `source` | `ModelSource` (new field) | `ModelSource.ANACONDA_S3` (explicit) | `ModelSource.HUGGING_FACE` (default; existing call sites unaffected) |
| `s3_bucket` | `str \| None` (new field) | `None` on both current entries — the bucket is resolved from the shared `anaconda_s3_bucket` config instead (see below); set per-entry only when a specific entry's files genuinely live in a different bucket | `None` (unused for `HUGGING_FACE` entries) |
| `s3_prefix` | `str \| None` (new field) | The object-key prefix within the bucket (`"clef-flash"`, `"clef"`) — **per entry**, and still an **unverified placeholder**: the exact object-key layout within the hosted bucket has not yet been confirmed end-to-end (research R3-addendum-2/R3-addendum-3) | `None` (unused for `HUGGING_FACE` entries) |

**Validation rules** (unchanged from existing `ModelSpec` usage, plus three new rules):
`get()` looks up by key case-insensitively; `REGISTRY` membership is the sole validity check.
ember does not verify downloaded weights against a hash before importing/executing code from
the directory (constitution Article V, "Model Loading" — `ember/serving/integrity.py` is
deleted; a `REGISTRY` entry is a directory of known-good sources for discoverability, not a
security gate). New rules: (1) `pull()`/`resolve_dir()`/`remove()` in `ember/models.py`
dispatch on
`spec.source` to select the download mechanism (`huggingface_hub.snapshot_download` for
`HUGGING_FACE`, direct `boto3` AWS S3 access via `ember/cfg/anaconda_s3.py` for
`ANACONDA_S3`); (2) `anaconda_s3.download()` resolves the bucket as `spec.s3_bucket` if set,
else the shared `anaconda_s3_bucket` config value, and raises a clear `RuntimeError` naming
the registry entry if neither yields a bucket or if `s3_prefix` is unset; (3) any
`botocore.exceptions.ClientError`/`BotoCoreError` raised during the S3 listing or download,
and any `ValueError` raised by `boto3.client()` construction itself, MUST be caught and
re-raised as `RuntimeError` (chained via `from exc`) — `ember/cli.py`'s top-level handler only
prints a clean `error: ...` message for `RuntimeError`/`KeyError`; an uncaught `ClientError`
would otherwise surface as a raw traceback, breaking the FR-009 clarity requirement (found and
fixed during critical review, research R5).

**Relationships**: Unchanged beyond the dispatch above. A `ModelSpec` is resolved by
`resolve_dir()`/`pull()`/`remove()` in `ember/models.py` and passed into `Engine`/`load_clef`
in `ember/serving/runtime.py` exactly as any existing entry is — `runtime.py` itself is
unmodified (research R2); the S3 download logic lives in `ember/cfg/anaconda_s3.py`, split out
of `ember/models.py` to stay under the Article X §10.3 sizing ceiling.

## AWS S3 connection configuration (new config keys, `ember/cfg/config.py`)

Per research R3-addendum-3, a plain AWS S3 bucket is made available when ember runs on
Anaconda's hosted platform; access needs connection details supplied explicitly (never
auto-detected). The *prefix* (`s3_prefix`) is always per-entry on `ModelSpec` above, since
each model's files live at their own path; the *bucket* usually isn't — one hosted bucket
holds every model's files, so `anaconda_s3_bucket` is a shared config fallback, with a
per-entry `ModelSpec.s3_bucket` override available for the rare exception:

| Key | Env var | Default | Meaning |
|-----|---------|---------|---------|
| `anaconda_s3_access_key_id` | `EMBER_ANACONDA_S3_ACCESS_KEY_ID` | `None` | Access key ID (secret), shared — never defaulted |
| `anaconda_s3_secret_access_key` | `EMBER_ANACONDA_S3_SECRET_ACCESS_KEY` | `None` | Secret access key (secret), shared — never defaulted |
| `anaconda_s3_region` | `EMBER_ANACONDA_S3_REGION` | `None` | AWS region passed to the S3 client |
| `anaconda_s3_bucket` | `EMBER_ANACONDA_S3_BUCKET` | `None` | Shared bucket name used when a `REGISTRY` entry's own `s3_bucket` is unset (the common case) |

No custom `endpoint_url` config exists — `boto3.client("s3", ...)` is constructed with no
endpoint override, targeting standard AWS S3 (research R3-addendum-3 superseded the earlier
Cloudflare R2/Anaconda-internal-catalog framing from R3-addendum/R3-addendum-2).

These follow the same `config.resolve()` flag > env > config-file > default precedence
already used throughout `ember/cfg/config.py`, consistent with Article XIII §13.5. The two
credential keys are secrets and MUST be masked in `ember config show` output the same way
`auth_token`/`server_auth_token` already are (existing pattern from
`specs/001-remote-inference-servers/`), and MUST NOT be logged.

## Entity: `DEFAULT` (existing, `ember/models.py`)

No schema change. The module-level constant changes value from `"flash"` to `"anaconda-flash"`
(the new registry key). No new selection mechanism, precedence rule, or configuration key is
introduced (research R4; the user explicitly declined to specify a selection mechanism for a
hypothetical future multi-Anaconda-entry case during `/speckit.clarify`).

## Entities inherited unchanged from `specs/001-remote-inference-servers/`

The following entities, already shipped, are reused without modification for User Story 3
(Anaconda-hosted models) per research R5 — no new fields, no new config keys:

- **Inference Endpoint** (`ember/cfg/endpoint.py` `Endpoint`) — `url`, `host`, `scheme`,
  `is_local`, `allow_insecure_transport`, `request_timeout`. An Anaconda-hosted endpoint is
  simply a non-loopback `Endpoint` instance like any other remote server.
- **Endpoint credentials** (`auth_token`, `auth_header` config keys) — a user's Anaconda-issued
  credential is carried exactly like any other configured credential.
- **Remote-serving configuration** (`server_auth_token`, HTTP-layer `Depends` guard) — governs
  the *server* side only; irrelevant to ember acting as a client against an Anaconda-operated
  endpoint.

## No new provider-abstraction entities

`ModelSource` is a two-member enum selecting a *download mechanism*, not a "Provider" or
"Vendor" entity, a plugin registry, or any multi-tenancy/selection construct beyond the
existing `REGISTRY`/`DEFAULT` pair — consistent with the spec's Clarification 2 ("no new
provider-abstraction layer"). It exists only because constitution Article X §10.7 requires
any value drawn from a fixed, known set to be an enum rather than a bare string, now that a
second, genuinely different download mechanism is a concrete requirement (research
R3-addendum) — this is the minimal compliant encoding of that fact, not a generalized
provider framework. Per-entry `s3_prefix` on `ModelSpec`, with a shared `anaconda_s3_bucket`
config fallback for the bucket, is the same pattern `repo`/`revision` already establish (each
entry is self-describing data, sharing only genuine cross-entry connection facts); it is not
a new abstraction layer, it is the existing `ModelSpec` contract extended with two more plain
fields.

## Initial Anaconda registry scope

Per the user's explicit direction (2026-10-07): "we will initially support clef, and
clef-flash, and there will be many others to follow, the contract is most important." Both
sizes get an Anaconda-hosted equivalent at launch:

| Registry key | Mirrors | Params | `s3_prefix` (illustrative, not yet verified against the live bucket) |
|---|---|---|---|
| `anaconda-flash` | `flash` | 9B | `"clef-flash"` |
| `anaconda-clef` | `full` | 27B | `"clef"` |

Both entries' `s3_bucket` is `None` — the bucket is resolved from the shared
`anaconda_s3_bucket` config at pull time (research R3-addendum-3), not pinned here. Adding a
future third Anaconda entry (or a genuinely new model family) means adding one more
`ModelSpec` to `REGISTRY` with its own `s3_prefix` (and `s3_bucket` only if it genuinely lives
elsewhere) — no code change to the download dispatch, the config schema, or the CLI. This is
the concrete test of "the contract is most important": a new entry is pure data.
