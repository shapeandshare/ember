# Phase 0 Research: Mined Vault Recipes — Tag Assignment First

**Status**: Phase 0 output for `/speckit.plan`, grounded in two fact-finding passes: the Old Growth vault at the pin, and the current `evals/dataset/` mechanisms.

## Verified facts

**Source (Old Growth vault at the pin).**

- **Pin**: `692f4bb58b7f62105aeb73fba8dfee12bfdecd53`. The sibling checkout's HEAD (`422648d9`) differs only by the `LICENSES.md` grant — no vault content differs, so measurements at HEAD are valid at the pin.
- **Vocabulary** (`docs/vault/_meta/tags.md`, 150 lines): five axes — `type/*` exactly 1 (11 values), `domain/*` 0+ (13 values), `status/*` at most 1 (6 values; omit when stable), `layer/*` at most 1 (6 values), `concept/*` 0+ (10 values). Required frontmatter: `title`, `type`, `tags`, `created`, `updated`; also `aliases`, `phase`, `layer`, `system`, `stale`, `stale_reason`, `source`, `code-refs`, `spec-refs`, `related`.
- **Oldgrowth's own tooling**: `scripts/ci/vault_audit.py` enforces the schema mechanically, but its `DOMAIN_VOCAB` lists 10 of the 13 documented domains — `tags.md` is canonical, and the miner follows it.
- **Layout**: `Specs/` holds 850 `.md` across 166 numbered folders whose main note is `NNN Title/NNN Title.md` (166/166 present); two numbers repeat (`007`, `164`), so ids use full folder names. Non-Specs folders total 208 `.md`; 28 loose root `.md` include domain MOCs (`" — Domain MOC.md"`), folder hubs (`Code.md` …), `index.md`, `README.md`. `_meta/` holds `tags.md` + 11 templates.
- **Sizes (236 non-Specs notes)**: min 100 words, median 584.5, max 16,413 — **no note under 80 words**. Thin stubs are not the problem; MOCs/hubs/index/templates are the non-content material.

**Ember side (existing mechanisms).**

- `Source` `REQUIRED[mined] = {artefact, commit}` — `commit` must be 40-hex, and any other field raises; a second 40-hex check lives in `check.py`.
- `RegisterRow` fields: `id`, `name`, `urls`, `licence`, `verdict`, `reason`, `snapshot`, `mirror`, `transformation`, `feeds`, `items_imported`, `attribution`, `upstream_available`, `notes`. A `used` row needs `snapshot`, `mirror`, and `transformation`, and **`mirror.sha256` must equal `snapshot.sha256`**; share-alike needs `attribution`; excluding licence classes force `excluded`; only `used` rows may count items.
- **Gaps**: `register.validate()` and `lint.source_rules()` resolve only `SourceKind.imported` (never `mined`); `splitting._family_key()` has no `mined` branch; no permission field exists.
- **Flow**: adding items changes `dataset_content_sha256`; `card` regenerates the card and appends `versions.lock`; `check` fails until the version is recorded and every id is in `splits.lock`; `tier` needs a benchmark bundle for the version.

## Decisions

### R1 — Snapshot reading: the pinned commit, through read-only git

`VaultSnapshot` reads the tree with read-only plumbing (`git -C <source-dir> archive <commit> docs/vault` to a temp dir, or per-file `git show <commit>:<path>`). The working tree is never read. `<source-dir>` defaults to `<repo>/../oldgrowth` and is overridable, so tests exercise the real code path against a fixture repository.

Rationale: FR-001/SC-001 need byte-for-byte reproducibility; only committed bytes give it. Rejected: reading the working tree (drifts); a vault copy checked in (redistribution beyond the grant, a second copy to sync).

### R2 — Frontmatter parsing: the vault-audit pattern, no new dependency

Header regex + `yaml.safe_load` + frozen Pydantic models (`extra="allow"`), as `scripts/vault_audit.py` does. PyYAML is already a dependency.

Rationale: Article XV §15.4 (reuse) and §15.2 (boring over novel).

### R3 — The as-read vocabulary is the gold universe; drift is excluded, never guessed

`TagVocabulary` is parsed from `docs/vault/_meta/tags.md` at the pin (backticked `axis/value` tokens). A tag outside it, or a malformed axis fragment, excludes the note with reason `drift`; nothing is mapped silently. Where oldgrowth's own audit disagrees with `tags.md` (its `DOMAIN_VOCAB` is short three values), `tags.md` is canonical.

Rationale: FR-003, FR-014; the spec assumption that the vocabulary as-read defines the universe.

### R4 — Deterministic, seeded selection from the memory notes

Candidates are the non-spec memory notes only (maintainer-clarified 2026-10-12): every `.md` not under `_meta/`, not `type/spec`, not `type/moc`, and not a hub, index, or README. Candidates sort by `artefact`; a fixed-seed `random.Random` (seed a module constant, recorded in the manifest) picks 65 spread across `type/*` values and `domain/*` groups. The miner calls the existing `assign_new` + `append_lock` so new ids are pinned; no `_family_key` change is made — the 65 notes are distinct, and a second recipe over the same notes can add a `("mined", artefact)` key later.

Item id = `<recipe>-<path-slug>`.

Rationale: FR-001/FR-002/SC-001.

### R5 — Exclusions are declared and recorded

`ExclusionReason` StrEnum: `drift` (R3), `non_content` (type/moc, hubs, index, README, `_meta`; an 80-word floor is kept as a backstop even though no memory note trips it), `secret` (a candidate whose title+body trips the `SECRET_PATTERNS` from `evals/dataset/secret_guard.py` — excluded, or redacted with the redaction recorded; never relaxed), and `tag_set_bounds` (empty gold, or over the declared cap). A committed manifest records the rule values, the seed, per-note exclusions (`artefact → reason`), and the counts the card reports.

Rationale: FR-007/FR-014 and the spec Edge Cases.

### R6 — `tag_assignment`: gold, candidate set, questions, state

- **state** = `title`, then the note body with frontmatter stripped, then the full as-read vocabulary grouped by axis with each value's one-line description (maintainer-clarified 2026-10-12): the vault's own decision context, grounded in the documented meanings (FR-017).
- **questions** = one `noul` per candidate tag, `qid` = the tag, asking whether the note deserves it.
- **candidates** = the note's gold tags plus a seeded distractor set (preferring same-axis, not-in-gold values), sorted and capped at 16 (maintainer-clarified).
- **gold** = 1 for exactly the note's vocabulary tags, 0 otherwise.

Rationale: FR-003/FR-010; `noul` is the kit's multi-label shape and needs no new question type (Article II).

### R7 — Provenance: a `used` row, plus a mined→row link

Two additive, evals-internal schema changes (each with tests, in the same commit):

1. `Source` for `mined` gains **`register_row`** (required) beside `artefact`/`commit`; `register.validate()` gains a `mined` branch that resolves it, so a mined item whose source has no `used` row fails the check (FR-004).
2. `RegisterRow` gains **`permission: str | None`**, required by the `used` validator when `licence.class_ is LicenceClass.custom_permissive` — the permission a custom-permissive used source rests on. Old Growth is all-rights-reserved under a written grant → `custom_permissive` + permission; ember's own MIT vault is `permissive` → none needed (FR-013).

The row: `id = oldgrowth-vault`; licence reading "All rights reserved; written permission granted for the ember benchmark dataset", class `custom_permissive`; `permission` = `LICENSES.md §Exception — ember benchmark reproduction (commit 422648d9)`; `snapshot` = `SnapshotRef(version=692f4bb5…, sha256=<tree digest>, retrieved_on=…)`; `mirror` = `MirrorRef(location="shapeandshare/oldgrowth @ 692f4bb5 (private)", sha256=<same digest>, public=False)` — the source tree itself satisfies `mirror.sha256 == snapshot.sha256` without committing a vault copy; `attribution` = "Old Growth — distributed in the ember benchmark dataset with written permission"; `transformation` describes extraction into items.

Items: `source.kind=mined`, `register_row=oldgrowth-vault`, `artefact=<repo-relative note path>`, `commit=692f4bb5…`. The tree digest is sha256 over the sorted `path\0<git blob sha>` pairs.

Rationale: FR-004/FR-005/FR-012/FR-013; the parent makes the register the whole licence story.

### R8 — Versioning: append-only, one new version

Items change the content hash; the operator runs `card` (regenerate + append `versions.lock`) then `check`. Existing bundles keep their version; the leaderboard renders one table per version.

Rationale: FR-008 and the parent's rules.

### R9 — CLI: `ember eval mine` (top-level passthrough)

Follows the `capture`/`context` pattern (`add_help=False` + `REMAINDER`, `cmd_eval_mine` lazy-importing `evals.dataset.mine.main` — checkout-only), rather than the in-place `dataset` group: the miner reads an external repository. It writes only items, the manifest, and `splits.lock`, and is idempotent. Refusals (missing grant, missing pin, missing source dir) exit non-zero, naming the missing thing. Flags: `--recipe` (default `tag_assignment`), `--source-dir`, `--dataset`, `--lock`.

Rationale: FR-012; XV §15.4; matches `capture`, which also turns external material into items.

### R10 — Kit after the first real run

Add the recipe to `ember/agent_kit/ember-advise/SKILL.md` with thresholds measured from the run, mirror byte-identically to `packages/claude-plugin/skills/ember-advise/SKILL.md`, and run `make check`. Numbers are never hand-typed.

Rationale: FR-011, Article III §3.3.

## Consequences to accept

- `mined_vault` recipes count toward the headline (maintainer-clarified 2026-10-12): the headline features every decision family, and a coding-only headline is rejected. The "coding recipes only" wording in README.md/AGENTS.md is updated when the first mined recipe scores (FR-006).
- The ember-vault secondary source keeps its tested mechanism; items are deferred until a coverage gap is recorded (maintainer-clarified).
- The 65 items are far under `SIZE_TARGET = 300`; lint stays in `report` mode and the card shows the size gap — the normal bootstrap state.
