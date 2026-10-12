# Tasks: Benchmark Hygiene — Phase 1

**Input**: Design documents from `/specs/006-benchmark-hygiene/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R12), data-model.md, contracts/
(cli, stability, kinds-and-tiers, probe-shape, capture, card-and-report), quickstart.md

**Tests**: REQUIRED. Constitution Article XI (TDD, Red-Green-Refactor) binds every task:
the test tasks in each slice are written first and confirmed failing before the
implementation tasks that follow them, and `make check` must be green at every checkpoint.

**Organization**: Seven user stories from spec.md, in priority order. US1 (label stability)
and US2 (controlled comparison) are the two phase gates and form the MVP — US1 first
because the comparison is pure execution once the harness exists, while stability needs
new tooling. Each story is independently testable; the dependency section records the two
real couplings (US7's card edition after US1+US4; everything else free).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: the user story the task serves; omitted for Setup, Foundational, and Polish
- Exact file paths in every description; constraints quoted from data-model.md

## Path Conventions

Single Python project at the repository root: package `ember/`, eval harness `evals/`,
tests `tests/`, scripts `scripts/`, tracked bundles `benchmark/`, probe snapshots
`evals/context/runs/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the baseline and confirm the state every story builds on.

- [X] T001 Run `make setup` then `make check` and record the baseline (no file changes): the unit suite is green, `fail_under = 94`, `evals/clef-flash.jsonl` has 475 items
- [X] T002 [P] Recon (read-only): run `ember eval dataset hash` and `ember eval dataset check`; confirm the current content hash `1e1bb88d…c367` is recorded in `evals/dataset/versions.lock`, the CUDA bundle `benchmark/17f0b0ad64efb65d273590632833508766b2aae6_20261012T012758Z/` exists on that hash, and `evals/context/runs/` is empty

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The two new directories and the decision note every story references. Nothing
else in this phase is cross-story: the tools are story-local by design (R12).

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 [P] Create `evals/dataset/stability/.gitkeep`, `evals/dataset/candidates/.gitkeep`, and `tests/fixtures/.gitkeep` (US1's round records, US6's candidates, and the shared fixtures)
- [X] T004 [P] Write `vault/decisions/2026-10-11-hygiene-stability-records-and-probe-key.md` from `vault/_meta/templates/decision.md` recording R1 (a round record, not a per-item field), R6 (the `(model, device, dtype, dataset_content_sha256)` match key), and R10 (annotations never move the hash); tags from `vault/_meta/tags.md` (`type/decision`, `domain/tooling`, `status/draft`); link it under the decisions heading in `vault/ember.md`; run `make vault-audit`

**Checkpoint**: Directories exist, the decision note is linked, `make check` remains green.

---

## Phase 3: User Story 1 — A reader can see how stable the gold labels are (Priority: P1) 🎯 MVP

**Goal**: The `risk` and `effort` recipes publish a label-stability measurement from a blinded
re-label round, with the single-rater statement, and the card carries it.

**Independent Test**: Run the stability tool on the current dataset: the round record lands in
`evals/dataset/stability/`, `--report` prints agreement, the card's `label_stability` is
non-null, and the single-rater sentence renders. No other story is needed.

### Tests for User Story 1 ⚠️ (write first, confirm failing)

- [X] T005 [P] [US1] Create `tests/test_dataset_stability.py` with failing tests: the emitted sheet contains `id`/`category`/`question`/`criteria`/`anchors`/`state` and MUST NOT contain the item's `gold_labels` (blinding); ingest rejects an unknown item id, a duplicate id in one round, an unfilled `relabel`, and a sheet whose `original` no longer matches the dataset (each exits 1, nothing written); agreement and `by_label` compute exactly as contracts/stability.md states; a disagreement lands in `unstable`; `StabilityRound` round-trips through JSON; `--report` prints agreement without writing

### Implementation for User Story 1

- [X] T006 [P] [US1] Create `evals/dataset/records/stability_entry.py`: `StabilityEntry(id: str, category: str, question: str, original: int, relabel: int, agrees: bool, labelled_on: str)` — `agrees` is computed by the tool, never provided; docstring notes it is annotation-only for the content hash
- [X] T007 [P] [US1] Create `evals/dataset/records/stability_round.py`: `StabilityRound(round_id: str, cooling_off: str, method: str, labelled_on: str, entries: list[StabilityEntry])` with a validator that no item id appears twice
- [X] T008 [P] [US1] Create `evals/dataset/records/stability_result.py`: `StabilityResult(agreement: float, by_label: dict[str, float], unstable: list[str], rater_count: int = 1)` — levels without entries are omitted from `by_label`
- [X] T009 [US1] Create `evals/dataset/stability.py`: `emit(items, scope) -> dict` (blinded sheet, `relabel: None`, original labels withheld), `ingest(sheet, items, dataset_path)` (validate per T005; write `evals/dataset/stability/<round-id>.json` via `write_atomic`), `report(rounds)` (agreement per recipe/label), `result_for(recipe)` (the `StabilityResult` for the card). Scope: `change_risk`/`risk` and `effort_approach`/`effort` only (R11)
- [X] T010 [US1] Wire `ember eval dataset stability` into `ember/commands/parser.py` (the `dataset` subparser's name loop + `--emit`/`--ingest`/`--report`/`--round`/`--dataset`/`--out` flags) and `ember/commands/eval.py` (`modules` map); add the dispatch case to `tests/test_cli_eval_dataset.py`
- [X] T011 [US1] Fill the card's reserved field in `evals/dataset/card.py`: `recipes.<category>.label_stability` gets `StabilityResult` (or `null` for uncovered recipes); the card renders the single-rater sentence verbatim from contracts/card-and-report.md; regenerate `evals/dataset/card.json` + `CARD.md`; update `tests/test_dataset_card_check.py`
- [ ] T012 [US1] Execute the pass: `ember eval dataset stability --emit --out /tmp/stability-sheet.json`, fill every `relabel` in a second sitting (the maintainer's blinded re-label), `--ingest`, commit `evals/dataset/stability/<round-id>.json`, confirm `--report` prints agreement per recipe — **emit done 2026-10-11 (168 items, blinded); ingest awaits the maintainer's second sitting**
- [X] T013 [US1] Run `make check` and quickstart step 2; confirm the stability block and single-rater sentence render

**Checkpoint**: US1 is functional alone: agreement published, card carries it, tests green.

---

## Phase 4: User Story 2 — One controlled comparison proves MPS and CUDA agree (Priority: P1) 🎯 MVP

**Goal**: Two committed bundles — MPS and CUDA, float16, same dataset content hash, settings
identical except the device — plus a build-visible gate.

**Independent Test**: The gate test finds both bundles and asserts their equality; the
comparison view renders. No other story is needed.

### Tests for User Story 2 ⚠️ (write first, confirm failing)

- [X] T014 [P] [US2] Create `tests/test_benchmark_comparison.py`: find the newest MPS bundle and the newest CUDA bundle among `benchmark/*/model.json` whose `meta.dataset_content_sha256` equals the current content hash; assert both are `dtype: float16`; assert their `settings` differ only in `device`; assert both carry `recipe_sha256`; render the pair through `evals.eval.report_compare` and assert the view names any per-recipe difference. Must FAIL until T015 lands the MPS bundle

### Implementation for User Story 2

- [X] T015 [US2] Run the MPS half on this machine: `EMBER_DEVICE=mps ember eval run --deployment-label "Local (MPS)"` (or the MPS server URL), then `ember eval snapshot`; commit the new `benchmark/<mps-run-id>/` bundle
- [X] T016 [US2] Confirm the CUDA half: `benchmark/17f0b0ad…_20261012T012758Z/` is on the same content hash with `dtype: float16`; `ember eval report --compare <mps> <cuda>` renders side by side with any difference named and the numerics note
- [X] T017 [US2] Confirm the leaderboard holds two rows: the MPS bundle's `deployment_key` (`Local (MPS)|mps`) differs from the CUDA one; extend `tests/test_site_leaderboard.py` to assert both rows render once both bundles exist
- [X] T018 [US2] Run `make check`; the gate test (T014) now passes

**Checkpoint**: Both phase gates' evidence exists; US2 works without US1.

---

## Phase 5: User Story 3 — Every score level is anchored to a rubric (Priority: P2)

**Goal**: `Scale` gains per-level anchors; a missing or indistinguishable anchor fails the build.

**Independent Test**: Inspect `risk`/`effort`/`alert_level` anchors; blank one and watch the
enforced lint fail. No other story is needed.

### Tests for User Story 3 ⚠️ (write first, confirm failing)

- [X] T019 [P] [US3] Create `tests/test_dataset_anchors.py`: `anchors` length equals the question's `criteria` length; every anchor is non-empty; no anchor equals its neighbour; a blanked or duplicated anchor produces an enforced `scale-anchored` finding; the three declared scales pass

### Implementation for User Story 3

- [X] T020 [US3] Add `anchors: list[str]` to `evals/dataset/records/scale.py` with a validator (non-empty entries; count matches on validation against criteria)
- [X] T021 [P] [US3] Create `evals/dataset/anchors.py`: `validate_anchors(scale, criteria) -> list[str]` returning human-readable problems (count, empty, adjacent-equal)
- [X] T022 [P] [US3] Add `scale_anchored = "scale-anchored"` to `evals/dataset/records/lint_rule.py`
- [X] T023 [US3] Add the anchor check to `evals/dataset/lint.py::scale_rules()` with `enforced=True` (always-on, like `scale-declared`/`dangerous-set-declared`)
- [X] T024 [US3] Write the anchors in `evals/dataset/scales.py` for `("change_risk","risk")`, `("effort_approach","effort")`, `("vision_score","alert_level")` — each level's text distinguishes it from its neighbours; `since` stays `FOUNDATIONS_VERSION` (annotations; R10)
- [X] T025 [US3] Run `make check`; lint reports no `scale-anchored` findings; `ember eval dataset card --check` still fresh (anchors do not change the card schema)

**Checkpoint**: Anchors declared and enforced; the stability pass re-runs against them later.

---

## Phase 6: User Story 4 — Every item carries a kind and a tier; non-easy accuracy publishes (Priority: P2)

**Goal**: `Item.kind` populated for all 475 items (with exemptions where a kind is absent),
tiers derived from the committed bundles, non-easy accuracy in the report.

**Independent Test**: The audit reports `untagged: 0`; `ember eval dataset tier` writes tiers
and the hash is unchanged; the report's tier block renders. No other story is needed.

### Tests for User Story 4 ⚠️ (write first, confirm failing)

- [X] T026 [P] [US4] Create `tests/test_dataset_kind_audit.py`: the audit prints per-recipe kind counts, the untagged count, and shares against `KIND_SHARES`; exits 0; `--json` emits the same; after T027/T028 the current dataset reports `untagged: 0`
- [X] T027 [P] [US4] Add to `tests/test_dataset_lint.py`: every `kind-shares` gap on the current dataset is either met or exempted via `RecipeSpec.exemptions`; an unmet, non-exempt kind fails `--enforce-all` naming recipe, kind, and shortfall

### Implementation for User Story 4

- [ ] T028 [US4] Tag all 475 items with `Item.kind` in `evals/clef-flash.jsonl` (an editorial pass — one `ItemKind` per item); commit the dataset; assert `ember eval dataset hash` content hash is UNCHANGED (annotation-only)
- [ ] T029 [US4] Populate `RecipeSpec.exemptions` in `evals/dataset/recipes.py` where a recipe cannot meet a kind's minimum (reason text as the value); regenerate the card's `exemptions` by T044 later
- [X] T030 [US4] Create `evals/dataset/kinds.py` (the audit: counts, untagged, shares vs `KIND_SHARES`) and wire `ember eval dataset kind` into `ember/commands/parser.py` + `eval.py`; add the dispatch case to `tests/test_cli_eval_dataset.py`
- [X] T031 [US4] Run `ember eval dataset tier` against the committed bundles; the tool's own hash-invariance check must pass; commit the tiered `evals/clef-flash.jsonl`
- [X] T032 [US4] Confirm `metrics_phase0.tiers()` renders easy vs non-easy accuracy per recipe for the current version; extend `tests/test_metrics_aggregate.py` if the current fixture does not cover an untiered run — **machinery confirmed (Phase 0 tests); the live block is null on the committed runs (they predate tiering) and populates on the next run**
- [X] T033 [US4] Run `make check` and quickstart steps 3–4

**Checkpoint**: Kinds and tiers are real; the lint's kind gaps are closed or reasoned.

---

## Phase 7: User Story 5 — Every leaderboard row carries the long-context shape (Priority: P3)

**Goal**: Rows carry `request_cap` / `first_drop_length` / `worst_depth` from a matching probe
snapshot, or "not measured"; the site renders them.

**Independent Test**: Build the site with a snapshotted probe: matching rows show the figures,
unmatched rows say "not measured". No other story is needed.

### Tests for User Story 5 ⚠️ (write first, confirm failing)

- [X] T034 [P] [US5] Create `tests/test_probe_linking.py`: `probe_shape(row, snapshots)` returns a `ProbeShape` when `device`, `dtype`, and `dataset_content_sha256` match and the row's model (repo+revision) is in the manifest's `models`; the newest match wins; no match returns `None`; the site table renders the three figures or "not measured" (extend `tests/test_site_benchmark.py`)

### Implementation for User Story 5

- [X] T035 [US5] Add `dataset_content_sha256: str` to `evals/context/records/probe_manifest.py` and set it in `evals/context/run_context.py` at probe start via `evals.dataset.hashes.dataset_content_sha256(evals.dataset.io.read_items(<the scored dataset>))`
- [X] T036 [P] [US5] Create `evals/context/records/probe_shape.py`: `ProbeShape(request_cap: int | None, first_drop_length: int | None, worst_depth: Depth | None)`
- [X] T037 [US5] Create `evals/context/link.py`: `probe_shape(row, snapshots_dir) -> ProbeShape | None` reading `evals/context/runs/*/summary.json` per the T034 rule
- [X] T038 [US5] Extend `evals/leaderboard.py::_row()` with `probe` (the `ProbeShape` as a dict, or `None`) via T037
- [X] T039 [US5] Extend `scripts/build_site_benchmark.py::_leaderboard_table_html()` with a probe column following the `_risk_cell`/`_recipe_cell` pattern; a `None` probe renders "not measured"
- [ ] T040 [US5] Snapshot a probe run: `ember eval context --models flash`, then `ember eval context --snapshot <run_id>`; commit `evals/context/runs/<run_id>/`; confirm the MPS row shows real figures (this run takes hours on MPS — deferred; every row correctly says "not measured" until it lands)
- [X] T041 [US5] Run `make check` and quickstart step 6

**Checkpoint**: The probe shape is on every row, honestly reported.

---

## Phase 8: User Story 6 — Real agent sessions can become captured items (Priority: P3)

**Goal**: A consented, redacted transcript converts to a candidate item; unsafe input is refused.

**Independent Test**: The fixture converts end-to-end; a missing redaction record and a
surviving secret are both refused. No other story is needed.

### Tests for User Story 6 ⚠️ (write first, confirm failing)

- [X] T042 [P] [US6] Create `tests/test_dataset_capture.py`: a fixture transcript + matching redaction record converts to a schema-valid `Item` (`source.kind=captured`, `session_id`, `redaction_sha256`, gold = reviewed choice, `acted`, `acted_differs` true when they differ); a missing/mismatched redaction record exits 1 (`refused_no_redaction`); a transcript whose state trips `secret_guard` exits 1 (`refused_live_secret`); malformed input exits 2; nothing is written on refusal

### Implementation for User Story 6

- [X] T043 [P] [US6] Create the records under `evals/dataset/records/`: `session_transcript.py` (`SessionTranscript(session_id, turns, reviewed_choice, acted_choice)`), `transcript_turn.py` (`TranscriptTurn(role, content)`), `redaction_record.py` (`RedactionRecord(session_id, redaction_sha256` 64-hex`, method, redacted_on)`), `capture_outcome.py` (`CaptureOutcome` StrEnum: `converted`, `refused_no_redaction`, `refused_live_secret`)
- [X] T044 [US6] Create `evals/dataset/capture.py`: `convert(transcript, redaction, items) -> tuple[CaptureOutcome, Item | None]`; run `secret_guard.no_live_secret` on the resulting state; write candidates to `evals/dataset/candidates/<session-id>.jsonl` via `write_atomic`; never write to `evals/clef-flash.jsonl`
- [X] T045 [US6] Wire `ember eval capture import` as a top-level subcommand (`ember/commands/parser.py`, `ember/commands/eval.py`, and the `register_eval` call site in `ember/cli.py`); add a dispatch case to `tests/test_cli.py` or `tests/test_cli_eval_dataset.py`
- [X] T046 [US6] Commit the fixtures `tests/fixtures/session.json` and `tests/fixtures/session.redaction.json` (no live secrets — the guard must pass on them)
- [X] T047 [US6] Run `make check` and quickstart step 7

**Checkpoint**: Capture works and refuses unsafe input; nothing unredacted can land.

---

## Phase 9: User Story 7 — The dataset card publishes the hygiene edition (Priority: P3)

**Goal**: The generated card carries kinds, tiers, split coverage, source kinds with licences,
stability, the single-rater sentence, and the register hash; freshness stays the gate.

**Independent Test**: Regenerate the card: all hygiene sections present, `inter_source_agreement`
null with a reason, freshness check green. Needs US1 (label_stability) and US4 (kinds/tiers);
independent otherwise.

### Tests for User Story 7 ⚠️ (write first, confirm failing)

- [X] T048 [P] [US7] Extend `tests/test_dataset_card_check.py`: the card's per-recipe blocks carry non-null `kind_shares` counts matching the dataset, real `easy_items`, `label_stability` for covered recipes, `exemptions` with reasons, `rubric_since`; the card states single-rater; `inter_source_agreement` is null with a reason; a dataset or register change without regeneration fails `--check`

### Implementation for User Story 7

- [X] T049 [US7] Complete the card edition in `evals/dataset/card.py`: render kinds/exemptions/tiers/source shares/licences (register rows) and the `inter_source_agreement` reason; keep `register_sha256` embedded (already)
- [X] T050 [US7] Regenerate `evals/dataset/card.json` + `CARD.md`; `ember eval dataset card --check` prints fresh; `evals/dataset/versions.lock` gains no line (the content hash did not move)
- [X] T051 [US7] Run `make check` and quickstart step 8

**Checkpoint**: All seven stories are independently functional; the card is the publication.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Documentation consistency, the vault, and the final gates (dev workflow gate 4).

- [X] T052 [P] Update `AGENTS.md`: the Testing table gains `test_dataset_stability.py`, `test_dataset_anchors.py`, `test_dataset_kind_audit.py`, `test_dataset_capture.py`, `test_probe_linking.py`, `test_benchmark_comparison.py`; the Benchmark section names the stability pass, the controlled comparison, and (with US5's column) the probe shape
- [X] T053 [P] Update `README.md`'s Benchmark section (stability, comparison, probe shape, capture) — user-facing prose only, no hand-typed numbers
- [X] T054 [P] Write `vault/sessions/2026-10-11-benchmark-hygiene.md` (what the phase did; append-only) and list it in `vault/ember.md`; `make vault-audit`
- [X] T055 Run quickstart.md steps 1–8 end to end; `make pr-ready`; `make test-cov` and, if the measured coverage rose, ratchet `fail_under` in `pyproject.toml` (Article XI §11.2 — the floor may only increase)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: after Setup — blocks all stories.
- **US1 and US2 (P1)**: after Foundational; independent of each other. US1 is the tooling MVP; US2 is the evidence MVP (its MPS run needs only the existing harness).
- **US3 (P2)**: after Foundational; independent. Its anchors make the US1 re-label sheet richer, so run T024 before re-running T012 if both are in flight.
- **US4 (P2)**: after Foundational; independent. Its tiers need `benchmark/` bundles (US2's MPS run enriches the derivation, but the CUDA bundle already suffices).
- **US5 (P3)**: after Foundational; independent (its snapshot task T040 takes hours and may land last).
- **US6 (P3)**: after Foundational; independent.
- **US7 (P3)**: after **US1** (label_stability) and **US4** (kind/tier content); the only cross-story dependency.
- **Polish (Phase 10)**: after the desired stories.

### Within Each Story

- Tests before implementation (Article XI); models before services; CLI wiring with its test; `make check` at every checkpoint.

### Parallel Opportunities

- T002–T004 (Setup/Foundational) run together.
- Within US1: T006–T008 (records) together, then T009–T011.
- Within US3: T021–T022 together.
- Within US4: T026–T027 together; T028–T032 sequential (dataset mutations).
- Within US5: T036 together with T035.
- Within US6: T043 together; then T044–T046.
- Across stories: US3, US5, US6 can proceed in parallel with US1/US2/US4 once Foundational completes; US7 last.

---

## Parallel Example: User Story 1

```bash
# Records first (different files, no dependencies):
Task: "Create evals/dataset/records/stability_entry.py per T006"
Task: "Create evals/dataset/records/stability_round.py per T007"
Task: "Create evals/dataset/records/stability_result.py per T008"

# Then the tool and its wiring:
Task: "Create evals/dataset/stability.py per T009"
Task: "Wire ember eval dataset stability per T010"
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Phases 1–2 (baseline, dirs, note).
2. **US1** → the stability pass publishes (one phase gate).
3. **US2** → the comparison is committed (the other gate).
4. STOP and validate both independently — the phase's exit gate is met.

### Incremental Delivery

1. US1 → agreement published.
2. US2 → deployment equivalence committed.
3. US3 → anchors enforced (improves the re-label round).
4. US4 → kinds/tiers real, non-easy accuracy live.
5. US5 → probe shape on every row ("not measured" until a snapshot).
6. US6 → capture pipeline ready (first real capture is the maintainer's).
7. US7 → the card's hygiene edition (needs US1+US4).
8. Polish → docs, vault, quickstart, ratchet.

---

## Notes

- [P] tasks touch different files; dataset mutations (T028, T031) are never parallel.
- Every dataset mutation asserts hash invariance; a stability adjudication that changes a gold
  label is the one path that moves the hash — record the new version per R10.
- Commit after each task or logical group; keep `make check` green at every checkpoint.
- The probe snapshot (T040) and the first capture (after T047) are the only tasks that depend
  on the maintainer's own environment rather than code; everything else is deterministic.

---

## Phase 11: Convergence

**Purpose**: Gaps found by `/speckit.converge` after the implementation passes. The four
already-tracked open tasks (T012's re-label ingest, T028/T029's kind tagging, T040's probe
snapshot) are deliberately deferred and are not duplicated here.

- [X] T056 Re-run the full benchmark on the current dataset version and snapshot it, so each recipe's report and the leaderboard publish the non-easy accuracy block now that tiers exist (353 of 475 items are easy; the committed runs predate tiering and render `tiers: null`) per FR-011/SC-003 (partial)
- [ ] T057 Add the stability-publication half of the phase gate: a check that a committed round covers the scoped recipes and the card's `label_stability` is non-null on the current version — land it together with T012's ingest per FR-018/SC-008 (partial)
