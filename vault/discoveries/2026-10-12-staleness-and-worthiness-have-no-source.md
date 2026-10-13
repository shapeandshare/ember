---
title: "No stale markers and no did-not-become fragments exist at the pinned vault"
type: discovery
tags:
  - type/discovery
  - domain/tooling
  - domain/provenance
  - status/draft
created: "2026-10-12"
updated: "2026-10-12"
code-refs:
  - evals/dataset/mined/mine.py
  - specs/007-mined-vault-recipes/spec.md
---

# No stale markers and no did-not-become fragments exist at the pinned vault

Part of [[ember]]. Two of specs/007's three later recipes cannot be mined from the
pinned source (`692f4bb5`) because their gold conventions have no material:
`staleness` has zero positives and `memory_worthiness` has no negatives.
`note_placement` mined fine (30 items, 10 folders — see
[[2026-10-12-mined-vault-miner]]).

## What was tested

A structured scan of every note at the pin: frontmatter `stale:`, `status/stale`,
`status/superseded`, and candidate-pool membership (the exclusion rules applied
exactly as the miner applies them). Vault-wide: **1,074 notes, all with no stale or
superseded marker**; `git grep` hits for those terms are prose discussions
(e.g. `Discoveries/Spec Stub Status Tag Vocabulary Debt.md`, whose frontmatter reads
`status: reviewed`), not markers.

## Finding

- `staleness` (“is this note's claim stale?”; gold = the `stale:`/`status/*`
  convention) would emit only gold-`false` items — a degenerate grader with no
  positive class. The vault keeps itself current: the audit sets `stale:` only when
  drift is confirmed, and the maintainer clears it after re-verification, so at this
  pin no note is marked.
- `memory_worthiness` (“does this fragment deserve a note?”; gold = what comparable
  material became) needs fragments that did **not** become notes. The vault stores
  only what was kept — the raw material has no home in the source, so negatives
  cannot be drawn without inventing them.
- `note_placement` is unaffected: every note has an actual folder, so the gold has
  full variance (30 items across 10 folders).

## Relevance

Both recipes are deferred rather than shipped degenerate (specs/007 assumptions let
each recipe graduate when its material exists). Options when they return: mine
`staleness` from a later pin where the audit has flagged notes, or from the
semantic-drift flow once markers exist; ground `memory_worthiness` in a captured
session source (the `ember eval capture` path exists for consented material) with
the maintainer adjudicating where the convention is silent. The tasks list records
the deferral; nothing blocks the shipped families.

## References

- `specs/007-mined-vault-recipes/spec.md` (US3, FR-003), `tasks.md` (T026/T030)
- `evals/dataset/mined/exclusions.py` (the candidate scan)
- `vault/discoveries/2026-10-12-oldgrowth-vault-real-shapes.md`
