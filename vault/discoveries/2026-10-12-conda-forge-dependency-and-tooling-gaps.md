---
title: "conda-forge cannot carry ember's declared dependency stack (and micromamba ignores conda-lock's unified YAML)"
type: discovery
tags:
  - type/discovery
  - domain/distribution
  - status/draft
created: "2026-10-12"
updated: "2026-10-12"
code-refs:
  - conda/lock-environment.yml
  - conda/recipe.yaml
  - scripts/freeze_conda_lock.py
  - specs/008-conda-release/spec.md
---

# conda-forge cannot carry ember's declared dependency stack (and micromamba ignores conda-lock's unified YAML)

Part of [[ember]]. Planning the conda-forge release (`specs/008-conda-release`) surfaced one
blocking gap and two tooling surprises: conda-forge cannot co-install ember's declared
dependency ranges for Python 3.12, `micromamba`/`conda` do not install from conda-lock's unified
YAML, and PyPI's `ember-advise` sdist uses an underscore filename.

## What was tested

- A real dependency solve against conda-forge repodata for `osx-arm64` + `linux-64`, Python 3.12,
  with ember's declared ranges (`conda-lock -f conda/lock-environment.yml -p osx-arm64 -p linux-64`).
- Reduced solves pinning one constraint at a time (`transformers` alone; `pytorch` + `torchvision`
  alone) to isolate each conflict.
- `micromamba create -f <conda-lock.yml>` (unified) versus `micromamba create -f conda-osx-arm64.lock`
  (explicit render), both against a throwaway lock.
- `curl` probes of `https://pypi.org/packages/source/e/ember-advise/{ember-advise,ember_advise}-0.15.0.tar.gz`.

## Finding

1. **No solution for the declared ranges.** conda-forge's `transformers` needs `tokenizers`,
   which needs `huggingface_hub <2`; conda-forge carries only `huggingface_hub 1.32.0` and
   `2.2.0`, so the declared floor `>=1.33` cannot co-install with `transformers`. Separately,
   `torchvision 0.28.0` pairs only with `pytorch <2.14`, while Python 3.12 has only `pytorch
   2.14.1` — so the pinned `torch 2.14` + `torchvision 0.29` pair has no channel build. Best
   co-installable stacks: `pytorch 2.13.0` + `torchvision 0.28.0` (linux-64) and `pytorch 2.12.0`
   + `torchvision 0.27.1` (osx-arm64), both with `huggingface_hub 1.32.0`.
2. **Unified lock files are not installable.** `micromamba create -f <conda-lock.yml>` (and conda's
   equivalent) create an **empty** environment; only the `--kind explicit` render installs
   packages. The smoke now consumes `conda-<platform>.lock`.
3. **PyPI filename form.** The sdist is `ember_advise-0.15.0.tar.gz`; the hyphenated filename
   `ember-advise-0.15.0.tar.gz` 404s. The recipe's `source.url` must use the underscore filename
   (the path segment keeps the normalized project name).
4. **MPS is compiled in, but unconfirmed.** conda-forge's osx-arm64 `pytorch` 2.14.1 is built with
   `USE_MPS=ON` (the `cpu_generic_…` build string is BLAS naming, not CPU-only), yet conda-forge
   deliberately does not assert `torch.backends.mps.is_available()` in CI — the first-publication
   run must confirm it on real Apple Silicon.

## Relevance

The conda door cannot ship within the declared ranges until conda-forge catches up (a
`torchvision` build for `pytorch 2.14`, and a `huggingface_hub` in `[1.33,2)`). The maintainer
approved the deeper divergence on 2026-10-12 (constitution v3.4.0): the artifact pins
`pytorch >=2.12,<2.14`, `torchvision >=0.27,<0.29`, `huggingface_hub >=1.32,<2`, validated by
the first-publication model-backed runs. The explicit-render
requirement is now built into `scripts/freeze_conda_lock.py`, `make conda-lock`, and
`make conda-smoke`, so the smoke design is correct regardless of the pin decision.

Staged-recipes CI surfaced one further consequence: rattler-build runs `pip check` in the test
phase, and the wheel's own metadata (from `pyproject.toml`) declares the upstream ranges this
environment deliberately overrides — so every platform's build failed until the recipe set
`tests[].python.pip_check: false` (with a comment recording why). Windows then failed at the
test because `ember/serving/process.py` imports the Unix-only `fcntl` — ember is macOS/Linux
only, so the recipe skips `win`. conda-forge's linter forbids platform skips on `noarch`
recipes, so the recipe is **not** noarch (built per platform), and `run: python` must be left
unconstrained for non-noarch packages.

## References

- `conda/lock-environment.yml`, `conda/recipe.yaml`
- `scripts/freeze_conda_lock.py`, `tests/test_freeze_conda_lock.py`
- `specs/008-conda-release/spec.md` (FR-004), `research.md` (R3/G1, R5, R6)
- conda-forge `torchvision-feedstock` issue #135 (torch↔torchvision versions decoupled from PyPI)
