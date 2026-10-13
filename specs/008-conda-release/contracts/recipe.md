# Contract: conda-forge recipe (`conda/recipe.yaml`)

**Feature**: `008-conda-release` · v1 recipe format · macOS and Linux only (Windows skipped) · Python 3.12 build

The recipe is the interface between ember and conda-forge. It is authored in-repo for review and
version sync, submitted to `conda-forge/staged-recipes`, and thereafter lives canonically in the
`conda-forge/ember-advise-feedstock` repository (kept current by `regro-cf-autotick-bot`).

## Required shape

```yaml
context:
  version: "0.15.0"        # MUST equal pyproject.toml [project].version (rewritten by cz bump)
  python_min: "3.12"

package:
  name: ember-advise
  version: ${{ version }}

source:
  url: https://pypi.org/packages/source/e/ember-advise/ember_advise-${{ version }}.tar.gz
  sha256: <sdist sha256>

build:
  number: 0
  skip: [win]                # ember imports fcntl (Unix-only), so Windows is unsupported
  script: ${{ PYTHON }} -m pip install . -vv --no-deps --no-build-isolation
  python:
    entry_points:
      - ember = ember.cli:main
      - gut = ember.cli:main
      - ember-advise = ember.cli:main
      - ember-mcp = ember.mcp.mcp_server:main

requirements:
  host:
    - python ${{ python_min }}.*
    - pip
    - hatchling >=1.27
  run:
    - python                      # unconstrained for non-noarch; the 3.12 build pins it
    - pytorch >=2.12,<2.14         # PyPI "torch"; approved co-installability divergence (v3.4.0)
    - torchvision >=0.27,<0.29
    - transformers >=5.18,<6
    - safetensors >=0.8,<1
    - huggingface_hub >=1.32,<2    # PyPI "huggingface-hub"; below the declared floor (transformers' chain)
    - accelerate >=1.15,<2
    - pillow >=12,<13
    - fastapi >=0.142,<1
    - uvicorn-standard >=0.54,<1   # PyPI "uvicorn[standard]"
    - pydantic >=2.13,<3
    - mcp >=2.3,<3
    - httpx >=0.28,<1
    - prometheus_client >=0.21,<1  # PyPI "prometheus-client"
    - boto3 >=1.40,<2

tests:
  - python:
      imports: [ember]
      pip_check: false   # the wheel's declared ranges are the upstream ones this recipe overrides (v3.4.0)
  - script:
      - ember --help
      - python -c "import sys, ember.mcp.mcp_server; assert 'torch' not in sys.modules"

about:
  license: MIT
  license_file: LICENSE
  summary: "A gut feeling for coding agents: calibrated advice over MCP from Cloudflare's Clef model."
  homepage: https://shapeandshare.github.io/ember/
  repository: https://github.com/shapeandshare/ember

extra:
  recipe-maintainers:
    - <maintainer-github-handle>
```

## Rules

1. **Version**: written literally in `context.version` for the submitted release — a frozen
   submission snapshot, **not** listed in `[tool.commitizen] version_files` (commitizen cannot
   refresh `source.sha256`, so a version-wired copy would lie); the feedstock bot carries future
   versions, and `tests/test_distribution.py` asserts only a valid `X.Y.Z`.
2. **Names**: every `run` dependency uses its conda-forge name, not its PyPI name
   (`pytorch`, `huggingface_hub`, `prometheus_client`, `uvicorn-standard`).
3. **Entry points**: all four scripts declared; naming matches `[project.scripts]` exactly.
4. **Python**: `python_min: "3.12"` pins the build to 3.12; `run: python` stays unconstrained (non-noarch).
5. **License**: SPDX `MIT` + `license_file: LICENSE` shipped in the sdist.
6. **No weights**: the package carries only the tool (well under 50 MB); weights remain a
   runtime download (Article I).
7. **Platforms**: not noarch — Windows is skipped (`skip: [win]`; ember imports the Unix-only
   `fcntl`).

## Approved dependency divergence (co-installability)

conda-forge cannot install the declared set for Python 3.12: `torchvision` co-installs only
with `pytorch <2.14` (feedstock #135 decouples torch↔torchvision from PyPI), and the
`transformers` chain forces `huggingface_hub <2` while conda-forge offers only `1.32.0` in that
range (below ember's `>=1.33` floor). **Maintainer decision (2026-10-12, constitution
v3.4.0): diverge** — the recipe pins the newest co-installable stack: `pytorch >=2.12,<2.14`,
`torchvision >=0.27,<0.29`, `huggingface_hub >=1.32,<2`.

- Validated by the first-publication model-backed runs on both platforms (FR-005); the run
  records name the series exercised.
- Recorded in the spec (FR-004 exception), research R3, and the plan's Complexity Tracking.
- Retired — pins converged back to the declared ranges — when conda-forge catches up, with
  fresh model-backed runs per the lock-move rule (FR-015).

## Submission steps (one-time)

1. Fork `conda-forge/staged-recipes`; branch from `main`.
2. Add `recipes/ember-advise/recipe.yaml` (above).
3. Run `conda-smithy recipe-lint .` (and optionally a local build) until clean.
4. Open a PR titled `Add ember-advise`; comment `@conda-forge/help-python, ready for review!`.
5. Address review; ensure the maintainer comment confirms willingness.
6. On merge, `create_feedstocks` creates `conda-forge/ember-advise-feedstock`.
7. Optionally open `@conda-forge-admin, please add bot automerge` once the recipe is stable.
