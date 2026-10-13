# Tasks: Conda Release of ember

**Input**: Design documents from `/specs/008-conda-release/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (recipe, locks, smoke)

**Tests**: TDD is mandatory in this repository (constitution Article XI): every implementation task ships its failing-first test in the **same commit**. This list embeds the test work in each task instead of separate test tasks. `make check` must pass before every commit; model-backed steps run locally/on owned hardware only — never in CI.

**Organization**: Tasks are grouped by user story. **MVP = Setup + Foundational + US1** (the door opens: `conda install -c conda-forge ember-advise` works). Both P1 stories (US1 + US2) gate "shipped": US2's model-backed runs validate the artifact before it counts. US3–US5 land incrementally.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4, US5)
- Exact file paths are in every description

## Path Conventions

Repository root is the working directory. Conda artifacts under `conda/`; tooling scripts under `scripts/`; Make targets under `shared/`; workflows under `.github/workflows/`; tests under `tests/` (flat files); docs at repo root; specs under `specs/008-conda-release/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: The two static conda artifacts every story derives from

- [x] T001 [P] Author `conda/lock-environment.yml` — the dependency-only source spec per `specs/008-conda-release/contracts/locks.md`: `channels: [conda-forge]`; `platforms: [osx-arm64, linux-64]`; `python=3.12`; runtime deps in **conda names**, exactly: `pytorch >=2.14,<2.15`; `torchvision >=0.28,<0.29` (the approved divergence — newest channel series; retired when 0.29.x ships); `transformers >=5.18,<6`; `safetensors >=0.8,<1`; `huggingface_hub >=1.33,<3`; `accelerate >=1.15,<2`; `pillow >=12,<13`; `fastapi >=0.142,<1`; `uvicorn-standard >=0.54,<1`; `pydantic >=2.13,<3`; `mcp >=2.3,<3`; `httpx >=0.28,<1`; `prometheus_client >=0.21,<1`; `boto3 >=1.40,<2`. MUST NOT list `ember-advise`.
- [x] T002 [P] Author `conda/recipe.yaml` — the conda-forge v1 submission snapshot per `specs/008-conda-release/contracts/recipe.md`: `context.version: "0.15.0"` (the release being submitted; **not** wired to commitizen — the feedstock bot carries future versions) and `python_min: "3.12"`; `source.url` = `https://pypi.org/packages/source/e/ember-advise/ember_advise-${{ version }}.tar.gz` with the sdist `sha256` read from PyPI; `build`: `number: 0`, `skip: [win]` (Unix-only), `script: ${{ PYTHON }} -m pip install . -vv --no-deps --no-build-isolation`, and `python.entry_points` with exactly `ember`, `gut`, `ember-advise`, `ember-mcp` mapped to their `[project.scripts]` targets; `requirements.host`: `python ${{ python_min }}.*`, `pip`, `hatchling >=1.27`; `requirements.run` identical to T001 (same conda names and ranges, including `torchvision >=0.27,<0.29`; `python` unconstrained for non-noarch); `tests`: import `ember` with `pip_check: false`; `about`: `license: MIT`, `license_file: LICENSE`, repository URL, the README summary; `extra.recipe-maintainers` with the maintainer's GitHub handle; header comment: "Submission snapshot; the canonical, live recipe is conda-forge/ember-advise-feedstock (bot-updated)."

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The lock, its tooling, and the offline contract checks — required by US2 and US3

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Add the conda contract tests to `tests/test_distribution.py` (failing first), then generate the lock to go green: (a) `conda/recipe.yaml` exists, parses, `context.version` is a valid `X.Y.Z` string, lists the four entry points, its `run` deps include the exact conda names with `torchvision >=0.28,<0.29`, and its `about` metadata is `license: MIT`, `license_file: LICENSE`, and the repository URL; (b) `conda/lock-environment.yml` exists and contains no `ember-advise`; (c) `conda/ember-deps.conda-lock.yml` exists, parses, contains both `osx-arm64` and `linux-64` package sets, and each platform carries a `metadata.input_hash`. Generate with `conda-lock -f conda/lock-environment.yml -p osx-arm64 -p linux-64 --lockfile conda/ember-deps.conda-lock.yml` (conda-lock 4.x); commit the lock. (depends on T001; the recipe assertions need T002)
- [x] T004 Add `tests/test_freeze_conda_lock.py` (failing first) and implement `scripts/freeze_conda_lock.py`: default mode runs the conda-lock command above, renders both per-platform explicit locks (which the smoke installs from), verifies the platforms, and prints a summary; `--check` runs `conda-lock --check-input-hash -f conda/lock-environment.yml -p osx-arm64 -p linux-64 --lockfile conda/ember-deps.conda-lock.yml` and maps exit `4` = in sync → process exit `0`; exit `0` (lock would change) → actionable error naming `make conda-lock`; anything else → error. Tests monkeypatch `subprocess.run` and use `tmp_path` fixtures — no network, no conda-lock required. Script follows house style: `ROOT = Path(__file__).resolve().parents[1]`, why-docstring, `main() -> int`, `if __name__ == "__main__": raise SystemExit(main())`. (depends on T001)
- [x] T005 Add `conda-lock` and `conda-lock-check` targets to `shared/release.mk` (beside `deployment-requirements`), invoking `scripts/freeze_conda_lock.py` and its `--check` mode; update the root `Makefile` header comment target list. (depends on T004)

**Checkpoint**: lock + tooling + offline checks ready. (US1 itself needs only T001–T002.)

---

## Phase 3: User Story 1 - A conda user installs ember and gets a working `advise` (Priority: P1) 🎯 MVP

**Goal**: `ember-advise` is live on conda-forge; a fresh env installs it and runs the CLI.

**Independent Test**: On a clean machine with only conda installed: run the documented install command in a fresh env and get the four CLI aliases and `ember doctor` working (the model-backed half completes in US2).

- [x] T006 [US1] Lint the recipe: `conda-smithy recipe-lint conda/recipe.yaml` (the staged-recipes linter); fix every finding; re-run `make check` to confirm the conda contract tests still pass.
- [x] T007 [US1] Local build smoke (recommended, not required): build the package locally (`conda build conda/`, or the staged-recipes pixi task), then verify in a fresh env that `ember`, `gut`, `ember-advise`, `ember-mcp` are on `PATH` and `python -c "import ember.mcp.mcp_server"` succeeds without importing torch. If local build infra is unavailable, note it and rely on staged-recipes CI.
- [x] T008 [US1] Submit to conda-forge: fork `conda-forge/staged-recipes`, branch from `main`, add `recipes/ember-advise/recipe.yaml`; open a PR titled `Add ember-advise`; comment `@conda-forge/help-python, ready for review!` and the maintainer willingness confirmation; address review; merge → confirm `conda-forge/ember-advise-feedstock` is created and its first build promotes to the channel. (submitted 2026-10-12: PR #35165 open — the maintainer willingness comment from @joshburt is still needed; review/merge/feedstock waits apply)
- [ ] T009 [US1] Verify the door end-to-end (no model): in a fresh env, `conda install -c conda-forge "ember-advise==<version>"`; the four CLI aliases respond to `--help`; `ember doctor` runs to completion without crashing (it may report the model as absent — expected per Article XIV §14.1). Save the exact commands and outputs for the US2 records. Also exercise the unsupported path: in a Python 3.13 environment, attempt `conda install -c conda-forge ember-advise` and confirm the solver refuses with the `python >=3.12,<3.13` constraint visible (SC-006).

**Checkpoint**: the door is open — installable CLI works. (Full "working advise" completes at US2.)

---

## Phase 4: User Story 2 - The artifact is version-locked to the release and verified on hardware (Priority: P1)

**Goal**: the first-publication model-backed runs pass on both platforms and are recorded; the artifact is provably the release.

**Independent Test**: re-run the recorded verification steps on real hardware; inspect the version/metadata/lock as the tests do.

- [ ] T010 [P] [US2] First-publication model-backed run — Apple Silicon (MPS), per `specs/008-conda-release/quickstart.md` §4: environment from the committed lock plus `conda install -c conda-forge ember-advise==<version>`; assert `python -c "import torch; print(torch.backends.mps.is_available())"` prints `True` (the R4 empirical gate — if it does not, stop, record the limitation, and do not ship osx-arm64); `ember model pull`; `ember doctor` (MPS reported); `ember start`; one `advise` request. Capture version, device, lock hash, and outputs for T012. (depends on T009 + T003)
- [ ] T011 [P] [US2] First-publication model-backed run — Linux (CUDA), reusing the AWS GPU deployment path (`make aws-*`): conda environment from the lock on the instance, `EMBER_DEVICE=cuda ember serve`, one `advise` request. Capture the same record fields. (depends on T009 + T003)
- [ ] T012 [US2] Record the verification in `COMPATIBILITY.md` (FR-017): add a conda-forge verified-state subsection naming platform, device (MPS/CUDA), version, lock identity, the torchvision 0.28 series exercised, and the date; update the top "Last verified" line. (depends on T010, T011)
- [x] T013 [US2] Write the vault records: first add `domain/distribution` to `vault/_meta/tags.md`; write `vault/decisions/2026-10-12-conda-forge-release.md` (channel, locks, smoke policy, the approved divergence citing constitution v3.3.0 and its retirement condition) and `vault/discoveries/2026-10-12-conda-forge-dependency-and-tooling-gaps.md` (the channel gaps, the unified-lock/tooling finding, and the MPS evidence); link both from `vault/ember.md`; run `make vault-audit`.

**Checkpoint**: the artifact counts as shipped (spec FR-005/FR-017).

---

## Phase 5: User Story 3 - Future releases keep the channel current (Priority: P2)

**Goal**: the no-model smoke runs per release (CI-able), proving the channel carries the release and the environment works.

- [x] T014 [US3] Add the `conda-smoke` target to `shared/testing.mk` (per `specs/008-conda-release/contracts/smoke.md`): takes `VERSION=<v>`; creates the env from the committed explicit lock with `micromamba create -f conda-$(CONDA_PLATFORM).lock` (platform auto-detected, overridable); installs `micromamba install -c conda-forge "ember-advise==$(VERSION)"`; runs `ember --help`, `gut --help`, `ember-advise --help`, and `ember doctor`; asserts the four entry points exist and `python -c "import sys, ember.mcp.mcp_server; assert 'torch' not in sys.modules"`; **zero model starts**; root `Makefile` header updated. (depends on T003 + T005; end-to-end run is T016)
- [x] T015 [US3] Create `.github/workflows/conda-smoke.yml`: matrix `osx-arm64` (macos-latest) + `linux-64` (ubuntu-latest); SHA-pin `mamba-org/setup-micromamba` with a `# vX.Y.Z` comment; the target builds the env from the explicit lock; run `make conda-lock-check` and `make conda-smoke VERSION=…`; triggers: `workflow_dispatch` (version input) + a weekly `schedule`; retry the install step while the channel catches up (bounded attempts, like `publish-mcp-registry`); `permissions: {}` at workflow level, `contents: read` per job, `persist-credentials: false`; validate with `uvx zizmor@1.30.1 .github/`. (depends on T014)
- [ ] T016 [US3] Validate the smoke for real: run `make conda-smoke VERSION=<published version>` locally and the workflow via dispatch; confirm zero model starts / no weights download, and that the channel version equals the release (SC-003 evidence — note the bot PR timestamp for the sync window); run the smoke against an unpublished version and confirm the failure reports the drift actionably (never passes silently); keep the output for T021.

**Checkpoint**: release-to-channel sync is enforced without model starts.

---

## Phase 6: User Story 4 - The docs present conda as an equal install path (Priority: P2)

**Goal**: README (and therefore the site) presents conda beside uv and git.

- [ ] T017 [US4] Update `README.md`: add the conda install block beside the existing installs (channel `conda-forge`, the exact command, supported platforms `osx-arm64`/`linux-64`, channel-flag note), and add the conda row/note to the naming table (distribution name stays `ember-advise`), plus a troubleshooting line for unsupported Pythons (the solver refuses and names the `>=3.12,<3.13` constraint). Run `make check`; the site picks it up via `scripts/build_site_docs.py` — no `site/_data/docs.json` change (README is entry `overview`).

**Checkpoint**: a reader can complete the install from README alone.

---

## Phase 7: User Story 5 - Provenance and compliance hold like every other door (Priority: P3)

**Goal**: metadata, secrets, and redistribution boundaries verified and recorded.

- [x] T018 [US5] Audit and record provenance: recipe `about` matches (MIT, `license_file: LICENSE`, repository, summary) and mirrors the release; no workflow added by T015 stores credentials; `conda/` contains no secrets and no model weights (`grep -ri "token\|secret\|password" conda/` clean; the lock lists public conda-forge packages only); append the audit outcome to the T013 decision note.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Repository-wide consistency and final gates

- [ ] T019 Update `AGENTS.md`: add the conda watch-out (the door; the `torchvision >=0.28,<0.29` divergence under constitution v3.3.0 with its retirement condition; the smoke never starts the model), a "Where truth lives" row for `conda/`, and a Recent Changes entry.
- [ ] T020 [P] Update the v3.3.0 Sync Impact Report's propagation line in `.specify/memory/constitution.md` from "➖ pending with implementation" to "✅" (AGENTS.md watch-out + COMPATIBILITY.md record landed).
- [ ] T021 Final gates: `make pr-ready`; `make check`; `make test-cov` (floor 94 unchanged); `make vault-audit`; `uvx zizmor@1.30.1 .github/`; walk every scenario in `specs/008-conda-release/quickstart.md`; commit with conventional messages and the fitting scopes (`ci:`, `docs:`, `chore:`; cross-cutting changes may omit scope).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001–T002)**: none — start immediately; both parallel.
- **Foundational (T003–T005)**: needs Setup (T003 needs T001; T005 needs T004) — BLOCKS US2 and US3 (US1 needs only T001–T002).
- **US1 (T006–T009)**: needs T002. T008 has external waits (staged-recipes review → feedstock creation → channel promotion).
- **US2 (T010–T013)**: T010/T011 need T009 (published artifact) + T003 (lock); T012/T013 need T010/T011.
- **US3 (T014–T016)**: needs T003 + T005; T016 needs a published version.
- **US4 (T017)**: needs T002 — independent of hardware.
- **US5 (T018)**: needs T002/T003; reads T015.
- **Polish (T019–T021)**: needs all desired stories.

### User Story Dependencies

- **US1 (P1)**: recipe → submission → installable CLI. No dependency on other stories.
- **US2 (P1)**: verification of the US1 artifact — depends on US1's publication; independently testable by re-running the recorded steps.
- **US3 (P2)**: automation of the per-release check; depends only on the lock/tooling, not on US2's manual runs.
- **US4 (P2)**: docs; independent once the recipe exists.
- **US5 (P3)**: audit; independent of US2's hardware runs.

### Within Each User Story

- Tests (embedded) MUST be written and FAIL before implementation.
- Artifact authoring before tooling before automation; manual verification before records; records before polish.

### Parallel Opportunities

- T001 ∥ T002 (different files).
- T004 ∥ US1's T006–T007 (different files).
- T010 ∥ T011 (different hardware paths).
- T017 ∥ T014 (different files).
- T020 ∥ anything after T013.

---

## Parallel Example: Setup

```bash
Task: "Author conda/lock-environment.yml (T001)"
Task: "Author conda/recipe.yaml (T002)"
```

## Parallel Example: US2 verifications

```bash
Task: "First-publication model-backed run — Apple Silicon MPS (T010)"
Task: "First-publication model-backed run — Linux CUDA via AWS (T011)"
```

---

## Implementation Strategy

### MVP First (Setup + Foundational + US1)

1. T001–T002: the two static artifacts.
2. T003–T005: lock + tooling + offline checks (needed for US2/US3; US1 can proceed in parallel).
3. T006–T009: lint → submit → verify install. **STOP and VALIDATE**: a fresh env installs and runs the CLI.
4. Note: both P1 stories gate "shipped" — the release only counts after US2's recorded model-backed runs.

### Incremental Delivery

1. Setup + Foundational → contract tests green.
2. US1 → the door opens (demo: fresh-env install).
3. US2 → verification recorded → the door is trusted.
4. US3 → per-release smoke automation.
5. US4 + US5 + Polish → docs, audit, consistency.

### Parallel Team Strategy

- One person: sequential T001→T021.
- Two people: A: setup + US1 + US2 (publication-critical path); B: T004–T005 + US3 workflow + US4 docs.
- Hardware runs (T010/T011) parallelize trivially.

---

## Notes

- [P] tasks = different files, no dependencies.
- Tests are embedded (Article XI): each task's failing test ships in the same commit.
- Zero model starts anywhere in CI; T010/T011 are manual, on real hardware, and recorded.
- Never hand-edit `conda/ember-deps.conda-lock.yml`; regenerate via `make conda-lock`.
- The `torchvision` divergence is retired when conda-forge ships 0.29.x — converge the pin and repeat a model-backed run (FR-015; constitution v3.3.0).
- External waits (staged-recipes review, bot PRs) do not block coding on other tasks.

---

## Implementation status (2026-10-12/13 — submitted; PR CI green)

- **Done**: T001, T002, T003, T004, T005, T006, T007, T013, T014, T015, T018 — artifacts; contract tests (all 5 conda tests green); the committed unified lock + both explicit renders (`make conda-lock`; `make conda-lock-check` in sync); freeze tooling (14 tests, ruff clean); recipe lint clean (after adding `about.homepage` and fixing the sdist URL to the underscore filename); a local `conda-build --no-test` produced the `ember-advise-0.15.0` `.conda` (non-noarch, osx-arm64); the `conda-smoke` target and `conda-smoke.yml` workflow (zizmor: no findings; the smoke consumes the per-platform explicit lock); vault decision + discovery notes (hub-linked; `make vault-audit` clean); static provenance audit clean.
- **Approved divergence (constitution v3.4.0, maintainer-approved 2026-10-12)**: the conda artifact pins the newest co-installable stack — `pytorch >=2.12,<2.14`, `torchvision >=0.27,<0.29`, `huggingface_hub >=1.32,<2` — resolved as pytorch 2.13.0/2.12.0, torchvision 0.28.0/0.27.1, huggingface_hub 1.32.0; validated at first publication, retired when conda-forge catches up.
- **Local end-to-end pre-flight (T007 completion, T016 pre-check; 2026-10-12)**: an environment created from `conda-osx-arm64.lock` installs the locally built `ember-advise-0.15.0` package; all four entry points respond, `ember doctor` runs without the model, and `import ember.mcp.mcp_server` stays torch-free.
- **Submitted (T008, 2026-10-12; CI green 2026-10-13)**: the recipe is at [conda-forge/staged-recipes#35165](https://github.com/conda-forge/staged-recipes/pull/35165) (`Add ember-advise`). All checks pass — `conda-forge-linter` "All recipes are excellent.", `linter` pass, linux_64/osx_64 builds pass, win_64 correctly skipped. The maintainer willingness comment from `@joshburt` is still required.
- **Recipe hardening from staged-recipes CI (2026-10-13)**: `pip_check: false` (the wheel declares the upstream ranges the divergence overrides), non-noarch + `skip: [win]` (`fcntl` is Unix-only; conda-forge forbids skips on noarch), and an unconstrained `run: python` (non-noarch rule) — see [[2026-10-12-conda-forge-dependency-and-tooling-gaps]].
- **Interim self-hosted channel (2026-10-13)**: `.github/workflows/conda-channel.yml` builds osx-arm64 + linux-64 and uploads to the `shapeandshare` channel on **prefix.dev** via OIDC trusted publishing (no stored secrets, matching the repo's posture); `scripts/render_conda_recipe.py` (+ `tests/test_render_conda_recipe.py`) renders the frozen recipe for each released version. Pending: create the prefix.dev channel + trusted publisher (owner `shapeandshare`, repo `ember`, workflow `conda-channel.yml`); then add the install path to README.
- **Remaining**: T009 (feedstock creation → first build → channel) awaits review/merge; T010–T012 need the channel plus real MPS/CUDA hardware; T016 needs a published version (its local pre-flight passed); T017/T019/T020 document the shipped door; T021's final `pr-ready`/model gates.
