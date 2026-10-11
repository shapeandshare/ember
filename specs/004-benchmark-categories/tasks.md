# Tasks: Benchmark Categories — Phase 0 (Foundations)

**Input**: Design documents from `/specs/004-benchmark-categories/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R20), data-model.md, contracts/
(dataset, http-api, run-artifacts, report-and-leaderboard, register, cli), quickstart.md

**Tests**: REQUIRED. Constitution Article XI (TDD, Red-Green-Refactor) binds every task:
the test tasks in each slice are written first and confirmed failing before the
implementation tasks that follow them, and `make check` must be green at every checkpoint.

**Organization**: The programme spec has ten user stories; this tasks file implements
**User Story 1 — Phase 0 (Foundations)** only, per the spec's Delivery Series. User Stories
2–10 are delivered by their own specifications (one per phase) and do not appear here. US1
is large, so its phase is split into seven slices (3A–3G) that follow plan.md's delivery
order; every task in them carries the `[US1]` label.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: `[US1]` for every Phase 0 slice task; none for Setup, Foundational, Polish
- Exact file paths in every description; constraints quoted from data-model.md

## Path Conventions

Single Python project at the repository root: package `ember/`, eval harness `evals/`,
tests `tests/`, scripts `scripts/`, site `site/`, tracked bundles `benchmark/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Package skeleton, tooling scope, make targets, and the planning decision note.

- [X] T001 Create `evals/dataset/__init__.py` and `evals/dataset/records/__init__.py` as bare docstring-only package markers (Article X §10.1: no imports, no re-exports)
- [X] T002 [P] Extend `[tool.mypy].files` in `pyproject.toml` to `["ember", "evals/dataset"]` so the new package is type-checked strictly from its first module (R18)
- [X] T003 [P] Add make targets to `shared/testing.mk` with `##` help comments: `dataset-lint` → `$(PY) -m evals.dataset.lint`, `dataset-card` → `$(PY) -m evals.dataset.card`, `audit-sources` → `python3 scripts/audit_data_sources.py` (contracts/cli.md)
- [X] T004 [P] Write `vault/decisions/2026-10-10-benchmark-foundations-token-split-and-registries.md` from `vault/_meta/templates/decision.md` recording R1 (one recipe registry), R8 (token split in `usage`), R9 (seven source kinds, legacy shim), R11 (hashes and versions), R19 (debt paydown), R21 (consistency and by-source summaries), R22 (changelog hash); tags from `vault/_meta/tags.md` (`type/decision`, `domain/tooling`, `status/draft`); link it under the decisions heading in `vault/ember.md`; run `make vault-audit`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The records and the two registries every slice reads, and the retirement of
`report_text.RECIPES` so there is one source of truth (R1, R2, R6).

**⚠️ CRITICAL**: No slice of Phase 3 can begin until this phase is complete.

### Tests (write first, confirm failing)

- [X] T005 [P] Create `tests/test_dataset_tooling.py` with record tests: `Scale` rejects `dangerous_from=None` when `dangerous_end != none` and rejects a non-`None` `dangerous_from` when `dangerous_end == none`; `Scale.legend(levels=4)` returns `"0 Negligible → 3 High"`; `RecipeSpec.headline` is `False` for `family in {vision, integration}` and `True` otherwise; `RecipeSpec` defaults are `risk=False`, `compliance=()`, `policy_slot=False`, `dangerous_options={}`, `lint=LintMode.report`, `exemptions={}`; every enum in data-model.md exposes exactly the listed values
- [X] T006 [P] Add to `tests/test_eval_benchmark.py`: `test_every_dataset_recipe_is_registered` (every `category` in `ITEMS` is a key of `evals.dataset.recipes.RECIPES` and every registered recipe has items) and `test_every_score_question_declares_its_scale` (for every `score` question: `SCALES[(category, qid)]` exists, `criteria[0] == scale.low`, `criteria[-1] == scale.high`, and `dangerous_from < len(criteria)` when set; every `SCALES` key names an existing score question)

### Implementation

- [X] T007 [P] Create the ten StrEnums in `evals/dataset/records/`, one class per file with exactly these values: `dangerous_end.py` `DangerousEnd` (`low`, `high`, `none`); `family.py` `Family` (`coding`, `vision`, `mined_vault`, `risk_trio`, `harm_security`, `spec_kit`, `grounding`, `long_tier`, `boundary`, `memory_loop`, `low_priority`, `integration`); `lint_mode.py` `LintMode` (`report`, `enforce`); `compliance_framework.py` `ComplianceFramework` (`owasp_llm_top10`, `mitre_atlas`, `nist_ai_rmf`, `eu_ai_act`, `iso_42001`, `enkrypt`); `source_kind.py` `SourceKind` (`authored`, `mined`, `captured`, `perturbed`, `templated`, `drafted`, `imported`); `item_kind.py` `ItemKind` (`positive`, `negative`, `control`, `hard_negative`, `near_miss`, `adversarial`, `insufficient_context`, `variant`, `long_tier`); `split.py` `Split` (`dev`, `test`); `verdict.py` `Verdict` (`candidate`, `conditional`, `excluded`, `unconfirmed`, `used`); `licence_class.py` `LicenceClass` (`permissive`, `share_alike`, `custom_permissive`, `non_commercial`, `research_only`, `gated`, `composite`, `unconfirmed`); `lint_rule.py` `LintRule` (`size-target`, `label-in-both-splits`, `kind-shares`, `template-share`, `scale-declared`, `dangerous-set-declared`, `source-resolves`, `family-split`, `split-pinned`, `near-duplicate-gold`, `no-live-secret`); NumPy docstrings on each
- [X] T008 [P] Create `evals/dataset/records/scale.py`: frozen Pydantic `Scale(category: str, question: str, quantity: str, low: str, high: str, dangerous_end: DangerousEnd, dangerous_from: int | None)` with a model validator enforcing "`dangerous_from` required iff `dangerous_end != none`" and a `legend(levels: int) -> str` returning `f"0 {low} → {levels - 1} {high}"`
- [X] T009 [P] Create `evals/dataset/records/compliance_ref.py`: frozen Pydantic `ComplianceRef(framework: ComplianceFramework, ref: str, title: str)`
- [X] T010 Create `evals/dataset/records/recipe_spec.py`: frozen Pydantic `RecipeSpec(category, title, when, state, decides, family: Family, phase: int, risk: bool = False, compliance: tuple[ComplianceRef, ...] = (), policy_slot: bool = False, dangerous_options: dict[str, frozenset[str]] = {}, lint: LintMode = LintMode.report, exemptions: dict[ItemKind, str] = {})` with the `headline` property (`family not in {Family.vision, Family.integration}`)
- [X] T011 Create `evals/dataset/scales.py` with `SCALES: dict[tuple[str, str], Scale]` holding exactly: `("change_risk", "risk")` quantity "risk of shipping unreviewed", low "Negligible", high "High", `dangerous_end=high`, `dangerous_from=2`; `("effort_approach", "effort")` quantity "work required", low "Trivial (minutes)", high "Large (a day or more)", `dangerous_end=none`; `("vision_score", "alert_level")` quantity "alert severity", low "No alert (calm green)", high "High (red)", `dangerous_end=high`, `dangerous_from=2`
- [X] T012 Create `evals/dataset/recipes.py` with `RECIPES: dict[str, RecipeSpec]` for the nine dataset recipes: the five coding recipes take `title`/`when`/`state`/`decides` verbatim from the current `report_text.RECIPES` entries with `family=Family.coding`; `vision_noul`, `vision_choice`, `vision_score`, `vision_video` get `family=Family.vision` and short titles ("Vision: dominant colour, yes/no", "Vision: dominant colour, choice", "Vision: alert level, score", "Vision: colour change across frames"); all `phase=0`, `risk=False`, `lint=LintMode.report`
- [X] T013 Create `evals/analysis_design.py` by moving `_recipes` and `_composition` out of `evals/analysis.py` (R19); `_recipes` builds each recipe entry from `RECIPES[category].model_dump()` plus the dataset's questions; `_composition["sources"]` keeps today's string-based `skill_md`/`curated` counting unchanged (the typed `source` arrives in slice 3B and T047 switches it); `evals/analysis.py` imports from `.analysis_design` and no longer references `report_text.RECIPES`
- [X] T014 Delete `RECIPES` from `evals/report_text.py` and move `REFERENCES` into a new `evals/report_references.py`; update `evals/analysis.py` (`"references": report_references.REFERENCES`) and any other importer found by `grep -rn "report_text.REFERENCES\|report_text.RECIPES"`; confirm `wc -l evals/report_text.py` < 400
- [X] T015 Run `make check` and `.venv/bin/pytest tests/test_eval_report.py -q`: every existing report test still passes (recipe cards still show title/when/state/decides); T005–T006 now pass

**Checkpoint**: Registries exist, `report_text.RECIPES` is gone, all tests green.

---

## Phase 3: User Story 1 — Every published number carries its direction, its risk, and its provenance (Priority: P1) 🎯 MVP

**Goal**: Phase 0 of the programme: declared and enforced score direction, risk-aware
recipes and metrics, token split per item, typed provenance on every item, vision out of the
headline, the dataset tooling package, the data-source register, and versioned, resumable
runs.

**Independent Test**: quickstart.md steps 1–9 — `make check` green; the three direction
checks pass and a reversed scale fails; `ember eval dataset {hash,lint,card --check,check}`
behave as contracted; the register validates with no `used` row; the rebuilt committed
bundles keep every per-recipe figure; a run carries `tokens` per row, can be interrupted
and resumed, and lands on a versioned leaderboard.

### Slice 3A — Direction (FR-001–FR-004; R3–R5)

#### Tests (write first, confirm failing)

- [X] T016 [P] [US1] Add `test_score_scorer_is_monotonic_with_unit_adjacent_error` to `tests/test_eval_benchmark.py`: for every `score` question spec in `ITEMS`, for each level *k*, `metrics.score_question(spec, gold=k, answer={"type": "score", "score": float(k), "probabilities": one-hot at str(k)})` gives `predicted == k` and `abs_error == 0.0`; `expected` strictly increases with *k*; with `gold=k` and `score=k+1`, `abs_error == 1.0`
- [X] T017 [US1] Move the module-scoped `synthetic_run`, `report`, and `bundle` fixtures (and their `_answers`/`DATASET`/`ITEMS` imports from `tests.test_eval_benchmark`) from `tests/test_eval_report.py` into `tests/conftest.py`, keeping names, scope, and behaviour so every existing `tests/test_eval_report.py` test still passes unchanged; `tests/test_eval_report.py` (568 lines) must not grow in this feature (Article X §10.3)
- [X] T018 [P] [US1] Create `tests/test_eval_report_phase0.py` (uses the shared fixtures) with `test_score_legends_render_in_html_and_markdown` — the `bundle`'s `report.html` and `report.md` both contain `0 Negligible → 3 High`, `0 Trivial (minutes) → 3 Large (a day or more)`, and `0 No alert (calm green) → 3 High (red)` — and `test_protocol_states_direction_rules` — `report["text"]["protocol"]` contains a bullet starting "Every `score` scale runs from least to most" and one starting "For a `noul` question, P(true) is the probability"

#### Implementation

- [X] T019 [US1] Append two bullets to `PROTOCOL` in `evals/report_text.py`: "Every `score` scale runs from least to most of the quantity its instruction names; index 0 is always the least. The expected score is read in those units. A scale is never reversed to make a label read naturally." and "For a `noul` question, P(true) is the probability of the condition the instruction names; the condition is phrased so that `true` is the pole that calls for caution."; reword the existing bullet "Every change alters the dataset's SHA-256…" to "A change to any item's state, media, questions, gold, or split alters the dataset's content hash, which each run records, so runs on different label sets cannot be compared by accident; annotations (kind, tier, source, rationale) do not."
- [X] T020 [US1] In `evals/analysis_design.py` `_recipes`, add `legend` (from `SCALES[(category, qid)].legend(len(criteria))`) and `dangerous_end` to every `score` question entry; in `evals/analysis.py` add `report["text"]["scales"]` = list of `{question, category, legend, dangerous_end}` and add `legend` to each `score_spread` entry
- [X] T021 [US1] Create `evals/sections/sections_scores.py` by moving `ordinal` and `confusion` out of `evals/sections/sections_results.py` (R19); in `ordinal`, emit `Para(f"Scale: {legend}")` immediately before each score question's table; update the `BUILDERS` tuple in `evals/document.py` to `sections_scores.ordinal` and `sections_scores.confusion`
- [X] T022 [US1] In `evals/sections/sections_results.py` `results()`, after the "By question type" table add `Heading("Scales", "scales")` and a `Definitions` block with one entry per `report["text"]["scales"]` item: term `` `{question}` `` and text `"{legend} (dangerous end: {dangerous_end})"`; confirm T016–T018 pass and `wc -l evals/sections/sections_results.py` < 400

### Slice 3B — Typed `source` and the dataset tooling core (FR-010, FR-026–FR-031, FR-035–FR-036, FR-046; R9, R13, R14, R16, R17)

#### Tests (write first, confirm failing)

- [X] T023 [P] [US1] Add `Source` tests to `tests/test_dataset_tooling.py`: each kind requires exactly its references — `authored`: `dataset_version` (64 hex), optional `note`; `mined`: `artefact`, `commit` (40 hex); `captured`: `session_id`, `redaction_sha256` (64 hex); `perturbed`: `parent_id`, `perturbation`; `templated`: `family`, `template_version`; `drafted`: `draft_id`, `adjudicated` must be `True`; `imported`: `register_row`, `record_id`; a foreign field or a missing one raises; `Item` validates `rationale` non-empty, `gold_labels` keys == `questions` keys, `kind: ItemKind | None`, `acted_differs=False` and `second_review=False` defaults
- [X] T024 [P] [US1] Add `io` tests to `tests/test_dataset_tooling.py`: `read_items` maps a bare `"curated"` source to `Source(kind=authored, dataset_version=<given legacy hash>)` and `"skill_md"` to the same with `note="reproduces a worked example in ember/agent_kit/ember-advise/SKILL.md"`; `write_items` → `read_items` round-trips; output lines are `json.dumps(model_dump(exclude_none=True), ensure_ascii=False)` in input order
- [X] T025 [P] [US1] Add `hashes` tests to `tests/test_dataset_tooling.py`: `projection(item)` contains exactly `id`, `category`, `split`, `state`, `images`/`videos`/`media_kwargs` when present, `questions`, `gold_labels` and nothing else; `dataset_content_sha256(items)` and `recipe_sha256(items)` are unchanged when an item's `source`, `rationale`, `kind`, `tier`, or review fields change and change when a `state`, `gold_labels`, `questions`, or `split` value changes; `recipe_sha256` is unchanged when another recipe's items change and is independent of item order; `dataset_sha256(path)` equals `hashlib.sha256(path.read_bytes()).hexdigest()`
- [X] T026 [P] [US1] Add `splitting`/`leakage` tests to `tests/test_dataset_tooling.py`: `assign_new` places new items per label toward 40/60 within the recipe, is deterministic (the same input twice gives the same assignment; items are visited in id order; ties go to `test`), keeps a perturbed item with its parent, a templated item with the first member of its family, and an imported item with earlier items from the same external record, and appends only new ids to the lock; `leakage.check` fails when an id's split differs from the lock, when a perturbation parent and child or two template-family members or two items with the same imported `register_row`+`record_id` sit in different splits; passes on the real dataset with the committed lock
- [X] T027 [P] [US1] Add `dedup` tests to `tests/test_dataset_tooling.py`: two items whose `state` differ only in whitespace and case are exact duplicates; two items with token-set Jaccard ≥ 0.85 and identical gold are a near-duplicate finding; the same pair with different gold is allowed; Jaccard is computed over whitespace-split tokens of the normalised state
- [X] T028 [P] [US1] Add `lint` tests to `tests/test_dataset_tooling.py`: one passing and one failing constructed dataset per `LintRule`; `kind-shares` thresholds exactly `negative ≥ 20%`, `control ≥ 10%`, `hard_negative ≥ 15%`, `near_miss ≥ 10% of score items`, `adversarial ≥ 5%`, `insufficient_context ≥ 5%`, `variant ≥ 10%`, `long_tier ≥ 10%` (only recipes whose `exemptions` do not cover the kind); untagged items are a `kind-shares` finding; `size-target` is 300 (400 when `risk`); `label-in-both-splits` also requires ≥ 40 per label in `test`; `template-share` ≤ 30%; a finding on a `LintMode.enforce` recipe makes `run()` return non-zero while a `report` recipe only lists it; `no-live-secret` flags a state containing an AWS access key id (`AKIA` + 16 uppercase alphanumerics), a GitHub token (`gh[pousr]_` + 36 chars), a Slack token (`xox[abprs]-…`), a Google API key (`AIza` + 35 chars), a PEM private-key block, or a signed web token (three base64url segments starting `eyJ`) — including a string leaf inside a dict state — makes `run()` return non-zero even for a `report` recipe, and passes when the exact value is listed in `example_secrets.json` (`AKIAIOSFODNN7EXAMPLE`)
- [X] T029 [P] [US1] Add `card` tests to `tests/test_dataset_tooling.py`: `card.build()` returns per-recipe `items`, `per_label_per_split`, `kind_shares` (+ `untagged`), `source_shares`, `external_sources`, `label_stability=None`, `inter_source_agreement=None`, `rater_count=1`, `second_review_pending`, `acted_differs_share=None`, `easy_items`, `recipe_sha256`, `gaps`, `exemptions`, and top-level `dataset_content_sha256`, `dataset_sha256`, `register_sha256`, `generated_from`; `render_markdown` is deterministic; `test_committed_card_is_fresh` regenerates `card.json` and `CARD.md` in memory and compares bytes with the committed files
- [X] T030 [P] [US1] Add `check` tests to `tests/test_dataset_tooling.py`: `check.run()` passes on the real dataset; fails naming the item when a `mined` commit is not 40 hex, when an `imported` item's `register_row` is missing or not `used`, when a `perturbed` parent id does not exist, when an id is absent from `splits.lock`, and when `example_secrets.json` has a duplicate value or an entry without a URL
- [X] T031 [P] [US1] Add `tiers` tests to `tests/test_dataset_tooling.py`: `tiers.easy_ids(versions, current)` over synthetic leaderboard versions returns exactly the ids that every row's producing run for that recipe scored fully correct (an item missed by any row is not easy; a row lacking the recipe is ignored); `tiers.apply(items, easy_ids)` sets `tier="easy"` on those and clears it elsewhere; `dataset_content_sha256` is identical before and after `apply`; `main(["--from", dir, "--dataset", path])` rewrites the file, prints the counts, and returns 1 when no row exists on the current version
- [X] T032 [P] [US1] Create `tests/test_cli_eval_dataset.py` (new module; `tests/test_cli.py` is 829 lines and must not grow): `ember eval dataset lint|card|hash|check` dispatch to `evals.dataset.{lint,card,hashes,check}.main` with the parsed flags (`--dataset PATH`, `--enforce-all`, `--json`, `--check`), using the same monkeypatch pattern as the existing `ember eval context` dispatch test in `tests/test_cli.py`

#### Implementation

- [X] T033 [P] [US1] Create `evals/dataset/records/source.py`: frozen Pydantic `Source` with `kind: SourceKind` and optional reference fields, a model validator enforcing the per-kind required set from data-model.md and rejecting fields that belong to another kind, and `LEGACY_SOURCES = {"curated": ..., "skill_md": ...}` helpers used by the shim
- [X] T034 [US1] Create `evals/dataset/records/item.py`: frozen Pydantic `Item` with the fields and defaults in data-model.md (`id`, `category`, `split: Split`, `state`, optional `images`/`videos`/`media_kwargs`, `questions: dict[str, dict]`, `gold_labels`, `rationale` non-empty, `source: Source`, `kind: ItemKind | None = None`, `parent_id`, `template_family`, `external_label`, `acted`, `acted_differs: bool = False`, `second_review: bool = False`, `second_pass`, `tier: Literal["easy"] | None`) and the validator `gold_labels.keys() == questions.keys()`
- [X] T035 [US1] Create `evals/dataset/io.py`: `DATASET_PATH`, `read_items(path, *, legacy_dataset_version: str | None) -> list[Item]` (bare-string `source` shim), `write_items(path, items)` (atomic via `evals.export.write_atomic`, one `json.dumps(item.model_dump(exclude_none=True), ensure_ascii=False)` per line)
- [X] T036 [P] [US1] Create `evals/dataset/hashes.py`: `projection(item) -> dict` (exactly `id`, `category`, `split`, `state`, `images`, `videos`, `media_kwargs` when present, `questions`, `gold_labels`); `dataset_content_sha256(items)` and `recipe_sha256(items)` over `"\n".join(json.dumps(projection(i), sort_keys=True, ensure_ascii=False) for i in sorted(items, key=lambda i: i.id))`; `dataset_sha256(path)` (file bytes, provenance only); `register_sha256(path)`; and `main(argv)` printing all four (`--json`, `--dataset PATH`)
- [X] T037 [US1] Migrate `evals/clef-flash.jsonl`: compute the pre-migration `dataset_sha256`, read with `read_items(legacy_dataset_version=<that hash>)`, write back with `write_items`; every `source` is now an object; commit the new file (the dataset hash changes by design — FR-012 concerns committed runs, not the live file)
- [X] T038 [US1] Create `evals/dataset/splitting.py` (not `split.py`, which is the `Split` enum under `records/`): `read_lock(path) -> dict[str, Split]`, `append_lock(path, assignments)` (atomic; never rewrites existing ids), `assign_new(items, lock) -> dict[str, Split]` — deterministic, no randomness: visit unassigned items in id order; place each in the split that most reduces the maximum deviation from the 40/60 target across the item's own `(category, question, label)` strata, ties to `test`; a perturbed item follows its parent, a templated item the first member of its family, an imported item any earlier item from the same external record — and `main(argv)` with `--init` that seeds the lock from the current dataset's splits and `--dataset PATH`; generate and commit `evals/dataset/splits.lock` from the migrated dataset
- [X] T039 [P] [US1] Create `evals/dataset/dedup.py`: `normalise(state) -> str` (JSON canonical form for dicts, whitespace-collapsed, lower-cased), `exact_duplicates(items)`, `near_duplicates(items, threshold=0.85)` (token-set Jaccard over whitespace tokens of the normalised state; pairs with identical `gold_labels` only)
- [X] T040 [US1] Create `evals/dataset/leakage.py`: `check(items, lock) -> list[LintFinding]` for `split-pinned` (id's split ≠ lock), `family-split` (perturbation parent/children, `template_family`, and `imported` items sharing `register_row`+`record_id` across splits)
- [X] T041 [US1] Create `evals/dataset/records/lint_finding.py` (frozen Pydantic `LintFinding(rule: LintRule, category: str, message: str, item_id: str | None, enforced: bool)`) and `evals/dataset/lint.py`: one function per `LintRule` with the thresholds from T028, `no-live-secret` scanning every string leaf of each `state` with the formats from T028 and the allow-list from `example_secrets.json`, always `enforced=True` regardless of `LintMode`, `run(items, lock, register, *, enforce_all=False) -> list[LintFinding]`, `main(argv)` (`--enforce-all`, `--json`) returning 1 when any finding is `enforced`
- [X] T042 [US1] Create `evals/dataset/card.py`: `build(items, register, findings) -> dict` (fields from T029, including `easy_items` per recipe and the top-level content hash), `render_markdown(card) -> str`, `write(card)` (atomic `card.json` + `CARD.md`), `main(argv)` with `--check` (exit 1 when the committed files differ); generate and commit `evals/dataset/card.json` and `evals/dataset/CARD.md`
- [X] T043 [P] [US1] Create `evals/dataset/records/example_secret.py` (frozen Pydantic `ExampleSecret(value, vendor, url, read_on: date)`, all non-empty) and `evals/dataset/example_secrets.json` (`schema_version: 1`; entries for AWS's documented `AKIAIOSFODNN7EXAMPLE` and `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` with the IAM documentation URL and `read_on: 2026-10-10`); `evals/dataset/register.py` gains `load_example_secrets(path)` validating unique values
- [X] T044 [US1] Create `evals/dataset/tiers.py`: `easy_ids(versions, current_content_sha256) -> set[str]` (over every row of the current version, an item is easy when each row's producing run for that recipe scored it fully correct, read from the bundles' `trace.jsonl` by run id), `apply(items, easy_ids) -> list[Item]`, and `main(argv)` with `--from DIR` (default `benchmark/`) and `--dataset PATH` that rewrites annotations only, prints `easy: n (+a / -r)`, asserts `dataset_content_sha256` is unchanged, and returns 1 when no leaderboard row exists on the current version
- [X] T045 [US1] Create `evals/dataset/check.py`: `run(items, lock, register) -> list[str]` resolving every `source` per T030, every id present in the lock, and hashes computable; `main(argv)` returning 1 on any failure
- [X] T046 [US1] Wire the CLI: in `ember/commands/parser.py` `register_eval()` add a `dataset` sub-parser with sub-commands `lint` (`--dataset PATH`, `--enforce-all`, `--json`), `card` (`--dataset PATH`, `--check`), `hash` (`--dataset PATH`, `--json`), `check` (`--dataset PATH`), `tier` (`--from DIR` default `benchmark/`, `--dataset PATH`), `--dataset` defaulting to `evals/clef-flash.jsonl` as `eval run --dataset` does; in `ember/commands/eval.py` add `cmd_eval_dataset` following the existing `_EVAL_CHECKOUT_ERROR` lazy-import pattern (the checkout-only harness is not an `ember`-internal module; keep the same justification comment the other handlers carry) and dispatching to the module's `main`; wire in `ember/cli.py`
- [X] T047 [US1] Update `evals/analysis.py` values for the report text: `skill_md` = authored items whose `source.note` names SKILL.md, `curated` = other items; update the shared `synthetic_run` fixture in `tests/conftest.py` if it builds `source` strings; confirm T023–T032 pass and `make check` is green

### Slice 3C — Data-source register (FR-039–FR-045; R15)

#### Tests (write first, confirm failing)

- [X] T048 [P] [US1] Create `tests/test_data_source_register.py`: `RegisterRow` requires unique `id`, ≥ 1 `urls` entry with `read_on`, `licence` with `reading`, `read_at`, `read_on`, `class`, a `verdict`, and a `reason`; `verdict == used` requires `snapshot`, `mirror`, `transformation`, and `mirror.sha256 == snapshot.sha256`; `verdict != used` requires `items_imported == 0`; `class in {non_commercial, research_only, gated}` forces `verdict == excluded`; `register.validate(rows, items)` fails when an `imported` item references a row that is not `used` or when `items_imported` disagrees with the dataset; the committed `evals/dataset/register.json` validates, contains no `used` row, and contains rows with ids `nist-juliet`, `cvefixes`, `apachejit`, `swe-bench`, `agentdojo`, `deepset-prompt-injections`, `ragtruth`, `scancode-licensedb`, `nvidia-aegis-2`, `typesafe-evalsafe-security-incidents`, and `excluded` rows `anli`, `r-judge`, `agentharm`, `commitbench`, `beavertails`, `wildguardmix`, `toxigen`, `secretbench`, `bipia`, `gpqa`; `example_secrets.json` validates (`ExampleSecret` fields, unique values) and a duplicate value or missing URL is rejected
- [X] T049 [P] [US1] Add `scripts/audit_data_sources.py` to the parametrised `test_eval_scripts_run_directly_as_make_runs_them` in `tests/test_eval_benchmark.py` (responds to `--help` with exit 0)

#### Implementation

- [X] T050 [P] [US1] Create the register records in `evals/dataset/records/`, one class per file: `url_reading.py` `UrlReading(url, read_on: date)`; `licence_reading.py` `LicenceReading(reading, spdx: str | None, read_at, read_on: date, class_: LicenceClass)` (serialised as `class`); `snapshot_ref.py` `SnapshotRef(version, sha256: 64 hex, retrieved_on: date)`; `mirror_ref.py` `MirrorRef(location, sha256: 64 hex, public: bool)`; `register_row.py` `RegisterRow` with the fields and cross-field validators from T048 plus `feeds: list[str]`, `items_imported: int = 0`, `attribution: str | None`, `upstream_available: bool = True`, `notes: str | None`
- [X] T051 [US1] Create `evals/dataset/register.py`: `REGISTER_PATH`, `load(path) -> list[RegisterRow]`, `validate(rows, items) -> list[str]` (cross-checks from T048), and `sha256(path)`
- [X] T052 [US1] Write `evals/dataset/register.json` (`schema_version: 1`, `recorded_on: "2026-10-10"`) with one row per source in spec.md's Candidate External Sources table, plus the Cloudflare Decision Index members and TypeSafe's four `evalsafe-*` datasets, using the licence readings, `read_on: 2026-10-10`, verdicts, and reasons stated there; general-knowledge benchmarks get `verdict: excluded`, `reason: "out of scope (FR-042)"`; `snapshot`, `mirror`, `transformation` are `null` and `items_imported` is `0` on every row
- [X] T053 [US1] Create `scripts/audit_data_sources.py` (standalone, network): `--rows id,id`, `--timeout 20`; per row HEAD-then-GET each URL (`url_ok`), re-read the licence page and record whether the SPDX id or licence name appears (`licence_reading_unchanged`), and for `used` rows fetch the mirror and compare SHA-256 (`mirror_ok`); write `evals/dataset/register-audit.json` atomically with `audited_on`; exit 1 when a `used` row fails `mirror_ok` or any of its URLs fails; never modify `register.json`

### Slice 3D — Risk metrics, consistency, and the headline composition (FR-005–FR-007, FR-011, FR-012, FR-036, FR-037; R7, R10, R19, R21)

#### Tests (write first, confirm failing)

- [X] T054 [P] [US1] Create `tests/test_risk_metrics.py`: `unsafe_partition` — `noul` → gold `True`; `choice` → `RecipeSpec.dangerous_options[qid]`; `score` → levels `≥ dangerous_from` when `dangerous_end == high` and `≤ dangerous_from` when `low`; on hand-built records: `dangerous_recall` (argmax over every answer), `dangerous_recall_at_threshold` (only answers with `choice` confidence ≥ 0.85 or `noul` P ≥ 0.80 / ≤ 0.20; `score` reuses the plain figure), `missed_dangers` (unsafe items with a confident safe verdict), `safe_precision` and its at-threshold variant; `bar` is 0.98 when the partition includes a question named `harm_kind` or `weakens_control`, else 0.95; `met` compares the at-threshold recall with `bar`; empty and all-safe inputs return `None` recall without raising
- [X] T055 [P] [US1] Create `tests/test_metrics_aggregate.py` with `test_aggregate_headline_excludes_capability_recipes` — synthetic results mixing coding and `vision_*` categories give `summary["overall"]` over coding questions only and `summary["capability"]` with the vision items, questions, accuracy, `accuracy_ci`, and per-category figures; `summary["risk"] == {}` when no registered recipe is `risk`; `summary["tokens"]` has `median_state`, `max_state`, `state_bins` when rows carry `tokens` and is `None` otherwise
- [X] T056 [P] [US1] Add to `tests/test_metrics_aggregate.py`: `test_aggregate_reports_consistency_over_variant_groups` — synthetic items where `perturbed` rows with `source.perturbation ∈ {"paraphrase", "format"}` point at a parent via `parent_id` give `summary["consistency"][category] == {"groups": n, "agreement": share of groups whose every member received the same predicted label on every question}` and `None` for a recipe without groups; `test_aggregate_reports_accuracy_by_source_kind` — a recipe holding `authored` and `imported` items gets `summary["by_source_kind"][category][kind] == {"items", "accuracy", "item_accuracy"}` per kind, and a single-kind recipe gets no entry; `test_aggregate_reports_non_easy_accuracy` — rows carrying `tier == "easy"` give `summary["tiers"] == {"easy_items", "easy_questions", "non_easy": {"items", "questions", "accuracy", "accuracy_ci"}}` computed over the untiered rows, and `None` when no row carries a tier
- [X] T057 [P] [US1] Add to `tests/test_eval_report_phase0.py`: with `RECIPES` monkeypatched to add a `risk=True` recipe whose `dangerous_options` are set and a synthetic run over it, the bundle renders a "Dangerous recall" table with recall at threshold, missed dangers, bar, and `met`/"not met"; the Results section renders a "Capability panel" table listing the vision recipes; the summary section states "Headline over coding recipes; vision recipes in the capability panel"; a synthetic run with variant groups renders a "Consistency" row (groups, agreement) and one with mixed source kinds renders a "By source" table

#### Implementation

- [X] T058 [US1] Create `evals/metric_functions.py` by moving `macro_f1`, `reliability`, `calibration_error`, `brier_multiclass`, `brier_binary`, `ranked_probability_score`, `bootstrap_ci`, and `BINS` out of `evals/metrics.py` (R19); update importers: `evals/metrics.py`, `evals/context/scoring.py`, `evals/context/reproduce.py`, `tests/test_eval_benchmark.py`, `tests/test_context_probe.py`, `tests/test_snapshot_evals.py` (import the defining module, no re-exports)
- [X] T059 [US1] Create `evals/risk_metrics.py` with `unsafe_partition`, `dangerous_recall`, `dangerous_recall_at_threshold`, `safe_precision`, `safe_precision_at_threshold`, `missed_dangers`, `bar_for`, and `summarize(records, spec, scales) -> dict` producing `{dangerous_recall, dangerous_recall_at_threshold, safe_precision, safe_precision_at_threshold, missed_dangers, unsafe_n, bar, met}`; add `"evals/risk_metrics.py"` to `[tool.mypy].files` in `pyproject.toml`
- [X] T060 [US1] Update `aggregate()` in `evals/metrics.py`: `overall` over records whose `RECIPES[category].headline` is `True`; `capability` block for the rest (`None` when empty); `risk` per `risk` recipe via `risk_metrics.summarize`; `tokens` from rows carrying `tokens` (bins of state tokens with `n`, `accuracy`, `brier`; `None` when no row carries them); `consistency` per recipe over variant groups (an original plus every `perturbed` item with `parent_id` → it and `source.perturbation ∈ {paraphrase, format}`; `agreement` = share of groups whose every member received the same predicted label on every question; `None` without groups); `by_source_kind` per recipe with more than one source kind (`{items, accuracy, item_accuracy}` per kind); `tiers` (`easy_items`, `easy_questions`, `non_easy{items, questions, accuracy, accuracy_ci}`) when any row carries `tier`, else `None`; keep `categories`, `questions`, `choice`, `noul`, `score`, `misses` unchanged; confirm `wc -l evals/metrics.py` < 400
- [X] T061 [US1] Create `evals/analysis_findings.py` by moving `_findings` out of `evals/analysis.py` (R19); surface `summary["capability"]`, `summary["risk"]`, `summary["consistency"]`, and `summary["by_source_kind"]` in the report model; `report["meta"]` gains `dataset_content_sha256`, `recipe_sha256`, `register_sha256`, `settings`, and `tokens_available` copied from `config`, and `meta.dataset` gains `content_sha256` (`null`/`false` when a pre-Phase-0 bundle lacks them); in `evals/sections/sections_front.py` recipe cards show `family`, a "risk recipe" badge, and compliance references when present, and the design section renders the generated card's per-recipe rows; confirm `wc -l evals/analysis.py` < 400
- [X] T062 [US1] In `evals/sections/sections_results.py` `results()`: add the summary note "Headline over coding recipes; vision recipes in the capability panel." in `sections_front.summary`, a "Capability panel" `Table` (recipe, items, item accuracy, question accuracy) after "By recipe", a "Dangerous recall" `Table` for `summary["risk"]` entries (recipe, recall at threshold, missed dangers, bar, met / **not met**), a "Consistency" row per recipe with variant groups (groups, agreement), a "By source" `Table` per recipe with more than one source kind, and an "All items / Non-easy" accuracy pair when `summary["tiers"]` is present; confirm T054–T057 pass

### Slice 3E — Token split end to end (FR-009; R8)

#### Tests (write first, confirm failing)

- [X] T063 [P] [US1] Add to `tests/test_runtime_unit.py`: with the fake joint module and processor, `Engine.advise()` returns `usage` containing `state_tokens`, `fixed_tokens`, `media_tokens` equal to the measured `RequestSize` parts and summing to `input_tokens`
- [X] T064 [P] [US1] Add to `tests/test_http_api.py` (model-backed fixture): the three `usage` keys are present on every `200` across `noul`/`choice`/`score` requests and sum to `input_tokens`; `413`, `422`, and `503` bodies are unchanged (no `usage`)
- [X] T065 [P] [US1] Add to `tests/test_mcp_tool.py`: with the stub endpoint returning a `usage` carrying the three keys, the `advise` tool result contains them unchanged
- [X] T066 [P] [US1] Create `tests/test_run_evals.py`: with `evals.eval.client._advise` monkeypatched to return a body whose `usage` lacks the split, `run_evals.run_evals(...)` returns 1 and prints the error naming the server version and the minimum before any trace row is written; with the split present, every trace row has `tokens == {total, state, fixed, media}` with `state + fixed + media == total`
- [X] T067 [P] [US1] Add to `tests/test_eval_report_phase0.py`: for a run whose rows carry `tokens`, the bundle contains figure `fig-tokens` as valid SVG and its caption states the median and maximum state length; for a run whose rows lack `tokens` (`meta.tokens_available == false`), the figure is absent and the Results section states that the token split is unavailable for this run

#### Implementation

- [X] T068 [US1] In `ember/serving/runtime.py` `Engine.advise()`, after the existing `usage.input_tokens` invariant check, add `state_tokens=size.state`, `fixed_tokens=size.fixed`, `media_tokens=size.media` to the response's `usage`; update the method docstring
- [X] T069 [P] [US1] Document the API change: the `usage` example in README "Usage" gains the three keys with one sentence on what they are; `COMPATIBILITY.md` notes the minimum ember server version that returns the split and that the benchmark harness requires it
- [X] T070 [US1] Create `evals/eval/client.py` by moving `DEFAULT_SERVER`, `TIMEOUT`, `_DEVICE_LABELS`, `_resolve_server`, `_deployment_label`, `_model_name`, `_health`, `_advise` out of `evals/eval/run_evals.py` (R19); update `run_evals.py` and any test importing them
- [X] T071 [US1] In `evals/eval/run_evals.py`: on the first `200`, require `usage.state_tokens`, `fixed_tokens`, `media_tokens`; if absent print `error: the server at <label> (ember <version or "unknown">) does not return the token split in usage; ember >= <min> is required for the benchmark.` and return 1 before writing any row; otherwise write `tokens: {total: input_tokens, state, fixed, media}` into every trace row together with the item's annotations `kind`, `tier`, `source_kind`, `parent_id`, `perturbation` (`null` when absent)
- [X] T072 [US1] Create `evals/charts/charts_tokens.py` (binned accuracy and Brier against state tokens, same SVG helpers as `evals/charts/charts.py`); in `evals/analysis.py` pass `summary["tokens"]` through; in `evals/sections/sections_results.py` add `Figure("tokens", ...)` with a caption stating the median and maximum state tokens when `summary["tokens"]` is present, and otherwise a `Para` stating the token split is unavailable for this run (pre-Phase-0 trace); confirm T063–T067 pass (`make test` for the model-backed ones)

### Slice 3F — Run manifest, resume, hashes, and the bundle rebuild (FR-012, FR-034, FR-066; R10–R12)

#### Tests (write first, confirm failing)

- [X] T073 [P] [US1] Add to `tests/test_run_evals.py`: `results/<run-id>_run.json` exists before the first `_advise` call with `run_id, model, deployment_label, settings{dtype, max_length, max_request_length}, dataset_sha256, dataset_content_sha256, recipe_sha256, register_sha256, split, category, started_at`; every trace row carries `tokens` and the annotations `kind`, `tier`, `source_kind`, `parent_id`, `perturbation`; the final `config` carries `dataset_content_sha256`, `recipe_sha256`, `register_sha256`, `settings`, `policy == {}`, `resumed`; `--resume` skips ids already in the trace and ends with every item exactly once and `resumed: true`; a resume whose live `dtype` differs or whose dataset content hash differs (a gold edit) returns 1 naming the mismatched field, while a `rationale`-only edit between interruption and resume is accepted
- [X] T074 [P] [US1] Add to `tests/test_snapshot_evals.py`: `snapshot --rebuild <run-id>` on a synthetic bundle whose `dataset.jsonl` still has string sources rewrites `results.json["summary"]` from the bundle's `trace.jsonl`, reads the dataset through the legacy shim using the bundle's `config.dataset_sha256` as `legacy_dataset_version`, keeps `config`, joins `kind`, `tier`, `source_kind`, `parent_id`, `perturbation` into the rows by id, adds `dataset_content_sha256` and `recipe_sha256` (computed from the bundle's `dataset.jsonl`) and `register_sha256: null` when absent, rewrites `model.json` whose `meta` carries `dataset_content_sha256`, `recipe_sha256`, `register_sha256`, `settings`, and `tokens_available: false`, and leaves the privacy scrub unchanged
- [X] T075 [P] [US1] Create `tests/test_benchmark_bundles.py`: for every `benchmark/*/` bundle, recomputing the summary from its `trace.jsonl` reproduces the stored `summary["categories"]` and `summary["questions"]` exactly, `summary["capability"]` holds only `vision_*` categories, `model.json["meta"]` carries `recipe_sha256`, and `meta.dataset_content_sha256` equals `dataset_content_sha256` of the current `evals/clef-flash.jsonl` (the permanent form of the FR-012 gate, and proof the source migration changed no scored content)

#### Implementation

- [X] T076 [US1] Create `evals/eval/resume.py`: Pydantic `RunManifest` (fields from T073), `write(path, manifest)` (atomic), `read(path)`, `mismatches(manifest, health_engine, dataset_content_sha256, split, category) -> list[str]` (compares the content hash, so annotation-only edits do not block a resume), `done_ids(trace_path) -> set[str]` (via `evals.context.rows_file.read_rows`-style torn-line-safe reading)
- [X] T077 [US1] Update `evals/eval/run_evals.py`: write the manifest before the first request; append trace rows with `evals.context.rows_file`; add `--resume RUN_ID` (refuse with the mismatch list, else skip `done_ids`); add `dataset_content_sha256` and `recipe_sha256` (via `evals.dataset.hashes`), `register_sha256`, `settings`, `policy: {}`, `resumed` to `config`; confirm `wc -l evals/eval/run_evals.py` < 400
- [X] T078 [US1] Wire flags: `ember/commands/parser.py` `run --resume RUN_ID` and `snapshot --rebuild RUN_ID` (mutually exclusive with `results_file`); `ember/commands/eval.py` passes them through; add dispatch tests to `tests/test_cli_eval_dataset.py` (not `tests/test_cli.py`)
- [X] T079 [US1] In `evals/eval/snapshot_evals.py` add `--rebuild RUN_ID`: load `benchmark/<run>/trace.jsonl` rows, read `dataset.jsonl` with `io.read_items(legacy_dataset_version=config["dataset_sha256"])` (its sources are still strings), join each row's `kind`, `tier`, `source_kind`, `parent_id`, `perturbation` from that dataset by id, recompute `metrics.aggregate`, rewrite `results.json` (preserve `config`, add `dataset_content_sha256` and `recipe_sha256` from the dataset and `register_sha256: null` when absent) with the existing scrub, then `analysis.build(..., dataset_path=<bundle dataset>)` → `model.json` with `meta.tokens_available` reflecting whether the rows carry `tokens`; exit 1 when `trace.jsonl` or `dataset.jsonl` is missing
- [X] T080 [US1] Rebuild both committed bundles (`ember eval snapshot --rebuild clef-flash_20261003T203810Z` and `--rebuild Cloudflare__clef-flash_20261010T192756Z`), run quickstart step 6's comparison (categories and questions identical; `overall` changed only by the vision exclusion; `meta.dataset_content_sha256` equals the current dataset's content hash), and commit the rewritten `results.json` and `model.json`; confirm T073–T075 pass

### Slice 3G — Versioned leaderboard and site (FR-034, FR-066; R11)

#### Tests (write first, confirm failing)

- [X] T081 [P] [US1] Extend `tests/test_leaderboard.py`: `build()` returns `{"versions": [...]}` keyed by `dataset_content_sha256`, newest first; rows group by `(model_key, deployment_key, settings_key)`; a recipe column comes from the latest run in the group whose `recipe_sha256[category]` equals the version's; `headline` is present only when every `RECIPES[...].headline` recipe is assembled on this version, else `headline is None` and `incomplete is True`; `recipes[category].run_id` names the producing run and the row's `run_id` is the newest contributing run; runs without `dataset_content_sha256` form their own version keyed by their file `dataset_sha256` and never merge; a group holding an older full run and a newer partial run on the same version assembles the partial run's recipes over the older ones; `capability`, `risk`, `tiers`, `single_rater: True`, latency, and version fields pass through
- [X] T082 [P] [US1] Create `tests/test_site_benchmark.py`: `build_site_benchmark.headline(row)` includes `scope == "coding"` and `capability`; `_leaderboard_page_body(versions)` renders one `<table>` per version, newest first, with a `—` headline cell for an `incomplete` row, recipe cells linking to `/results/<producing run_id>/summary/`, and the Model cell linking to the row's `run_id`

#### Implementation

- [X] T083 [US1] Rewrite `evals/leaderboard.py`: add `settings_key(meta)` from `meta["settings"]` (falling back to `meta["engine"]` for `dtype`, `max_length`, `max_request_length`); `build(models)` groups by `(model_key, deployment_key, settings_key)` within each `dataset_content_sha256` version (file hash for pre-Phase-0 runs), assembles per-recipe columns, computes `headline`/`incomplete`, sets the row's `run_id` to the newest contributing run, and returns `{"versions": [...]}` per data-model.md; keep module docstring current
- [X] T084 [US1] Update `scripts/build_site_benchmark.py`: `headline(row)` adds `scope: "coding"` and `capability`; `_leaderboard_page_body` renders a table per version (title: content-hash prefix and item count) with Model · Deployment · Device · Headline · Items correct · per-recipe columns · Capability · Dangerous recall · Latency p50 · ember version · Run at, `—` plus a title attribute naming missing recipes for `incomplete` rows, recipe cells linking to the producing run and the Model cell to the row's `run_id`; write `site/_data/benchmark.json` as `{"leaderboard": {"versions": [...]}, "runs": {...}, "headline": headline(<newest row with a headline>)}`
- [X] T085 [US1] Update `site/index.md` "Measured, not promised" to state the headline covers coding recipes and link the capability panel on `/results/`; grep `site/_includes/benchmark_nav.html` and `site/_layouts/*.html` for `leaderboard.rows` and update any reference to the new `versions` shape; run `python3 scripts/build_site_benchmark.py` and confirm T081–T082 pass

**Checkpoint**: Phase 0 is functionally complete; quickstart steps 1–9 pass.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, governance, and the full verification pass.

- [X] T086 [P] Update `README.md` "Benchmark" section: structured `source` with the seven kinds, `ember eval dataset {lint,card,hash,check}` (with `--dataset`), the data-source register and `make audit-sources`, dataset versions and per-recipe columns on the leaderboard, `ember eval run --resume`, `ember eval snapshot --rebuild`, the capability panel, the consistency and by-source rows, and the `Benchmark dataset: <hash>` line each release's changelog carries
- [X] T087 [P] Update `AGENTS.md`: project structure (`evals/dataset/`, `evals/metric_functions.py`, `evals/risk_metrics.py`, `evals/analysis_design.py`, `evals/analysis_findings.py`, `evals/report_references.py`, `evals/sections/sections_scores.py`, `evals/charts/charts_tokens.py`, `evals/eval/client.py`, `evals/eval/resume.py`, `scripts/audit_data_sources.py`), commands table (`make dataset-lint`, `make dataset-card`, `make audit-sources`), Testing table rows for the new test files (`test_dataset_tooling.py`, `test_data_source_register.py`, `test_risk_metrics.py`, `test_metrics_aggregate.py`, `test_eval_report_phase0.py`, `test_cli_eval_dataset.py`, `test_run_evals.py`, `test_benchmark_bundles.py`, `test_site_benchmark.py`), watch-outs ("`usage` carries the token split and the harness requires it", "`splits.lock` is append-only; an item never changes split", "never import an external record without a `used` register row", "the headline is coding recipes only", "the dataset version is the content hash: annotations (kind, tier, source, rationale) never change it, gold/state/questions/split do", "`no-live-secret` is never relaxed; add vendor-documented example values to `example_secrets.json` with their URL", "the release workflow writes the dataset hash into the changelog"), and a Recent Changes entry dated 2026-10-10
- [X] T088 Amend `.specify/memory/constitution.md` with a PATCH Sync Impact Report (3.1.2 → 3.1.3) removing `evals/analysis.py`, `evals/sections/sections_results.py`, `evals/report_text.py`, `evals/metrics.py`, and `evals/eval/run_evals.py` from the §10.18 oversize list (listing the new line counts and the modules they were split into), recording that `evals/analysis.py` had grown from the recorded 793 lines to 826 before the split (unrecorded growth, as the 2.0.1 report did for `cli.py`), and updating the version line; verify each file is under 400 lines with `wc -l`
- [X] T089 Edit `.github/workflows/release-ember.yml`: after the version bump step, run `python3 -m evals.dataset.hashes --json`, prepend `Benchmark dataset: <dataset_sha256>` to the new version's section of `CHANGELOG.md` before the bump commit is pushed, and include the same line in the GitHub Release notes; keep every `uses:` SHA-pinned and `persist-credentials: false`; run `uvx zizmor@1.30.1 .github/` clean and `make release-dry` before pushing (needs a token with the `workflow` scope)
- [X] T090 Run `make pr-ready` (format, lint, mypy incl. `evals/dataset` and `evals/risk_metrics.py`, bandit, compile, unit tests) and fix anything it reports
- [X] T091 Run `make test` (model-backed: `usage` split over HTTP and MCP) and `make test-cov`; the coverage floor stays ≥ 81 — raise `fail_under` in `pyproject.toml` to the new measured level if it is higher (Article XI §11.2, never lower)
- [X] T092 Execute quickstart.md steps 1–9 end to end (including an interrupted-and-resumed run and the site build) and record any deviation as a follow-up task here
  - Deviations found: (a) a bare `ember eval run --resume RUN_ID` refused the run its own manifest described (`category: manifest 'routing', requested None`); fixed in `evals/eval/run_evals.py` (the resume inherits the manifest's split/category; an explicit different filter still mismatches) with `tests/test_run_evals.py::test_bare_resume_inherits_the_manifest_filters`. (b) The 2026-10-03 bundle is its own dataset version (`913e1b65…`, the 264-item dataset), so a fresh run forms a new incomplete row in the current version instead of joining that bundle's group; quickstart steps 6 and 9 now say so. (c) The negative resume path (restart with `EMBER_MAX_REQUEST_LENGTH=4096`) was not run live; `test_resume_refuses_a_changed_setting_or_gold` covers the settings mismatch. (d) `make release-dry` exits 21 (no releasable commits) until this work is committed.
- [X] T094 Split `tests/test_run_evals.py` (572 lines) under the 400-line ceiling: move the manifest/resume tests and their helpers (`_patch`, `_dataset`, `_answers_for`, `SPLIT_USAGE`) into `tests/test_run_evals_resume.py` or `tests/conftest.py` fixtures (follow-up from T092; not blocking)
- [X] T093 Append `vault/sessions/2026-10-10-benchmark-foundations.md` from `vault/_meta/templates/session-log.md` (what shipped, the rebuilt bundles, the API change), link it from `vault/ember.md`, and run `make vault-audit`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies; T002–T004 run in parallel after T001
- **Foundational (Phase 2)**: depends on Setup; **blocks every slice of Phase 3**
- **User Story 1 slices (Phase 3)**: all depend on Phase 2; slice order follows plan.md's
  delivery order, with these cross-slice dependencies:
  - 3B (dataset core) before 3C (register validation cross-checks items) and before 3F
    (hashes in `config`)
  - 3D (metrics) before 3F (`--rebuild` recomputes the new `aggregate`) and 3G (rows carry
    `capability`/`risk`)
  - 3E (token split) before 3F's `tokens` requirement is exercised in `test_run_evals.py`
  - 3F before 3G (leaderboard reads `recipe_sha256` from rebuilt bundles)
  - 3A is independent of 3B–3G after Phase 2
- **Polish (Phase 4)**: depends on all seven slices

### Within Each Slice

- Test tasks are written and confirmed failing before the implementation tasks that follow
  them (Article XI)
- Records before modules that read them; modules before CLI wiring; CLI before docs
- Each slice ends with its tests green and `make check` green

### Parallel Opportunities

- Phase 1: T002, T003, T004 together
- Phase 2: T005–T006 together; then T007, T008, T009 together; T011 after T008; T012 after
  T010; T013–T014 after T012 (T014 in parallel with T013)
- Slice 3A: T016 and T017 together; T018 after T017
- Slice 3B: T023–T032 together (ten test tasks); then T033, T036, T039, T043 together
- Slice 3C: T048–T049 together; T050 in parallel with 3B's T039
- Slice 3D: T054–T057 together (four test tasks)
- Slice 3E: T063–T067 together; T069 in parallel with T068
- Slice 3F: T073–T075 together
- Slice 3G: T081–T082 together
- Phase 4: T086–T087 together; T089 in parallel with T088

---

## Parallel Example: Slice 3B

```bash
# Write all nine test groups first (different test functions, one file — coordinate by
# section headers inside tests/test_dataset_tooling.py), then:
Task: "Create evals/dataset/records/source.py"            # T033
Task: "Create evals/dataset/hashes.py"                     # T036
Task: "Create evals/dataset/dedup.py"                      # T039
# then sequentially: item.py → io.py → migrate dataset → splitting.py + lock → leakage.py →
# lint.py → card.py → check.py → CLI wiring → analysis values
```

## Parallel Example: Slice 3E

```bash
Task: "tests/test_runtime_unit.py usage split"             # T063
Task: "tests/test_http_api.py usage split"                 # T064
Task: "tests/test_mcp_tool.py usage pass-through"          # T065
Task: "tests/test_run_evals.py split requirement"          # T066
Task: "tests/test_eval_report_phase0.py fig-tokens"      # T067
# then: T068 (runtime) and T069 (docs) together; T070 → T071 → T072
```

---

## Implementation Strategy

### MVP First (User Story 1 = Phase 0)

1. Phase 1: Setup (T001–T004)
2. Phase 2: Foundational (T005–T015) — **blocks everything**
3. Phase 3, slices 3A → 3B → 3C → 3D → 3E → 3F → 3G
4. **STOP and VALIDATE**: quickstart.md steps 1–9
5. Phase 4: Polish, governance, full verification

### Incremental Delivery

Each slice is a shippable increment with its own green tests:

1. 3A — direction is declared and enforced (reversed scales fail the build)
2. 3B — typed provenance and the dataset tooling under `make check`
3. 3C — the register with its first licence-verified survey
4. 3D — risk metrics and a coding-only headline
5. 3E — token split end to end
6. 3F — manifests, resume, hashes, rebuilt bundles (the FR-012 gate test)
7. 3G — versioned leaderboard and site

Phases 1–12 of the programme continue in their own specifications once Phase 0's gate is
green ("existing checks green; every per-recipe figure of the committed runs unchanged").

---

## Notes

- `[P]` tasks touch different files and have no dependency on an incomplete task
- Oversize-module splits (T013, T014, T021, T058, T061, T070) are part of the slice that
  first touches the file (Article X §10.18); never grow `metrics.py`, `analysis.py`,
  `report_text.py`, `sections_results.py`, or `run_evals.py` — nor the oversize test
  modules `tests/test_eval_report.py` and `tests/test_cli.py` (new tests go to
  `tests/test_eval_report_phase0.py`, `tests/test_metrics_aggregate.py`, and
  `tests/test_cli_eval_dataset.py`)
- The dataset migration (T037) changes the live dataset's hash by design; the FR-012 gate
  (T075, T080) is about committed bundles, which are rebuilt from their own traces
- Later-phase requirements intentionally absent here: FR-032 tiers (Phase 1), FR-044's
  import-time content check (Phase 3), the share-alike dataset file (first share-alike
  import) — see research R20
- Commit after each task or logical group with a `feat(evals)`/`test(evals)`/`chore(evals)`
  scope (AGENTS.md); the `usage` change in `ember/serving/runtime.py` is `feat(ember)`; the
  release-workflow change (T089) is `ci:`
- Verify tests fail before implementing; `make check` green at every checkpoint

## Phase 5: Convergence

- [X] T095 Render the generated dataset card in the report's Benchmark design section: `analysis_design.py` loads `evals/dataset/card.json` (or rebuilds it with `card.build`) and `sections_front.design()` adds a per-recipe `Table` (items, dev/test, per-label counts per split, kind shares, source shares, rater count, second-review queue, external sources with licence) in both HTML and Markdown, with a test in `tests/test_eval_report_phase0.py` per T061 / plan `sections_front.py` "generated card table" / FR-033 (partial)
- [X] T096 Record every protocol and rubric rule with the dataset version it first applies to: give each `report_text.PROTOCOL` entry (and the scale registry's rubric anchors) a `since` content hash, surface it in `card.json` and the report's Labelling protocol block, and make `evals/dataset/check.py` verify each `since` is the current or a prior recorded content hash per FR-046 (missing)
- [X] T097 Replace the "**One annotation team.**" limitation in `evals/report_text.py` with a "**Single rater.**" bullet that cites label stability as pending (Phase 1) and never implies an unmeasured inter-rater figure; test greps both renderings per plan `report_text.py` limitations wording / contract Limitations row / FR-065 (partial)
- [X] T098 Surface the policy text in force: copy `config.policy` into `report["meta"]["policy"]` in `evals/analysis.py` and state it in the Benchmark design section ("default criteria" when empty), with a test per FR-008 and the empty-policy-slot edge case (partial)
- [X] T099 In `evals/sections/sections_phase0.py::_tiers_blocks`, when `summary["tiers"]["non_easy"]["items"] == 0` render a sentence saying the non-easy subset is empty instead of a `Non-easy 0 / 0 / 0%` row, with a test per the spec's "non-easy subset is empty" edge case (partial)
- [X] T100 Compare enums by member, not value string: `row.verdict is not Verdict.used` in `evals/dataset/lint.py:220` and `i.split is Split.dev` / `Split.test` in `evals/dataset/card.py:61-62`; `make check` stays green per Constitution Article X (contradicts)

## Phase 6: Convergence

- [X] T101 Split `tests/test_dataset_tooling.py` (458 lines) under the 400-line ceiling by responsibility — e.g. keep the record tests (`Source`, `Item`, `Scale`, `RecipeSpec`) there and move the io/hashes tests to `tests/test_dataset_hashes.py` — keeping every test and `make check` green per plan: Constraints ("Article X §10.3 applies to `tests/` too") / Constitution X §10.3 (partial)
- [X] T102 Move the Phase 0 leaderboard-page tests (versions per table, incomplete rows, recipe-cell links, `_headline_model`, `benchmark.json` versions) out of `tests/test_site_benchmark.py` (447 lines) into `tests/test_site_leaderboard.py`, leaving the headline/hero tests in place, per plan: Constraints / Constitution X §10.3 (partial)
- [X] T103 Move the Phase 0 versions-and-assembly tests (`_versioned` helper and the six `specs/004` tests) out of `tests/test_leaderboard.py` (403 lines) into `tests/test_leaderboard_versions.py` per plan: Constraints / Constitution X §10.3 (partial)
