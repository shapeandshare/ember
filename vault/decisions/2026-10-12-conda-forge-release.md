---
title: "conda-forge release: channel, committed locks, and a no-model smoke"
type: decision
tags:
  - type/decision
  - domain/distribution
  - status/draft
created: "2026-10-12"
updated: "2026-10-13"
code-refs:
  - conda/lock-environment.yml
  - conda/recipe.yaml
  - scripts/freeze_conda_lock.py
  - scripts/render_conda_recipe.py
  - scripts/upload_conda_packages.py
  - shared/release.mk
  - shared/testing.mk
  - .github/workflows/conda-package.yml
  - .github/workflows/conda-smoke.yml
  - tests/test_distribution.py
---

# conda-forge release: channel, committed locks, and a no-model smoke

Part of [[ember]]. `specs/008-conda-release` adds conda-forge as an equal distribution door for
`ember-advise`, carrying the same CLI, MCP server, agent kit, and tested dependency series.

## Context

Users who manage Python environments with conda, mamba, or pixi had no conda-native install path.
The door is a new distribution channel, not a new product: names, behaviour, the agent contract,
and device rules are unchanged. Planning decisions were taken through `/speckit.clarify` and
`/speckit.plan`; the implementation status is tracked in `specs/008-conda-release/tasks.md`.

## Decision

- **Channel**: conda-forge. The v1 recipe (non-noarch: Unix-only, `skip: [win]`) is authored
  in-repo (`conda/recipe.yaml`) and submitted to `conda-forge/staged-recipes`; the resulting
  feedstock is canonical and carries versions via the conda-forge bot. No publishing credentials
  live in this repo.
- **Interim self-hosted channel (2026-10-13)**: while the feedstock is under review, releases
  are also published to the `joshburt` channel on **Anaconda.org** — the named channel users
  recognise. Anaconda.org has no OIDC, so publishing is automated with a stored credential: the
  org-level `ANACONDA_TOKEN` secret (exposed to this repo), read only by the `publish` job in
  `.github/workflows/conda-package.yml` and passed to anaconda-client as its native
  `ANACONDA_API_TOKEN`, which uploads via `scripts/upload_conda_packages.py` (`--skip-existing`,
  so reruns are safe). `release-ember.yml`'s `publish-conda` job dispatches `conda-package.yml`
  (`workflow_dispatch`, exempt from the GITHUB_TOKEN suppression that stops a bot-made `release`
  event from firing it) once PyPI has the sdist — see
  [[2026-10-13-github-token-release-events-are-suppressed]]. `rattler-build` is fetched from a
  pinned, sha256-verified release asset rather than via the official action, which the repo's
  Actions allow-list blocks — see [[2026-10-13-actions-allow-list-blocks-third-party-actions]].
  (`prefix.dev` — OIDC, no stored secret — was rejected: a URL channel too undiscoverable for a
  public tool.)
  `scripts/render_conda_recipe.py` renders the recipe per release. Retire this job when the
  conda-forge feedstock lands and its bot publishes versions.
- **Locks**: the dependency environment (never `ember-advise` itself) is pinned by `conda-lock`;
  the unified lock and the per-platform **explicit** renders are committed. The smoke installs from
  the explicit render — see [[2026-10-12-conda-forge-dependency-and-tooling-gaps]].
- **Verification**: one model-backed run per platform at first publication (MPS on Apple Silicon;
  CUDA on the AWS GPU path), then a no-model smoke per release (`make conda-smoke`,
  `conda-smoke.yml`) so making a release starts the model zero times. Records go to
  `COMPATIBILITY.md` plus a vault note.
- **Approved divergence** (constitution v3.3.0, extended to v3.4.0 on 2026-10-12): the conda
  artifact pins the newest co-installable stack conda-forge can install — `pytorch >=2.12,<2.14`,
  `torchvision >=0.27,<0.29`, `huggingface_hub >=1.32,<2` (below the declared floor) — validated
  by the first-publication model-backed runs and converged back when conda-forge catches up.
  The PyPI distribution is unchanged.

## Consequences

- `make conda-lock` regenerates the unified lock and both explicit renders; `make conda-lock-check`
  gates staleness offline; `make conda-smoke VERSION=<v>` runs the no-model smoke.
- The recipe is a frozen submission snapshot (v0.15.0), intentionally not wired to commitizen;
  the feedstock bot carries future versions.
- No release can reach conda-forge until the dependency gap is resolved (see the discovery note).
- Static audit (2026-10-12): the recipe's `about` metadata matches; `conda/` holds no secrets or
  weights; the `conda-smoke` workflow stores no credentials (`permissions: {}`,
  `persist-credentials: false`).
