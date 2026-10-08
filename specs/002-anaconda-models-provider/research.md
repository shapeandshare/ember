# Phase 0 Research: Anaconda Models as a First-Class Preferred Provider

**Feature**: `002-anaconda-models-provider`
**Date**: 2026-10-07
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

This file resolves the Technical Context's blocking unknown and the supporting questions
needed to make Phase 1 design concrete.

## R1 — Does an independent "Anaconda decision model" architecture exist?

**Finding**: No. There is no publicly shipped, independently-architected Anaconda decision
model (nothing comparable to a from-scratch competitor to Cloudflare's Clef). Internally,
Anaconda's decision-model work is tracked as **AISEC-63 "Decision Model Support"**
(Discovery stage, created 2026-10-05), whose own description reads: *"ie Jev or Clef / need
to add evals for decision models."* This ticket is explicitly scoped around **adopting**
third-party decision models (TypeSafe AI's Jev, Cloudflare's Clef), not minting a new
architecture.

What *is* concretely underway, and already linked from AISEC-63:

- **AISAGE-565** ("Unblock Cloudflare/clef ingestion — remote-code override + non-destructive
  staging promotion", reporter/assignee: Josh Burt, status New): active work to get
  `Cloudflare/clef` (the exact same upstream repo and pinned commit
  `2f3de3dd85f379784083b0814d997ab627200f0c` already in ember's own `REGISTRY`) through
  Anaconda's internal model-security-scan gate and into Anaconda's own model catalog, as a
  **catalog-only ingestion** ("the published collection is the deliverable, not a staging
  artifact for GGUF conversion"). The ticket records the architecture explicitly:
  `Qwen3_5ForConditionalGeneration (qwen3_5)`, loaded via `AutoModelForMultimodalLM` with
  `trust_remote_code=True` — i.e., **the identical artifact shape ember's `runtime.py`
  already loads today.**
- **AISAGE-566** (reporter: Josh Burt): a bug in Anaconda's catalog original-file allowlist
  that silently drops `*.py` files (including `joint_schema_model.py`) from published
  collection manifests for `trust_remote_code` models — directly caused by, and blocking,
  the Clef ingestion above.
- **Slack** (`#team-ai-security-guardrails`, DM threads): the reporter of both tickets
  (`jburt` — this project's maintainer) posted a POC of "using Clef as a local decision model
  exposed as a plugin/mcp to my agentic harness," linking this exact project
  (`shapeandshare.github.io/ember`), and separately confirmed: **"well I got ember working
  locally with the clef-flash from the catalog"** — i.e., ember has already been run
  successfully against the Anaconda-internal model catalog's copy of Clef-flash.
- A colleague (`prudiger`) is drafting an internal blog post, "Decision_Time," on "what are
  decision models?" and "building our own on the Anaconda AI Orchestration Platform" — an
  early-stage exploration, not a shipped product or a named model.

**Conclusion**: The near-term, concrete meaning of "Anaconda decision model" is **Cloudflare's
Clef, re-published through Anaconda's own model catalog/infrastructure** — not a novel
Anaconda-trained architecture. This is not a known fact to assume indefinitely (Anaconda may
later train or adopt a genuinely different model for this category — AISEC-63 remains open
Discovery), but it is the only concrete, in-progress artifact today, and it resolves the
plan's central risk favorably: **the first Anaconda registry entry is Clef-shape-compatible
by construction**, because it is Clef.

**Decision**: Treat "the Anaconda-published decision model" for this feature as **Anaconda's
own catalog-hosted copy of Cloudflare's Clef / Clef-flash artifact** (same upstream repo,
same pinned commit, same `Qwen3_5ForConditionalGeneration` + `joint_schema_model.py` +
`joint_head.safetensors` shape), sourced from Anaconda's model catalog/distribution rather
than directly from Hugging Face. This is recorded here as the Phase 0 research outcome, not
hardcoded into the spec, because the spec intentionally left model selection open — this
research grounds the choice in verified, repo-external evidence rather than guessing.

**Alternatives considered**:
- *Wait for a genuinely novel Anaconda-trained decision model* — rejected for this feature:
  AISEC-63 is Discovery-stage with no committed timeline or architecture, and the spec's own
  scope (registry addition, no new abstraction) does not require waiting on that outcome.
- *Treat "Anaconda models" as entirely undefined and defer the registry entry to a future
  feature* — rejected: the spec explicitly requires at least one Anaconda registry entry
  (FR-001) and a new default (FR-002); verified internal evidence exists to ground a concrete
  choice now, so deferring indefinitely would be avoidable incompleteness.

## R2 — Can the existing loader (`ember/serving/runtime.py`) admit this artifact unmodified?

> **Note (2026-10-08)**: the `verify_model_dir`/`ember/serving/integrity.py` hash-verification
> step referenced below no longer exists — constitution Article V was redefined the same day
> ("Model Loading" replaces "Reproducibility by Pinning"; see
> `vault/decisions/2026-10-08-article-v-redefined-model-loading.md`). The core finding this
> section establishes (no loader modification needed; the artifact is identical to `flash`)
> remains true and is why `ember/serving/runtime.py` is still unmodified by this feature —
> only the integrity-verification detail below is stale. Left unedited for an honest record
> of the reasoning at the time.

**Finding**: Yes. Because R1 establishes the first Anaconda registry entry as Anaconda's own
distribution of the *same* Clef/Clef-flash artifact already in `ember/models.py` (same
backbone class `Qwen3_5ForConditionalGeneration`, same `joint_schema_model.py` contract,
same `joint_head.safetensors` + `joint_head_config.json` + `model.safetensors.index.json`
file set), the existing `load_clef` / `joint_module` / `Engine` code path in
`ember/serving/runtime.py` requires **no modification** to load it. `verify_model_dir`
(`ember/serving/integrity.py`) already takes its expected hashes from the `ModelSpec` passed
in, not from a hardcoded vendor assumption, so a new `ModelSpec` with Anaconda-sourced
provenance and the *same* pinned schema/head hashes (because it is the same upstream file)
passes integrity verification unchanged.

**Decision**: No loader-abstraction, no loader seam, no new provider layer. `REGISTRY` gains
one or more new `ModelSpec` entries that are data only — exactly the scope the spec's
Clarification 2 requires (Article XV honored: the simplest viable solution directly
satisfies the requirement).

**Alternatives considered**:
- *Generalize the loader now in anticipation of a future, architecturally different Anaconda
  model* — rejected per Article XV (YAGNI) and the spec's explicit scope choice. The broader
  "decision model" category is architecturally heterogeneous across vendors (frozen-backbone
  encoder models, logprob-only post-processing approaches, different head shapes), so a
  generic loader built against a single data point would be speculative generality. Build it
  when a second, genuinely different artifact shape is a concrete requirement (constitution
  Article X §10.9's "introduce an abstraction only when the second concrete use case
  arrives" spirit, mirrored in Article XV §15.3).

## R3 — Where does the "Anaconda-published" model's weight download point to?

**Finding**: Anaconda's model catalog ingestion of Clef (AISAGE-565) is a **catalog-only
ingestion**: the deliverable is the published collection in Anaconda's own catalog/storage
(R2-backed staging promoted to a collection layout), not a Hugging Face repo under an
Anaconda org. Anaconda's catalog is accessed through Anaconda-internal infrastructure
(the OBP catalog proxy / Foundry collection API referenced in the tickets), not the public
Hugging Face Hub API that `ember/models.py`'s `pull`/`resolve_dir`/`remove` functions
currently call via `huggingface_hub.snapshot_download`.

**Decision**: This is a genuine new fact the registry must accommodate, deferred to
`/speckit.tasks` implementation detail rather than resolved here with an unverified specific
mechanism: a new Anaconda `ModelSpec` entry needs a download path that is **not**
`huggingface_hub.snapshot_download` against a public HF repo, because Anaconda's catalog is
not the public Hub. The simplest options, in order of preference per Article XV:

1. If Anaconda's catalog exposes an HF-Hub-compatible API surface (many internal model
   catalogs proxy the Hub API shape), reuse `huggingface_hub.snapshot_download` pointed at
   that internal endpoint (`HF_ENDPOINT` override) — zero new code, just a different
   `endpoint`/`repo` pair in the spec.
2. If not, a minimal, additive pull path specific to Anaconda-catalog-sourced entries,
   following the same `ModelSpec`-driven, pinned-revision, integrity-hash-verified contract,
   added to `ember/models.py` only for entries whose source is the Anaconda catalog rather
   than the public Hub.

This spec and plan do not pick between these two until the actual catalog API shape is
confirmed at implementation time (it is an internal, actively-changing surface — the
allowlist bug AISAGE-566 is still open against it). `tasks.md` MUST include a task to verify
the catalog's download API shape before writing the pull implementation.

**Alternatives considered**:
- *Assume HF-Hub-compatible API without verification* — rejected: AISAGE-566 shows the
  catalog's manifest/file-serving behavior has open bugs specific to `trust_remote_code`
  models like Clef; assuming compatibility without checking risks a broken `ember model pull`
  for the exact model this feature cares about.

### R3-addendum — Verified at `/speckit.implement` (T001), 2026-10-07

**Finding**: Confirmed directly with the catalog's admin/creator (this project's maintainer):
the published Clef-flash collection is **not** reachable through an HF-Hub-compatible API.
Download access is via **an S3-compatible storage location** (bucket/prefix), with access
mediated by credentials/signed-URL issuance — not the Metaflow-specific `AnacondaModelClient`
referenced in the `Anaconda-Sandbox/noodles` design doc (that client is scoped to Outerbounds
Metaflow step execution and is not a general-purpose library ember can import). AISAGE-565
itself remains in Jira status "New" with unchecked acceptance criteria, but this reflects
administrative ticket hygiene, not the actual state of the artifact — the maintainer confirms
the collection is live in both stage and prod catalogs today.

**Decision**: Option 2 from the list above applies. `ember/models.py` needs a minimal,
additive S3-compatible download path for Anaconda-catalog-sourced `ModelSpec` entries,
distinct from the existing `huggingface_hub.snapshot_download` path used for Clef's public HF
entries. Concretely:

- A new config key pair for the S3-compatible endpoint/credential (e.g.
  `anaconda_catalog_endpoint_url`, `anaconda_catalog_bucket`, and a credential — access
  key/secret or a session token — resolved through the existing `config.resolve()`
  precedence, mirroring how `server_auth_token` etc. were added in
  `specs/001-remote-inference-servers/`), added to `ember/cfg/config.py` `DEFAULTS`.
- A `ModelSource` `StrEnum` (per constitution Article X §10.7 — this is exactly the
  "value drawn from a fixed, known set" the article requires as an enum, not a bare string)
  with members for at least `HUGGING_FACE` and `ANACONDA_S3`, stored on each `ModelSpec` to
  select which download branch `pull()`/`resolve_dir()`/`remove()` take.
- The S3-compatible download itself uses `boto3` (the standard, mature, boring choice for
  S3-compatible object storage — Article XV §15.2 "prefer mature, well-understood libraries")
  rather than a hand-rolled HTTP client or an attempt to wrap an inaccessible internal SDK.
  `boto3` is a new dependency and MUST be justified in the implementing commit per Article
  XV §15.2 (one line: "boto3 is the standard client for the S3-compatible catalog storage
  this feature's Anaconda registry entry downloads from").
- The exact bucket/prefix/object-key layout for the published Clef-flash collection is not
  yet pinned — implementation (T011) MUST treat endpoint, bucket, and credential as
  configuration the user supplies, not hardcode a specific bucket name or region, since that
  infrastructure is still evolving (AISAGE-565/566 are both open).

**Final shape, confirmed directly with the maintainer** (superseding the two-step
catalog-API/presigned-URL option explored and then set aside as unnecessary complexity for
this feature): ember is given a **direct S3-compatible location** (endpoint URL, bucket,
prefix, and static credentials — access key ID + secret access key) and downloads the
collection's files from it directly via `boto3`, with no intermediate catalog-API
token-exchange step. This mirrors the exact pattern already used by this organization's own
`ai-core-flows` `StorageClient`/R2-ingestion code for S3-compatible (Cloudflare R2) access:

```python
client = boto3.client(
    "s3",
    endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",  # or any S3-compatible endpoint
    aws_access_key_id=access_key_id,
    aws_secret_access_key=secret_access_key,
    region_name="auto",
)
```

No anonymous/unsigned-request pattern exists anywhere in the organization's own S3-compatible
code (verified by inspecting `ai-core-flows`); every access path uses explicit credentials via
`boto3`, so ember's implementation follows the same convention rather than inventing an
unsigned-access special case.

**Alternatives considered**:
- *Two-step catalog-API bearer-token → presigned-URL → HTTPS GET flow* (model-foundry's
  `DownloadCommand` pattern, verified in `model-foundry/src/vendor/.../download.py`) —
  considered and explicitly set aside by the maintainer in favor of direct S3-compatible
  access for this feature; simpler for a first cut, and consistent with "we'll need to do the
  same thing for Outerbounds" per the maintainer's own framing.
- *Wrap `AnacondaModelClient`* — rejected: that client is Metaflow-step-scoped
  (`task_decorate` wrapper, `current.anaconda_models` namespace) per the `noodles` design doc;
  it is not meant for use outside a running Metaflow flow and ember is a standalone CLI/MCP
  tool with no Metaflow runtime.
- *Block implementation entirely until AISAGE-565 formally closes* — rejected per the
  maintainer's direct confirmation that the artifact is live in both environments today;
  waiting on ticket-status hygiene that doesn't reflect actual system state would be
  process-over-substance.

### R3-addendum-2 — Real connection values located; prefix remains unverified, 2026-10-07

**Finding** (user direction: "check out .env for dev/prod locations and buckets we need this
to work (pit of success)"): `model-foundry/.env` and `.env.prod` (gitignored, real local
values on this machine) confirm the Anaconda model catalog's storage is **Cloudflare R2**,
not generic S3, with:

- Shared R2 account ID across dev/prod: `4472618dcba92dc88189efc96d9c27ba`
- Dev/stage bucket: `dev-model-catalog` — `model-foundry`'s own `.env.example` documents the
  convention this mirrors: "Defaults to the staging catalog so a fresh local checkout can
  never mutate production by accident."
- Prod bucket: `prod-model-catalog` (`.env.prod`, "matches deployment/deploy.prod.yaml")
- `ai-core-flows`' `flows/catalog_ingest_flow.py` constructs the identical endpoint pattern
  (`https://{account_id}.r2.cloudflarestorage.com`, `region_name="auto"`), confirming the
  `boto3` client shape already implemented in `ember/models.py::_s3_client` is correct.

**However**, the only matching R2 object-key construction found —
`catalog_ingest_flow.py::_build_r2_key` — writes a **different artifact shape** than what
ember needs: `models/{model_uuid}/quantized/{file_uuid}/{filename}`, a single GGUF file keyed
by database UUIDs (for a presumably llama.cpp/quantized serving path), not a directory of
files (`config.json`, `joint_schema_model.py`, `joint_head.safetensors`,
`model.safetensors.index.json`) at a stable, human-readable prefix. No code implementing
AISAGE-565's "catalog-only, non-destructive, non-GGUF" raw-snapshot ingestion was found in
`ai-core-flows` or `model-foundry` — consistent with that ticket's Jira status ("New") being
an honest reflection of its code state, not just administrative lag.

**Decision**: Apply "pit of success" asymmetrically, per what is and isn't actually verified:

- **Wire in the real, verified connection values as defaults**: `anaconda_s3_endpoint_url`
  now defaults to the real R2 endpoint (`ember/cfg/config.py` `DEFAULTS`) — the account ID is
  not a secret, and defaulting it means a user who supplies only credentials + a bucket name
  gets a working connection immediately, without separately hunting down the account ID.
  Credentials themselves remain un-defaulted (`None`), as they must.
- **Default each Anaconda `REGISTRY` entry's `s3_bucket` to `dev-model-catalog`**, the safe
  dev/stage bucket — never `prod-model-catalog` by default, mirroring `model-foundry`'s own
  safety convention exactly.
- **Leave `s3_prefix` as an explicitly-marked, unverified placeholder** (`"clef-flash"`,
  `"clef"`) rather than guessing a key layout with no supporting evidence, or blocking on it.
  Both the `REGISTRY` entries (inline comments) and `COMPATIBILITY.md` state plainly that the
  prefix is unverified and name the exact reason (the only known ingestion path produces a
  different artifact shape) so a future contributor fixing this has the context immediately,
  without re-deriving it.

This is the deliberate line "pit of success" draws here: default what is actually known and
safe (connection, dev bucket), and be loud about what is not yet known (prefix/object-key
layout) rather than fabricating a second fact to match the first.

**Alternatives considered**:
- *Guess a prefix based on `_build_r2_key`'s pattern (e.g.
  `models/{some-id}/snapshot/...`)* — rejected: there is no evidence AISAGE-565's actual
  ingestion uses any variant of this pattern, since it is explicitly a different artifact
  type (full snapshot vs. single quantized file); inventing a second unverified fact compounds
  the risk rather than reducing it.
- *Also default `s3_prefix`* — rejected: unlike the endpoint (verified, stable, non-secret)
  and the dev bucket (verified, with a known-safe convention to copy), no equivalent
  verification exists for the prefix; defaulting it would manufacture false confidence.
- *Leave the endpoint undefaulted too, for consistency with the prefix caveat* — rejected:
  the endpoint and bucket are independently verified facts from two separate internal
  sources (`model-foundry`'s own two env files, cross-checked against `ai-core-flows`' live
  code), unlike the prefix; treating verified and unverified facts identically would be its
  own kind of imprecision.

### R3-addendum-3 — Corrected: plain AWS S3 bucket, not Cloudflare R2 / Anaconda's
internal catalog, 2026-10-08

**Finding**: Direct maintainer correction, superseding R3-addendum and R3-addendum-2 in full:
"we will not call R2 in this scenario, when running hosted we will have access to an s3
bucket will all of the files, so we just need to target this instead." The actual design is
simpler than R3-addendum/R3-addendum-2 assumed: when ember runs on Anaconda's hosted
platform, a plain **AWS S3** bucket is made available, already containing the full model
files — not Anaconda's internal model-catalog infrastructure, not Cloudflare R2, and not the
`model-foundry`/`ai-core-flows` R2-access pattern those addenda investigated. That earlier
research (AISAGE-565/566 catalog ingestion, the `dev-model-catalog`/`prod-model-catalog` R2
buckets, the verified R2 account endpoint) described a different, adjacent system — Anaconda's
model-catalog publishing pipeline — not the hosted-runtime access path this feature actually
needs.

**Decision**: Simplify accordingly:

- **Drop the custom `endpoint_url`/R2-compatibility framing.** `ember/cfg/anaconda_s3.py`'s
  `s3_client()` now constructs a plain `boto3.client("s3", ...)` with no `endpoint_url`
  parameter — standard AWS S3, not an S3-compatible third-party endpoint. The
  `anaconda_s3_endpoint_url` config key and its R2-account default
  (`4472618dcba92dc88189efc96d9c27ba.r2.cloudflarestorage.com`) are removed entirely.
- **Still explicit, opt-in configuration — no auto-detection.** This remains unchanged from
  R3-addendum: ember never detects that it is running on Anaconda's hosted platform. The
  hosted platform's own bootstrap step (or a user) sets
  `EMBER_ANACONDA_S3_ACCESS_KEY_ID`/`_SECRET_ACCESS_KEY`/`_REGION`/`_BUCKET`, per spec
  Clarification 5 and FR-007.
- **Drop the `dev-model-catalog`/`prod-model-catalog` bucket defaults.** Neither registry
  entry defaults `s3_bucket` anymore; the real hosted bucket name is not yet known at
  authoring time and is intentionally left for explicit configuration rather than guessed
  from the now-irrelevant R2 catalog convention.
- **New shared config key: `anaconda_s3_bucket`.** Because the hosted-runtime bucket is a
  single bucket holding every model's files (not a per-model catalog bucket), a shared
  `EMBER_ANACONDA_S3_BUCKET` config key was added so the hosted platform's bootstrap step can
  configure it once. A registry entry's own `ModelSpec.s3_bucket`, if set, still overrides
  this shared value — unchanged from the per-entry-location principle R3-addendum-2
  established, just with a sensible shared fallback since one bucket is now the common case
  rather than the exception.
- **`s3_prefix` remains genuinely unverified**, exactly as R3-addendum-2 left it — this
  correction is about *where the bucket lives and how ember connects to it* (confirmed: plain
  AWS S3, explicit config), not about *what key layout the bucket uses internally* (still
  unconfirmed). `tasks.md` T031 remains open and blocked on the same missing fact: no real
  bucket/credentials/object layout have been exercised end-to-end.

**Alternatives considered**:
- *Keep the R2-compatible `endpoint_url` parameter as an optional override* — rejected per
  Article XV (YAGNI): no second S3-compatible provider is a concrete requirement today: the
  hosted platform is plain AWS S3, and `boto3.client("s3", ...)` already defaults correctly
  to AWS's own endpoints without any extra parameter. Add it back only if a second concrete
  non-AWS deployment target actually arrives.
- *Keep the per-entry-only `s3_bucket` design without a shared fallback* — rejected: with one
  hosted bucket holding every model (not per-entry catalog buckets, which was the R2-era
  model), requiring every future entry to repeat the same bucket name would violate Article
  XV's reuse-first principle; the shared-with-override design keeps both cases simple.

## R4 — Default selection among multiple Anaconda entries

**Finding**: Not yet a concrete concern — R1 identifies exactly one near-term candidate
(Anaconda's catalog copy of Clef/Clef-flash), so there is no immediate "which of several
Anaconda entries is default" decision to make.

**Decision**: Mirror the existing pattern exactly: `ember/models.py`'s module-level
`DEFAULT` constant names one registry key, exactly as it names `"flash"` today. When a second
Anaconda entry is added in the future, whoever adds it updates `DEFAULT` the same way a
future Clef revision bump would. No new selection mechanism, flag, or precedence rule is
introduced now (per the user's explicit "roll off" signal during `/speckit.clarify` — this
is registry-entry bookkeeping, not a product decision).

**Alternatives considered**: An automatic "smallest/fastest" selection rule — rejected,
unnecessary complexity for one entry, and the user explicitly declined to specify this ahead
of need.

## R5 — Hosted-endpoint path: does anything new need building?

**Finding**: No. User Story 3 (Anaconda-hosted models) requires only that a user can point
`server_url`/`auth_token`/`auth_header` (already-shipped config keys from
`specs/001-remote-inference-servers/`) at an Anaconda-operated HTTP(S) endpoint serving the
existing `/v1/systemone` contract. The clarification session already established this is
**always explicit configuration**, never auto-detected. Anaconda's own infrastructure
direction (the `Anaconda-Sandbox/noodles` design doc for Outerbounds/Metaflow model serving)
is a separate, general-purpose model-catalog-to-vLLM/llama.cpp serving layer for a different
consumption pattern (Metaflow steps, OpenAI-compatible chat endpoints) — it does not
constrain or require changes to ember's existing remote-endpoint client, because ember talks
to a `/v1/systemone`-shaped server, not an OpenAI-chat-shaped one. Whether Anaconda chooses
to front a Clef-serving ember-compatible HTTP server with that infrastructure someday is an
Anaconda-operations decision, invisible to ember's client contract.

**Decision**: No client-side code change beyond what already exists. FR-006/FR-007 are
satisfied by documentation (README/COMPATIBILITY.md) describing how to point ember at an
Anaconda-hosted endpoint using existing config, not by new code.

**Alternatives considered**: Build Anaconda-specific endpoint-discovery or auth-scheme code —
rejected per Clarification 5 (no auto-detection) and Article XV (no concrete requirement
beyond "reuse the existing mechanism").

## R6 — Agent-kit and documentation re-measurement scope (Article III §3.3)

**Finding**: Because R1/R2 establish the new default as the *same* Clef-flash artifact
already measured in `ember/agent_kit/` and `COMPATIBILITY.md` (same weights, same revision,
same inference behavior — only the distribution source differs), the kit's "Observed" numbers
and thresholds do **not** need re-measurement for correctness. The only required documentation
change is **framing**: naming Anaconda's catalog distribution as the default/preferred source
while keeping Cloudflare's public Hugging Face repo as a fully supported alternative source
for the identical model.

**Decision**: Skip kit re-measurement (no numbers change); update prose only (README,
COMPATIBILITY.md, `ember/agent_kit/instructions.md` if it names a source) to reflect the new
default source and preference framing. If a future, genuinely different Anaconda model
replaces this one, re-measurement per §3.3 applies then, not now.

**Alternatives considered**: Re-measure defensively — rejected as unnecessary work (Article
XV) when the underlying model and weights are unchanged.

## Resolved unknowns from Technical Context

All Technical Context entries are now concrete:

- The loader question (biggest named risk) resolves to **no loader change required**.
- Model selection resolves to **Anaconda's catalog-hosted Clef/Clef-flash** as the first
  Anaconda `REGISTRY` entry and new `DEFAULT`, grounded in verified internal evidence
  (Jira `AISEC-63`, `AISAGE-565`, `AISAGE-566`; Slack POC confirmation), not invented.
- The one remaining open implementation detail — the exact shape of Anaconda's catalog
  download API for `ember model pull` — is explicitly deferred to task-level verification
  (R3) rather than guessed, because it is an actively-changing internal surface with a known
  open bug.
- No new dependencies. No constitution amendment. No new provider-abstraction layer.

## R5 — Critical review findings, fixed at implementation time (2026-10-08)

A post-implementation critical review (not a new research question, but findings worth
recording for future maintainers) surfaced two real defects in the first implementation pass,
both fixed with a failing test written first:

1. **`paths.anaconda_s3_cache()` eagerly created a directory on read-only calls.** The
   original implementation called `path.mkdir(parents=True, exist_ok=True)` inside the path
   accessor itself, mirroring `config_dir()`/`state_dir()`/`log_dir()` (which are needed by
   every ember invocation and are safe to create eagerly). But `anaconda_s3_cache()` is only
   relevant to users who actually pull an `ANACONDA_S3` entry — a plain `ember model list` or
   `ember doctor` was observed, in real manual testing on the implementing machine, to create
   `~/.cache/ember/anaconda-models/` as an unwanted side effect of a pure read operation.
   Fixed by making `anaconda_s3_cache()` a pure path computation (like `hf_hub_cache()`) and
   moving `mkdir` into `_download_anaconda_s3`, the one place that actually writes.
2. **`botocore.exceptions.ClientError`/`BotoCoreError` and `boto3.client()`'s own
   `ValueError`(malformed endpoint) were not caught.** `ember/cli.py`'s top-level handler only
   catches `RuntimeError`/`KeyError` cleanly (prints `error: ...` and exits 1); any other
   exception propagates as a raw Python traceback. A wrong bucket name, bad credentials, or
   network failure during `_download_anaconda_s3`'s `list_objects_v2`/`download_file` calls,
   or a malformed `anaconda_s3_endpoint_url` at `_s3_client()` construction time, would have
   broken the "same clarity standard as the existing disk-space check" requirement (spec
   FR-009). Fixed by wrapping both call sites in `try/except` and re-raising as `RuntimeError`
   with the original exception chained (`from exc`).

Both findings were caught by deliberately re-reading the implementation end-to-end rather than
re-running the existing (passing) test suite, which by construction could not have caught
either gap — the mocked tests never exercised a real, uncaught exception path or inspected the
filesystem for an unwanted side effect. This is recorded as a reminder that a green test suite
proves the tests pass, not that the implementation is complete.

## A note on research methodology and independence

This research used Anaconda-internal tools (Jira, Slack, GitHub) available in this
environment to verify, not merely trust, an initial research pass. The verified tickets
(`AISEC-63`, `AISAGE-565`, `AISAGE-566`) and Slack messages are reporter-attributed to this
project's own maintainer, which means **this feature's grounding model (Clef via Anaconda's
catalog) is, at the time of writing, substantially the maintainer's own in-progress internal
work**, not an independent, externally-validated Anaconda product. This is recorded plainly
rather than obscured: it explains why the research converges cleanly (the maintainer is
already running ember against this exact artifact, per the "well I got ember working locally
with the clef-flash from the catalog" Slack message), and it means the Phase 1 design should
not overstate the maturity or independence of "Anaconda models" as a product — it is an
internal integration in progress, which matches the spec's own Assumptions section ("at least
one Anaconda-published decision model exists... by implementation time").
