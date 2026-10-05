---
title: add SonarCloud scanning
type: session-log
tags:
  - type/session-log
  - domain/tooling
created: 2026-10-04
updated: 2026-10-04
code-refs:
  - .github/workflows/ci.yml
  - sonar-project.properties
---

# session: add SonarCloud scanning

Part of [[ember]].

## What was done

Added SonarCloud scanning to the CI pipeline.

### Files changed

- `sonar-project.properties` — new file; org `shapeandshare`, project `shapeandshare_ember`,
  source `ember/`, tests `tests/`, coverage report path `coverage.xml`, exclusions for
  `scripts/`, `site/`, `benchmark/`, `evals/`, `packages/`, `vault/`, `assets/`.
- `.github/workflows/ci.yml` — new `sonar` job: `ubuntu-latest`, `contents: read` only,
  `fetch-depth: 0` for blame history, unit tests via `uv run pytest tests/ -m "not model and not evals" --cov=ember --cov-report=xml --cov-fail-under=0`,
  then `SonarSource/sonarqube-scan-action@d209202bc7d53ff1cc128f7f907dac145c9d6ae9 # v8.3.0`.

  The `--cov-fail-under=0` keeps the job reporting-only: the coverage ratchet
  (`fail_under=71`, Article XI) is enforced by `make test-cov` against the local full
  suite, while this narrower CI subset computes ~70%.

### Key decision: use sonarqube-scan-action, not sonarcloud-github-action

`SonarSource/sonarcloud-github-action` was archived 2026-10-22. zizmor flagged it
`archived-uses` (medium severity). The official drop-in replacement is
`SonarSource/sonarqube-scan-action` (active, SonarSource-maintained, same env vars and
`sonar-project.properties` convention). Pinned to `v8.3.0` /
`d209202bc7d53ff1cc128f7f907dac145c9d6ae9`. zizmor reports clean after the swap.

## Outstanding manual step (repo admin)

The Actions allow-list currently permits only `astral-sh/setup-uv@*` and
`zizmorcore/zizmor-action@*`. Add the new action before pushing:

```bash
gh api -X PUT repos/shapeandshare/ember/actions/permissions/selected-actions \
  --input - <<<'{
    "github_owned_allowed": true,
    "verified_allowed": false,
    "patterns_allowed": [
      "astral-sh/setup-uv@*",
      "zizmorcore/zizmor-action@*",
      "SonarSource/sonarqube-scan-action@*"
    ]
  }'
```

Also add `SONAR_TOKEN` to repo secrets if not already present:
Settings → Secrets and variables → Actions → New repository secret.
