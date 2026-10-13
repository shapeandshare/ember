# Feature Specification: Conda Release — ember on a Conda Channel

**Feature Branch**: `008-conda-release`

**Created**: 2026-10-12

**Status**: Draft

**Input**: User description: "we need a conda release of ember"

## Context

ember reaches users today through the `ember-advise` wheel on PyPI (`uv tool install`), pinned
git installs, the MCP Registry, and the Claude Code plugin. Users who manage their Python
environments with conda, mamba, or pixi have no conda-native door: installing ember means
leaving their environment toolchain for a separate one.

This feature adds one more equal distribution door: a conda package for the `ember-advise`
distribution on conda-forge, installed with the ecosystem's own tools and carrying the same
product — the CLI, the MCP server, the agent kit, and the same tested dependency series. It is
a new door, not a new product: names, behavior, the agent contract, device rules, and
dependency-pinning obligations are unchanged (constitution Articles I, III, V, VI).

Four repo rules shape the non-negotiables below: the distribution name stays `ember-advise`;
model weights are never redistributed and keep downloading at runtime (Article I); dependency
ranges stay anchored to tested versions — a channel that cannot satisfy them gets no artifact
rather than a widened one (Article V); and verification is real — one model-backed run per
platform at first publication, a no-model smoke for every release after (Article VII).

## Clarifications

### Session 2026-10-12

- Q: Which channel should the conda release target? → A: conda-forge — the community
  standard, MIT-compatible, with automated version updates from PyPI and no publishing
  credentials in this repository.
- Q: Which platforms must the first conda release support? → A: osx-arm64 (local, the tested
  MPS path) and linux-64 (servers), each with a model-backed verification run.
- Q: Should conda ride every release automatically? → A: Yes — version-synced as part of the
  release contract via conda-forge's automated version updates, with drift covered by the
  distribution checks.
- Q: How often must the conda artifacts pass a model-backed verification run? → A: Once per
  platform at first publication; later releases ride the committed lock with the no-model
  smoke, and a fresh run happens only when something breaks.
- Q: Which device must linux-64's model-backed verification run exercise? → A: CUDA on
  NVIDIA hardware, reusing the AWS GPU deployment path (the flagship Linux server mode).
- Q: Where should the locks and verification records live? → A: Locks are committed in the
  repository so the distribution checks can gate them; the verification record goes into
  COMPATIBILITY.md's verified state plus a vault note with the run details.
- Q: conda-forge cannot satisfy `torchvision>=0.29,<0.30`; hold the release or diverge? → A:
  Governed divergence — the conda recipe pins the newest channel-available series
  (`torchvision >=0.28,<0.29`), validated by the first-publication model-backed run and
  retired when conda-forge ships 0.29.x.
- Q: conda-forge still cannot install the declared ranges as a set (huggingface_hub floor;
  torchvision/pytorch pairing); hold or deepen the divergence? → A: Deepen it (constitution
  v3.4.0) — the conda artifact pins the newest co-installable stack
  (`pytorch >=2.12,<2.14`, `torchvision >=0.27,<0.29`, `huggingface_hub >=1.32,<2`),
  validated by the first-publication model-backed runs and retired when conda-forge catches
  up.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A conda user installs ember and gets a working `advise` (Priority: P1)

A developer who lives in conda creates an environment, installs ember from conda-forge with
conda, mamba, or pixi, and gets the same product: the `ember` CLI, the MCP server, and a
working `advise` after the usual weight download. No uv, no pip, no leaving the environment.

**Why this priority**: It is the entire request; everything else protects it.

**Independent Test**: On a clean machine with only a conda distribution installed, follow just
the published instructions — create an environment, install, `ember model pull`, `ember
doctor`, one `advise` through the documented path — and get a calibrated answer.

**Acceptance Scenarios**:

1. **Given** a fresh conda environment, **When** the documented install command runs, **Then**
   every runtime dependency resolves from conda channels with no pip step, and `ember`, `gut`,
   `ember-advise`, and `ember-mcp` are all available in the environment.
2. **Given** the installed environment, **When** `ember doctor` runs, **Then** it reports
   platform, dependencies, model, and server readiness in the same form as the PyPI install.
3. **Given** weights pulled and the server running, **When** an `advise` request is served,
   **Then** the response carries calibrated probabilities and the token split, identical in
   shape to the PyPI install.
4. **Given** a conda environment whose Python version is outside the supported range, **When**
   the install is attempted, **Then** the solver refuses and the supported version is visible
   as the constraint.

---

### User Story 2 - The artifact is version-locked to the release and verified on hardware (Priority: P1)

Whatever lands on the channel is the release: the same version string, the same dependency
constraints as the published distribution, one recorded model-backed verification run per
platform at first publication, and a no-model smoke — against the committed lock — for every
later release.

**Why this priority**: A conda artifact that quietly carries different dependency ranges would
be a different, untested product; keep pins honest.

**Independent Test**: Inspect the channel artifact's version and constraints against the
release; run the no-model smoke from the committed lock; for a platform's first publication,
re-run the recorded model-backed steps on real hardware.

**Acceptance Scenarios**:

1. **Given** release vX.Y.Z is published, **When** the channel artifact is inspected, **Then**
   its version is X.Y.Z and its dependency constraints mirror the release's.
2. **Given** a platform's first publication, **When** the model-backed run (server start plus
   one advise; MPS on Apple Silicon, CUDA on NVIDIA hardware) completes, **Then** the result
   is recorded in COMPATIBILITY.md and a vault note, tied to the lock; every later release
   passes the no-model smoke against the committed lock, and a failed smoke triggers a fresh
   model-backed run before that release is treated as shipped.
3. **Given** the tested dependency series cannot be satisfied on some platform, **When** the
   package is built, **Then** that platform is omitted rather than shipping with widened
   ranges — the approved co-installability divergence (FR-004) aside.
4. **Given** any platform artifact, **When** its contents are inspected, **Then** it contains
   no model weights and no user state — it carries only the tool, well under 50 MB.

---

### User Story 3 - Future releases keep the channel current (Priority: P2)

As releases land, the newest version on the channel tracks the release, so `conda install`
users and `uv` users are on the same version; drift is detectable rather than silent.

**Why this priority**: A release door that goes stale silently splits the user base across
versions; the repo's release contract exists to prevent exactly that.

**Independent Test**: After a release completes, inspect the channel for the new version; run
the smoke against an unpublished version and see the drift reported, not swallowed.

**Acceptance Scenarios**:

1. **Given** a new ember release, **When** its PyPI upload completes, **Then** the newest
   conda-forge version equals the release within one day.
2. **Given** the channel lagging the newest release, **When** the documented sync check runs,
   **Then** it reports the drift actionably rather than passing silently.

---

### User Story 4 - The docs present conda as an equal install path (Priority: P2)

A reader of the README (and therefore the site, which renders from it) finds the conda
instructions next to the uv and git installs: the channel, the command, and the supported
platforms — enough to complete the install without leaving the page.

**Why this priority**: A door nobody can find is not a door; the repo's naming and install
documentation are part of the public contract.

**Independent Test**: Hand only the README to a conda user on a clean machine; they complete
the install.

**Acceptance Scenarios**:

1. **Given** README's install section, **When** a conda user scans it, **Then** the conda
   command, channel, and supported platforms are stated beside the existing install paths.
2. **Given** the naming table, **When** the conda row is read, **Then** the distribution name
   stays `ember-advise` and the command names match the PyPI install.

---

### User Story 5 - Provenance and compliance hold like every other door (Priority: P3)

The artifact's metadata is correct (name, version, MIT license, project links), the build
source is reviewable and reproducible from the released source, and publishing stores no
long-lived credentials — matching the existing release posture (Trusted Publishing, no stored
secrets).

**Why this priority**: Hygiene rather than capability, but a distribution door is public API
and the repo's release contract already governs it.

**Independent Test**: Inspect the artifact metadata; audit the publishing path for stored
secrets; rebuild from the published source.

**Acceptance Scenarios**:

1. **Given** the channel artifact metadata, **When** inspected, **Then** license,
   description, and project links match the project.
2. **Given** the publishing path, **When** audited, **Then** it uses channel automation,
   OIDC, or short-lived credentials — no stored long-lived secrets.
3. **Given** the build source, **When** inspected, **Then** it builds from a released version,
   never an unreleased branch.

---

### Edge Cases

- **Unsupported platform or Python version** (Intel Mac, Windows, Python other than 3.12):
  the install MUST fail with the constraint visible — no silent wrong-environment result.
- **Conflicting dependency versions already in the environment** (a different model-runtime
  series, an older MCP SDK): the solver's resolution is the arbiter; ember's constraints are
  never widened to force a fit.
- **The channel's Apple Silicon build of the model runtime may not support the MPS
  accelerator path**: this is a pre-ship feasibility gate — if it cannot be verified, the
  platform waits and the limitation is recorded, rather than shipping a build whose primary
  local path is broken.
- **CPU-only Linux hosts**: they run the documented fallback; the platform's recorded
  verification exercises CUDA, and CPU mode is not a second model-backed gate.
- **Channel priority mixing** (the channel is not among the user's defaults): the install
  command and its channel flag must be documented verbatim; a user following the docs
  verbatim must not hit a resolution surprise.
- **Channel lag**: the channel's newest version behind the release is detected by the
  distribution checks, not discovered by users.
- **`ember eval`** continues to require a checkout; the conda artifact is for using ember,
  not the benchmark tooling — documented as with the PyPI install.
- **A release fails the no-model smoke**: it is answered by a fresh model-backed run or a
  fix, and the outcome is recorded — the failure is never silently kept.
- **The locked environment needs to move** (a security patch, a dependency-range change): the
  lock is updated deliberately and a fresh model-backed run repeats before the new lock is
  committed.
- **Redistribution boundary**: weights and media never enter any artifact; the install stays
  well under 50 MB on every platform.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A conda package for the `ember-advise` distribution MUST be published to
  conda-forge and installable with conda, mamba, or pixi; all runtime dependencies MUST
  resolve from conda channels, with no pip step required by the documented install.
- **FR-002**: The installed package MUST provide the same commands as the published
  distribution: `ember`, `gut`, `ember-advise`, and `ember-mcp`.
- **FR-003**: The conda package version MUST equal the corresponding ember release version,
  and builds MUST come from the released source, never an unreleased branch.
- **FR-004**: The conda package MUST carry the release's dependency constraints — the model
  runtime pinned to the tested minor series and Python 3.12 (the supported version) — and MUST
  NOT ship a platform with widened ranges when its channel dependencies cannot satisfy them.
  A recorded, approved exception covers co-installability: the conda artifact pins the newest
  stack conda-forge can install together — `pytorch >=2.12,<2.14`, `torchvision >=0.27,<0.29`,
  `huggingface_hub >=1.32,<2` (below the declared floor) — validated by the first-publication
  model-backed runs and converged back when the channel catches up (constitution v3.4.0).
- **FR-005**: The conda release MUST support osx-arm64 and linux-64. Each platform gets one
  model-backed run (server start plus one advise on real hardware), recorded at first
  publication — MPS on Apple Silicon for osx-arm64, CUDA on NVIDIA hardware for linux-64
  (reusing the AWS GPU deployment path); later releases ride the committed lock (FR-015) with
  the no-model smoke (FR-016), and a failed smoke triggers a fresh model-backed run before
  the release is treated as shipped.
- **FR-006**: No artifact MAY contain model weights, user state, or secrets; weights remain a
  runtime download under the existing rules (constitution Article I).
- **FR-007**: The release process MUST keep conda-forge in version sync with every ember
  release through the channel's automated version updates (a feedstock version PR opened from
  each PyPI release), with the feedstock stewarded so updates merge promptly; drift MUST be
  reported by the project's checks.
- **FR-008**: The publishing path MUST NOT store long-lived credentials in this repository or
  its workflows; conda-forge's automated version updates carry each release, so no publishing
  credential is needed here.
- **FR-009**: Package metadata MUST carry the correct name, version, MIT license, and project
  links (repository, homepage).
- **FR-010**: The conda install path — channel, command, supported platforms — MUST be
  documented in README.md beside the existing install paths (and therefore on the site), and
  the naming table MUST stay consistent with the distribution-name rules.
- **FR-011**: The project's distribution checks (`tests/test_distribution.py` contract) MUST
  cover the conda-forge distribution's version, metadata, and committed-lock sync, so drift
  fails the checks.
- **FR-012**: The build source MUST be reviewable and reproducible from the released source
  (the conda-forge feedstock recipe), so a third party can rebuild the artifact.
- **FR-013**: Unsupported platform or Python attempts MUST fail actionably, with the
  constraint visible, never producing a broken or silently wrong environment (Article XIV).
- **FR-014**: Installing via conda MUST NOT change any existing behavior — CLI, MCP, config,
  weight management, and local/self-hosted/remote modes are identical to the PyPI install;
  only the delivery door differs.
- **FR-015**: Each supported platform MUST have a hash-pinned lock of its verified dependency
  environment, committed in the repository so the exact verified set is reproducible and the
  distribution checks can gate it; the lock moves only as a deliberate act, and moving it
  repeats the model-backed run before the new lock is committed.
- **FR-016**: Every release MUST pass a no-model smoke against the committed lock —
  environment created from it, the CLI and `ember doctor` run, and the MCP server imports
  without the model stack — which MUST be runnable without a model or accelerator hardware;
  making a release starts the model zero times.
- **FR-017**: Each recorded model-backed run MUST be reflected in COMPATIBILITY.md's verified
  state (platform, device, version, lock) and detailed in a vault note, giving the
  verification record a governed, committed home.

### Key Entities

- **Conda channel**: the distribution point users install from (conda-forge — resolved by
  FR-001).
- **Conda artifact**: the per-platform package built from one release, carrying its own
  metadata and dependency constraints.
- **Verified environment lock**: the hash-pinned, per-platform record of the exact dependency
  set that passed the model-backed run; committed and reproducible, and the base every later
  release's smoke tests against.
- **Build source (recipe)**: the reviewable configuration that produces an artifact from the
  released source (the conda-forge feedstock recipe).
- **Version-sync check**: the release-contract check that the channel's newest version matches
  the newest release.
- **Verification record**: a recorded model-backed run (first publication per platform, plus
  any fresh run after a failure or lock move), tied to the lock and environment it ran in, and
  kept in COMPATIBILITY.md's verified state and a vault note.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A conda user on a clean supported machine reaches a working `advise` response by
  following only the documented steps, without leaving the conda ecosystem (zero pip or uv
  steps).
- **SC-002**: Each supported platform carries one recorded model-backed verification run at
  first publication (MPS on Apple Silicon; CUDA on NVIDIA hardware); every later release
  passes the no-model smoke against the committed lock, and making a release starts the model
  zero times.
- **SC-003**: The newest conda-forge version equals the newest ember release within one day
  of the PyPI upload; zero silent drift beyond that.
- **SC-004**: Version, metadata, or lock drift between the channel and the release is caught —
  the release smoke fails when the channel lacks the version, the lock-integrity check fails
  when the lock is stale — and the check logic is exercised in the test suite.
- **SC-005**: Zero model-weight bytes in any artifact; artifact downloads stay well under
  50 MB (the tool without weights).
- **SC-006**: An install attempt on an unsupported platform or Python version yields an
  actionable constraint refusal, never a broken environment (exercised as a test).
- **SC-007**: A reader can complete the conda install from README alone, and the commands
  found there work as written.

## Assumptions

- **conda-forge acceptance**: conda-forge accepts MIT-licensed Python packages and public
  source; the project submits a recipe once for community review and stewards the resulting
  feedstock (version updates then flow automatically from PyPI).
- **Feasibility snapshot (2026-10-12)**: a live solve resolved the conda environment on both
  platforms only via the recorded co-installable divergence below (pytorch 2.12/2.13,
  torchvision 0.27/0.28, huggingface_hub 1.32.0); the MCP SDK (mcp 2.3.0) is in range. The full runtime dependency set MUST be confirmed to resolve on
  conda-forge before the first artifact ships (FR-001/FR-004). Whether conda-forge's Apple
  Silicon runtime build supports the MPS path MUST be verified (FR-005) before an osx-arm64
  artifact ships; if it cannot, that platform waits and the limitation is recorded.
- **The conda stack divergence is approved and recorded (constitution v3.4.0)**: conda-forge
  cannot install the declared set for Python 3.12 (no `huggingface_hub` in `[1.33,2)`;
  `torchvision` pairs only with `pytorch <2.14`), so the conda artifact pins the newest
  co-installable stack — `pytorch >=2.12,<2.14`, `torchvision >=0.27,<0.29`,
  `huggingface_hub >=1.32,<2` — validated by the first-publication model-backed runs and
  reverted when conda-forge catches up.
- **Verification scope**: the recorded conda runs verify the artifact and its locked
  environment on real hardware; ember's own code changes remain covered by the pre-merge
  model-backed suite (constitution Article VII), since model starts cannot gate every release.
- **Verification economy**: no small test model suitable for CI exists yet; when one is
  found, model-backed checks can extend toward every build — nothing here blocks that path.
- **Weights stay external**: the ~18 GB weights continue to download from Hugging Face at
  runtime; no channel redistributes them (constitution Article I).
- **The release pipeline remains the version source of truth**: the conda artifact is built
  from a released version, so the channel can never lead the release.
- **No constitution change**: this feature adds a door; it does not change names, the agent
  contract, device rules, or dependency-pinning obligations. A channel that would force such a
  change (for example, widening the model-runtime range) is a governed change, not a side
  effect of this feature.
- **`ember eval`** continues to require a checkout; the conda artifact is for using ember, not
  the benchmark tooling.
