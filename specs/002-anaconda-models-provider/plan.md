# Implementation Plan: Anaconda Models as a First-Class Preferred Provider

> **Superseded (2026-10-08)** — see `spec.md`'s header note and
> `vault/decisions/2026-10-08-simplify-remove-anaconda-s3-registry-entries.md`. The
> `ANACONDA_S3` registry subsystem this plan documents was removed; do not implement
> against this file.

**Branch**: `002-anaconda-models-provider` | **Date**: 2026-10-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-anaconda-models-provider/spec.md`

## Summary

Add Anaconda-published decision models to the existing model registry (`ember/models.py`)
with the same metadata shape and lifecycle already used for Cloudflare's Clef models, make an
Anaconda model the new default, and allow a user to reach an Anaconda-hosted decision-model
endpoint through the existing single-remote-endpoint mechanism (`ember/cfg/endpoint.py`,
shipped in `specs/001-remote-inference-servers/`). No new provider-abstraction layer, no new
configuration surface for the *hosted-endpoint* path, and no migration/notice machinery for
the default change (per the spec's clarifications).

The technical approach is **additive to two already-shipped mechanisms**: the model registry
(local weights, pull/list/select/remove) and the remote-endpoint client (hosted inference).
Phase 0 research (verified against Anaconda's internal Jira and Slack — see
[research.md](./research.md)) resolved the central engineering risk favorably: the first
concrete Anaconda-published decision model is Anaconda's own model-catalog distribution of
Cloudflare's Clef/Clef-flash artifact — the identical `Qwen3_5ForConditionalGeneration` +
`joint_schema_model.py` shape the existing `Engine`/`load_clef` loading path already serves.
No loader change, and no new provider-abstraction layer, is required.

**Post-implementation update (2026-10-08)**: implementation diverged from this plan's original
single-entry, zero-new-dependency scope in three verified, documented ways (see `research.md`
R3-addendum/R3-addendum-2/R3-addendum-3 and the vault decision note): (1) **two** registry
entries shipped (`anaconda-flash` and `anaconda-clef`, not one), per the user's "many others to
follow" direction; (2) a plain **AWS S3** bucket is made available when ember runs on
Anaconda's hosted platform (not an HF-Hub-compatible API, and — after an initial, since-
corrected Cloudflare R2/Anaconda-internal-catalog hypothesis — not R2 or any S3-compatible
third-party endpoint either), requiring a new `boto3` dependency and a minimal additive
download branch in `ember/models.py`/`ember/cfg/anaconda_s3.py`; (3) each entry's `s3_prefix`
lives on `ModelSpec` itself (per-entry), while `s3_bucket` is resolved from a shared
`anaconda_s3_bucket` config fallback (one hosted bucket holds every model), alongside the S3
*connection* details (`anaconda_s3_access_key_id`/`_secret_access_key`/`_region`). The core
architectural conclusion — no loader change, no new provider-abstraction layer — held
throughout; see the "Modules to change" and Constitution Check sections below for the
reconciled, as-shipped design.

## Technical Context

**Language/Version**: Python 3.12 (uv-managed), matching the existing codebase.

**Primary Dependencies**:

- torch 2.14 (MPS) + transformers 5.18 — model loading (existing)
- huggingface-hub — weight pull/list/rm for `HUGGING_FACE`-sourced registry entries (existing;
  unchanged for `flash`/`full`)
- FastAPI + uvicorn, httpx, pydantic, mcp — serving/client stack (existing, unchanged)
- **`boto3>=1.40,<2` (+ `boto3-stubs[s3]` for `mypy --strict`) — NEW dependency**, added during
  implementation once it was confirmed that a plain AWS S3 bucket, not an HF-Hub-compatible
  API, is made available when ember runs on Anaconda's hosted platform. Justified per Article
  XV §15.2 as the standard, mature client for S3 object storage. See `research.md`
  R3-addendum-3 and the vault decision note.

**Storage**: Hugging Face shared cache (or a checkout's `.models/<dir>`) for local
`HUGGING_FACE`-sourced weights (`flash`/`full`), identical to Clef today. A separate
local cache (`ember/cfg/paths.py::anaconda_s3_cache()`) for `ANACONDA_S3`-sourced weights
(`anaconda-flash`/`anaconda-clef`), populated by direct `boto3` AWS S3 download — see
data-model.md. JSON config file (`ember/cfg/config.py` + `ember/cfg/paths.py`) for the
default-model key and the existing remote-endpoint keys (`server_url`, `auth_token`,
`auth_header`, `allow_insecure_transport`, `request_timeout`) for the hosted-endpoint path
(FR-006; unchanged, no new keys there). **Four NEW config keys were required for the local
S3 download path** (not the hosted-endpoint path): `anaconda_s3_access_key_id`,
`anaconda_s3_secret_access_key`, `anaconda_s3_region`, `anaconda_s3_bucket` — see
data-model.md "AWS S3 connection configuration."

**Testing**: pytest (unit + model-backed where weights are present), mypy strict, ruff,
bandit — existing gates, unchanged.

**Target Platform**:
- Local Anaconda model: macOS Apple Silicon (MPS), CPU fallback — same as Clef (Article VI).
- Anaconda-hosted endpoint: any supported client host (CLI/MCP), reusing the existing
  endpoint client; no model loaded locally in that mode.

**Project Type**: Existing CLI tool + local/remote HTTP inference service + MCP stdio server
(no new project type).

**Performance Goals**: No new performance targets beyond what SC-001 already states (same
setup-time class as the current Clef default). Because research (R6) establishes the new
default as the identical Clef-flash weights already measured, no new latency/calibration
measurement is required; `COMPATIBILITY.md`'s existing numbers for `flash` apply unchanged to
the Anaconda-sourced entry.

**Constraints**:
- **RESOLVED by research (see research.md R1/R2)**: the first concrete Anaconda-published
  decision model is Anaconda's own model-catalog distribution of Cloudflare's Clef/Clef-flash
  artifact (same `Qwen3_5ForConditionalGeneration` backbone, same `joint_schema_model.py`
  contract, same pinned commit already in `ember/models.py`) — verified against Anaconda's
  internal Jira (`AISEC-63`, `AISAGE-565`, `AISAGE-566`) and Slack. The existing
  `ember/serving/runtime.py` loading path therefore requires **no modification**; new
  registry entries are data only (confirmed; `runtime.py` is unmodified in the shipped
  implementation).
- **RESOLVED by research (research.md R3 / R3-addendum / R3-addendum-3, implementation-time
  verification and a direct maintainer correction)**: Anaconda's hosted runtime is **not**
  HF-Hub-compatible and is **not** reachable through the Metaflow-scoped `AnacondaModelClient`.
  It is a plain **AWS S3 bucket**, made available when ember runs on Anaconda's hosted
  platform, already containing the full model files. (An earlier implementation pass
  hypothesized Anaconda's internal model-catalog infrastructure over Cloudflare R2 —
  R3-addendum/R3-addendum-2 — which the maintainer corrected in R3-addendum-3: that
  investigated a different, adjacent system, not the hosted-runtime access path this feature
  needs.) The shipped design adds a `ModelSource` `StrEnum` (`HUGGING_FACE` | `ANACONDA_S3`) to
  `ModelSpec`, dispatched on `spec.source` in `ember/models.py`'s
  `pull()`/`resolve_dir()`/`remove()` — a minimal, additive source-dispatch enum, not a general
  provider abstraction. The `boto3`-based download logic itself (`s3_client()`/`download()`)
  lives in `ember/cfg/anaconda_s3.py`, split out of `ember/models.py` after it briefly exceeded
  the Article X §10.3 sizing ceiling (tasks.md T032). `s3_prefix` is per-entry on `ModelSpec`;
  `s3_bucket` is resolved from a shared `anaconda_s3_bucket` config fallback (one hosted
  bucket holds every model's files), with a per-entry override available for the rare
  exception — per the user's explicit "many others to follow" direction recorded in
  data-model.md.
- No new provider-abstraction layer (per spec Clarification 2); additions are registry
  entries, a default-selection change, and a minimal source-dispatch enum — not a general
  multi-vendor plugin mechanism (confirmed: `ModelSource` has exactly two members and no
  plugin/registration API).
- No new consumer-facing configuration surface for "Anaconda **hosted-endpoint**" mode beyond
  the existing `server_url`/`auth_token`/`auth_header` keys (FR-006) — this constraint holds;
  it applies only to User Story 3's remote-endpoint path. It does **not** extend to the local
  model-pull path (User Stories 1–2), which required the four new `anaconda_s3_*` config keys
  described above to let `ember model pull anaconda-flash` work at all.
- No auto-detection of "running on Anaconda's platform" (Clarification 5); the hosted
  endpoint is always explicit configuration — this applies equally to the AWS S3 download path:
  ember never detects it is running on Anaconda's hosted platform, the hosted platform's own
  bootstrap step (or a user) sets the `EMBER_ANACONDA_S3_*` keys explicitly.
- No migration/compatibility/notice mechanism for the default change (Clarification 4,
  FR-012).
- Model weights SHOULD target a concrete Hugging Face (or equivalent) commit/revision in
  `REGISTRY` for reproducible downloads, though Article V no longer requires it (redefined
  2026-10-08, constitution 3.0.0 — see the Constitution Check below) — resolved: both
  Anaconda entries target the identical commit SHAs already used by `flash`/`full`, since
  they redistribute the same upstream artifact.
- **Known limitation, carried forward rather than blocking**: each Anaconda entry's
  `s3_prefix` (`"clef-flash"`, `"clef"`) is an explicitly-marked **unverified placeholder** —
  the exact object-key layout within the hosted AWS S3 bucket has not yet been confirmed
  end-to-end against real credentials and a real bucket. A real
  `ember model pull anaconda-flash`/`anaconda-clef` may fail or pull from the wrong location
  until this is corrected. See research.md R3-addendum-2/R3-addendum-3 and data-model.md.

**Scale/Scope**:
- **Two** new `REGISTRY` entries ship with this feature (not one, as originally scoped here):
  `anaconda-flash` (mirrors `flash`, 9B) and `anaconda-clef` (mirrors `full`, 27B), per the
  user's mid-implementation direction ("we will initially support clef, and clef-flash, and
  there will be many others to follow") recorded in data-model.md "Initial Anaconda registry
  scope." `anaconda-flash` becomes the new `DEFAULT`.
- One new `DEFAULT` value (`anaconda-flash` replaces `flash`), set independently in two places
  that must be kept in sync by hand: `ember/models.py::DEFAULT` and
  `ember/cfg/config.py::DEFAULTS["model"]` (Article XIII layering prevents `config.py` from
  importing `models.py`) — see the vault decision note's "Consequences" section.
- No new HTTP routes, no new MCP tool, no new CLI subcommands — existing `model
  pull/list/path/rm`, `doctor`, `/health` surfaces are reused and their *content* (not shape)
  changes to include Anaconda entries.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Gate Results (pre-design)

- **Article I — Local-First by Default**: **PASS**. The new default model still runs
  locally; the Anaconda-hosted endpoint is reached only through the already-amended,
  already-opt-in remote-endpoint mechanism from `specs/001-remote-inference-servers/`. No
  further amendment needed — Article I already accommodates "a user MAY explicitly configure
  a single remote inference endpoint."
- **Article II — Typed Decisions, Not Text**: **PASS**. Research confirms the Anaconda entry
  is the same Clef/Clef-flash artifact already conforming to the Jev/SystemOne
  calibrated-probability contract; no adaptation needed.
- **Article III — Agent-Legible Contract**: **PASS, no re-measurement required.** Research
  (R6) confirms the new default is bit-identical model weights to what the agent kit's
  "Observed" numbers already measure; only prose framing (which source is preferred) changes.
  `instructions.md` stays ≤ 2048 bytes.
- **Article IV — Lazy, Non-Interfering Lifecycle**: **PASS**. No lifecycle changes; the
  warm-server autostart/pidfile pattern is unaffected by which model is loaded.
- **Article V — Model Loading** (retitled from "Reproducibility by Pinning" 2026-10-08;
  constitution 3.0.0, MAJOR — see `vault/decisions/2026-10-08-article-v-redefined-model-loading.md`):
  **PASS.** The new `REGISTRY` entries target the same commit SHA already used for Clef-flash
  (`ember/models.py`), a download-targeting convenience since it is the same upstream
  artifact made available through Anaconda's hosted AWS S3 bucket — not a verified pin.
  `ember/serving/integrity.py` is deleted; no model-weight hash verification occurs for any
  source (`HUGGING_FACE`, `ANACONDA_S3`, or `EMBER_MODEL_S3_URI`).
- **Article VI — Apple Silicon First**: **PASS**. No new hardware target; local Anaconda
  models run under the same MPS-first/CPU-fallback rule as Clef.
- **Article X §10.18 (migration debt) / §10.3 (sizing)**: **PASS (pre-design)**, revisited
  post-design below. Research confirms no loader change is needed, so `runtime.py` (already
  at 507 lines, pre-existing migration debt) does not grow from this feature. `ember/models.py`
  itself was not yet known to grow at this pre-design checkpoint, since R3's S3-vs-HF-Hub
  question was still open.
- **Article XIII — Layered Architecture**: **PASS**. No layer boundary changes: the engine
  layer (`runtime.py`) still owns model I/O; MCP/HTTP layers are untouched by which registry
  entry is loaded.
- **Article XIV — Pit of Success**: **PASS**. The "not pulled → actionable message naming
  `ember model pull`" and "503 while loading" behaviors already generalize to any registry
  entry; no new failure mode class is introduced.
- **Article XV — Simplicity First and YAGNI**: **PASS.** The spec explicitly rejects a new
  provider-abstraction layer (Clarification 2), and research confirms the simplest viable
  solution — pure-data registry entries, no loader change — fully satisfies the requirement.

No Constitution Check failures requiring a human-approved amendment are found. This differs
from `001-remote-inference-servers`, which required an Article I amendment; this feature fits
inside the already-amended Article I and the already-existing registry pattern.

## Project Structure

### Documentation (this feature)

```text
specs/002-anaconda-models-provider/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md         # Phase 1 output (/speckit.plan command)
├── quickstart.md         # Phase 1 output (/speckit.plan command)
├── contracts/            # Phase 1 output (/speckit.plan command)
├── checklists/
│   └── requirements.md   # Spec quality checklist (already created by /speckit.specify)
└── tasks.md              # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
ember/
  models.py                 # REGISTRY: added anaconda-flash + anaconda-clef ModelSpec
                              #   entries; changed DEFAULT to "anaconda-flash"; added the
                              #   ModelSource StrEnum, dispatched on spec.source in
                              #   pull()/resolve_dir()/remove(). 360 lines (the S3 download
                              #   logic itself lives in cfg/anaconda_s3.py below, split out to
                              #   stay under the Article X SS10.3 ceiling).
  cfg/
    anaconda_s3.py            # NEW: s3_client()/download() — direct boto3 AWS S3 download
                              #   logic for ANACONDA_S3-sourced entries (plain AWS S3, no
                              #   custom endpoint_url; research R3-addendum-3), split out of
                              #   models.py (150 lines, 100% coverage; mirrors paths.py already
                              #   owning anaconda_s3_cache()).
  serving/
    runtime.py               # Engine / load_clef / joint_module: NO CHANGE for this feature
                              #   (research R2: same artifact shape, loader already handles
                              #   it) — confirmed unmodified by this feature specifically,
                              #   though simplified separately the same day when constitution
                              #   Article V was redefined (2026-10-08, "Model Loading"):
                              #   ember/serving/integrity.py and _classify_dir/skip_integrity
                              #   were removed entirely — see
                              #   vault/decisions/2026-10-08-article-v-redefined-model-loading.md.
                              #   This feature's own scope never touched integrity.py; its
                              #   later removal is a separate, repo-wide change.
  commands/
    doctor.py                 # _doctor_check_models: NO CHANGE — confirmed; already iterates
                              #   REGISTRY generically.
    models.py                 # cmd_model_pull/list/path/rm: NO CHANGE — confirmed; the
                              #   source-dispatch lives entirely in ember/models.py, not here.
  cfg/
    config.py                 # DEFAULTS["model"]: updated to "anaconda-flash" (T013), with a
                              #   comment noting it must stay in sync with models.DEFAULT by
                              #   hand (no automatic derivation; Article XIII layering
                              #   prevents config.py from importing models.py). Also gained
                              #   four new keys: anaconda_s3_access_key_id,
                              #   anaconda_s3_secret_access_key (both un-defaulted secrets,
                              #   masked in `ember config show`), anaconda_s3_region (no
                              #   default), and anaconda_s3_bucket (shared fallback for the
                              #   common one-bucket-per-deployment case; no custom
                              #   endpoint_url — plain AWS S3, research R3-addendum-3).
    paths.py                  # Added anaconda_s3_cache() — a pure path computation (like
                              #   hf_hub_cache()), NOT eagerly creating the directory (a real
                              #   defect in the first pass, fixed per research.md R5).

docs/
  README.md                   # Update "currently Cloudflare's Clef-Flash" framing; document
                              #   Anaconda's hosted distribution as the preferred/default
                              #   source, Cloudflare's public repo as a supported alternative
                              #   source, same model
  COMPATIBILITY.md             # Add the Anaconda-hosted entry to "Tested models" (same
                              #   verified numbers as flash, per research R6)
  ember/agent_kit/*            # Prose-only update if a source is named; no number re-measurement

tests/
  test_runtime_unit.py         # Non-model-backed: joint_module resolves the new dir
                              #   correctly; model-backed: load through Engine/load_clef
  test_cli.py                  # ember model list/pull/rm with the Anaconda entry; doctor
                              #   output; default resolves to the Anaconda entry when unset
  test_mcp_tool.py             # Model-backed: advise end-to-end against the new default, locally
```

**Structure Decision**: No new top-level module, package, or service. This feature is scoped
to additive changes inside the existing single Python package (`ember/`), touching the model
registry (including a minimal, additive S3-compatible download branch — not the engine's
loader, which remains unmodified) and documentation/tests that already cover the
registry-generic code paths. This matches the spec's explicit "no new abstraction layer"
scope decision (Clarification 2) and Article XV.

## Phase 0: Outline & Research

> **Status**: COMPLETE → [research.md](./research.md).

**Outcome**: Six decisions (R1–R6), plus two implementation-time addenda to R3 and a
post-implementation critical-review addendum to R5. The central risk resolves favorably: the
first concrete Anaconda-published decision model is Anaconda's own model-catalog distribution
of Cloudflare's Clef/Clef-flash artifact (verified against Anaconda's internal Jira and
Slack), so the existing loader needs no modification and no new provider-abstraction layer is
required — directly matching the spec's Clarification 2 scope choice. The one real open
implementation detail (the download API shape for `ember model pull`) was resolved at
`/speckit.implement` time (R3-addendum, R3-addendum-2, and a maintainer correction in
R3-addendum-3) rather than guessed: a plain AWS S3 bucket, made available when ember runs on
Anaconda's hosted platform, accessed via a new `boto3` dependency — **one new dependency**,
justified per Article XV §15.2, not "no new dependencies" as this section originally stated.

## Phase 1: Design & Contracts

> **Status**: COMPLETE.

**Artifacts**:
- [data-model.md](./data-model.md) — `ModelSpec` extension (if any), the default-selection
  value, and the (unchanged) remote-endpoint entities inherited from
  `specs/001-remote-inference-servers/`.
- [contracts/model-registry.md](./contracts/model-registry.md) — the registry entry contract
  Anaconda models must satisfy to be listed/pulled/selected/removed like Clef models.
- [contracts/hosted-endpoint.md](./contracts/hosted-endpoint.md) — confirms the Anaconda-hosted
  path reuses the existing `server_url`/`auth_token`/`auth_header` contract from
  `specs/001-remote-inference-servers/contracts/` with no new fields.
- [quickstart.md](./quickstart.md) — runnable validation: default-model resolution, explicit
  Anaconda/Clef selection, and (if a hosted endpoint is available) the remote path.

### Modules to change

| Module | Change |
|--------|--------|
| `ember/models.py` | **Shipped**: added `anaconda-flash` + `anaconda-clef` `ModelSpec` entries to `REGISTRY`; changed `DEFAULT` from `"flash"` to `"anaconda-flash"`; added the `ModelSource` `StrEnum` (`HUGGING_FACE`/`ANACONDA_S3`), dispatched on `spec.source` in `pull()`/`resolve_dir()`/`remove()` — R3-addendum's Option 2, confirmed and implemented. 360 lines (under the Article X §10.3 400-line ceiling after the `ember/cfg/anaconda_s3.py` split below) |
| `ember/cfg/anaconda_s3.py` | **Shipped (new file, 2026-10-08)**: `s3_client()`/`download()` — direct `boto3` AWS S3 download logic (no custom endpoint_url; research R3-addendum-3), split out of `ember/models.py` to pay down a transient Article X §10.3 sizing violation (150 lines, 100% test coverage); mirrors the existing precedent that `ember/cfg/paths.py` already owns `anaconda_s3_cache()` |
| `ember/serving/runtime.py` | **No change for this feature** (research R2: identical artifact shape; existing loader already handles it) — confirmed unmodified by this feature. Separately simplified the same day when Article V was redefined (removed `_classify_dir`/`skip_integrity`); see the constitution-amendment decision note, not this feature's own scope |
| `ember/serving/integrity.py` | **Deleted the same day** as part of the separate Article V redefinition (constitution 3.0.0) — not a change made by this feature; noted here only so this table does not claim a file still exists that does not |
| `ember/commands/doctor.py`, `ember/commands/models.py` | **No change** — confirmed; already registry-generic, covered by new tests |
| `ember/cfg/config.py` | **Shipped**: `DEFAULTS["model"]` updated to `"anaconda-flash"`; four new AWS S3 connection keys added (`anaconda_s3_access_key_id`, `anaconda_s3_secret_access_key`, `anaconda_s3_region`, `anaconda_s3_bucket`) |
| `ember/cfg/paths.py` | **Shipped**: added `anaconda_s3_cache()` (pure path computation, not eagerly created — see research R5 defect fix) |
| `README.md`, `COMPATIBILITY.md`, `ember/agent_kit/*` | **Shipped**: default-model source framing updated (Anaconda-hosted distribution preferred, Cloudflare's public repo a supported alternative source for the same model); no kit number re-measurement needed (research R6) |
| `.specify/memory/constitution.md` | Article I unaffected, no amendment required for the hosted-endpoint path; **§10.18 migration debt updated separately** to record `ember/models.py`'s new line count (see Constitution Check below) |

### Tests to add

| Test file | Coverage |
|-----------|----------|
| `tests/test_runtime_unit.py` | Model-backed: load the Anaconda registry entry through the existing, unmodified `Engine`/`load_clef`; non-model-backed: `joint_module` resolves the Anaconda directory correctly |
| `tests/test_cli.py` | `ember model list` includes Anaconda entries with correct metadata; `ember model pull <anaconda-key>` / `ember model rm <anaconda-key>`; `ember doctor` reports the new default as the selected model when unconfigured |
| `tests/test_mcp_tool.py` | Model-backed: `advise` end-to-end against the new Anaconda default, locally |
| `tests/test_agent_kit.py` | Confirm kit instructions/skill content remains internally consistent after any default-model framing update |

## Constitution Check — Post-Implementation Re-Evaluation (2026-10-08)

> Revisited after implementation diverged from this plan's original single-entry,
> no-new-dependency design (see `tasks.md`'s implementation-status note and
> `research.md` R3-addendum/R3-addendum-2). Findings below reflect the actual shipped code,
> not the pre-design assumptions.

- **Article I**: unaffected; no amendment required. PASS.
- **Article II**: PASS — the external `advise` response shape is unchanged; no model-loading
  adaptation needed (research R2).
- **Article III**: PASS — no kit number re-measurement needed (research R6); default-source
  framing updated in README.md/COMPATIBILITY.md/agent_kit.
- **Article IV**: PASS — unaffected.
- **Article V** ("Model Loading", retitled 2026-10-08 — see
  `vault/decisions/2026-10-08-article-v-redefined-model-loading.md`): PASS — both new
  `REGISTRY` entries (`anaconda-flash`, `anaconda-clef`) target the same commit SHAs as the
  existing `flash`/`full` entries (download convenience), since they redistribute the
  identical artifacts. No integrity-hash verification occurs for any entry (`integrity.py`
  deleted separately the same day, not as part of this feature's own scope).
- **Article VI**: PASS — unaffected.
- **Article X §10.7 (enums)**: PASS — `ModelSource` is correctly a two-member `StrEnum`, not a
  bare string or boolean flag, per the fixed-set-value rule.
- **Article X §10.3/§10.18 (sizing / migration debt)**: **PASS (resolved 2026-10-08).**
  `runtime.py` is confirmed unchanged by this feature (`integrity.py` no longer exists — it
  was deleted the same day by the separate Article V redefinition, not by this feature).
  `ember/models.py` temporarily grew to 470 lines adding the `ModelSource` enum and the S3
  download path — over the 400-line ceiling — and was briefly recorded as constitution §10.18
  migration debt during `/speckit.analyze` remediation. That debt was then paid down in the
  same feature (`/speckit.implement`, tasks.md T032): the S3-compatible download logic
  (`s3_client`/`download`, formerly `_s3_client`/`_download_anaconda_s3`) was split into a new
  module, `ember/cfg/anaconda_s3.py` (150 lines, 100% test coverage), mirroring the existing
  precedent that `ember/cfg/paths.py` already owns `anaconda_s3_cache()`. `ember/models.py` is
  now 360 lines, under the ceiling; the §10.18 entry has been removed (see the corresponding
  constitution amendment) since the debt no longer exists.
- **Article XIII**: PASS — the engine layer remains the only place model-loading logic lives;
  the S3-compatible download path lives in the shared config layer (`ember/cfg/anaconda_s3.py`,
  alongside `ember/cfg/paths.py::anaconda_s3_cache()`), not in `runtime.py`/`serving/`; no
  leakage into MCP/HTTP. A `TYPE_CHECKING`-guarded, `# cycle:`-tagged import breaks the
  `ember.cfg` ↔ `ember.models` type-only reference per Article X §10.5.
- **Article XIV**: PASS — unaffected; existing 503/actionable-error behavior generalizes. The
  post-implementation critical review (research R5) additionally hardened this: uncaught
  `botocore` exceptions are now wrapped as `RuntimeError` so a bad bucket/credential/endpoint
  produces the same actionable-error standard as the pre-existing disk-space check, rather than
  a raw traceback.
- **Article XV**: **PASS, with a documented complexity addition.** The design is the simplest
  viable solution that actually satisfies FR-001–FR-012 given the real constraint research
  surfaced (a plain AWS S3 bucket, not HF-Hub-compatible, is what Anaconda's hosted platform
  provides) — a two-member enum plus one new dependency (`boto3`) is minimal for that fact,
  not speculative generality. This is more than the pre-design plan anticipated ("no new
  dependency"), and that increase is justified here and in the vault decision note, per
  §15.1's documentation requirement.

## Complexity Tracking

> The Article X §10.3 sizing violation (`ember/models.py` briefly at 470 lines) was recorded
> as constitution §10.18 migration debt during `/speckit.analyze` remediation and then paid
> down in the same feature via a module split (`tasks.md` T032) — no outstanding Complexity
> Tracking item remains for it. The one durable complexity addition is the `boto3` dependency,
> justified below and in `pyproject.toml`.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| New dependency: `boto3` (+ `boto3-stubs[s3]`) | Anaconda's hosted platform makes a plain AWS S3 bucket available, not an HF-Hub-compatible API (R3-addendum-3) | A hand-rolled HTTP client or wrapping the Metaflow-scoped `AnacondaModelClient` were both rejected (research R3-addendum); `boto3` is the standard, mature client for AWS S3 (Article XV §15.2) |
