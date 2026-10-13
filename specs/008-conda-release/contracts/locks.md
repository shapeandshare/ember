# Contract: committed dependency locks (`conda/`)

**Feature**: `008-conda-release` · Platforms `osx-arm64`, `linux-64` · Python 3.12

The locks pin the **dependency environment** that ember is verified against — not ember itself.
They are committed so the release checks can gate them offline (FR-011, FR-015) and so the
per-release smoke tests a reproducible environment (FR-016).

## Artifacts

| Path | Role | Committed |
|---|---|---|
| `conda/lock-environment.yml` | dependency-only source spec (no `ember-advise`) | ✅ |
| `conda/ember-deps.conda-lock.yml` | unified multi-platform lock (exact builds + sha256 + `metadata.input_hash`) | ✅ (primary) |
| `conda-osx-arm64.lock`, `conda-linux-64.lock` | per-platform `--kind explicit` renders — **what the smoke installs from** (micromamba/conda ignore the unified YAML) | ✅ (required) |

## Source spec contract

```yaml
# conda/lock-environment.yml
channels:
  - conda-forge
platforms:
  - osx-arm64
  - linux-64
dependencies:
  - python=3.12
  - pytorch >=2.12,<2.14        # approved co-installability divergence (constitution v3.4.0)
  - torchvision >=0.27,<0.29
  - transformers >=5.18,<6
  - safetensors >=0.8,<1
  - huggingface_hub >=1.32,<2   # below the declared floor; forced by transformers' chain
  - accelerate >=1.15,<2
  - pillow >=12,<13
  - fastapi >=0.142,<1
  - uvicorn-standard >=0.54,<1
  - pydantic >=2.13,<3
  - mcp >=2.3,<3
  - httpx >=0.28,<1
  - prometheus_client >=0.21,<1
  - boto3 >=1.40,<2
```

**MUST NOT list `ember-advise`** — the app is installed separately from conda-forge at smoke
time (it cannot be locked before it is published).

## Rules

1. **Regeneration** is the only way to change a lock:
   `conda-lock -f conda/lock-environment.yml -p osx-arm64 -p linux-64 --lockfile conda/ember-deps.conda-lock.yml`.
   Never hand-edit.
2. **Integrity gate**: `make conda-lock-check` runs `conda-lock --check-input-hash` against the
   committed lock (exit `4` = in sync) and the smoke workflow invokes it; `tests/test_distribution.py`
   asserts both platforms and the presence of per-platform `metadata.input_hash` in the lock.
3. **Both platforms present**: the lock must contain `osx-arm64` and `linux-64`.
4. **Deliberate moves only**: the lock moves when the dependency set changes on purpose (a
   security patch, a range change) — and a move triggers a fresh model-backed run before the new
   lock is committed (FR-015).
5. **Ordering**: regeneration targets an already-released range set (mirrors
   `deployment/requirements.txt`); the pinned ember version itself is never in the lock.
6. **Generation target**: `make conda-lock` in `shared/release.mk`, implemented by
   `scripts/freeze_conda_lock.py` (same shape as `scripts/freeze_deployment_requirements.py`):
   regenerate the unified lock, render both per-platform explicit locks, verify them, and no-op
   when unchanged.
7. **Explicit renders are required**: the smoke installs from `conda-<platform>.lock`; both
   `make conda-lock` and `make conda-lock-check` fail when an explicit render is absent.

## Regeneration cadence

- On any PR that changes `pyproject.toml`'s dependency ranges.
- On a schedule (weekly) to pick up conda-forge rebuilds, opened as a PR (never auto-merged
  blind) so the smoke job validates the new environment.
