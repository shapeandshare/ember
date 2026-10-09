---
title: release automation constraints on a public repo
type: discovery
tags:
  - type/discovery
  - domain/tooling
  - status/draft
created: 2026-10-05
updated: 2026-10-09
code-refs:
  - .github/workflows/release-ember.yml
---

# release automation constraints on a public repo

Part of [[ember]]. Four GitHub behaviors make an automated bump-PR release
flow trickier than it looks; each one cost a failed release cycle during
the 2026-10-04/05 hardening of [[2026-10-04-version-components-separately]].

## What was tested

Live release cycles for both components on the public `shapeandshare/ember`
repository: the skip path (`docs(plugin):` commit), the happy path
(`fix(plugin):` commit), the approval-gated recovery, and a behind-main
collision. Logs, run states, and branch states were captured from
`gh run list/view`, the runs REST API, and the PR API.

## Finding

1. **Bot PR checks can sit in `action_required`.** The bump PRs opened by
   `github-actions[bot]` with `GITHUB_TOKEN` needed a maintainer to approve
   their first workflow runs (the public-repo contributor gate). The wait
   step timed out at 10 min, twice. A synchronize run after approval did
   **not** need approval again.
2. **`GITHUB_TOKEN`-initiated merges do not start workflows.** When
   auto-merge (enabled by the bot) merged the bump PR, no `push`-triggered
   release run fired — GitHub's recursion prevention. The release needed a
   `workflow_dispatch` to complete.
3. **Strict "require branches to be up to date" blocks the bump PR as soon
   as main advances.** Nothing updated the branch; auto-merge waited
   forever on a `BEHIND` PR with green checks. `gh pr update-branch` fixed
   it and the follow-up CI run needed no approval.
4. **Tags point at pre-squash bump commits, so `git describe` cannot find
   them from main.** Commitizen matches the current version against the
   tag list by name (`find_tag_for`), not `git describe` — which is why
   cz bumped correctly while `git describe --tags` failed on main. The
   resume detection had to match by name too (`refs/tags/v$version`).

## Relevance

The hardened workflows now handle all four: the wait detects
`action_required` and prints instructions; the timeout message directs a
maintainer to approve, let the bump PR merge, then **dispatch** the
workflow; the wait updates a `BEHIND` branch; and the resume path detects
"main carries a version newer than the last tag" and goes straight to
tagging and publishing. Tags created from now on target merged main
commits. Any future automation that opens PRs with `GITHUB_TOKEN` on this
repo will hit constraints 1–3 and should plan for them.

## References

- `vault/decisions/2026-10-04-version-components-separately.md`
- `vault/decisions/2026-10-03-harden-github-before-going-public.md`
- Release-plugin run logs 37248332838 (timeout), 37250282925 (resume path)
- PR #49 (approval-gated bump PR), PR #50 (resume logic), PR #51 (behind-branch fix)
