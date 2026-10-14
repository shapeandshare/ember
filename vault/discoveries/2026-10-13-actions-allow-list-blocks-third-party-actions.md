---
title: "The repo's Actions allow-list blocks third-party actions (silent startup_failure)"
type: discovery
tags:
  - type/discovery
  - domain/distribution
  - status/draft
created: "2026-10-13"
updated: "2026-10-13"
code-refs:
  - .github/workflows/conda-package.yml
  - .github/workflows/conda-smoke.yml
  - tests/test_workflows.py
---

# The repo's Actions allow-list blocks third-party actions (silent startup_failure)

Part of [[ember]]. `conda-package.yml` and `conda-smoke.yml` had never run: both used a
third-party Action, and the repository's Actions allow-list blocks it, failing every run at
startup (`startup_failure`) with the reason visible only in the Actions tab.

## What was tested

Dispatching `conda-package.yml`:

```bash
gh workflow run conda-package.yml --ref main -f version=0.16.0 -F publish=true
# → startup_failure, 0 jobs
```

`actionlint` and the YAML parse test both passed, so it was not syntax. The run page's
annotation named the cause.

## Finding

The repository setting is `allowed_actions: selected` with
`patterns_allowed: [astral-sh/setup-uv@*, zizmorcore/zizmor-action@*, ruby/setup-ruby@*,
SonarSource/sonarqube-scan-action@*]` and `github_owned_allowed: true`. Any `uses:` outside
GitHub-owned `actions/*` and those patterns makes the workflow refuse to start —
`prefix-dev/rattler-build-action` and `mamba-org/setup-micromamba` were both blocked.

## Relevance

Workflows must stick to GitHub-owned actions or the four allow-listed publishers. Where a
third-party action was wanted, the tool is now installed directly from a pinned release asset
with a sha256 check (`rattler-build` in `conda-package.yml`, `micromamba` in `conda-smoke.yml`),
the same pattern `release-ember.yml` uses for `mcp-publisher`. `tests/test_workflows.py` now
fails if any workflow uses an action outside the allow-list, so this cannot merge unnoticed
again.

## References

- `.github/workflows/conda-package.yml`, `.github/workflows/conda-smoke.yml`
- `tests/test_workflows.py` — the allow-list guard
- `vault/discoveries/2026-10-13-github-token-release-events-are-suppressed.md` — the other
  silent workflow failure fixed the same day
