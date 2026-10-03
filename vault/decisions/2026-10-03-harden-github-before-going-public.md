---
title: harden GitHub before going public
type: decision
tags:
  - type/decision
  - domain/tooling
  - domain/governance
  - status/draft
created: 2026-10-03
updated: 2026-10-03
code-refs:
  - .github/workflows/ci.yml
  - .github/workflows/ci-check.yml
  - .github/workflows/release.yml
  - .github/dependabot.yml
  - .github/CODEOWNERS
  - SECURITY.md
---

# harden GitHub before going public

Part of [[ember]]. Before the repository goes public, its workflows treat every pull
request as untrusted code, a `zizmor` job in `ci` keeps them that way, and the
repository and organization settings below are applied in order.

## Context

- On a public repository, a fork's pull request runs the `pull_request` workflows from
  its own branch, so it can rewrite any step, including `runs-on` and `permissions`.
- An audit on 2026-10-03 found 38 zizmor findings (14 high): actions pinned to mutable
  tags, no `permissions:` on `release.yml` or `ci-check.yml`, checkout persisting the
  token, a cached release build, and no Dependabot cooldown. The repository's default
  token was read-write and allowed to approve pull requests, the planned release flow
  wanted a broad personal access token, `CODEOWNERS` named an owner GitHub could not
  resolve, and `SECURITY.md` sent reporters to maintainer-only settings.
- The org's self-hosted macOS runners were reachable from this repository (see
  [[2026-10-03-self-hosted-vms-cannot-hold-the-model]]), and organization secrets are
  visible to it even though no workflow uses them.
- gitleaks found no secrets in the 75 commits across all refs.

## Decision

- Every `uses:` is pinned to a full commit SHA with a version comment, at the major
  version already in use; Dependabot bumps both, after a 7-day cooldown.
- Workflows start from `permissions: {}` and grant per job; checkout sets
  `persist-credentials: false`; every job has a timeout and every workflow a
  concurrency group.
- `release.yml` runs only from `main`, holds the only write permission (`contents`),
  never restores a cache, uses the preinstalled `gh` instead of a third-party release
  action, and documents trusted publishing instead of long-lived tokens.
- No workflow uses `pull_request_target`, `workflow_run`, org secrets, or self-hosted
  runners. Model-backed tests stay on a maintainer's machine.
- Vulnerability reports go through private vulnerability reporting, linked from
  `SECURITY.md` and the issue chooser.

## Consequences

- `uvx zizmor@1.30.1 .github/` must stay clean under the regular and pedantic personas.
- Constitution quality gate 3 names a maintainer's Apple Silicon machine for the
  model-backed suite (1.3.2); this repository never uses a self-hosted runner.
- Settings live outside the repository files. Apply them in order; each must read back
  as set.

| When | Setting | Who |
| --- | --- | --- |
| Applied 2026-10-03 | Default workflow token read-only; Actions may not approve pull requests | repo admin |
| Applied 2026-10-03 | `main` ruleset requires `compile, unit tests, build, install smoke` from GitHub Actions | repo admin |
| Applied 2026-10-03 | Tag ruleset `release-tags`: `v*` tags cannot be deleted or moved; immutable releases on | repo admin |
| Done 2026-10-03 | The runner group holding the self-hosted runners does not allow public repositories (narrowing its repository access is optional) | org owner |
| Done 2026-10-03 | Organization secrets are scoped to the repositories that use them; this repository receives no credentials | org owner |
| Applied 2026-10-03 | Actions allow-list: GitHub-owned plus `astral-sh/setup-uv` and `zizmorcore/zizmor-action`; SHA pinning required; `workflow security (zizmor)` a required check | repo admin |
| Applied 2026-10-03 | Fork pull request workflows need approval for all external contributors; private vulnerability reporting | repo admin |
| Blocked 2026-10-03 | Secret scanning with push protection, and CodeQL default setup: the enforced org code-security configuration `shapeandshare-org-config-1` disables them; an org owner must enable them there or attach this repository to the `GitHub recommended` configuration | org owner |

```bash
R=repos/shapeandshare/ember
# After the workflow change merges
gh api -X PUT $R/actions/permissions --input - <<<'{"enabled":true,"allowed_actions":"selected","sha_pinning_required":true}'
gh api -X PUT $R/actions/permissions/selected-actions --input - <<<'{"github_owned_allowed":true,"verified_allowed":false,"patterns_allowed":["astral-sh/setup-uv@*","zizmorcore/zizmor-action@*"]}'
# Right after going public
gh api -X PUT $R/actions/permissions/fork-pr-contributor-approval -f approval_policy=all_external_contributors
gh api -X PATCH $R --input - <<<'{"security_and_analysis":{"secret_scanning":{"status":"enabled"},"secret_scanning_push_protection":{"status":"enabled"}}}'
gh api -X PUT $R/private-vulnerability-reporting
gh api -X PATCH $R/code-scanning/default-setup -f state=configured
```
