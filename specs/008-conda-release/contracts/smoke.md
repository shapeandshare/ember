# Contract: no-model release smoke

**Feature**: `008-conda-release` · Runs on `osx-arm64` and `linux-64` · **Zero model starts**

The smoke proves a released `ember-advise` installs and runs against the verified dependency
environment, without ever starting the model (FR-016). It is the per-release enforcement of the
conda door.

## Steps (must all pass)

1. **Create the environment from the committed explicit lock** (dependencies only):
   `micromamba create -n <env> -f conda-<platform>.lock` — the `make conda-smoke` target does
   this (platform auto-detected, overridable with `CONDA_PLATFORM`), and CI installs micromamba
   directly from a pinned, sha256-verified release asset (the repository's Actions allow-list
   blocks `mamba-org/setup-micromamba`). The unified YAML is not installable by micromamba/conda.
2. **Install the release on top, preferring conda-forge**:
   `micromamba install -n <env> -c conda-forge -c joshburt "ember-advise==<version>"`.
   conda-forge is canonical, so it wins once the feedstock publishes; until then the interim
   `joshburt` channel supplies the package, which keeps the smoke live instead of red. (This is
   also the live version-sync check — it fails only if neither channel has that version. Drop
   `-c joshburt` at conda-forge onboarding.)
3. **Run the CLI aliases**: `ember --help`, `gut --help`, `ember-advise --help` succeed;
   `ember-mcp` is present.
4. **Run `ember doctor`**: reports platform/dependencies/model/server readiness without loading
   the model.
5. **Torch-free MCP import**:
   `python -c "import sys, ember.mcp.mcp_server; assert 'torch' not in sys.modules"`.

## Invariants

- **No model, no GPU, no weights**: the smoke MUST NOT load the model or require an accelerator
  (Article IV / FR-016). Making a release starts the model zero times.
- **Runnable in CI** on GitHub-hosted `macos-latest` (arm64) and `ubuntu-latest`.
- **Single implementation**: exposed as `make conda-smoke VERSION=<v>` in `shared/testing.mk`; the
  CI job calls that target so local and CI behavior cannot drift.
- **Failure response**: a failed smoke triggers a fresh model-backed run (or a fix), recorded;
  the failure is never silently kept.

## CI shape

A matrixed job (`os` × `platform`) in `.github/workflows/conda-smoke.yml`, triggered on
demand (`workflow_dispatch` with a `version` input) and weekly (`schedule`); channel lag is
tolerated by retrying the install step (bounded attempts). Every `uses:` SHA-pinned +
`# vX.Y.Z`; `permissions: {}` at workflow level; `contents: read` per job. The job never loads
the model.

## Out of scope

Loading the model, one-advise inference, and the MPS/CUDA device paths are **not** part of this
smoke — they belong to the first-publication model-backed verification (see
[quickstart.md](../quickstart.md)).
