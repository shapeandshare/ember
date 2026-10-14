---
title: "A GITHUB_TOKEN-created release does not fire the `release` event"
type: discovery
tags:
  - type/discovery
  - domain/distribution
  - status/draft
created: "2026-10-13"
updated: "2026-10-13"
code-refs:
  - .github/workflows/release-ember.yml
  - .github/workflows/conda-package.yml
---

# A GITHUB_TOKEN-created release does not fire the `release` event

Part of [[ember]]. `conda-package.yml` triggers on `release: published`, but cutting the first
release with the new conda channel (v0.16.0) reached PyPI and the MCP Registry and silently
skipped the conda upload — no workflow run fired at all.

## What was tested

`make release-ember` ran `release-ember.yml` for v0.16.0. Its `release-ember` job created the
GitHub Release with the workflow's `GITHUB_TOKEN`. Afterwards:

```bash
gh run list --event release          # → [] (no run)
gh run list --workflow conda-package.yml
# only stale `push`-event runs; none from the release
```

PyPI (`curl https://pypi.org/pypi/ember-advise/0.16.0/json` → 200) and the MCP Registry both
published; Anaconda stayed at 404.

## Finding

GitHub suppresses workflow runs for events triggered by the repository's `GITHUB_TOKEN`, with
only two exceptions: `workflow_dispatch` and `repository_dispatch`. The `release: published`
event that `release-ember.yml` causes is suppressed, so `conda-package.yml` never started.
`publish-pypi` and `publish-mcp-registry` were unaffected because they are jobs **in the same
run**, not a downstream event.

## Relevance

Any workflow keyed on a `release`/`tag`/`push` event produced by the release bot will never
fire. Conda is wired the supported way instead: `release-ember.yml`'s `publish-conda` job
dispatches `conda-package.yml` with `workflow_dispatch` (version + `publish=true`) once PyPI has
the sdist — which also removes the PyPI-lag race in the recipe render. A `release` trigger stays
on `conda-package.yml` for a release a person makes in the UI, since a human action does fire it.

## References

- `.github/workflows/release-ember.yml` — the `publish-conda` job
- `.github/workflows/conda-package.yml` — the `publish` input and its gate
- GitHub docs: events triggered by `GITHUB_TOKEN` (the `workflow_dispatch` / `repository_dispatch`
  exemption)
