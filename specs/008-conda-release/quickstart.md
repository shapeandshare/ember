# Quickstart: validating the conda release

**Feature**: `008-conda-release` · Prerequisites: a checkout, `conda-lock` (4.x), and a
conda/mamba/micromamba on `PATH` (for the lock/smoke steps).

This guide proves the feature end-to-end. It references
[contracts/recipe.md](./contracts/recipe.md), [contracts/locks.md](./contracts/locks.md),
[contracts/smoke.md](./contracts/smoke.md), and [data-model.md](./data-model.md) rather than
duplicating them.

## 1. Recipe is lint-clean

```bash
conda-smithy recipe-lint conda/recipe.yaml      # or: pixi run lint in staged-recipes
```

**Expected**: no lint findings; `build.number: 0`; `skip: [win]`; four entry points; the
`run` deps use conda names (`pytorch`, `huggingface_hub`, `prometheus_client`, `uvicorn-standard`).

## 2. Locks are present and in sync

```bash
make conda-lock                                  # regenerate (no-op if unchanged)
conda-lock --check-input-hash -f conda/lock-environment.yml -p osx-arm64 -p linux-64 --lockfile conda/ember-deps.conda-lock.yml
pytest tests/test_distribution.py -k conda -q
```

**Expected**: the unified lock contains both platforms; `conda-lock --check-input-hash` reports
in sync (exit `4`, no re-solve); the distribution tests pass.

## 3. No-model smoke (per release, zero model starts)

```bash
make conda-smoke VERSION=0.15.0
```

**Expected**, per [contracts/smoke.md](./contracts/smoke.md): env created from the lock;
`ember-advise==0.15.0` installed from conda-forge; `ember`/`gut`/`ember-advise --help` succeed;
`ember doctor` reports readiness; the MCP server imports with `torch` absent from `sys.modules`.
**The model never loads.**

## 4. First-publication model-backed verification (once per platform)

Run once per platform at first publication, and again only after a failure or a deliberate lock
move ([spec.md](./spec.md) FR-005/FR-017). Weights are downloaded normally (not part of any
artifact).

**Apple Silicon (MPS)**:

```bash
conda install -n <env> -c conda-forge "ember-advise==<version>"
ember model pull                # ~18 GB, cached in the Hugging Face cache
ember doctor                    # must report the MPS device
ember start
# one advise request through the MCP/HTTP path returns calibrated probabilities + token split
```

**Linux (CUDA)** — reuse the existing AWS GPU deployment path (`make aws-*`) with conda:

```bash
# on the GPU instance: conda create from the lock, install ember-advise==<version>,
# EMBER_DEVICE=cuda ember serve, then one advise request (server start + one advise)
```

**Expected**: `torch.backends.mps.is_available()` is `True` on Apple Silicon (the empirical
confirmation of [research.md](./research.md) R4); the advise response carries calibrated
probabilities and the token split. **Record** the run in `COMPATIBILITY.md`'s verified state
(platform, device, version, lock) and a vault note (FR-017). If MPS cannot be verified, the
osx-arm64 platform waits and the limitation is recorded.

## 5. Docs and release contract

```bash
grep -n "conda install" README.md           # install path documented beside uv/git
make site                                   # README → /docs/overview/, COMPATIBILITY → /docs/compatibility/
make check                                  # includes tests/test_distribution.py (conda checks)
```

**Expected**: README documents the channel, command, and supported platforms; the site renders
the same (no manifest change needed); distribution checks cover recipe-version, lock presence,
and lock integrity.

## 6. Publication (one-time, then automatic)

Follow the submission steps in [contracts/recipe.md](./contracts/recipe.md); after the feedstock
exists, `regro-cf-autotick-bot` opens version PRs from PyPI (target: channel current within one
day, SC-003). The per-release smoke ([contracts/smoke.md](./contracts/smoke.md)) is the ongoing
gate.
