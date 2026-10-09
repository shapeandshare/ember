---
title: version components separately
type: decision
tags:
  - type/decision
  - domain/governance
  - domain/tooling
  - status/superseded
created: 2026-10-04
updated: 2026-10-09
code-refs:
  - pyproject.toml
  - packages/opencode-plugin/package.json
  - packages/opencode-plugin/CHANGELOG.md
  - .github/workflows/release-ember.yml
---

# version components separately

> Superseded by [[2026-10-09-publish-releases-to-pypi-and-the-mcp-registry]]: the opencode plugin no longer versions or releases separately.

Part of [[ember]]. Each releasable component carries its own version, changelog,
and git tag series — `v*` for the Python package, `plugin/v*` for the opencode
plugin — and its own release workflow; `evals/` and `site/` are unversioned and
appear in the root changelog only.

## Context

- The repo ships two independently installable artifacts: the `gut` wheel (PyPI,
  CLI, MCP server, agent kit) and the npm plugin `opencode-ember-advise`. They
  change on different cadences, and opencode's plugin API can move independently of
  the Python stack.
- Until 2026-10-04 a single root `CHANGELOG.md` and one `v*` tag series covered
  everything, so a plugin-only release could not be identified or pinned.
- `evals/` is an internal benchmark harness that no consumer installs or pins (the
  published form is `benchmark/<run-id>/` data the site renders), and `site/` is
  rebuilt from `main` on every deploy; a version number for either would have no
  consumer.
- GitHub Actions cannot open pull requests unless the repository enables it, and
  the original hardening had set the workflow token read-only (see
  [[2026-10-03-harden-github-before-going-public]]).

## Decision

- Commit scopes name the component: `ember`, `plugin`, `evals`, `site`;
  cross-cutting changes may omit the scope. The discipline lives in `AGENTS.md`
  principle 6 and `CONTRIBUTING.md`.
- Versioned separately: `ember` → `v*` tags + PyPI wheel + root `CHANGELOG.md`;
  `plugin` → `plugin/v*` tags + npm package + `packages/opencode-plugin/CHANGELOG.md`.
- Two release workflows, one per component, triggered by each component's paths:
  `release-ember.yml` (`ember/**`, `evals/**`) and `release-plugin.yml`
  (`packages/opencode-plugin/**`). Each computes the next version from conventional
  commits, commits the bump, pushes a `ci/bump-*` branch (no tag yet), opens a PR
  with auto-merge, waits for that PR to actually merge, then verifies the merged
  version, tags the merged commit, builds, and creates the GitHub Release.
- The ember side releases on commitizen's rules. The plugin side releases only for
  `feat` (minor) and `fix`/`perf`/`refactor`/`revert` (patch) commits;
  `docs`/`chore`/`test`/`ci`/`style`/`build` changes accumulate until a
  release-worthy commit arrives.
- `evals/` and `site/` are not versioned; their changes ride the root changelog.
- The repository enables "Allow GitHub Actions to create and approve pull requests"
  with a read-write default token so the workflows can open their bump PRs with
  `GITHUB_TOKEN` — no stored personal token.

## Consequences

- A plugin-only `feat(plugin):` commit releases `plugin/v*` without touching the
  Python version, and vice versa; a commit touching both releases both.
- A bump can never trigger another bump: bump subjects (`release v…`,
  `release plugin/v…`) are filtered out of the commit scan, only the component's
  own paths trigger its workflow, and GitHub does not start workflow runs from
  `GITHUB_TOKEN`-initiated merges — three independent guards.
- Tags are created only after the bump PR merges, so a blocked, closed, or
  timed-out release leaves no tag and no release behind; re-running the workflow
  force-pushes the same branch, reuses the open PR, and updates a branch that fell
  behind main while waiting. Tags created from now on point at merged main commits
  (the lookup matches by tag name, like commitizen, because older tags point at
  pre-squash bump commits).
- If the bump PR's checks sit in `action_required` — the public-repo contributor
  gate observed on the bot's first PRs — the wait prints a note and eventually
  fails with instructions; a maintainer approves the runs, lets the bump PR merge,
  then dispatches the workflow. A resumed run detects that main already carries the
  new version and goes straight to tagging and publishing it.
- Bump PRs pass the full `pr-ready` gate before merging, including the
  workflow-security job; the token change buys no bypass of the ruleset's required
  checks (documented in [[2026-10-03-harden-github-before-going-public]]).
- A new component that consumers install must get its own scope, version file,
  changelog, and release path; internal folders stay on the root changelog.
- Manual triggers: `make release-ember` / `make release-plugin` dispatch the
  workflows; `make release-dry` previews the next ember version.
