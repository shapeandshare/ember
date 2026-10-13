# Tasks: Mined Vault Recipes — Tag Assignment First

**Input**: Design documents from `/specs/007-mined-vault-recipes/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: TDD is mandatory in this repository (constitution Article XI): every implementation task ships its failing-first test in the **same commit**. This list embeds the test work in each task instead of separate test tasks. `make check` must pass before every commit; `make test` runs locally for model-affecting steps.

**Organization**: Tasks are grouped by user story. **MVP = Foundational + US1 + US2** (the phase gate: `tag_assignment` on the leaderboard with full provenance). US3–US5 land incrementally after the gate.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4, US5)
- Exact file paths are in every description

## Path Conventions

Repository root is the working directory. Tooling lives under `evals/`, CLI wiring under `ember/commands/`, tests under `tests/` (flat files), specs under `specs/007-mined-vault-recipes/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: The new package marker the miner modules live in

- [x] T001 Create the mined-tooling package skeleton: `evals/dataset/mined/__init__.py` (bare, docstring-only marker — no imports or re-exports, Article X §10.1); confirm `python -c "import evals.dataset.mined"` succeeds.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema and primitives every story builds on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T002 Add `permission: str | None = None` to `RegisterRow` in `evals/dataset/records/register_row.py` and extend `_verdict_is_consistent` so a `used` row raises when `licence.class_ is LicenceClass.custom_permissive` and `permission` is empty (verbatim: *"a custom-permissive used row needs the permission it rests on"*); failing test first in `tests/test_data_source_register.py`.
- [x] T003 Add `register_row` to the `mined` kind's required references in `evals/dataset/records/source.py`: `REQUIRED[SourceKind.mined] = frozenset({"artefact", "commit", "register_row"})`; foreign fields still raise, `commit` still matches `^[0-9a-f]{40}$`; update the mined fixtures in `tests/test_dataset_tooling.py`; failing test first.
- [x] T004 Extend `register.validate()` in `evals/dataset/register.py` with a `mined` branch mirroring `imported`: a mined item whose `source.register_row` names no row, or names a row that is not `used`, is a problem; resolved rows count toward `items_imported`; failing tests first in `tests/test_data_source_register.py`. (depends on T003)
- [x] T005 [P] Add the shared fixture vault helper `tests/fixture_vault.py`: `build_fixture_vault(tmp_path)` creates a throwaway `git init` repository with a `docs/vault/` tree — seeded notes covering a decision, a discovery, a session-log, a `type/moc` hub, `index.md`, a drift note (tag absent from `_meta/tags.md`), a fake-secret note, and a `Specs/NNN Title/NNN Title.md` spec note — plus a small controlled `_meta/tags.md` and a granted `LICENSES.md`; returns the repo path and commit. Git plumbing only; no network.
- [x] T006 [P] Implement `evals/dataset/mined/snapshot.py`: `VaultSnapshot` reads files with read-only git at a pinned commit (`git show` / `git ls-tree` / `git cat-file`), never the working tree; `.read(path)`, `.files()`, `.tree_digest()` = sha256 over sorted `path\0<git blob sha>` pairs; failing tests first (fixture vault). (depends on T005)
- [x] T007 [P] Implement `evals/dataset/mined/frontmatter.py`: `NoteFrontmatter` (frozen Pydantic, `extra="allow"`) parsed with the vault-audit pattern (header regex + `yaml.safe_load`) and a body extractor that strips frontmatter; failing tests first. (depends on T005)
- [x] T008 [P] Implement `evals/dataset/mined/vocabulary.py`: `TagVocabulary` built from the as-read `_meta/tags.md` (five axes: type/domain/status/layer/concept; every value with its one-line description); `.contains(tag)`, `.values_for(axis)`, `.as_state_block()` producing the FR-017 block (values grouped by axis, each with its description); failing tests first. (depends on T005)

**Checkpoint**: Schemas and primitives ready — user stories can begin.

---

## Phase 3: User Story 1 - `tag_assignment` runs and appears on the leaderboard (Priority: P1) 🎯 MVP

**Goal**: A deterministic miner produces the 65 items from the pinned vault, the dataset records its new version, and the leaderboard shows a `tag_assignment` column.

**Independent Test**: Re-run `ember eval mine --recipe tag_assignment` — identical bytes and ids (SC-001); run the benchmark; the current version's leaderboard row carries a `tag_assignment` column (FR-009).

- [x] T009 [P] [US1] Implement `evals/dataset/mined/exclusions.py` (with `ExclusionReason`, `ExclusionRecord`, `CandidateNote`): reasons `out_of_scope` (`type/spec`), `non_content` (moc/hubs/`index.md`/`README.md` and the 80-word floor), `drift`, `tag_set_bounds` (empty gold or more than 8 tags), `secret` (reusing `SECRET_PATTERNS` from `evals/dataset/secret_guard.py`); failing tests first (one fixture note per reason).
- [x] T010 [P] [US1] Implement `evals/dataset/mined/selection.py`: deterministic, seeded selection (module constants `SEED`, `RECIPE_SIZE = 65`) spreading picks round-robin across `type/*` groups; failing tests first (determinism, seed sensitivity, spread, fewer-than-count). The sampling manifest is written by T012.
- [x] T011 [US1] Implement `evals/dataset/mined/tag_assignment.py`: gold = exactly the note's vocabulary tags; candidates = gold + seeded same-axis distractors (`DISTRACTOR_COUNT = 8`), sorted, capped at **16** (FR-010); one `noul` per candidate (qid = the tag); state = title + body + the vocabulary block (FR-017); failing tests first (determinism, exact gold, cap). (depends on T007, T008)
- [x] T012 [US1] Implement the composition root `evals/dataset/mined/mine.py` (plus `sampling_manifest.py` and `mine_summary.py`; `emit.py` was absorbed): ids `<recipe>-<path-slug>`; `source` = `mined`/`register_row`/`artefact`/`commit`; write through `io.write_items`; extend `splits.lock` via `splitting.assign_new` + `append_lock`; write the manifest atomically; idempotency test (two runs → identical bytes). (depends on T011)
- [x] T013 [US1] Add the refusals to the miner (FR-012) in `evals/dataset/mined/mine.py`: the pinned commit (`VaultSnapshot.require`) and the written grant (committed `LICENSES.md` read at HEAD via `VaultSnapshot.read_file`, never the working tree) — missing → `MineError` naming the missing grant; failing tests first. (depends on T012)
- [x] T014 [US1] [P] Wire the CLI: a `mine` passthrough subcommand in `ember/commands/parser.py` (`add_help=False` + `REMAINDER`, mirroring `capture`/`context`) and `cmd_eval_mine` in `ember/commands/eval.py` (lazy import of `evals.dataset.mined.mine.main` behind `_EVAL_CHECKOUT_ERROR`); failing tests first (unknown `--recipe` exits 2). (depends on T012)
- [x] T015 [US1] Register the recipe: a `_mined_vault` helper (`family=Family.mined_vault`, `phase=2`) and the `tag_assignment` `RecipeSpec` in `evals/dataset/recipes.py`; failing tests first (family value; `headline` is true — every decision family counts).
- [x] T016 [US1] Run the live mine against the pinned commit: `uv run ember eval mine --recipe tag_assignment`; verify 65 items, spread across multiple `type/*` values and `domain/*` groups (US1-AS3); commit `evals/clef-flash.jsonl`, `evals/dataset/mined/<manifest>.json`, `evals/dataset/splits.lock`. (depends on T014, T015)
- [x] T017 [US1] `uv run ember eval dataset lint` (report mode; the size-target gap vs 300 is expected and noted) and `uv run ember eval dataset card` (regenerate `card.json`/`CARD.md`, append the new version to `versions.lock`); commit the artifacts. (depends on T016)
- [x] T018 [US1] Local MPS gate run: `ember start`; `uv run ember eval run --category tag_assignment`; `uv run ember eval snapshot`; `uv run ember eval dataset tier`; commit the `benchmark/` bundle. (depends on T017; recommended after T024's check green)
- [x] T019 [US1] AWS deployment gate run (SC-002 second leg): `export EMBER_SERVER_URL="https://ember-default.tail5be351.ts.net"` + `EMBER_AUTH_TOKEN="$(make -s aws-token)"`; `uv run ember eval run --category tag_assignment`; record the results; unset. (depends on T018)
- [x] T020 [US1] Mechanical gate test (FR-009): assert the current dataset version's leaderboard includes a `tag_assignment` column — extend `tests/test_leaderboard_versions.py` (and the site test pattern in `tests/test_site_leaderboard.py` if needed); failing before the bundle lands, green after. (depends on T018)

**Checkpoint**: US1 functional — the gate column exists; US2 completes the provenance before shipping.

---

## Phase 4: User Story 2 - Nothing lands without licence and provenance (Priority: P1)

**Goal**: The `oldgrowth-vault` `used` row exists with the grant, snapshot, and mirror; the dataset check enforces it.

**Independent Test**: Remove the row (fixture) → check fails naming it; with the row → card renders the source and the live check is green (SC-003).

- [x] T021 [US2] Add the `oldgrowth-vault` `used` row to `evals/dataset/register.json`: licence reading "All rights reserved; written permission granted for the ember benchmark dataset", class `custom_permissive`; `permission` = `LICENSES.md §Exception — ember benchmark reproduction (commit 422648d9)`; `snapshot.version` = `692f4bb58b7f62105aeb73fba8dfee12bfdecd53` with the T016 tree digest as `sha256`; `mirror` = the source repository at the pin (`public: false`) with `sha256` equal to the snapshot (validator: *"mirror hash differs from snapshot hash"*); `transformation`, `attribution`; `items_imported` reconciled by `validate`; failing test first in `tests/test_data_source_register.py` (validate accepts; a non-`used` or missing row fails via T004's branch).
- [x] T022 [US2] Provenance enforcement tests in `tests/test_mined_provenance.py`: a mined item with no register row, and one whose row is not `used`, each produce a `check.run` problem naming it; with the row, clean. Failing tests first.
- [x] T023 [US2] Card rendering (FR-016): assert `card.json`/`CARD.md` show the mined source, its licence reading, the permission reference, and the hashes — extend `evals/dataset/card.py` if needed and cover it in `tests/test_dataset_card_check.py`.
- [x] T024 [US2] Live check: `uv run ember eval dataset check` is green with the mined items and the row in place; regenerate/commit the card if T023 changed it. (depends on T016, T021)
- [x] T025 [US2] Revocation removal-path test (FR-015/SC-007): drop the mined items, re-mine without them (or drop the source), `card` records a new version, `check` green — nothing silently kept; in `tests/test_mined_provenance.py`.

**Checkpoint**: MVP complete — the gate column with full provenance.

---

## Phase 5: User Story 3 - The other three vault recipes follow (Priority: P2; post-gate)

**Goal**: `staleness`, `note_placement`, and `memory_worthiness` mine from the same pinned source, score, and join the leaderboard.

**Independent Test**: Each recipe's items reproduce from the pin, pass the lint at its declared size, and score on the leaderboard (US3-IT).

- [ ] T026 [US3] Implement the `staleness` extractor `evals/dataset/mined/staleness.py` — gold = the `stale:` + `status/*` convention (with `stale_reason:` pairing); failing tests first on fixture notes (stale `true`, `status/stale`, stable). **(deferred: the pinned source has zero frontmatter stale/superseded markers — see the vault discovery)**
- [ ] T027 [US3] Register `staleness` in `evals/dataset/recipes.py` with its declared item count; mine (`ember eval mine --recipe staleness`), lint/card/check, MPS run + snapshot, commit. (depends on T026; deferred with it)
- [ ] T028 [US3] Implement the `note_placement` extractor `evals/dataset/mined/note_placement.py` — options = the plausible placements, gold = the placement the note actually has; failing tests first.
- [ ] T029 [US3] Register `note_placement` with its declared count; mine, lint/card/check, run + snapshot, commit. (depends on T028)
- [ ] T030 [US3] Implement the `memory_worthiness` extractor `evals/dataset/mined/memory_worthiness.py` — gold = what comparable material actually became, with adjudications recorded where the convention is silent; failing tests first. **(deferred: the source has no did-not-become-note fragments to draw negatives from — see the vault discovery)**
- [ ] T031 [US3] Register `memory_worthiness` with its declared count; mine, lint/card/check, run + snapshot, commit. (depends on T030; deferred with it)

---

## Phase 6: User Story 4 - The recipes are usable by agents as they land (Priority: P2)

**Goal**: The `ember-advise` kit carries each recipe with thresholds from real runs.

**Independent Test**: The kit lists the recipe with run-measured thresholds; agent-kit contract tests pass (US4-IT).

- [x] T032 [US4] Kit: add `tag_assignment` to `ember/agent_kit/ember-advise/SKILL.md` with thresholds **from the T018 run output** (never hand-typed); mirror byte-identically to `packages/claude-plugin/skills/ember-advise/SKILL.md`; `make check` (agent-kit + distribution tests). (depends on T018)
- [ ] T033 [US4] Kit: add each US3 recipe as its run completes — same two files, thresholds from that recipe's run output, mirrored copy kept byte-identical. (depends on T027, T029, T031)

---

## Phase 7: User Story 5 - The secondary source stays mappable (Priority: P3)

**Goal**: The ember-vault (MIT) mapping is tested; items stay deferred until a coverage gap is recorded.

**Independent Test**: A mined item resolving to a `permissive` `used` row without `permission` passes the validators and `check` (US5-IT).

- [x] T034 [US5] Test the permissionless mapping in `tests/test_mined_provenance.py`: a `permissive` `used` row needs no `permission` field, and a mined item pointing at it validates and checks clean; add one line to `quickstart.md` that ember-vault items are deferred until a coverage gap is identified and recorded.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T035 [P] Docs sweep (FR-006): replace "coding recipes only" / coding-only headline wording in `README.md` and `AGENTS.md` (and any echo in `scripts/build_site_benchmark.py` / `site/` prose and `specs/004-benchmark-categories/spec.md`) with the every-decision-family rule.
- [x] T036 [P] Vault: decision note `vault/decisions/2026-10-12-mined-vault-miner.md` (miner design + the five clarifications) and a session log; link both from `vault/ember.md`; `make vault-audit` clean.
- [x] T037 Full local gates: `make pr-ready` and `make test` (model-backed) pass; `make test-cov` holds the 94 floor; no new failures.
- [x] T038 Open the PR for `007-mined-vault-recipes` once the maintainer confirms (merging to `main` triggers the release workflow; commit scopes per AGENTS.md — `evals`/`ember`). — [PR #125](https://github.com/shapeandshare/ember/pull/125), all checks green

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001)**: none — start immediately.
- **Foundational (T002–T008)**: after T001; BLOCKS all stories. T002/T003 can run in parallel (different files); T004 after T003; T005–T008 parallel after T002 (T006–T008 depend on T005).
- **US1 (T009–T020)** and **US2 (T021–T025)**: after Foundational; the two P1 stories are twins.
- **US3 (T026–T031)**, **US4 (T032–T033)**, **US5 (T034)**: after the gate (US1+US2); US4 depends on each recipe's run.
- **Polish (T035–T038)**: after the desired stories complete.

### Cross-Story Notes

- T016 mines items before the row exists; the **check** in T024 (and the recommended placement of T018 after T024) needs T021's row — execute T021 before T024, and T024 before T018's run if you want the check green before scoring.
- T013/T014 both follow T012; T015 is independent of the miner code.
- The gate test T020 needs T018's snapshot bundle.

### Parallel Opportunities

- Foundational: T002 + T003 together; then T005 → T006 + T007 + T008 together.
- US1: T009 + T010 together; T014 alongside T013 after T012.
- Polish: T035 + T036 together.

## Parallel Example: Foundational

```bash
# After T001/T005:
Task: "T006 evals/dataset/mined/snapshot.py — VaultSnapshot with tree digest"
Task: "T007 evals/dataset/mined/frontmatter.py — NoteFrontmatter + body extractor"
Task: "T008 evals/dataset/mined/vocabulary.py — TagVocabulary + as_state_block"
```

## Implementation Strategy

### MVP First (the phase gate)

1. T001 → T002–T008 (foundation).
2. US1 T009–T017 (miner + registration + mine + version recorded).
3. US2 T021–T024 (row + enforcement + live check).
4. US1 T018–T020 (MPS run, AWS run, gate test) — **STOP**: the maintainer reviews and gets feedback before US3.

### Incremental Delivery

1. Gate green → feedback window (the maintainer's stated goal).
2. US3 per recipe (staleness → note_placement → memory_worthiness), each with its run and leaderboard column; US4 kit updates as each lands.
3. US5 mechanism, Polish, PR.

### Notes

- Commits: conventional, scoped (`feat(evals): …`, `feat(ember): …`), atomic, tests in the same commit (Article XI).
- ≤400 lines per module; no new dependencies; annotation-only edits never move the content hash.
- Dataset discipline: every item addition → `card` records a new version; never compare across versions.

---

## Phase 2 Close-out (converge, 2026-10-12)

The US1/US2 gate is green and [PR #125](https://github.com/shapeandshare/ember/pull/125)
carries the shipped work; these are the remaining unbuilt items across the feature's own
follow-through.

- [ ] T039 [Post-release] Upgrade the AWS deployment to the current release (`make aws-up EMBER_VERSION=<next>` reboots in place; the SSM config already carries `max_request_length: 24576` — the refusals come from the installed 0.12.0 wheel, which predates the per-model request caps) and re-run the CUDA legs (`--category tag_assignment`, `--category note_placement`), re-snapshot, so the comparison halves carry no cap-refused items. See `vault/discoveries/2026-10-12-cuda-deployment-request-cap-drift.md`.
- [x] T040 [Follow-up] Handle category-scoped (partial) newest bundles in `scripts/build_site_benchmark.py` and its tests: the headline now comes from the newest complete run (falling back to the newest headline-capable run, and to no headline when none exists), so a partial newest can be snapshotted safely (`test_build_survives_a_partial_newest_bundle`, `test_build_with_only_a_partial_run_writes_no_headline`).
- [ ] T041 [Release ops] After PR #125 merges and the release workflow publishes (v0.15.0), dispatch the Pages deploy and verify the new recipes render; T026/T027/T030/T031 (the deferred recipes) re-open when their material exists.
