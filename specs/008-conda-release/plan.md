# Implementation Plan: Conda Release of ember

**Branch**: `008-conda-release` | **Date**: 2026-10-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/008-conda-release/spec.md`

**Note**: Filled by `/speckit.plan`; the execution workflow is defined by the command.

## Summary

Add conda-forge as an equal distribution door for the `ember-advise` distribution: author a v1
conda-forge recipe (non-noarch; Unix-only, Windows skipped), commit per-platform dependency
locks (`conda-lock`), add a
no-model release smoke to CI, extend the distribution-contract tests, document the install path
in README/COMPATIBILITY, and record the one-time model-backed verification. No runtime code
changes — the CLI, MCP server, agent kit, device rules, and dependency pins are untouched.

**The governed decision is resolved (maintainer-approved 2026-10-12)**: conda-forge cannot
install the declared set for Python 3.12 (`torchvision` pairs only with `pytorch <2.14`; the
`transformers` chain forces `huggingface_hub 1.32.0`, below the floor); the conda recipe pins
the newest co-installable stack (`pytorch >=2.12,<2.14`, `torchvision >=0.27,<0.29`,
`huggingface_hub >=1.32,<2`), validated by the first-publication model-backed runs and retired
when conda-forge catches up. Recorded as a spec clarification (FR-004), constitution amendments
(Article V — channel-artifact exception, v3.3.0 → v3.4.0), research R3, and the Complexity
Tracking below; the Constitution gate is green with this recorded exception.

## Technical Context

**Language/Version**: Python 3.12 (package unchanged); `conda-lock` 4.x (tooling only); conda-forge
v1 `recipe.yaml`; Make + shell + GitHub Actions YAML.

**Primary Dependencies**: The existing runtime deps, in conda names —
`pytorch`, `torchvision`, `transformers`, `safetensors`, `huggingface_hub`, `accelerate`,
`pillow`, `fastapi`, `uvicorn-standard`, `pydantic`, `mcp`, `httpx`, `prometheus_client`,
`boto3`. New **tooling** (not package) deps: `conda-lock`; `mamba`/`micromamba` in CI.

**Storage**: Committed YAML locks under `conda/`; generated site docs under `site/_docs/`
(gitignored).

**Testing**: `pytest` (extend `tests/test_distribution.py`); a no-model smoke (`make conda-smoke`
+ CI job); a one-time manual model-backed verification per platform (MPS on Apple Silicon; CUDA
via the AWS GPU path).

**Target Platform**: `osx-arm64` and `linux-64`, Python 3.12 only.

**Project Type**: Distribution / packaging (no application runtime changes).

**Performance Goals**: The smoke runs in CI with no model and no GPU; making a release starts the
model zero times; the channel version tracks a release within one day (SC-003).

**Constraints**: Article V/VI pin discipline (torch/torchvision tested series); no model weights
in any artifact; no stored long-lived secrets; the model cannot run in CI; conda-forge recipe v1
+ non-noarch (Unix-only, `skip: [win]`); the recorded co-installable divergence (R3/G1, constitution v3.4.0).

**Scale/Scope**: 1 package, 2 platforms, 1 Python minor, 2 committed locks, 1 smoke job, plus
docs, tests, and a vault record.

## Constitution Check

*GATE: evaluated before Phase 0 research, re-checked after Phase 1 design.*

| Article | Gate | Status |
|---|---|---|
| I — Local or Remote, Never Silent | No network/privacy change; weights stay a runtime download, never redistributed | **PASS** |
| II — Typed Decisions, Not Text | No product-surface change | **PASS** |
| III — Agent-Legible Contract | Tool/schema/kit unchanged; kit thresholds untouched | **PASS** |
| IV — Lazy, Non-Interfering Lifecycle | Smoke never starts the model; no login/boot behavior | **PASS** |
| V — Model Loading | PyPI pinning unchanged; conda pins the newest co-installable stack (`pytorch >=2.12,<2.14`, `torchvision >=0.27,<0.29`, `huggingface_hub >=1.32,<2`) with a recorded, validated exception | **PASS with amendments (v3.3.0 → v3.4.0)** — maintainer-approved 2026-10-12; validated by the first-publication model-backed runs (R3/G1) |
| VI — Apple Silicon and CUDA | Verification devices fixed (MPS / CUDA); MPS availability must be empirically verified | **PASS** (with a verification task) |
| VII — Verification Over Assertion | First-publication model-backed runs + per-release no-model smoke + distribution checks | **PASS** |
| VIII/X — Tooling & Python Conventions | New script follows house style; tests added; no runtime code; no new debt | **PASS** |
| XI — TDD & Coverage Ratchet | Tests written first for the distribution checks and script; `fail_under` unchanged | **PASS** |
| XIII — Layered Architecture | Touches only `scripts/`, `tests/`, `conda/`, `.github/`, docs | **PASS** |
| XIV — Pit of Success | Unsupported platform/Python refused actionably; solver behavior documented | **PASS** |
| XV — Simplicity / YAGNI | `conda-lock` (not pixi); no new runtime deps; recipe also recorded in the feedstock | **PASS** |
| IX — Project Memory Vault | Decision + verification notes planned, linked from the hub | **PASS** |

**Post-Phase 1 re-check**: Article V is now green with the recorded channel-artifact exception
(constitution v3.4.0); all other gates unchanged. Complexity Tracking records the approved
divergence.

## Project Structure

### Documentation (this feature)

```text
specs/008-conda-release/
├── plan.md              # this file
├── spec.md              # feature spec
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── recipe.md        # conda-forge recipe contract
│   ├── locks.md         # committed lock contract
│   └── smoke.md         # no-model smoke contract
└── checklists/
    └── requirements.md  # spec quality checklist
```

### Source Code (repository root) — changes only

```text
conda/                                # NEW: committed conda-forge artifacts
├── recipe.yaml                       #   authored v1 recipe (submitted to staged-recipes)
├── lock-environment.yml              #   dependency-only source spec (no ember-advise)
└── ember-deps.conda-lock.yml         #   unified osx-arm64 + linux-64 lock (committed)

scripts/
└── freeze_conda_lock.py              # NEW: regenerate/verify the lock (mirrors freeze_deployment_requirements.py)

shared/
├── release.mk                        # EDIT: add `conda-lock` target (beside `deployment-requirements`)
└── testing.mk                        # EDIT: add `conda-smoke` target

.github/workflows/
└── conda-smoke.yml                   # NEW: per-release smoke (workflow_dispatch + weekly schedule)

tests/
└── test_distribution.py              # EDIT: recipe snapshot, lock presence/platforms, dependency-name checks

README.md                             # EDIT: conda install block + naming row
COMPATIBILITY.md                      # EDIT: conda verification record (platform/device/version/lock)
Makefile                              # EDIT: header comment target list
vault/
├── _meta/tags.md                     # EDIT: add domain/distribution before first use
├── decisions/2026-10-12-conda-forge-release.md
├── discoveries/2026-10-12-conda-forge-pytorch-mps-and-torchvision-gap.md
└── ember.md                          # EDIT: link the new notes under Decisions/Discoveries/Sessions
```

**Structure Decision**: Single-project layout. The feature adds one new directory (`conda/`),
one script, two Make targets, one CI job, and edits to existing docs/tests — it introduces no new
runtime code or package layer, matching the spec's "a new door, not a new product".

## Requirement coverage

| Requirement | Where satisfied |
|---|---|
| FR-001 conda-forge package, conda-only deps | `contracts/recipe.md`; `conda/lock-environment.yml` |
| FR-002 same four commands | `contracts/recipe.md` entry points |
| FR-003 version equality + released source | `contracts/recipe.md`; the feedstock bot carries versions; the live smoke installs by exact version |
| FR-004 dependency constraints, no widened platforms | `contracts/recipe.md`; approved co-installability divergence recorded (G1, v3.4.0) |
| FR-005 platforms + model-backed checkpoint policy | `contracts/smoke.md`; `quickstart.md` §4 |
| FR-006 no weights/state/secrets | `contracts/recipe.md`; `contracts/locks.md` |
| FR-007 channel version sync | `contracts/smoke.md` (live install-by-version); `tests/test_distribution.py` |
| FR-008 no stored credentials | conda-forge bot publishes; no CI secrets added |
| FR-009 metadata | `contracts/recipe.md` `about` |
| FR-010 docs | README install block; `site/_data/docs.json` (no change) |
| FR-011 distribution checks | `tests/test_distribution.py` additions; the live smoke job (version sync) |
| FR-012 reviewable/reproducible build source | `conda/recipe.yaml` + the public feedstock |
| FR-013 actionable refusals | recipe python pin; the T009 refusal exercise |
| FR-014 no behavior change | no runtime code touched |
| FR-015 committed hash-pinned locks | `contracts/locks.md`; `make conda-lock` |
| FR-016 per-release no-model smoke, zero model starts | `contracts/smoke.md`; `make conda-smoke` + CI job |
| FR-017 verification record | `COMPATIBILITY.md` + vault note |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Conda recipe pins the newest co-installable stack (`pytorch >=2.12,<2.14`, `torchvision >=0.27,<0.29`, `huggingface_hub >=1.32,<2`), diverging from the released PyPI ranges (older torch/torchvision; a below-floor huggingface_hub) | conda-forge cannot install the declared set for Python 3.12 at all (proven by live solves); without the divergence the conda door cannot ship | Waiting for the channel was considered; the maintainer approved the deeper divergence (2026-10-12, constitution v3.4.0) so the door ships now with a model-backed-validated environment, retired when conda-forge catches up |
