---
title: "Anaconda models as preferred provider: hosted-S3 Clef, not a new abstraction"
type: decision
tags:
  - type/decision
  - domain/models
  - domain/cli
  - domain/governance
  - status/stale
created: "2026-10-07"
updated: "2026-10-08"
code-refs:
  - ember/models.py
  - ember/cfg/config.py
  - ember/cfg/paths.py
  - ember/cfg/s3.py
  - ember/commands/config.py
  - pyproject.toml
  - tests/test_model_integrity.py
---

# Anaconda models as preferred provider: hosted-S3 Clef, not a new abstraction

> **Fully superseded (2026-10-08) by [[2026-10-08-simplify-remove-anaconda-s3-registry-entries]].**
> The entire `anaconda-flash`/`anaconda-clef` `REGISTRY`-entry design this note describes —
> including the `ModelSource` enum, `s3_bucket`/`s3_prefix` fields, and the shared
> `anaconda_s3_bucket` config key — was removed the same day, per direct maintainer pushback
> ("this is like shaving the yacht, do we actually need this level of complexity?").
> `EMBER_MODEL_S3_URI` (shipped earlier the same day) already solved the hosted-deployment
> case on its own, making this entire parallel mechanism unnecessary. `REGISTRY` now holds
> only `flash`/`full`; `DEFAULT` is `"flash"` again. (This note was also previously flagged
> as *partially* superseded by the Article V redefinition — `schema_sha256`/`head_sha256`
> removal — which is now moot since the fields those hashes lived on are gone entirely.)
> Kept below, unedited, for an honest record of the design at the time.

Part of [[ember]]. `anaconda-flash`/`anaconda-clef` — the identical Cloudflare Clef-Flash/Clef
artifacts, made available through a plain AWS S3 bucket when ember runs on Anaconda's hosted
platform — are the initial Anaconda registry entries, with `anaconda-flash` as the new default
(`DEFAULT` in `ember/models.py`); `flash`/`full` remain fully supported via explicit
selection. "Many others to follow" (user direction, 2026-10-07) drove a follow-up hardening:
each Anaconda entry names its own S3 prefix on `ModelSpec`, with the bucket resolved from a
shared config fallback (one hosted bucket holds every model), so the contract scales to
additional entries without touching shared config per-model. No new provider-abstraction
layer was built. Feature `specs/002-anaconda-models-provider/`.

> **Correction (2026-10-08, same day as initial implementation)**: the "Context" and parts of
> "Decision"/"Consequences" below describe the implementation's *first* pass, which
> hypothesized Anaconda's internal model-catalog infrastructure over Cloudflare R2 (a
> verified R2 account endpoint, a `dev-model-catalog` bucket default, cross-referenced against
> `model-foundry`/`ai-core-flows`). The maintainer corrected this directly the same day: "we
> will not call R2 in this scenario, when running hosted we will have access to an s3 bucket
> will all of the files, so we just need to target this instead." The R2/catalog research
> investigated a different, adjacent system (Anaconda's model-catalog *publishing* pipeline),
> not the hosted-*runtime* access path this feature actually needs. The shipped, corrected
> design: a plain AWS S3 bucket (no custom `endpoint_url`, no R2 framing), explicit
> opt-in configuration only (never auto-detected, unchanged from the original design), with
> the bucket resolved from a new shared `anaconda_s3_bucket` config key rather than a
> per-entry R2-catalog bucket default. Left below for an honest record of what was
> investigated and why it changed, rather than silently rewritten — see
> `specs/002-anaconda-models-provider/research.md` R3-addendum-3 for the full correction.

## Context

*(Superseded framing — see the correction note above. Kept verbatim for an honest record of
the first investigation pass.)*

The user asked for "Anaconda models" to become a first-class preferred provider of decision
models. Research during `/speckit.plan` found no independently-architected Anaconda decision
model exists yet (Jira `AISEC-63`, Discovery stage, scoped around adopting Jev/Clef rather
than training something new). What does exist, concretely and in progress: Anaconda is
ingesting Cloudflare's own `clef-flash` artifact (same pinned commit already in `REGISTRY`)
into its internal model catalog (`AISAGE-565`/`AISAGE-566`), and the maintainer had already
run ember successfully against that catalog copy locally. During `/speckit.implement`, the
catalog's actual download mechanism was initially investigated as a direct S3-compatible
location (endpoint, bucket, prefix, credentials) against Anaconda's internal catalog
infrastructure — not an HF-Hub-compatible API, and not the Metaflow-scoped
`AnacondaModelClient` referenced in `Anaconda-Sandbox/noodles`. **This framing was corrected
the same day**: the actual mechanism is a plain AWS S3 bucket made available at hosted
runtime, unrelated to the internal catalog pipeline this paragraph describes.

## Decision

- **The Anaconda entry is the same artifact, a different source.** `anaconda-flash`'s
  `ModelSpec` pins the identical commit, `schema_sha256`, and `head_sha256` as `flash` — it is
  Clef-Flash made available through Anaconda's hosted S3 bucket, not a new model. This made
  the existing `Engine`/`load_clef` loader usable unmodified (research R2): no loader change
  was needed.
- **`ModelSource` is a two-member `StrEnum`** (`HUGGING_FACE`, `ANACONDA_S3`) on `ModelSpec`,
  added because constitution Article X §10.7 requires a fixed-set value to be an enum, not a
  bare string, now that a second download mechanism is a concrete requirement. It is not a
  general multi-vendor provider framework — the spec explicitly rejected building one.
- **Direct AWS S3 download, not a catalog-API token exchange, and not R2.** A two-step
  bearer-token-to-presigned-URL flow (the pattern `model-foundry` actually uses for consumer
  downloads) was considered and explicitly set aside by the maintainer. *(Corrected
  2026-10-08, same day: the download target is a plain AWS S3 bucket made available on
  Anaconda's hosted platform — not Cloudflare R2, and not Anaconda's internal model-catalog
  infrastructure. An initial pass investigated the R2/catalog path based on an incomplete
  understanding of the hosted-runtime access model; the maintainer corrected this directly.
  `boto3` remains the chosen client — the standard, mature choice for AWS S3 regardless of
  which specific storage system was targeted.)*
- **New dependency: `boto3`** (plus `boto3-stubs[s3]` for `mypy --strict`), justified inline
  in `pyproject.toml` — the standard, mature client for AWS S3 object storage.
- **Per-entry prefix, shared bucket (revised 2026-10-08).** Each `ModelSpec` carries its own
  `s3_prefix` (like `repo` already does for Hugging Face entries), so a second entry
  (`anaconda-clef`) never means changing a prefix the first entry (`anaconda-flash`) also
  relies on. Unlike the prefix, the *bucket* is usually the same across every entry in a given
  deployment (one hosted-platform bucket holds every model), so it resolves from a shared
  `anaconda_s3_bucket` config fallback by default, with a per-entry `ModelSpec.s3_bucket`
  override available for the rare exception. *(This supersedes an earlier design where
  `s3_bucket` also defaulted per-entry to a specific Cloudflare R2 bucket name
  (`"dev-model-catalog"`) — that default is removed entirely now that the real bucket is
  hosted-platform-specific, with no stable value to guess.)* Only the *connection*
  credentials/region stays global config (`anaconda_s3_access_key_id`, `_secret_access_key`,
  `_region`). Credential keys are masked in `ember config show` like `auth_token`.
- **`DEFAULT` changed in two places that must stay in sync by hand**: `ember/models.py`'s
  `DEFAULT` and `ember/cfg/config.py`'s `DEFAULTS["model"]` are independently-maintained
  literals (config.py cannot import models.py — Article XIII layering), a pre-existing
  duplication risk this feature's implementation had to discover and account for.
- **No migration notice, no new "preferred provider" abstraction, no auto-detection** of
  Anaconda's platform for the hosted-endpoint path **or the hosted S3 download path** — all
  per explicit spec clarifications; the hosted-endpoint story reuses
  `specs/001-remote-inference-servers/` entirely unchanged.
- **The `dev-model-catalog`/`prod-model-catalog` R2 bucket investigation is superseded, not
  deleted.** Per the user's explicit earlier direction ("check out `.env` for dev/prod
  locations and buckets we need this to work — pit of success"), `model-foundry`'s
  `.env`/`.env.prod` were inspected and cross-checked against `ai-core-flows`'
  `CatalogIngestFlow`, confirming Cloudflare R2 storage with a shared account and
  dev/prod bucket convention for Anaconda's *catalog-publishing* infrastructure. This research
  remains an accurate record of that adjacent system, but is **not** the hosted-*runtime*
  access path this feature uses — the maintainer's same-day correction established that
  explicitly (research R3-addendum-3). The R2 endpoint default and `dev-model-catalog` bucket
  default have been removed from `ember/cfg/config.py`/`ember/models.py`.
- **`s3_prefix` remains genuinely unverified**, unaffected by the R2→AWS-S3 correction — this
  was always a separate open question (the object-key layout within whatever bucket is used),
  not resolved by confirming the bucket/connection mechanism.

## Consequences

- Pulling `anaconda-flash`/`anaconda-clef` works once **credentials and a bucket** are set
  (`EMBER_ANACONDA_S3_ACCESS_KEY_ID`/`_SECRET_ACCESS_KEY`/`_BUCKET`) — no defaults exist for
  any of these (unlike the superseded R2 design, which defaulted the endpoint and bucket).
  Without them, `ember model pull anaconda-flash` fails with an actionable `RuntimeError`
  (same clarity standard as the existing disk-space check, spec FR-009).
- Anyone changing the default registry key in the future must update both
  `ember/models.py::DEFAULT` and `ember/cfg/config.py::DEFAULTS["model"]` — there is no single
  source of truth for this value by design (layering), only a code comment pointing at the
  other file.
- `s3_prefix` (`ember/models.py` `REGISTRY`) remains an explicitly-marked unverified
  placeholder — the actual object-key layout within the real hosted bucket has not been
  confirmed end-to-end. Correcting it later is a one-line change to the affected entry only
  (per-entry, not config), exactly the scaling property this contract was hardened for.
- Adding a third Anaconda entry (or a genuinely different decision-model architecture, the
  open possibility `AISEC-63` tracks) is pure `REGISTRY` data: a new `ModelSpec` with its own
  `s3_prefix` (and `s3_bucket` only if it genuinely lives elsewhere) — no code change to the
  download dispatch, config schema, or CLI. This is the concrete test the contract was
  hardened to pass.
- A critical post-implementation review (2026-10-08) found and fixed two real defects the
  (passing) test suite had not caught: `paths.anaconda_s3_cache()` was eagerly creating
  `~/.cache/ember/anaconda-models/` as a side effect of read-only calls like `ember model
  list` (observed directly on the implementing machine); and `botocore.exceptions.ClientError`/
  `BotoCoreError`/`boto3.client()`'s own `ValueError` were uncaught, so a wrong bucket, bad
  credentials, or a malformed configuration would have printed a raw traceback instead of
  `cli.main`'s clean `error: ...` format. Both are fixed (lazy path computation; wrapped as
  `RuntimeError` with `from exc`), with regression tests. See research.md R5.
- A follow-up module split (`tasks.md` T032, same day) moved the S3 download logic
  (`s3_client()`/`download()`) out of `ember/models.py` into `ember/cfg/s3.py` after
  the `ModelSource`/S3-download addition pushed `ember/models.py` over the Article X §10.3
  400-line ceiling (470 lines); `ember/models.py` is now 359 lines.
- A second critical review (2026-10-08, after the R2→AWS S3 correction above) found and fixed
  an unrelated pre-existing bug surfaced by manually verifying the new `anaconda_s3_bucket`/
  `anaconda_s3_region` config keys: `ember config show` only reflected env-var overrides for
  `server_url` and the four secret keys, silently showing the default/file value for every
  other key (including these two new ones) regardless of an active `EMBER_*` override. Fixed
  by resolving every key through `config.resolve()`. See
  [[2026-10-08-config-show-ignored-env-overrides]] for the full discovery.
