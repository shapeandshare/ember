---
title: "conda-forge release: channel, committed locks, and a no-model smoke"
type: decision
tags:
  - type/decision
  - domain/distribution
  - status/draft
created: "2026-10-12"
updated: "2026-10-12"
code-refs:
  - conda/lock-environment.yml
  - conda/recipe.yaml
  - scripts/freeze_conda_lock.py
  - shared/release.mk
  - shared/testing.mk
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
  also publish to the `shapeandshare` channel on **prefix.dev** via OIDC trusted publishing — no
  stored secrets, matching this repo's posture (`pre-conda-forge`), driven by
  `.github/workflows/conda-channel.yml` and `scripts/render_conda_recipe.py`.
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
