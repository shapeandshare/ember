# Phase 0 Research: Conda Release of ember (`ember-advise` on conda-forge)

**Feature**: `008-conda-release` · **Date**: 2026-10-12 · **Spec**: [spec.md](./spec.md)

Research resolved every unknown in the plan's Technical Context, including the one governed
decision (R3/G1) — **maintainer-approved 2026-10-12**; everything is settled.

## Decision summary

| # | Question | Decision |
|---|----------|----------|
| R1 | Recipe format & submission process | conda-forge **v1 `recipe.yaml`** (non-noarch: Unix-only, `skip: [win]`), PyPI-sdist source, staged-recipes PR → auto-created feedstock; `regro-cf-autotick-bot` carries versions thereafter |
| R2 | Python version pin | `python_min: "3.12"` pins the build to Python 3.12; `run: python` stays unconstrained (non-noarch) |
| R3 | Dependency availability on conda-forge | The declared set is unsatisfiable for Python 3.12; the newest co-installable stack (`pytorch >=2.12,<2.14`, `torchvision >=0.27,<0.29`, `huggingface_hub >=1.32,<2`) is the **approved deep divergence** (2026-10-12, constitution v3.4.0) |
| R4 | MPS in conda-forge's osx-arm64 pytorch | Built with `USE_MPS=ON`; expected to work on Apple Silicon; **must be empirically verified post-install** before osx-arm64 ships |
| R5 | Lock tooling | **`conda-lock`** (not pixi); one committed unified lock for `osx-arm64` + `linux-64`, dependency-only (excludes `ember-advise`) |
| R6 | CI smoke mechanics | a pinned micromamba install reads the lock; then install `ember-advise==<release>` from conda-forge; run CLI/`doctor`/torch-free MCP import; matrix `macos-latest` + `ubuntu-latest` |
| R7 | Repo integration seams | Extend `tests/test_distribution.py`; lock regeneration mirrors the `deployment-requirements` triad; smoke target in `shared/testing.mk` + a workflow; README/COMPATIBILITY edits need no site-manifest change |

## R1 — Recipe format and submission process

**Decision**: Publish via conda-forge using the current **v1 `recipe.yaml`** (v0 `meta.yaml` is
deprecated for new recipes), `build.number: 0`, `skip: [win]` (ember is Unix-only), source = the
**PyPI sdist**
(`https://pypi.org/packages/source/e/ember-advise/ember_advise-${{ version }}.tar.gz`)
plus its `sha256`, and all four console scripts declared under `build.python.entry_points`.
Process: fork `conda-forge/staged-recipes` → `recipes/ember-advise/recipe.yaml` → PR (pass CI +
lint) → request review (`@conda-forge/help-python`) → merge → `create_feedstocks` auto-creates
`conda-forge/ember-advise-feedstock` and invites the submitter as maintainer. Thereafter
`regro-cf-autotick-bot` opens version-update PRs from PyPI (version, source URL, sha256);
dependency changes must be pushed onto the bot's branch. Automerge is opt-in via a
`@conda-forge-admin, please add bot automerge` issue.

**Rationale**: The package is pure Python, but ember is Unix-only (`ember/serving/process.py`
imports `fcntl`), and conda-forge's linter forbids platform skips on `noarch` recipes — so the
recipe is **not** noarch and declares `skip: [win]`. A pure-Python consumer still declares
`pytorch` as a plain `run` dependency. The submitter becomes the maintainer automatically; at
least one maintainer must confirm on the PR.

**Alternatives considered**: v0 `meta.yaml` (deprecated for new recipes); building our own
conda channel (rejected in `/speckit.clarify` — conda-forge chosen); vendoring a recipe mirror
only in the feedstock (rejected: the in-repo submission snapshot keeps the recipe reviewable
and its dependency contract checkable offline — see R7).

**Evidence**: conda-forge staged-recipes README + docs (`staged_recipes`, `life_cycle`),
`conda-forge/mcp-feedstock`, `conda-forge/geospatial-ml-feedstock`, `conda-forge/uvicorn-feedstock`,
`conda-forge/transformers-feedstock`.

## R2 — Python version pin

**Decision**: `context: { python_min: "3.12" }` pins the build to Python 3.12; the `run`
requirement is a bare `python` (conda-forge requires non-noarch packages to leave it
unconstrained). This matches `pyproject.toml`'s `requires-python = ">=3.12,<3.13"` through the
build, not the run metadata.

**Rationale**: A non-noarch build for a single Python version is the sanctioned way to support
exactly one interpreter (the linter requires an unconstrained `run: python`); the build string
ties the artifact to Python 3.12.

**Alternatives considered**: unstretched `python >={{ python_min }}` (would over-advertise
support beyond the tested interpreter).

## R3 — Dependency availability (the blocker)

All ranges below were checked live against conda-forge `repodata.json` (`osx-arm64`,
`linux-64`, `noarch`).

| ember dep (range) | conda-forge name | osx-arm64 | linux-64 | Notes |
|---|---|---|---|---|
| `torch>=2.14,<2.15` | **`pytorch`** | 2.14.1 ✅ | 2.14.1 ✅ | py312 builds present; osx build string `cpu_generic_py312_…` (MPS compiled in — see R4) |
| `torchvision>=0.29,<0.30` (diverges to `>=0.27,<0.29`) | `torchvision` | 0.27.1 (co-installable) | 0.28.0 (co-installable) | **G1**: conda-forge decouples torch↔torchvision from PyPI (feedstock #135); the approved deep divergence pins the newest co-installable stack (v3.4.0) |
| `transformers>=5.18,<6` | `transformers` | 5.19.0 ✅ | 5.19.0 ✅ | noarch |
| `safetensors>=0.8,<1` | `safetensors` | 0.8.0 ✅ | 0.8.0 ✅ | py312 builds |
| `huggingface-hub>=1.33,<3` | **`huggingface_hub`** | 1.32.0 (co-installable) | 1.32.0 (co-installable) | **G2**: only `1.32.0` co-installs with `transformers` (tokenizers needs `<2`); the approved deep divergence pins `>=1.32,<2` (below the declared floor) |
| `accelerate>=1.15,<2` | `accelerate` | 1.15.0 ✅ | 1.15.0 ✅ | noarch |
| `pillow>=12,<13` | `pillow` | 12.3.0 ✅ | 12.3.0 ✅ | py312 builds |
| `fastapi>=0.142,<1` | `fastapi` | 0.143.0 ✅ | 0.143.0 ✅ | noarch |
| `uvicorn[standard]>=0.54,<1` | **`uvicorn-standard`** | 0.54.0 ✅ | 0.54.0 ✅ | **G3**: conda has no extras; must depend on `uvicorn-standard` |
| `pydantic>=2.13,<3` | `pydantic` | 2.14.1 ✅ | 2.14.1 ✅ | noarch |
| `mcp>=2.3,<3` | `mcp` | 2.3.0 ✅ | 2.3.0 ✅ | **G4**: only `2.3.0` qualifies — thin margin |
| `httpx>=0.28,<1` | `httpx` | 0.28.1 ✅ | 0.28.1 ✅ | stable since 2024-12; no upstream 1.0 |
| `prometheus-client>=0.21,<1` | **`prometheus_client`** | 0.26.0 ✅ | 0.26.0 ✅ | **G3**: underscore, not hyphen |
| `boto3>=1.40,<2` | `boto3` | 1.43.111 ✅ | 1.43.111 ✅ | noarch |

**G1 — Approved deep divergence (co-installability)**: conda-forge cannot install the declared
set for Python 3.12. `torchvision`'s newest builds pair only with `pytorch <2.14` (best
co-installable pairs: `2.13.0`+`0.28.0` on linux-64; `2.12.0`+`0.27.1` on osx-arm64), and the
`transformers`→`tokenizers` chain requires `huggingface_hub <2`, which forces `1.32.0` — below
ember's declared floor. **Maintainer decision (2026-10-12): deepen the divergence**
(constitution v3.4.0) — the recipe pins the newest co-installable stack
(`pytorch >=2.12,<2.14`, `torchvision >=0.27,<0.29`, `huggingface_hub >=1.32,<2`):

- Validated by the first-publication model-backed runs (FR-005) on both platforms; the run
  records name the series exercised.
- Recorded in the spec (FR-004 exception), this research, the plan's Complexity Tracking, and
  the vault decision + discovery notes.
- **Retired** (pins converged back to the declared ranges) when conda-forge catches up, with
  fresh model-backed runs per the lock-move rule (FR-015).
- The held alternative (wait for the channel) was considered; the maintainer chose to ship the
  door now with a model-backed-validated environment.

**Other gaps (non-blocking)**: G2 `huggingface_hub` has no 1.33.x (2.2.0 is in range but a
major-version jump from what `uv.lock` may pin — the smoke/verification must exercise the
resolved version, not the PyPI one); G3 conda name mapping (`pytorch`, `huggingface_hub`,
`prometheus_client`, `uvicorn-standard`) must be used verbatim in the recipe; G4 `mcp` has a
one-version margin in range.

## R4 — MPS in conda-forge's osx-arm64 pytorch

**Decision**: Treat MPS as **expected-available but empirically unconfirmed**: the osx-arm64
`pytorch` 2.14.1 build is compiled with `USE_MPS=ON`, and the feedstock's own CI runs the real
MPS test suite on Apple Silicon runners; `torch.backends.mps.is_available()` depends on the
*running* macOS version and is deliberately not asserted in conda-forge's CI. The
first-publication model-backed run MUST verify it on real Apple Silicon before osx-arm64 ships
(spec edge case: platform waits if it cannot be verified).

**Evidence**: `pytorch-cpu-feedstock` `build.sh`/`meta.yaml` (single osx variant, no CUDA,
`USE_MPS` not disabled; a commented-out `mps.is_available()` assert with the "OSX too old"
rationale); PR #123 (MPS added, `is_available()` verified `True/True` on macOS 12.3+); PR #353
(live `TestModuleMPS` CI logs, osx-arm64). The `cpu_generic_…` build-string prefix is the BLAS
naming convention, not evidence of CPU-only compilation.

## R5 — Lock tooling

**Decision**: **`conda-lock`** (v4.x). Commit:
- `conda/lock-environment.yml` — the dependency-only source spec (`channels: [conda-forge]`,
  `python=3.12` + the runtime deps as conda names, `platforms: [osx-arm64, linux-64]`);
  **never lists `ember-advise`** (chicken-and-egg: the app can't be locked before it exists).
- `conda/ember-deps.conda-lock.yml` — the unified lock (both platforms, exact builds + sha256 +
  `metadata.input_hash`), the primary committed artifact.
- Required `conda-osx-arm64.lock` / `conda-linux-64.lock` explicit renders — the smoke
  installs from these; micromamba and conda ignore the unified YAML (verified 2026-10-12:
  `micromamba create -f <unified>` yields an empty environment).

Regeneration: `conda-lock -f conda/lock-environment.yml -p osx-arm64 -p linux-64 --lockfile
conda/ember-deps.conda-lock.yml`; `--check-input-hash` gates "did the source spec change?";
`--update <pkg>` bumps one package. Never hand-edit.

**Rationale**: conda-lock produces exactly the artifact this feature needs without asking the
repo to adopt a second, parallel environment manager; pixi would re-platform dev/CI for one
release concern (Article XV / YAGNI). Precedent: `catalyst-cooperative/pudl` ran this exact
pattern (committed conda-lock + micromamba CI) before later migrating wholesale to pixi.

**Alternatives considered**: pixi (bigger footprint; `no-deps` separation is an open feature
request); raw `conda list --explicit` files (single-platform, less reviewable).

## R6 — CI smoke mechanics

**Decision**: A matrixed job (`macos-latest` → osx-arm64, `ubuntu-latest` → linux-64) that:
1. micromamba is installed directly from a pinned, sha256-verified release asset (the repo's
   Actions allow-list blocks `mamba-org/setup-micromamba`); the `make conda-smoke` target
   creates the env from `conda-<platform>.lock`;
2. installs `ember-advise==<release>` from `-c conda-forge -c joshburt` on top (canonical channel
   first, interim channel as fallback);
3. runs `ember --help` (all aliases), `ember doctor`, and a `python -c` import of
   `ember.mcp.mcp_server` asserting `torch` is **not** in `sys.modules`.

The same steps are exposed as a `make conda-smoke` target (in `shared/testing.mk`) so CI and
local reproduction share one implementation; the workflow calls the target.

**Rationale**: the lock pins the dependency environment; installing the release on top tests
"does this release work against the verified environment". Zero model starts (FR-016); no GPU
needed. micromamba consumes the explicit render; the unified YAML is only the reviewable
record. Ordering matters: if the
recipe's ranges don't match the lock, `conda install` either no-ops (good) or bumps a package
(itself useful drift signal).

**Alternatives considered**: `conda-lock install` (works, but created the environment in an
unexpected root and needs conda-lock at smoke time) and `conda-incubator/setup-miniconda`
(equivalent, but a heavier conda install); running the smoke inside the release workflow
(rejected: the release must not depend on a channel that lags — see FR-007/SC-003).

## R7 — Repo integration seams

- **`tests/test_distribution.py`**: 9 tests, `@pytest.mark.parametrize` over module tuples
  (`INSTALL_DOCS`, `VERSIONED_MANIFESTS`) and a `_version_files()` helper reading commitizen's
  `version_files`. New conda tests assert statically (offline): the recipe snapshot exists and
  lists the four entry points and the exact conda dependency names; both lock artifacts exist
  and the unified lock contains both `osx-arm64` and `linux-64`; `conda/lock-environment.yml`
  lists no `ember-advise`. Lock staleness/integrity is checked by `make conda-lock-check`
  (conda-lock's `--check-input-hash`), invoked in the smoke workflow.
- **Makefile / `shared/*.mk`**: `deployment-requirements` (in `shared/release.mk`) is
  `uv export … && scripts/freeze_deployment_requirements.py` — the exact template. A
  `conda-lock` regeneration target belongs in `shared/release.mk` beside it, calling a new
  `scripts/freeze_conda_lock.py` (shape: `ROOT = Path(__file__).resolve().parents[1]`,
  why-docstring, `main() -> int`, `if __name__ == "__main__": raise SystemExit(main())`). The
  smoke target belongs in `shared/testing.mk` (beside `smoke`/`mcp-check`). Update the root
  `Makefile` header list and the `##` doc-comment (drives `make help`).
- **`scripts/`**: 8 existing scripts, all invoked via Make targets; style as above.
- **`.github/workflows/ci.yml`**: jobs `lint`, `typecheck`, `security`, `test`, `smoke`
  (macos-latest install-smoke — never loads the model), `sonar`, `zizmor`; every `uses:`
  SHA-pinned + `# vX.Y.Z`, `permissions: {}` at workflow level. The conda smoke either extends
  the existing `smoke` job or adds a matrixed `conda-smoke` job beside it.
- **`deployment/requirements.txt` + `scripts/freeze_deployment_requirements.py` + `shared/release.mk`**
  is the committed-artifact triad to mirror for the conda lock (ordering constraint: the pinned
  version must already be released before regeneration).
- **Docs**: `README.md` is `site/_data/docs.json` entry #1 (`overview`) and `COMPATIBILITY.md`
  is #2 — editing them is sufficient; **no site-manifest change**; `site/_docs/` is generated
  and gitignored.
- **Vault**: three hub sections (`Decisions`/`Discoveries`/`Sessions`); templates
  `decision.md`/`discovery.md`/`session-log.md`. No `domain/*` tag matches distribution/packaging
  today (closest: `domain/models`, `domain/tooling`) — add `domain/distribution` to
  `vault/_meta/tags.md` before first use. No conda references exist anywhere in the repo yet.
