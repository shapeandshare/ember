# Data Model: Conda Release of ember

**Feature**: `008-conda-release` · **Date**: 2026-10-12 · **Spec**: [spec.md](./spec.md)

This feature adds no runtime data structures. Its "data" is a set of committed release-contract
artifacts and the records that gate shipping. Entities below are described as they exist across
the channel, the repository, and the release pipeline.

## Entities

### 1. Recipe (`conda/recipe.yaml`)

The authored conda-forge recipe (v1 format); the submission source and the in-repo reviewable
record. The canonical build source is the resulting feedstock
(`conda-forge/ember-advise-feedstock`).

| Field | Meaning | Validation |
|---|---|---|
| `context.version` | Package version (frozen submission snapshot) | MUST be a valid `X.Y.Z` for the submitted release; NOT wired to commitizen — the feedstock bot carries future versions (FR-003) |
| `package.name` | `ember-advise` | MUST equal the distribution name (AGENTS.md naming) |
| `source.url` | PyPI sdist for the version | MUST be the release sdist; `sha256` recorded |
| `build.skip` | `[win]` | MUST skip Windows (ember imports the Unix-only `fcntl`) |
| `build.number` | Build number | Starts at `0` |
| `build.python.entry_points` | `ember`, `gut`, `ember-advise`, `ember-mcp` | MUST match `[project.scripts]` (FR-002) |
| `requirements.run` | Runtime deps in **conda names** | MUST mirror `pyproject.toml` ranges (one approved exception: `torchvision >=0.28,<0.29`), using `pytorch`, `huggingface_hub`, `prometheus_client`, `uvicorn-standard` (R3) |
| `requirements.run` python | `python >=3.12,<3.13` | MUST match `requires-python` (FR-004) |
| `about.license` / `license_file` | `MIT` / `LICENSE` | SPDX id + shipped licence file (FR-009) |
| `extra.recipe-maintainers` | Maintainer GitHub username(s) | At least one; confirmed by PR comment |

### 2. Lock environment spec (`conda/lock-environment.yml`)

The dependency-only source spec for the lock. **Excludes `ember-advise`** (it cannot be locked
against its own unpublished build).

| Field | Meaning | Validation |
|---|---|---|
| `channels` | `[conda-forge]` | Single channel (FR-001) |
| `dependencies` | `python=3.12` + the runtime deps as conda names | MUST cover the recipe's `run` set (minus `ember-advise`) |
| `platforms` | `[osx-arm64, linux-64]` | MUST equal the supported platform set (FR-005) |

### 3. Dependency lock (`conda/ember-deps.conda-lock.yml`)

The committed, hash-pinned solution for both platforms — the "verified environment" record
(FR-015).

| Field | Meaning | Validation |
|---|---|---|
| per-platform package set | exact version + build + sha256 for every dep | MUST resolve `python=3.12` |
| `metadata.input_hash` | hash of the source spec at solve time | Checked against `lock-environment.yml` by `make conda-lock-check` (`conda-lock --check-input-hash`); the tests assert its presence per platform (FR-011) |
| platforms present | both `osx-arm64` and `linux-64` | Both MUST be present |

Relationships: one lock environment spec → one lock; the lock never contains the recipe's own
package.

### 4. Conda artifact

A per-platform build on conda-forge for one version (`ember-advise-<version>-h…_0.conda`; not
noarch — Windows is skipped). Produced by the feedstock; **contains no model weights, user
state, or secrets** (FR-006).

### 5. No-model smoke

The per-release check (FR-016): create env from the lock → install `ember-advise==<version>`
from conda-forge → run the CLI aliases and `ember doctor` → import `ember.mcp.mcp_server`
asserting `torch` is not loaded. Zero model starts; runs without a GPU; invoked by
`make conda-smoke` and the CI job.

### 6. Version-sync state

The channel's newest `ember-advise` version vs. the release version. Checked live by the smoke
job (install by exact version) and reported as drift by the distribution checks (FR-007,
SC-003, SC-004).

### 7. Model-backed verification record (FR-017)

One record per platform at first publication (plus any fresh run after a failure or a deliberate
lock move): platform, device (MPS on Apple Silicon; CUDA on NVIDIA), version, lock identity,
date. Recorded in `COMPATIBILITY.md`'s verified state and detailed in a vault note.

## Lifecycle / state transitions

```
author recipe ──► staged-recipes PR ──► feedstock created ──► first build on channel
        │                                                            │
        ├─ lock generated (deps-only, both platforms) ───────────────┤
        │                                                            ▼
        │                                    first publication: model-backed run
        │                                    (MPS on osx-arm64; CUDA on linux-64)
        │                                                            │ recorded (COMPATIBILITY.md + vault)
        ▼                                                            ▼
 next release ──► bot opens a feedstock version PR (from PyPI) ─────► channel carries the release
        │                                                            │
        └─► no-model smoke (make conda-smoke / CI) ─────────────────► channel version == release
                     │
                     └─ failure ──► fresh model-backed run, or fix (never silently kept)

 deliberate lock move (security patch / range change) ──► regenerate lock ──► fresh model-backed run
```

## Validation rules (from the spec)

- Recipe package name matches the naming rules; the snapshot's version is a valid `X.Y.Z` for
  its submitted release; the channel equals the release (enforced live by the smoke) (FR-003).
- Dependency constraints mirror the release's ranges in conda names, with the one approved
  exception (`torchvision >=0.28,<0.29`, FR-004); a platform whose channel deps cannot satisfy
  the ranges is not shipped rather than shipped widened (FR-004).
- Locks exist for both platforms and are integrity-checked offline (FR-011, FR-015).
- Artifacts contain no weights/state/secrets (FR-006).
- Unsupported Python/platform attempts fail actionably (FR-013).
