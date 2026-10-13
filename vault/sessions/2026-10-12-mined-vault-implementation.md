---
title: "The mined-vault implementation session: the Phase 2 gate"
type: session-log
tags:
  - type/session-log
  - domain/tooling
  - domain/provenance
  - status/draft
created: "2026-10-12"
updated: "2026-10-12"
code-refs: []
---

# The mined-vault implementation session: the Phase 2 gate

Part of [[ember]]. Took specs/007 (Phase 2 of the benchmark programme) from
spec to a closed gate in one session: five maintainer clarifications, the
plan and task list, the full implementation, and the live runs.

## What the session did

- Clarified (specs/007): headline features every decision family; items from
  the non-spec memory notes only; 16-candidate cap; the full as-read
  vocabulary in item states; the ember-vault source deferred with its
  mechanism tested.
- Implemented the miner (`evals/dataset/mined/`): snapshot (read-only git at
  the pin), frontmatter, vocabulary, exclusions (first-match-wins), seeded
  selection, `tag_assignment` items, the `mine` composition root, and
  `ember eval mine`; two schema changes (`Source.mined.register_row`,
  `RegisterRow.permission`) with `register.validate` resolving mined items.
- Mined the 65 items from `692f4bb5` (200 candidates; exclusions recorded),
  appended the first `used` register row (`oldgrowth-vault`), and recorded
  dataset version `4049ac55a1fa`; `check` green.
- Ran the gate: MPS tag_assignment 80.5% (0 errors), CUDA 80.1% (7 items
  refused by the deployment's old cap), then the full MPS re-run 81.3% over
  1,535 questions (0 errors) as the newest bundle; tiers and card refreshed.
- Unit suite 1,749 passing; the real-data lessons and the deployment drift
  are written up as [[2026-10-12-oldgrowth-vault-real-shapes]] and
  [[2026-10-12-cuda-deployment-request-cap-drift]].

## Still open

US3: `note_placement` shipped (30 items across 10 folders, its kit entry
included); `staleness` and `memory_worthiness` are deferred — the pinned
source has no stale markers and no did-not-become fragments (see
[[2026-10-12-staleness-and-worthiness-have-no-source]]). Also open: the
deployment refresh plus a clean CUDA re-run; PR and release
(maintainer's call — merging to main triggers the release workflow). One
latent bug found on the way and fixed in the same session: the site build
crashed when the newest committed bundle was a category-scoped run
(`scripts/build_site_benchmark.py` assumed the kind blocks exist); the
headline now comes from the newest complete run (falling back to the newest
headline-capable run, and to no headline when none exists), with tests
covering a partial newest and a partial-only tree.
