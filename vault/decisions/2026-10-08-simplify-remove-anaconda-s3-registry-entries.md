---
title: "Simplification: removed the ANACONDA_S3 REGISTRY-entry subsystem"
type: decision
tags:
  - type/decision
  - domain/models
  - domain/cli
  - domain/governance
code-refs:
  - ember/models.py
  - ember/cfg/s3.py
  - ember/cfg/config.py
  - ember/cfg/paths.py
  - ember/serving/hosted.py
  - tests/test_model_integrity.py
  - tests/test_s3.py
created: "2026-10-08"
updated: "2026-10-08"
status: draft
---

# Simplification: removed the ANACONDA_S3 REGISTRY-entry subsystem

Part of [[ember]]. The `ANACONDA_S3` `REGISTRY`-entry subsystem — `anaconda-flash`/
`anaconda-clef` named entries, the `ModelSource` `StrEnum`, `ModelSpec.source`/`s3_bucket`/
`s3_prefix` fields, the shared `anaconda_s3_bucket` config key, and per-entry S3 dispatch in
`pull()`/`resolve_dir()`/`remove()` — is removed entirely. `REGISTRY` now holds only
Hugging-Face-sourced entries (`flash`/`full`); `DEFAULT` reverted to `"flash"`.
`EMBER_MODEL_S3_URI` (`ember/serving/hosted.py`, shipped the same day) remains the one and
only hosted-deployment mechanism — it already bypassed `REGISTRY` entirely, so it needed no
changes. This supersedes
[[2026-10-07-anaconda-models-as-preferred-provider]] in full.

## Context

Direct maintainer pushback while reviewing `ember/models.py`'s `REGISTRY` dict: "this is like
shaving the yacht, do we actually need this level of complexity?" Clarifying questions
established the actual requirements precisely:

- "we really only need[...] to know which model to pull when using huggingface, and where
  to read it from, for hosted, we only care about the s3 location to load model from."
- The HF-sourced pair (`flash`/`full`) earns its keep — useful for local dev without AWS
  access.
- The `ModelSource` enum was confirmed as the one piece of indirection still worth keeping
  in principle, but became moot once the S3-registry-entry case it dispatched for was
  removed — there was only ever one case left (`HUGGING_FACE`), so the enum itself (and the
  whole `source`/`s3_bucket`/`s3_prefix` field set) could go.
- Explicit confirmation to remove the whole subsystem, not a narrower cut.

The root cause of the complexity: `EMBER_MODEL_S3_URI` (added earlier the same day for
Outerbounds hosted deployments) already solves "where to read the hosted model from"
completely on its own — it parses `s3://bucket/prefix` directly from the URI, with no
`REGISTRY` lookup at all. The `anaconda-flash`/`anaconda-clef` `REGISTRY` entries were a
**second**, parallel mechanism for expressing the same underlying fact (an S3 location for a
Clef model) that the URI path had already made unnecessary. This is a case of implementing
two solutions to the same problem and not retiring the first one once the second shipped.

## Decision

- **`ModelSpec`** loses `source`, `s3_bucket`, `s3_prefix`. It is now just `name`, `repo`,
  `dir_name`, `params`, `approx_bytes`, `revision`, `kind` — a plain Hugging Face Hub registry
  entry, nothing else.
- **`ModelSource` `StrEnum` deleted entirely** — with only one source left
  (`HUGGING_FACE`), a fixed-set-of-one enum has no discriminating purpose; `REGISTRY` entries
  are implicitly HF-sourced now.
- **`REGISTRY`** holds only `flash`/`full`. **`DEFAULT`** reverts to `"flash"` (from
  `"anaconda-flash"`).
- **`pull()`/`resolve_dir()`/`remove()`** in `ember/models.py` lose their `ModelSource`
  dispatch branches entirely — always the Hugging Face Hub path now. `ember/models.py`:
  352 → 247 lines.
- **`ember/cfg/s3.py`** keeps only its two generic primitives,
  `s3_client()`/`download_prefix(bucket, prefix, dest, label)` — both still used by
  `ember/serving/hosted.py` for `EMBER_MODEL_S3_URI`. The `ModelSpec`-specific `download()`
  wrapper (which resolved a bucket from `spec.s3_bucket`/the shared config) is deleted.
  189 → 125 lines.
- **`ember/cfg/config.py`** loses the `anaconda_s3_bucket` key — nothing resolves a bucket
  from config anymore; `hosted.py` already parses bucket **and** prefix directly from the
  URI itself, so this key was never actually load-bearing for the one real consumer.
  `DEFAULTS["model"]` reverts to `"flash"`.
- **`ember/cfg/paths.py`** loses `anaconda_s3_cache()` — nothing resolves a shared local cache
  by `dir_name` for an S3-sourced `REGISTRY` entry anymore (`hosted_model_cache(uri)`,
  keyed by a hash of the URI, is the only S3-related cache function left, and it predates and
  is unrelated to this removal).
- **`ember/serving/hosted.py` is completely untouched** — it already parsed bucket/prefix
  directly from `EMBER_MODEL_S3_URI` via `urllib.parse.urlparse`, never referenced
  `ModelSpec`/`ModelSource`/`anaconda_s3_bucket` at all. This confirms the two mechanisms
  were genuinely redundant, not complementary.
- **Tests**: `tests/test_model_integrity.py` rewritten from ~700 lines (almost entirely
  `ANACONDA_S3`-registry-specific) down to ~76 lines of generic registry/pull/disk-check
  tests. A new `tests/test_anaconda_s3.py` holds the `s3_client()`/`download_prefix()` unit
  tests, now decoupled from `ModelSpec` entirely (plain `(bucket, prefix, dest, label)`
  arguments). `test_cli.py`/`test_commands.py`/`test_runtime_unit.py` updated to drop
  `anaconda-flash`/`anaconda-clef` parametrization and assertions.
- **Constitution Article V** ("Model Loading") corrected (PATCH 3.0.0 → 3.0.1): its body text
  named `HUGGING_FACE`/`ANACONDA_S3` as the two model sources — corrected to describe the
  actual two paths (`REGISTRY` entries, always HF-sourced; an independent
  `EMBER_MODEL_S3_URI`). The underlying principle (any runnable model, no hash verification,
  `REGISTRY` is not a security gate) is unchanged — this is a stale-fact fix, not a
  redefinition.
- **`specs/002-anaconda-models-provider/`** marked superseded (header notes on `spec.md`/
  `plan.md`), not deleted — kept for an honest historical record of what was built and why
  it was later simplified away, per this repo's vault/spec-doc convention of correcting
  rather than erasing history.

## Consequences

- `ember model list` now shows two entries (`flash`, `full`), both Hugging-Face-sourced, no
  credentials needed for either.
- A hosted deployment still works exactly as documented in README.md's "Hosted deployment: a
  model location supplied at start time" — `EMBER_MODEL_S3_URI` + optional
  `EMBER_ANACONDA_S3_ACCESS_KEY_ID`/`_SECRET_ACCESS_KEY` (optional since
  [[2026-10-08-optional-s3-credentials-iam-role]]) — completely unaffected by this removal.
- Adding a genuinely new model in the future means either (a) a new `flash`/`full`-shaped
  `REGISTRY` entry if it's on the public Hugging Face Hub, or (b) nothing at all in
  `ember/models.py` if it's hosted-S3-supplied — just point `EMBER_MODEL_S3_URI` at it. There
  is no longer a third, named-but-S3-sourced `REGISTRY` entry shape to choose between.
- Net code removed this session: `ember/models.py` -105 lines, `ember/cfg/s3.py` -64
  lines, plus the `ModelSource` enum, three `ModelSpec` fields, one config key, and one path
  helper function. Test suite: 357 → 332 tests (net removal reflecting the real subsystem
  removal, not a coverage regression — `make pr-ready` coverage still 90%+).
