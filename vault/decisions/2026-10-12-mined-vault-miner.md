---
title: "Mine the Old Growth vault into the benchmark (the tag_assignment recipe first)"
type: decision
tags:
  - type/decision
  - domain/tooling
  - domain/provenance
  - status/draft
created: "2026-10-12"
updated: "2026-10-12"
code-refs:
  - evals/dataset/mined/mine.py
  - evals/dataset/mined/exclusions.py
  - evals/dataset/mined/tag_assignment.py
  - evals/dataset/recipes.py
---

# Mine the Old Growth vault into the benchmark (the tag_assignment recipe first)

Part of [[ember]]. The benchmark mines the maintainer's Old Growth vault
(`../oldgrowth/docs/vault`, pinned at `692f4bb5`) into a new `mined_vault`
family — `tag_assignment` first (65 items), then `memory_worthiness`,
`note_placement`, `staleness`. This note records what the implementation
settled; the real-data surprises live in
[[2026-10-12-oldgrowth-vault-real-shapes]] and the deployment drift in
[[2026-10-12-cuda-deployment-request-cap-drift]].

## Context

- The source is all-rights-reserved; the copyright holder's written grant is
  recorded in `../oldgrowth/LICENSES.md` (commit `422648d9`), and the miner
  refuses without it (FR-012).
- Maintainer clarifications (specs/007, 2026-10-12): the headline features
  every decision family (a coding-only headline is rejected); items come from
  the non-spec memory notes only; candidate tag sets cap at 16; states carry
  the full as-read vocabulary with its one-line descriptions (FR-017); the
  ember-vault source keeps its tested mechanism with its items deferred.
- The label review protocol is unchanged: gold is the vault's own conventions,
  never the model's output.

## Decision

- `ember eval mine` snapshots the pinned commit through read-only git (never
  the working tree) and writes items, extends `splits.lock`, and records a
  sampling manifest atomically; re-mining is byte-idempotent and drops stale
  items of the recipe.
- Classification runs first-match-wins: out of scope under `Specs/` (by path,
  `type/spec` tag, or the `type` field), then moc/hub/index shapes, then an
  80-word floor and a 12,000-word ceiling (`oversize`), then tag-set bounds
  (empty or more than 8), then vocabulary drift, then the credential screen
  (reusing `SECRET_PATTERNS` from the dataset's secret guard).
- Gold is the note's own tags; each candidate tag becomes one `noul`;
  candidates are gold plus 8 seeded same-axis distractors, capped at 16; the
  state is the note plus the full as-read vocabulary (FR-017).
- Provenance: `Source.mined` requires `register_row`; `RegisterRow` gained
  `permission` (required for a `custom_permissive` used row);
  `register.validate` resolves mined items; the dataset card renders the
  source with its licence, permission, snapshot/mirror hashes, and
  attribution (FR-016).

## Consequences

- The phase gate: dataset version `4049ac55a1fa`; `check` is green; the MPS
  tag_assignment run scored 80.5% [77.8, 83.4] over 724 questions; the full
  MPS re-run (81.3% over 1,535 questions) is the newest bundle, so the
  headline features the mined family like every other decision recipe.
- The 65 items' per-label sparsity keeps the `label-in-both-splits` lint and
  the fixed-question-set test scoped to authored recipes; mined recipes carry
  per-item deterministic sets (FR-010). The lint reports those gaps in
  report mode and never enforces them.
- The three later recipes reuse the same miner with their own extractors
  (`memory_worthiness`, `note_placement`, `staleness`); nothing else needs to
  change to add them.
