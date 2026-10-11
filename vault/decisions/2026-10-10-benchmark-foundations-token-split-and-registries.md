---
title: "benchmark foundations: token split in usage, one recipe registry, content-hashed dataset versions"
type: decision
tags:
  - type/decision
  - domain/tooling
  - domain/server
  - domain/governance
  - status/draft
created: "2026-10-10"
updated: "2026-10-10"
code-refs:
  - evals/dataset/__init__.py
  - evals/metrics.py
  - evals/leaderboard.py
  - evals/eval/run_evals.py
  - ember/serving/runtime.py
  - specs/004-benchmark-categories/spec.md
  - specs/004-benchmark-categories/research.md
---

# benchmark foundations: token split in usage, one recipe registry, content-hashed dataset versions

Part of [[ember]]. Phase 0 of the benchmark-categories programme
(`specs/004-benchmark-categories/`) settles six planning decisions that every later phase
builds on: the server returns the token split in `usage`; recipes have one registry; items
carry a typed `source` with seven kinds; the dataset version is a content hash that ignores
annotations; every touched oversize `evals/` module is split; and the release flow names the
dataset hash in the changelog.

## Context

The maintainer's design note `docs/Ember Benchmark Categories.md` (2026-10-10) lays out a
thirteen-phase programme: new recipe families (the risk trio, harm and security, spec-kit
gates, grounding, boundary, memory), dataset growth to 10,000–14,000 items, measurement
hygiene, and an integration axis. Three constraints shaped the foundations: the project
has one maintainer (no second labeller), external datasets are welcome when their licences
allow, and provenance is required for everything. Planning (research R1–R24) found four
places where the obvious design would have hurt later phases.

## Decision

- **Token split in `usage` (R8).** `Engine.advise` already measures `RequestSize` for the
  limit check; it now adds `state_tokens`, `fixed_tokens`, `media_tokens` to the response's
  `usage`. The harness is an HTTP client with no engine in-process, so this is the only
  exact count available to it; it refuses to run against a server that lacks the fields.
  Additive and SystemOne-compatible, but a response-field change under Article II, so it
  lands with README, COMPATIBILITY, and tests.
- **One recipe registry (R1).** `report_text.RECIPES` (prose only) is retired into
  `evals/dataset/recipes.py` (`RecipeSpec`: prose plus family, phase, risk, compliance,
  policy slot, lint mode). Two registries would be reject-worthy under Article XV §15.4.
- **Typed `source`, seven kinds (R9).** `authored`, `mined`, `captured`, `perturbed`,
  `templated`, `drafted`, `imported`, each with the references that let the item be
  regenerated; `authored` was added because the design note's recipes are hand-written and
  that is neither mined nor drafted. Legacy `"curated"`/`"skill_md"` strings read as
  `authored` through a shim.
- **Content-hashed versions (R11).** The dataset version and per-recipe hashes cover the
  scoring projection only (`id`, `category`, `split`, `state`, media, `questions`,
  `gold_labels`). Hashing whole records would have made every annotation change — Phase 1
  re-tagging all 475 items by kind, tier tags, the `source` migration itself — a new version
  that orphans every earlier run. The file-bytes hash stays for provenance.
- **Debt paydown on touch (R19).** `metrics.py`, `analysis.py`, `report_text.py`,
  `sections_results.py`, and `eval/run_evals.py` are over the Article X 400-line ceiling and
  must change for Phase 0; each is split below it and removed from §10.18.
- **Changelog hash (R22).** The release workflow writes `Benchmark dataset: <hash>` into the
  new changelog section and the release notes, since commitizen cannot know the dataset.
- **Consistency and by-source summaries now (R21).** Computed by `aggregate` beside `risk`
  and `tokens` so Phases 3 and 7 do not reopen a freshly split module.

## Consequences

- `usage` is part of the public response; the minimum server version that returns the
  split is documented, and a hosted deployment must be upgraded before it is benchmarked.
- Re-tagging, tiering, and rationale edits never change the dataset version; a gold, state,
  question, or split change always does, and `--resume` compares content hashes.
- Every later phase's specification cites `specs/004-benchmark-categories/spec.md` as its
  parent and may refine but not weaken its rules.
- The §10.18 list in the constitution shrinks by five modules in the same change.
