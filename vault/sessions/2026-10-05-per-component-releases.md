---
title: per-component releases and hardening
type: session-log
tags:
  - type/session-log
  - domain/tooling
  - domain/governance
created: 2026-10-05
updated: 2026-10-05
---

# per-component releases and hardening

Part of [[ember]]. Split versioning and release automation per component,
then live-tested it until both paths released cleanly.

## What happened

- PR #31 introduced commit scope discipline (`ember`, `plugin`, `evals`,
  `site`) and the per-component versioning decision.
- PR #34 split `release.yml` into `release-ember.yml` (paths `ember/**`,
  `evals/**`) and `release-plugin.yml` (`packages/opencode-plugin/**`) —
  the per-job `contains(toJson(...))` conditions were unreliable on
  squash-merge push events.
- PR #36 fixed the plugin bootstrap scan (no `plugin/v*` tag meant an
  empty commit scan); PR #39 filtered bump commits so a bump never
  triggers another bump.
- PRs #32/#33/#37/#40/#48 live-tested the flows: `v0.2.0`, `plugin/v0.2.0`,
  `v0.3.0`, `plugin/v0.3.0`, and a real `fix(plugin):` for the npm plugin's
  hardcoded `EMBER_AUTOSTART` (with node:test coverage, wired into CI).
- PR #44 fixed plugin release-note extraction (dated headings); PR #45
  ignored `.coverage`.
- Critical review (PRs #46, #50, #51): releases now push the bump branch
  without a tag, wait for the PR to actually merge, update a `BEHIND`
  branch, detect a version already merged on main and resume at the tag
  step, then tag the merged commit. Tags now point at real main commits.
- Live recovery: the approval gate timed out a plugin release with no tag
  created; after approving the runs and merging the bump PR, a dispatch
  published `plugin/v0.3.1` through the resume path (tag `828e0f6`).

## Decisions and discoveries written back

- [[2026-10-04-version-components-separately]]
- [[2026-10-05-release-automation-constraints]]
- [[2026-10-03-harden-github-before-going-public]]

## Follow-ups

- The next `feat(ember)`/`fix(ember)` exercises the ember resume path (the
  ember flow shipped the same code but its last release predates it).
- Model-backed suite still requires a maintainer's Apple Silicon machine;
  run `make test` before the next model-affecting change.
