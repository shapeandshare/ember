# Feature Specification: Anaconda Models as a First-Class Preferred Provider

> **Superseded (2026-10-08).** The `ANACONDA_S3` `REGISTRY`-entry subsystem this spec
> describes (`anaconda-flash`/`anaconda-clef` registry entries, `ModelSource` enum,
> `s3_bucket`/`s3_prefix` fields, the shared `anaconda_s3_bucket` config key) was removed
> entirely per direct maintainer direction: a hosted deployment already has its own S3
> model location (`EMBER_MODEL_S3_URI`, see README.md "Hosted deployment: a model location
> supplied at start time"), so a parallel named-registry path for the same thing was
> unnecessary complexity. `REGISTRY` reverted to Hugging-Face-sourced entries only
> (`flash`/`full`); `DEFAULT` reverted to `"flash"`. See
> `vault/decisions/2026-10-08-simplify-remove-anaconda-s3-registry-entries.md` for the full
> rationale. This spec, `plan.md`, `research.md`, `data-model.md`,
> `contracts/model-registry.md`, and `tasks.md` are kept for an honest historical record of
> what was built and why it was later simplified away — do not implement against them.

**Feature Branch**: `002-anaconda-models-provider`

**Created**: 2026-10-07

**Status**: Draft

**Input**: User description: "We will be supporting anaconda models as a first class preferred provider of decision models"

## Clarifications

### Session 2026-10-07

- Q: What does "Anaconda models" refer to? → A: Both — Anaconda-published decision models
  that run locally (same pattern as the existing Cloudflare Clef models), **and**
  Anaconda-hosted decision models reachable over the network when ember is running on
  Anaconda's own platform.
- Q: What does "first class preferred provider" mean for scope? → A: No new
  provider-abstraction layer. Anaconda decision models are added to the existing model
  registry (same shape/lifecycle as Clef today) and become the recommended/default choice
  going forward; Clef models remain fully supported.
- Q: Are specific Anaconda model names/repos decided yet? → A: Not yet. Exact model
  identifiers, revisions, and hosted-endpoint details are a planning-phase research item.
  This spec defines the capability and user-facing behavior, not the pinned model names.
- Q: How should ember notify an existing user whose default model changes from Clef to
  Anaconda on upgrade? → A: No notification mechanism is required. ember has no installed
  consumer base to migrate; there is no backward-compatibility, legacy-notice, or
  one-time-warning requirement for this change. Ship the new default directly.
- Q: Should ember automatically detect that it is running on Anaconda's own platform and
  switch to the Anaconda-hosted endpoint on its own? → A: No. ember never auto-detects its
  environment; using the Anaconda-hosted endpoint always requires explicit configuration
  (server URL and any credential) via the existing opt-in remote-endpoint mechanism — no
  implicit network behavior based on environment detection.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run an Anaconda decision model locally by default (Priority: P1)

A user installs ember fresh (or upgrades an existing install) on their Apple Silicon Mac
and runs `ember model pull` / starts the server without specifying a model. Instead of
defaulting to Cloudflare's Clef, ember downloads and serves an Anaconda-published decision
model, because Anaconda models are now the preferred, default choice.

**Why this priority**: This is the core of "first class preferred provider" — the default
experience for every new and existing user must reflect the new preference. Without this,
the feature has no observable effect for the majority of users who never touch config.

**Independent Test**: On a clean config (no `model` override set via flag, env, or config
file), run `ember model pull` (or let autostart pull on first `advise` call) and confirm
the resolved model is an Anaconda registry entry, not Clef.

**Acceptance Scenarios**:

1. **Given** a fresh ember install with no model preference configured, **When** the user
   starts the server or calls `advise` for the first time, **Then** ember selects an
   Anaconda decision model as the default and reports that model's name in `ember doctor`
   / `ember model list` / the `/health` endpoint.
2. **Given** a user who has never set `EMBER_MODEL` or a `model` config key, **When** they
   run ember on a version including this feature, **Then** the server starts with the new
   Anaconda default — no migration path, legacy-mode flag, or compatibility notice is
   required.
3. **Given** a user who explicitly sets `model=flash` (or `full`), **When** they start
   ember, **Then** their explicit choice is respected and Clef runs unchanged.

---

### User Story 2 - Choose any supported Anaconda model explicitly (Priority: P1)

A user who wants a specific Anaconda decision model (not just the default) selects it the
same way they already select Clef today — by name, via CLI flag, environment variable, or
config file.

**Why this priority**: Users need the same selection ergonomics they already have for
Clef's `flash`/`full`; without this, Anaconda support is default-only and not a true
peer in the registry.

**Independent Test**: Run `ember model list` to see all registered Anaconda and Clef model
names, then `ember model pull <anaconda-model-name>` and `EMBER_MODEL=<anaconda-model-name>
ember start` and confirm the chosen model loads and serves requests.

**Acceptance Scenarios**:

1. **Given** the model registry includes one or more Anaconda entries, **When** the user
   runs `ember model list`, **Then** each Anaconda model appears with its name, parameter
   size, cached status, and disk usage, indistinguishable in format from Clef entries.
2. **Given** a user names a valid Anaconda model via `--model`, `EMBER_MODEL`, or the
   config file's `model` key, **When** they start the server, **Then** that exact model is
   loaded and used for all `advise` calls in that session.
3. **Given** a user names an unknown model, **When** they attempt to pull, start, or
   remove it, **Then** ember reports a clear error listing valid registered model names
   (existing behavior, unchanged, now including Anaconda names in the listed choices).

---

### User Story 3 - Use Anaconda-hosted models when running on Anaconda's platform (Priority: P2)

A user running ember inside Anaconda's own hosted platform (rather than on a personal
Apple Silicon Mac) configures ember to send `advise` requests to an Anaconda-hosted
decision-model endpoint instead of running inference locally.

**Why this priority**: Not every environment can run local MPS inference (e.g., shared or
non-Apple-Silicon platform environments). This extends the feature to Anaconda's hosted
offering using the existing opt-in remote-endpoint mechanism, so the platform's own
infrastructure becomes a first-class source of Anaconda decision models without requiring
local weights.

**Independent Test**: Configure the existing remote-endpoint settings (server URL +
credential) to point at an Anaconda-hosted decision-model endpoint, with no local model
pulled, and confirm `advise` calls succeed end-to-end and clearly identify that they were
served by the configured Anaconda-hosted model.

**Acceptance Scenarios**:

1. **Given** a user has been issued access to an Anaconda-hosted decision-model endpoint,
   **When** they configure ember to use it (server URL and any required credential),
   **Then** `advise` calls are sent to that endpoint and responses are usable identically
   to a local response (same shape, same calibrated probabilities).
2. **Given** a user has configured an Anaconda-hosted endpoint, **When** they inspect
   `ember doctor` / `/health`, **Then** ember clearly reports that it is using a
   remote Anaconda-hosted model (name/identifier) rather than local inference, so the
   user is never confused about where their `state` and answers are being sent.
3. **Given** no Anaconda-hosted endpoint is configured, **When** the user runs ember
   normally, **Then** behavior is unchanged from local-only operation (this scenario is
   strictly opt-in, consistent with the existing remote-inference opt-in behavior).

---

### Edge Cases

- What happens when an Anaconda model's weights fail to download (network failure, revoked
  access, disk space) during `ember model pull`? → Must fail with the same clear,
  actionable error pattern Clef pulls already use (disk-space check, retry guidance).
- What happens when a user has only Clef cached locally and runs a version of ember that
  now defaults to an Anaconda model? → The same "download happens on explicit pull / first
  use" pattern already in place for Clef applies unchanged: the new Anaconda default is
  pulled the same way the old Clef default was, with no additional consent step beyond
  what already exists today.
- How does the system handle a configured Anaconda-hosted endpoint that becomes
  unreachable mid-session? → Must surface the same actionable connection/timeout error the
  existing generic remote-endpoint feature already defines, not a new/different failure
  mode.
- What happens if both a local Anaconda model is cached and a remote Anaconda-hosted
  endpoint is configured? → The existing precedence rules (explicit endpoint config governs
  whether requests are local or remote) apply unchanged; this feature does not introduce
  a second, competing selection mechanism.
- What happens when an Anaconda model's capabilities differ from Clef's (e.g., different
  max context length, different supported question types)? → Differences must be
  documented per-model (as `COMPATIBILITY.md` already does per model), and ember must not
  assume Clef-specific limits apply to Anaconda models.
- **Known limitation at initial ship (added 2026-10-08, post-implementation)**: the exact
  object-key layout (`s3_prefix`) Anaconda's catalog storage uses for each model's files was
  not independently verifiable at implementation time — the only matching ingestion code
  found in this org's infrastructure produces a different artifact shape (GGUF-quantized,
  UUID-keyed) than the full HF-snapshot directory ember's loader needs. The shipped registry
  entries carry an explicitly-marked, unverified placeholder prefix. A real
  `ember model pull anaconda-flash`/`anaconda-clef` against the live bucket may therefore
  fail with a clear "no objects found" error (FR-009's actionable-failure standard still
  holds — this is a correct, fail-closed outcome, not a crash or a wrong-data outcome) until
  the prefix is corrected against the real bucket contents. This does not block FR-001–FR-007,
  FR-009–FR-012 (registry shape, defaulting, selection, error clarity, documentation, and
  no-migration-notice are all independently satisfied and verified by tests); it is narrowly
  about FR-008's "verify the integrity of **downloaded** artifacts" when nothing has actually
  downloaded yet because the location itself needs one more correction. See
  `research.md` R3-addendum-2 and `COMPATIBILITY.md`'s per-entry notes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The model registry MUST support one or more Anaconda-published decision
  models, registered with the same metadata shape already used for Clef models (name,
  source repository/identifier, parameter size, approximate download size, pinned
  revision, integrity hashes).
- **FR-002**: The system MUST change its default model selection to an Anaconda decision
  model for installs and sessions where the user has not explicitly configured a model
  preference (via CLI flag, environment variable, or config file).
- **FR-003**: The system MUST preserve full support for existing Clef models (`flash`,
  `full`); users who explicitly select a Clef model MUST continue to get that exact model,
  unaffected by the new default.
- **FR-004**: Users MUST be able to list, pull, select (by name, flag, env var, or config
  key), and remove Anaconda models using the exact same commands and mechanisms already
  used for Clef models — no new or parallel command surface for "Anaconda" specifically.
- **FR-005**: The system MUST report which model (Anaconda or Clef, local or hosted) is
  currently active through existing observability surfaces (`ember doctor`, `ember model
  list`, `/health`), so a user can always tell what is serving their requests.
- **FR-006**: The system MUST allow a user to configure ember to send `advise` requests to
  an Anaconda-hosted decision-model endpoint using the existing opt-in remote-endpoint
  configuration mechanism, without requiring any new, separate "Anaconda hosted mode"
  configuration surface.
- **FR-007**: Local-first behavior MUST be preserved: an unconfigured install remains
  local-only (default Anaconda model running locally), and sending requests to an
  Anaconda-hosted endpoint MUST remain an explicit, opt-in user choice. ember MUST NOT
  auto-detect that it is running on Anaconda's platform and MUST NOT switch to the
  Anaconda-hosted endpoint without explicit configuration (server URL and any credential)
  set by the user or the platform's own bootstrap step — never inferred from the runtime
  environment.
- **FR-008**: The system MUST verify the integrity of downloaded Anaconda model artifacts
  using the same pinning/hash-verification approach already required for Clef models.
- **FR-009**: Error handling, disk-space checks, and download-failure messaging for
  Anaconda models MUST match the existing behavior and clarity standard already provided
  for Clef models.
- **FR-010**: Documentation (README, COMPATIBILITY.md, agent onboarding kit where model
  names are surfaced) MUST reflect Anaconda models as the recommended default while
  continuing to document Clef models as supported alternatives.
- **FR-011**: Users who explicitly configure a Clef model (via flag, env var, or config
  key) MUST have that exact configuration respected; explicit configuration always
  overrides the default, regardless of which model is currently the default.
- **FR-012**: No migration path, legacy-mode flag, deprecation period, or user-facing
  change notice is required for switching the default from Clef to Anaconda. ember has no
  installed consumer base to migrate against; the new default ships directly like any
  other default-value change.

### Key Entities

- **Anaconda Decision Model (registry entry)**: A pinned, named decision model published
  by Anaconda, resolvable and runnable the same way a Clef registry entry is today — name,
  source identifier, parameter size, approximate size on disk, pinned revision, integrity
  hashes, and model category (`kind`).
- **Anaconda-Hosted Endpoint**: A remote inference endpoint, operated by Anaconda, that
  serves one or more Anaconda decision models over the network, configured through the
  existing single-remote-endpoint mechanism (URL plus optional credential) rather than a
  new provider-specific configuration concept.
- **Default Model Preference**: The model ember selects when no explicit user
  configuration is present; this entity's value changes from a Clef model to an Anaconda
  model as a result of this feature, while remaining fully overridable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user running ember with no prior model configuration gets an Anaconda
  decision model loaded and serving `advise` requests without any extra steps beyond what
  is required today to get Clef running (same command count, same setup time class).
- **SC-002**: 100% of users who explicitly configure a Clef model continue to run that
  exact Clef model, with zero unplanned switches to the new Anaconda default.
- **SC-003**: A user can switch between any registered Anaconda model and any registered
  Clef model using identical commands, with no feature-specific documentation beyond the
  model name itself.
- **SC-004**: A user pointed at an Anaconda-hosted endpoint can determine, within one
  command (`ember doctor` or equivalent), whether their `advise` requests are being served
  locally or by the Anaconda-hosted endpoint, with no ambiguity.
- **SC-005**: Zero reports of silent, unexplained network calls to an Anaconda-hosted
  endpoint from an install that did not explicitly configure one.

## Assumptions

- At least one Anaconda-published decision model exists (or will exist by implementation
  time) that is compatible with ember's existing decision-model serving contract (typed
  questions in, calibrated probabilities out) closely enough to reuse the current
  inference pipeline; any incompatibilities are a planning-phase research item, not
  something this spec resolves.
- "Running on Anaconda's platform" means an environment where Anaconda operates and grants
  access to a hosted decision-model inference endpoint reachable over HTTP(S) from the
  user's ember installation — the same transport shape the existing remote-inference
  feature (`specs/001-remote-inference-servers/`) already supports.
- Exact Anaconda model identifiers, pinned revisions, parameter sizes, and hosted-endpoint
  URLs/auth schemes are not yet decided and are explicitly deferred to the planning phase
  (`/speckit.plan`) and its research step, consistent with the user's direction that model
  selection is "not yet decided." This includes the mechanism for picking which single
  Anaconda entry is the default when the registry holds more than one (e.g., an explicit
  `DEFAULT` flag analogous to Clef's `flash`) — a registry/implementation detail left to
  planning, not a product-level ambiguity.
- "Preferred provider" does not require building a new pluggable multi-vendor abstraction;
  it is satisfied by adding Anaconda entries to the existing single registry and changing
  the default, per the user's explicit scope choice.
- Apple Silicon / MPS remains the supported local runtime target for any locally-run
  Anaconda model, consistent with existing project scope (no new hardware targets implied
  by this feature).
- ember has no installed consumer base requiring migration support; the default-model
  change ships without a transition period, compatibility shim, or notice mechanism, per
  the user's explicit direction.
