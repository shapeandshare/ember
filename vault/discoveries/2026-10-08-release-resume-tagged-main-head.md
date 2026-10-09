---
title: "A resumed release tagged main's head and swept later PRs into v0.6.0"
type: discovery
tags:
  - type/discovery
  - domain/tooling
  - status/draft
created: "2026-10-08"
updated: 2026-10-09
code-refs:
  - .github/workflows/release-ember.yml
  - CHANGELOG.md
---

# A resumed release tagged main's head and swept later PRs into v0.6.0

Part of [[ember]]. The release workflows' resume path tagged `origin/main` instead of the
commit that set the version, so a release resumed after later merges shipped those merges
under the old version. Extends [[2026-10-05-release-automation-constraints]].

## What was tested

- The run for #76 timed out waiting for bump PR #77 (`release v0.6.0`), so nothing was
  tagged. #78 merged next. #79's merge started the workflow, which found main at 0.6.0
  with no `v0.6.0` tag and took the resume path.
- `release-ember.yml` then ran `git tag … "${BUMP_TAG}" origin/main`: `v0.6.0` landed on
  #79's merge commit `85fa787`, not on the bump commit `6391c0b`. The release notes, taken
  from the `## v0.6.0` CHANGELOG section, listed only #76.
- `make release-dry` reported no new commits, so #78 and #79 would never get a release or
  a changelog entry of their own.

## Finding

- Both release workflows tagged main's head. In the resume path that is any later PR; even
  in the normal path, a PR merged between the bump's merge and the tag step would be swept
  in, and the release assets were built from main's head too.
- The commit that set a version can be found without running the release tooling:
  `git log -S 'version = "X"' -- pyproject.toml`, keeping the newest commit whose own tree
  carries that version (`"version": "X"` in `packages/opencode-plugin/package.json` for the
  plugin). On the real history it reproduces every correctly placed tag: `v0.4.0`,
  `v0.5.0`, and `plugin/v0.3.2`.

## Relevance

- Both workflows now tag that bump commit and build the release from its tree.
- The published `v0.6.0` was left in place (the maintainer chose to move forward rather
  than move a public tag); its release notes and the CHANGELOG now say it also ships #78
  and #79.

## References

- `.github/workflows/release-ember.yml`, `.github/workflows/release-plugin.yml`
- Release run 37868312174 (resumed, tagged `85fa787`); run 37821912620 (timed out)
