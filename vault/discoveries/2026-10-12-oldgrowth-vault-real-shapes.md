---
title: "The Old Growth vault's real shapes: em-dashes, binaries, spec siblings, one 17k-word note"
type: discovery
tags:
  - type/discovery
  - domain/tooling
  - domain/provenance
  - status/draft
created: "2026-10-12"
updated: "2026-10-12"
code-refs:
  - evals/dataset/mined/snapshot.py
  - evals/dataset/mined/exclusions.py
  - tests/fixture_vault.py
---

# The Old Growth vault's real shapes: em-dashes, binaries, spec siblings, one 17k-word note

Part of [[ember]]. The first live `ember eval mine` against the pinned
checkout (`692f4bb5`) crashed or mis-sampled four times before the 65-item
pool was right; every shape is now a regression test in the fixture vault.

## What was tested

The live miner against `../oldgrowth` at the pin, then the corrected run
(200 candidates, 65 items), repeated twice for byte-idempotency.

## Finding

- `git ls-tree` **C-quotes non-ASCII paths** (`"…\342\200\224…"` for an
  em-dash filename), so reads of `Anomalies — Domain MOC.md` failed; fixed
  with `ls-tree -z` (raw NUL-delimited paths).
- `docs/vault` carries **binary blobs** (PNG artwork); decoding them as UTF-8
  crashed the snapshot. `files()` now yields text files only, while the tree
  digest still covers every blob's path and Git blob sha.
- ~590 spec-kit siblings under `Specs/` carry `type: plan` / `tasks` /
  `research` … in the frontmatter **field** while their governed **tag** is
  `type/spec`; classification must trust the tag — and the path — not the
  field alone. A fifth flavour (`type: data-model` with a `type/reference`
  tag) is pinned by the fixture.
- `Governance/Constitution.md` (16,987 words) exceeded the model's
  per-request cap and 413'd on every run; the 12,000-word `oversize` ceiling
  keeps states inside the cap (the largest mined state is 8,504 words).
- Idempotency held across repeated runs: identical bytes for items, lock,
  and manifest.

## Relevance

Any future mining campaign over a real vault should expect these shapes; the
fixture vault (`tests/fixture_vault.py`) now pins each one, and the manifest
records the exclusion counts that explain every dropped note. The
`out_of_scope` rule (path, tag, or field) is the load-bearing one: a vault's
workflow artifacts can look like notes.

## References

- `evals/dataset/mined/snapshot.py`, `evals/dataset/mined/exclusions.py`
- `tests/fixture_vault.py`, `tests/test_mined_miner.py`
- `specs/007-mined-vault-recipes/research.md`
