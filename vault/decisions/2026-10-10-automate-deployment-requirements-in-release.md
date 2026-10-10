---
title: "Regenerate deployment/requirements.txt automatically in the release bump"
type: decision
tags:
  - type/decision
  - domain/tooling
  - status/draft
created: "2026-10-10"
updated: "2026-10-10"
code-refs:
  - .github/workflows/release-ember.yml
  - scripts/freeze_deployment_requirements.py
  - deployment/requirements.txt
---

# Regenerate deployment/requirements.txt automatically in the release bump

Part of [[ember]]. `.github/workflows/release-ember.yml`'s version-bump step now runs `make
deployment-requirements` and folds the result into the same bump commit, so
`deployment/requirements.txt`'s `ember-advise==<version>` pin (and its resolved dependency
set) stays current with every release automatically.

## Context

During this session's Outerbounds redeploy work
([[2026-10-10-fast-bakery-strips-ember-advise-from-deploy-requirements]],
[[2026-10-10-disable-torch-native-jit-for-cuda-compiler-gap]]), `deployment/requirements.txt`
had to be manually regenerated and committed after every release to pick up the new
`ember-advise` version — a step easy to forget, and in fact forgotten at least once this
session (the file still read `ember-advise==0.8.1` well after several releases had shipped
fixes to PyPI). The pin only matters at actual deploy time (`make deploy` always runs
`deployment-requirements` first), so a stale committed file is not itself a live bug — but it
is misleading: a developer reading the committed file sees a version far behind what's
actually released, and a deploy run from a checkout that skips `make deployment-requirements`
(unlikely given `deploy`'s own prerequisite, but possible via a raw `outerbounds app deploy`
invocation) would ship a stale, possibly pre-fix wheel.

## Decision

- **`.github/workflows/release-ember.yml`**: after `cz bump --changelog --yes` succeeds (so
  `pyproject.toml` already carries the new version) and before computing `BUMP_TAG`, the
  workflow runs `make deployment-requirements` and amends the result into the still-unpushed
  bump commit (`git commit --amend --no-edit`) if the file actually changed. This keeps a
  single atomic bump commit — version + changelog + deployment pin together — rather than a
  separate follow-up commit.
- **No loop-prevention risk**: the workflow's own paths filter is `ember/**`/`evals/**`;
  `deployment/**` does not match either, so amending this file into the bump commit cannot
  cause the bump to re-trigger `release-ember.yml` (the existing "Loop prevention" note at
  the top of the file already covers `pyproject.toml`/`uv.lock`/`CHANGELOG.md` for the same
  reason).
- **Runs the full `uv export` + freeze, not just the pin bump**: `make
  deployment-requirements` re-resolves the entire dependency set from `uv.lock` (which `cz
  bump` may itself have changed) and re-applies marker resolution, not merely the
  `ember-advise==<version>` line — so a release that also bumps a transitive dependency stays
  fully in sync, not just its own version pin.
- **No change needed to the "resume" path** (when main already carries a newer version than
  the last tag, from a bump PR that merged but whose release step failed): that path reads
  the *already-merged* `deployment/requirements.txt` from main, which by definition already
  went through this same regeneration on its own bump run.

## Consequences

- Every future release's bump PR diff will include `deployment/requirements.txt`'s refreshed
  contents whenever the dependency set or project version actually changed — reviewers should
  expect this and not treat it as unexpected scope.
- `scripts/freeze_deployment_requirements.py`'s own regression test
  (`test_committed_requirements_file_has_the_ember_advise_pin`, added in
  [[2026-10-10-regression-tests-for-outerbounds-deploy-contract]]) now has a second line of
  defense: even if a human forgets to run `make deployment-requirements` locally before a
  manual commit, the automated release path self-heals it on the next release.
- If `make deployment-requirements` ever fails in CI (e.g. `uv export` hitting a genuine
  resolution conflict), the bump step now fails loudly rather than silently shipping a stale
  file — this is treated as acceptable since a failing `uv export` here would likely indicate
  a real, release-blocking dependency problem worth surfacing immediately.

## References

- [[2026-10-10-fast-bakery-strips-ember-advise-from-deploy-requirements]] — the original gap
  this doesn't fix (the missing pin entirely) but complements (keeping the pin current once
  fixed).
- [[2026-10-10-regression-tests-for-outerbounds-deploy-contract]] — the test suite's own
  defense-in-depth for the same artifact.
