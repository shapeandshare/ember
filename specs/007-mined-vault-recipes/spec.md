# Feature Specification: Mined Vault Recipes — Tag Assignment First

**Feature Branch**: `007-mined-vault-recipes`

**Created**: 2026-10-11

**Status**: Draft

**Parent programme**: `specs/004-benchmark-categories/spec.md`. This feature is **Phase 2 (Mined vault recipes)** of that programme's Delivery Series, created because Phase 1's gate is green (label stability published; the controlled comparison committed). Every parent rule — the register, the two hashes, pinned splits, the protocol rules, the no-live-secret rule — applies unchanged; nothing here weakens them.

**Input**: Maintainer direction (2026-10-11): "if we are going to look at vault data, make sure to look at ../oldgrowth's vault in particular" — ship the first mined category quickly, for use and feedback.

## Context

The benchmark's first five recipes are authored. Phase 2 mines **real vault notes** so gold comes from work people actually did, not from prompts written for the benchmark:

- **Primary source**: the Old Growth vault at `../oldgrowth/docs/vault` — a sibling repository owned by the same maintainer — pinned at commit `692f4bb58b7f62105aeb73fba8dfee12bfdecd53`: **1,098 notes** with a governed, five-axis controlled tag vocabulary (`docs/vault/_meta/tags.md`: `type/*` — one per note, eleven values in use; `domain/*`, `status/*`, `concept/*`, plus frontmatter fields like `stale:`, `code-refs`, `related`), agent decision/discovery/session notes, MOCs, and templates.
- **Licensing is a hard prerequisite**: Old Growth's `LICENSE` is all-rights-reserved. The copyright holder (the same maintainer) MUST grant explicit written permission — a grant note in `../oldgrowth/LICENSES.md` covering reproduction, transformation, and distribution within the ember benchmark dataset — and the register row MUST record it before **any** item from that source lands. No permission note, no items.
- **Secondary source**: ember's own vault (`vault/`, MIT) — mined where it adds coverage.
- **Recipes, in order**: `tag_assignment` (65 items) first — the gate category — then `memory_worthiness`, `note_placement`, `staleness`. Gold comes from the vault's own conventions, so the benchmark grades a real decision, not a copy of the note.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - `tag_assignment` runs and appears on the leaderboard (Priority: P1)

A benchmark reader sees a new family on the leaderboard: given a note (its title and body) and the vault's controlled vocabulary, which tags does it deserve? The miner that produced the 65 items is reproducible from the pinned commit, so the reader can rebuild exactly what was scored.

**Why this priority**: It is the phase gate — "first mined category on the leaderboard; miner reproducible from a commit" — and it is the family the maintainer's own vault workflows use daily.

**Independent Test**: Re-run the miner against the pinned snapshot: it regenerates the same item ids, states, question sets, and gold labels (identical hashes). Run the benchmark: the leaderboard shows a `tag_assignment` column for the current dataset version.

**Acceptance Scenarios**:

1. **Given** the pinned snapshot of the source vault, **When** the miner runs, **Then** it reproduces every `tag_assignment` item byte-for-byte (same ids, states, question sets, gold) and records the source commit and snapshot hash on each item's `source`.
2. **Given** a full benchmark run on the current dataset version, **When** the leaderboard renders, **Then** `tag_assignment` appears as a category with its per-recipe figures, and the run records the dataset's content hash and the recipe's hash.
3. **Given** the 65 items, **When** their sampling is inspected, **Then** they span multiple `type/*` values and `domain/*` groups — not one folder — and their dev/test split obeys the parent's ratio and the pinned lock.

---

### User Story 2 - Nothing lands without licence and provenance (Priority: P1)

A reader of the dataset card sees, for every mined item, where it came from: the register row that names the source repository, the licence as read (all-rights-reserved), the copyright holder's written permission, the pinned snapshot, and the mirror — with hashes. An item whose source lacks a `used` register row cannot pass the dataset check.

**Why this priority**: The source is proprietary; provenance discipline is the entire defence, and the parent makes the register a hard rule.

**Independent Test**: Attempt to build the dataset with a mined item whose source has no `used` register row (or whose row lacks the permission record): the dataset check fails naming it. With the row present, the card renders the source and its licence.

**Acceptance Scenarios**:

1. **Given** the permission grant is absent from `../oldgrowth/LICENSES.md`, **When** mining is attempted, **Then** the miner refuses to emit items and names the missing grant.
2. **Given** a `used` register row for the source, **When** the dataset check runs, **Then** every mined item's `source` resolves to that row, and the row carries the licence reading, the permission reference, the snapshot, and the mirror with matching hashes.
3. **Given** the dataset card, **When** it renders, **Then** the mined source appears with its licence as read and attribution.

---

### User Story 3 - The other three vault recipes follow (Priority: P2)

A reader sees, after `tag_assignment`: `memory_worthiness` (does this session fragment deserve a note?), `note_placement` (where does the note belong?), and `staleness` (is this note's claim stale?). Each takes its gold from the vault's own conventions.

**Why this priority**: They complete the family's coverage of vault decisions, but the gate names only the first category — this story ships after it without changing the gate.

**Independent Test**: Each recipe's items reproduce from the pinned snapshot, pass the lint at its declared size, and score on the leaderboard.

**Acceptance Scenarios**:

1. **Given** the vault's `stale:`/`status/*` conventions, **When** `staleness` items are mined, **Then** each item's gold is that convention's outcome and the rationale names it.
2. **Given** a `note_placement` item, **When** it is scored, **Then** its options are the plausible placements for that note and the gold is the placement the note actually has.
3. **Given** a `memory_worthiness` item, **When** it is mined, **Then** its gold comes from comparable material that did (or did not) become a note, adjudicated where the convention is silent.

---

### User Story 4 - The recipes are usable by agents as they land (Priority: P2)

The maintainer's agents can ask the new recipes through ember's own tool: the `ember-advise` skill gains the vault recipes with starting thresholds re-measured from real runs, so the family is used (and feedback arrives) before the whole programme completes.

**Why this priority**: The maintainer's stated goal is use and feedback as soon as possible; a recipe that only exists in the benchmark is half-shipped.

**Independent Test**: After the first full run of `tag_assignment`, the kit's recipe list includes it with thresholds from that run; an agent following the skill can pose it.

**Acceptance Scenarios**:

1. **Given** a completed run of a new recipe, **When** the kit is updated, **Then** its thresholds come from that run's output (never hand-typed) and the skill documents how to pose the question.
2. **Given** the kit change, **When** the unit suite runs, **Then** the agent-kit contract tests pass (size caps, frontmatter, mirrored Claude plugin copy).

---

### User Story 5 - The secondary source adds coverage where it can (Priority: P3)

ember's own vault (MIT) contributes items where it covers a decision the primary source does not — no licensing gate, and dogfooding our own memory for the benchmark.

**Why this priority**: Coverage insurance; the primary source already satisfies the gate.

**Independent Test**: At least one mined item resolves to the ember-vault source with its own register row or source reference, and passes the same checks.

**Acceptance Scenarios**:

1. **Given** an ember-vault note selected for mining, **When** its item is built, **Then** its `source` names the artefact and commit of this repository and no external permission is required.

---

### Edge Cases

- **Vocabulary drift**: notes carrying tags no longer in (or never added to) the vocabulary as-read — e.g. the observed bare `type/` fragments — are excluded by a declared rule, or mapped with the mapping recorded; they are never guessed.
- **The source repository is dirty**: mining pins to the commit; the working tree's uncommitted state is irrelevant and never read.
- **A vault note's content trips `no-live-secret`**: the note is excluded, or redacted with the redaction recorded — the rule is never relaxed.
- **The snapshot is unavailable at check time**: the register's `used` invariants fail loudly; items never ship against an unrecorded source.
- **Permission is revoked or narrowed later**: a removal path exists — affected items are removed and a new dataset version is recorded; nothing is silently kept.
- **A note is an MOC or index** (thin content): excluded from content-bearing recipes by the declared selection rule unless a recipe explicitly targets them.
- **Tag sets are large or empty**: `tag_assignment` items whose gold set is empty or unboundedly large are excluded by the declared selection rule (a note with no differentiating content teaches nothing).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The miner MUST be reproducible from the pinned commit: item ids derive from the source path and commit; states, question sets, and gold labels regenerate byte-for-byte; each item's `source` records the artefact and the 40-hex commit.
- **FR-002**: `tag_assignment` MUST contribute 65 items, sampled deterministically across multiple `type/*` values and `domain/*` groups, split per the parent's ratio and pinned in the splits lock.
- **FR-003**: Gold definitions MUST be the vault's own conventions: `tag_assignment` = the note's actual controlled tags; `note_placement` = its actual placement; `staleness` = the `stale:`/`status/*` convention; `memory_worthiness` = what comparable material actually became, adjudicated where silent.
- **FR-004**: No item from the primary source MAY land without (a) the copyright holder's written permission recorded in the source repository and (b) a `used` register row carrying the licence reading, the permission reference, the snapshot, and the mirror; the dataset check MUST fail otherwise.
- **FR-005**: The pinned source MUST be snapshotted and mirrored with recorded hashes, per the parent's register invariants.
- **FR-006**: The four recipes MUST be registered (family `mined_vault`) with fixed question sets and declared scales where score-shaped; their headline membership follows the parent's family rule.
- **FR-007**: Mined items MUST pass the full lint (size targets, kind shares, leakage, dedup, `source-resolves`, `no-live-secret`); vault content is scanned and any live secret excludes or redacts the item.
- **FR-008**: Mined items MUST enter the content hash like any other; every version is recorded append-only; no comparison spans versions.
- **FR-009**: `tag_assignment` MUST appear on the leaderboard with per-recipe figures for the current version — the phase gate — and the gate MUST be mechanically checkable.
- **FR-010**: A `tag_assignment` item's candidate tag set (gold tags plus distractors) MUST be deterministic and reproducible, and its gold MUST be exactly the note's vocabulary tags.
- **FR-011**: Each recipe MUST join the `ember-advise` kit as it lands, with thresholds re-measured from real runs and the mirrored Claude plugin copy kept byte-identical.
- **FR-012**: Mining MUST refuse when the permission grant is absent, and MUST name the missing grant.
- **FR-013**: The secondary source (ember's own vault, MIT) MUST be mappable as a source without external permission; mined items resolve to its artefact and commit.
- **FR-014**: Notes with vocabulary drift or non-content shape MUST be handled by declared, recorded rules (exclude or map); nothing is guessed.
- **FR-015**: A permission revocation MUST have a removal path: affected items are removed and a new dataset version recorded.
- **FR-016**: The dataset card MUST render the mined sources, their licence readings, the permission references, and their hashes.

### Key Entities

- **Source snapshot**: the pinned commit's vault content, mirrored where the register requires it, with hashes.
- **Register row (primary source)**: licence as read (all-rights-reserved), the permission grant reference, snapshot, mirror, transformation, verdict `used`, attribution.
- **Mined item**: a benchmark item whose `source` names artefact + commit, with recipe-specific gold from the vault's conventions.
- **Candidate tag set**: the deterministic gold-plus-distractor set a `tag_assignment` item asks about.
- **Exclusion record**: the declared reason a note was not mined (drift, secret, non-content shape, permission scope).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Re-running the miner against the pinned snapshot reproduces all 65 `tag_assignment` items byte-for-byte (identical per-item hashes) — 100%.
- **SC-002**: `tag_assignment` renders on the leaderboard for the current dataset version, scored from both a local MPS run and the AWS deployment run; the gate check passes only then.
- **SC-003**: Every mined item resolves to a `used` register row carrying the permission reference and snapshot/mirror hashes; zero items otherwise (enforced by the dataset check).
- **SC-004**: The lint's enforced rules stay green with the mined items in the dataset, and the no-live-secret scan has excluded or recorded every hit.
- **SC-005**: The kit lists the new recipes with thresholds taken from real runs; the agent-kit contract tests and the mirrored plugin copy pass.
- **SC-006**: The four recipes' sizes and splits appear in the dataset card with their exclusions recorded.
- **SC-007**: Revoking the permission has a recorded removal path exercised in tests.

## Assumptions

- **The maintainer grants the permission**: they hold the copyright on both sides; the grant note in `../oldgrowth/LICENSES.md` is drafted for approval and is a blocking prerequisite, not a formality. Until it lands, no item from that source exists.
- **Source stability**: the Old Growth vault at commit `692f4bb5` is the frozen source; earlier or later commits are different sources, not adjustments.
- **The vocabulary as-read defines the tag universe** for `tag_assignment` gold; a tag absent from the vocabulary at the pinned commit is drift, handled by FR-014.
- **Sampling is seeded and deterministic**; the same snapshot always yields the same 65 notes.
- **Recipes graduate independently**: each joins the kit and the leaderboard when its items pass the lint and a run completes; the three later recipes need not wait for each other.
- **The agent eval and the harness are unchanged**; mined recipes are scored by the same machinery as authored ones.