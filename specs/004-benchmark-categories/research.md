# Research: Benchmark Categories — Phase 0 (Foundations)

**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Date**: 2026-10-10

This document resolves every design unknown for Phase 0. Each decision names the
requirements it serves. Later phases get their own research when their specifications are
written; nothing here pre-decides them beyond what the programme spec already fixes.

## R1. One registry for recipes, in a new `evals/dataset/` package (FR-005, FR-007, FR-008, FR-011)

**Decision**: Create `evals/dataset/` with a `records/` sub-package of Pydantic models and
enums (one class per file, the `evals/context/records/` pattern) and two registries:
`evals/dataset/recipes.py` (`RECIPES: dict[str, RecipeSpec]`) and
`evals/dataset/scales.py` (`SCALES: dict[tuple[str, str], Scale]`). `report_text.RECIPES`
(title, when, state, decides) moves into `RecipeSpec` and is deleted from `report_text.py`;
`analysis.py`'s three consumers read the registry.

**Rationale**: The spec wants risk, compliance, policy, family, and headline membership on
every recipe. Putting those next to the existing prose fields in one `RecipeSpec` is the only
way to have one source of truth (Article XV §15.4). `report_text.py` is over the 400-line
ceiling, so it cannot grow and should shrink when touched (§10.18).

**Alternatives considered**: a second `RECIPE_FLAGS` dict beside `report_text.RECIPES`
(two registries, reject-worthy under §15.4); a YAML file (adds a loader and a dependency for
~40 entries that are code anyway).

## R2. Scale registry shape and key (FR-001, FR-003a)

**Decision**: `Scale(category, question, quantity, low, high, dangerous_end, dangerous_from)`
keyed by `(category, question)`. `dangerous_end` is a `DangerousEnd` StrEnum
(`low`, `high`, `none`); `dangerous_from` is the first level index counted as dangerous
(`None` when `dangerous_end` is `none`). Initial entries: `change_risk/risk`
(Negligible → High, dangerous end high, from 2 — the `needs_review` rule), `effort_approach/effort`
(Trivial → Large, none), `vision_score/alert_level` (No alert → High, high, from 2).

**Rationale**: Question ids will collide across recipes in later phases (`severity` in
`constitution_gate` and `finding_severity`; `irreversible` in two recipes), so the key must
include the recipe. `dangerous_from` is what the asymmetric metrics need to turn an ordinal
into an unsafe/safe partition without guessing (FR-004).

**Alternatives considered**: keying by question id alone (collides at phase 5); storing
poles only and deriving "dangerous" as the top half (wrong for `needs_review`, which flips at
Medium).

## R3. Protocol lines (FR-002, FR-004)

**Decision**: Append two bullets to `report_text.PROTOCOL`, verbatim from the spec: the
score-direction sentence and the yes/no cautious-pole sentence. They render in the report's
"Labelling protocol" list through the existing `text["protocol"]` path. The existing bullet
"Every change alters the dataset's SHA-256…" is reworded to "A change to any item's state,
media, questions, gold, or split alters the dataset's content hash, which each run records,
so runs on different label sets cannot be compared by accident; annotations (kind, tier,
source, rationale) do not" (R11).

## R4. The three direction checks (FR-003, SC-002, SC-003)

**Decision**:
- *Registry matches dataset* — a dataset lint rule (`scale-declared`) and a test in
  `tests/test_eval_benchmark.py`: every score question in the dataset has a `Scale`, and
  `criteria[0] == low`, `criteria[-1] == high`; every `Scale` names a question that exists.
- *Monotonic scorer* — a test in `tests/test_eval_benchmark.py` beside the existing scorer
  tests: for each level *k*, an answer with `score=k` and a one-hot distribution at *k* yields
  `predicted == k`; `expected` rises with *k*; `abs_error` between adjacent levels is exactly
  1.0. This is the test item `failure_059` describes failing.
- *Legend rendered* — a test in a new `tests/test_eval_report_phase0.py` (the existing
  `tests/test_eval_report.py` is already over the 400-line ceiling; its module-scoped
  `synthetic_run`, `report`, and `bundle` fixtures move to `tests/conftest.py` so both
  modules share them): every score question's legend (`0 Negligible → 3 High`) appears in
  both the HTML and the Markdown output next to its table.

## R5. Legend text flows through `analysis` into the report (FR-003c)

**Decision**: `analysis` adds a `legend` string to every score question in
`report["recipes"][*]["questions"][*]` and to `report["score_spread"]`, built from `SCALES`.
`sections_results.results()` renders a `Definitions` block titled "Scales" after the
"By question type" table, and the ordinal section repeats each question's legend beside its
table. No new `Block` type.

**Rationale**: Sections never import `report_text` directly; everything they show is baked
into the report model by `analysis.build()`. `Definitions` already renders in HTML and
Markdown, so the legend cannot show in one format and not the other.

**Alternatives considered**: a new `Legend` block (two renderers to change for one string).

## R6. Recipe specification fields (FR-005, FR-007, FR-008, FR-011, FR-035)

**Decision**: `RecipeSpec(category, title, when, state, decides, family: Family, phase: int,
risk: bool, compliance: tuple[ComplianceRef, ...], policy_slot: bool,
dangerous_options: dict[str, frozenset[str]], lint: LintMode)`. `headline` is a property:
`family not in (Family.vision, Family.integration)`. `Family` and `LintMode`
(`report`, `enforce`) are StrEnums; `ComplianceRef(framework: ComplianceFramework, ref: str,
title: str)` with `ComplianceFramework` covering OWASP LLM Top 10, MITRE ATLAS, NIST AI RMF,
EU AI Act, ISO/IEC 42001, and Enkrypt. Phase 0 registers the nine existing recipes with
`risk=False`, empty compliance, `lint=report` (grandfathered), and the vision four with
`family=vision`.

**Rationale**: Every field the spec names, nothing speculative; `LintMode` is what lets the
lint gate new recipes while reporting the existing ones' gaps (FR-035). The `policy_slot`
flag and the run-config `policy` map exist now so phase 3 does not change the schema.

## R7. Asymmetric metrics (FR-005, FR-006, SC-010)

**Decision**: New module `evals/risk_metrics.py`. Given a recipe's records and its unsafe
partition — `noul`: gold `True`; `choice`: `RecipeSpec.dangerous_options[qid]`; `score`:
levels at or beyond `Scale.dangerous_from` toward the dangerous end — it computes:

- `dangerous_recall` = unsafe items predicted unsafe ÷ unsafe items (argmax, every answer);
- `dangerous_recall_at_threshold` = the same restricted to answers that clear the kit's
  acting threshold for their type (`choice` confidence ≥ 0.85; `noul` P ≥ 0.80 or ≤ 0.20;
  `score` has no threshold and reports the first figure);
- `missed_dangers` = unsafe items given a *confident* safe verdict (the count the spec
  wants shown);
- `safe_precision` and its at-threshold variant, symmetrically.

`aggregate()` adds `summary["risk"][category]` for risk recipes only, with `bar` (0.95, or
0.98 when the recipe's unsafe partition includes `harm_kind != none` or `weakens_control`)
and `met`. Rows and reports show dangerous recall at the threshold, the missed count, and
"not met" when below the bar.

**Rationale**: The failure the spec cares about is a confident safe verdict on an unsafe item —
that is what an agent acts on. The at-threshold recall measures exactly that; the plain recall
is kept so a model that is never confident cannot look safe by abstaining. The thresholds are
the kit's published ones already in `metrics.py`.

**Alternatives considered**: recall over all answers only (hides confident misses behind
hedged hits); a single pooled "unsafe" class across recipes (loses the per-recipe bars).

## R8. Token split: the server returns it in `usage`; the harness requires it (FR-009, SC-005)

**Decision**: `Engine.advise` already computes `RequestSize` for the limit check; it adds
`state_tokens`, `fixed_tokens`, and `media_tokens` to the response's `usage` object. The
harness records them per item as `tokens: {total, state, fixed, media}` and refuses to run
against a server whose responses lack them (actionable error naming the server version and
the minimum). The report gains a chart of accuracy and Brier against state tokens.

**Rationale**: `run_evals.py` is an HTTP client with no engine in-process; the only exact
count lives in the server, which has already paid for it. Adding fields to `usage` is
additive and SystemOne-compatible (clients ignore unknown fields), but it is a response-field
change under Article II, so it lands as a reviewed API change with README and tests
(`contracts/http-api.md`). Requiring the split keeps SC-005 honest ("100% of trace rows").

**Alternatives considered**: loading the model client-side to count (duplicates the probe's
architecture and cannot run against a remote server); a `POST /v1/count` endpoint (a second
request per item and a second route to maintain); recording `null` when absent (SC-005 would
be unmeasurable).

## R9. Structured `source` with seven kinds and a legacy shim (FR-010, FR-028, FR-046)

**Decision**: `source` becomes an object validated by `Source` (Pydantic): `kind:
SourceKind` plus the kind's references — `authored`: `dataset_version` (the whole-dataset
hash that introduced the item); `mined`: `artefact`, `commit`; `imported`: `register_row`,
`record_id`; `perturbed`: `parent_id`, `perturbation`; `templated`: `family`,
`template_version`; `drafted`: `draft_id`, `adjudicated: true`; `captured`: `session_id`,
`redaction_sha256`. Existing items migrate in Phase 0: `"curated"` →
`{"kind": "authored", "dataset_version": <hash before migration>}`; `"skill_md"` → the same
with `note: "reproduces a worked example in ember/agent_kit/ember-advise/SKILL.md"`. Reading an
old snapshot's `dataset.jsonl`, the parser maps a bare string through the same table so
re-rendering committed runs keeps working.

**Rationale**: The spec's regeneration references differ per kind; one model with a
per-kind validator is the smallest shape (§15.3). `authored` is added because the spec's own
recipes are "hand-authored" and that is neither mined nor drafted; the spec was amended
(FR-028) in this planning pass.

## R10. Vision rows leave the headline; committed runs are rebuilt (FR-011, FR-012, SC-001, SC-004)

**Decision**: `aggregate()` computes `overall` over headline recipes only and adds
`summary["capability"]` (items, questions, accuracy, per-category figures) for the rest;
the predicate comes from `RECIPES`. `ember eval snapshot --rebuild <run-id>` regenerates a
bundle's `results.json` summary and `model.json` from its own `trace.jsonl` and
`dataset.jsonl`; the two committed bundles are rebuilt and the gate is checked by comparing
`summary.categories` and `summary.questions` before and after (identical) while `overall`
changes and the report's summary states the composition. The leaderboard row's `accuracy`
is the headline figure; a capability panel renders on the leaderboard page and in the
report.

**Rationale**: Snapshots carry everything needed to recompute; re-deriving from the bundle
is the only way to move vision out of the headline for runs that exist, and it proves
per-recipe figures did not move.

## R11. Content hashes; leaderboard versions and assembly (FR-034, FR-066, SC-022, SC-023)

**Decision**: `evals/dataset/hashes.py` hashes the *scoring projection* of an item — `id`,
`category`, `split`, `state`, `images`, `videos`, `media_kwargs`, `questions`,
`gold_labels` — and nothing else. `dataset_content_sha256(items)` is the SHA-256 of the
projections of every item as canonical JSON (sorted keys, sorted by id, one per line);
`recipe_sha256(items)` is the same over one recipe's items. The raw file's SHA-256 stays
recorded as `dataset_sha256` (today's field) for byte-level provenance but is not the
version key. A run's `config` gains `dataset_content_sha256`, `recipe_sha256: {category:
hex}`, `register_sha256`, and `settings` (`dtype`, `max_length`, `max_request_length` from
the engine). `leaderboard.build()` returns `{"versions": [{"dataset_content_sha256",
"rows": [...]}, ...]}`, newest version first, each row carrying `recipes: {category:
{accuracy, item_accuracy, items, recipe_sha256, run_id}}`. Within a (model, deployment,
settings) group a row is assembled per recipe from the latest run whose per-recipe hash
equals the current version's; `headline` is present only when every headline recipe
matches; otherwise `incomplete: true`. The site renders the newest version's table first and
older versions below it. A pre-Phase-0 run that was not rebuilt has no content hash and
forms its own version keyed by its file hash.

**Rationale**: Exactly the clarified rule (Q1, Q5) — with one correction found in planning:
hashing whole records would make every annotation change (Phase 1 re-tags all 475 items by
kind; tiers; a rationale edit; the Phase 0 `source` migration itself) a new version that
orphans every run before it. Hashing only what the model is scored on keeps a version
stable under annotation and changes it exactly when state, media, questions, gold, or split
change — the cases where comparing runs would be wrong. The `PROTOCOL` sentence "Every
change alters the dataset's SHA-256…" is reworded to say which changes alter the version
(R3's task). A pleasant consequence: the committed bundles, rebuilt from their own traces,
share the current content hash and sit on the current version with full headlines.

**Alternatives considered**: file-bytes hash as the version (orphans runs on every
re-tag); hashing everything except an explicit deny-list (fragile as fields are added —
an allow-list projection fails closed).

## R12. Resumable runs (FR-066, SC-023)

**Decision**: `run_evals` writes `results/<run-id>_run.json` (model, deployment label,
settings, dataset and register hashes, split, category) before the first request and appends
trace rows through `evals/context/rows_file.py`'s torn-line-safe writer. `ember eval run
--resume <run-id>` reloads the manifest, refuses if the live server's model, device, or
settings or the dataset hash differ, skips ids already in the trace, and continues under the
same run id; `results.json` is written at the end as today.

**Rationale**: Reuses the probe's append-only rows file (§15.4); the manifest is what makes
"refuse if settings changed" decidable.

## R13. Dataset tooling package and CLI (FR-026–FR-031, FR-035–FR-037)

**Decision**: `evals/dataset/` top-level modules: `io.py` (read/write the JSONL
deterministically, legacy source shim), `hashes.py`, `splitting.py` (stratified assignment of
new items only, against `splits.lock`; named to avoid colliding with the `Split` enum's
`records/split.py`), `dedup.py` (exact on a normalised state; near at ≥ 0.85 token-set
Jaccard, kept only when gold differs), `leakage.py` (families, imports, pinning), `card.py`
(generate `card.json` and `CARD.md`), `lint.py` (rules and modes), `register.py` (load and
validate `register.json`), `check.py` (the provenance check: `source` resolves, register
rows, hashes). Every `dataset` sub-command that reads the dataset takes `--dataset PATH`
(default `evals/clef-flash.jsonl`), as `ember eval run` does, so a scratch copy can be
linted or hashed. CLI: `ember eval dataset {lint,card,hash,check}` through the existing
`register_eval()` pattern; make targets `dataset-lint`, `dataset-card`. The unit suite runs
lint (report mode), card freshness, and check, so `make check` is the gate.

**Rationale**: Mirrors how `evals/context/` is organised and wired; one package level with
a `records/` sub-package keeps nesting at two levels (§10.3).

## R14. Split pinning via a committed lock (FR-027, FR-030, SC-012)

**Decision**: `evals/dataset/splits.lock` is a committed JSON map `{item_id: split}`.
`splitting.py` assigns new items and appends to the lock; `leakage.py` fails if any item's
split differs from the lock, and the lock is regenerated only by appending. The assignment
rule is deterministic and has no randomness: unassigned items are visited in id order; each
is placed in the split that most reduces the maximum deviation from the 40/60 target across
that item's own labels (one stratum per `(category, question, label)`), ties going to `test`
(the reporting split); a perturbed item follows its parent, a templated item follows the
first member of its family, and an imported item follows any earlier item from the same
external record. Tests cover: an existing id cannot change split; new items restore the
ratio; the same input always yields the same assignment; a family straddling splits fails.

**Alternatives considered**: comparing against the previous git commit (shells out in tests);
pinning by hashing the id into a split (cannot stratify per label).

## R15. Data-source register (FR-039–FR-045, SC-014, SC-015)

**Decision**: `evals/dataset/register.json`, validated by `RegisterRow` (Pydantic) with
`Verdict` (`candidate`, `conditional`, `excluded`, `unconfirmed`, `used`) and
`LicenceClass` (`permissive`, `share_alike`, `custom_permissive`, `non_commercial`,
`research_only`, `gated`, `composite`, `unconfirmed`) StrEnums. Fields exactly as FR-040,
including `mirror: {location, sha256} | null`. Build-time validation: every `used` row has a
mirror and hash; every row has a licence reading and date; every imported item resolves to a
`used` row. `scripts/audit_data_sources.py` (network; not a test) re-checks URLs, licence
readings, and mirror hashes before a dataset publication and writes `register-audit.json`.
The first survey enters every row of the spec's Candidate External Sources table plus the
Decision Index and TypeSafe datasets, with the licence readings and dates from the spec.

**Rationale**: The `provenance.json` + `check_provenance.py` pattern already in the repo;
JSON because the register is data the lint reads, not prose.

## R16. Dataset card is generated and committed (FR-033, SC-016)

**Decision**: `card.py` writes `evals/dataset/card.json` and renders `evals/dataset/CARD.md`
from it; a test regenerates both into memory and fails if they differ from the committed
files. The report's design section renders the same card data per recipe. Phase 0 fields
that have no data yet (`label_stability`, `inter_source_agreement`, `acted_differs_share`)
are present and `null`; `rater_count` is 1; `second_review_pending` counts tagged items.

## R17. Lint rules and modes (FR-035)

**Decision**: Rules: `size-target`, `label-in-both-splits`, `kind-shares` (with documented
exemptions read from `RecipeSpec.exemptions`), `template-share`, `scale-declared`,
`dangerous-set-declared` (risk recipes), `source-resolves`, `family-split`, `split-pinned`,
`near-duplicate-gold`. A rule failure on a recipe in `LintMode.enforce` fails the build;
on a `report` recipe it is listed in the card's gaps. Untagged items (`kind` absent) count as
a gap, never pass.

## R18. Typing and tooling scope (Article VIII, X)

**Decision**: Add `evals/dataset` and `evals/risk_metrics.py` to `[tool.mypy].files`; keep
ruff `D` scoped to `ember/` but write NumPy docstrings in the new modules anyway (Article X
binds `evals/`). Register and card JSON are written atomically with `evals.export.write_atomic`.

## R19. Paying down §10.18 debt on every oversize module this phase touches (Article X)

**Decision**: Each touched module over 400 lines is split below it and removed from §10.18
with a PATCH Sync Impact Report: `evals/metrics.py` → pure formulas move to
`evals/metric_functions.py`; `evals/analysis.py` → `_recipes`/`_composition`/card assembly to
`evals/analysis_design.py` and `_findings` to `evals/analysis_findings.py`;
`evals/report_text.py` → `REFERENCES` to `evals/report_references.py`;
`evals/sections/sections_results.py` → `ordinal`/`confusion` to `evals/sections/sections_scores.py`;
`evals/eval/run_evals.py` → HTTP helpers to `evals/eval/client.py` and the manifest/resume
logic to `evals/eval/resume.py`. Importers follow the moves (no re-exports).

**Rationale**: §10.18 says debt is paid down when the file is next touched and must never
grow; every one of these files must change for Phase 0.

## R20. What this phase leaves for later phases

- `kind` is optional on items until Phase 1 re-tags the 475 items; the card shows them as
  untagged. Re-tagging does not change the dataset version (R11).
- `second_review`, `acted`, `acted_differs`, and `second_pass` exist in the `Item` model and
  are `null`/absent until the phases that fill them.
- FR-032's tier *tool* ships in Phase 0 (R23); it is *run* in Phase 1, after the controlled
  MPS/CUDA comparison gives the version its first full runs, and the non-easy accuracy row
  renders as soon as any row carries a tier.
- No recipe is `risk=True` yet; the metrics ship with synthetic-record tests and render only
  for flagged recipes. Likewise the `consistency` and `by_source_kind` summaries (R21) are
  computed but empty until variants and imports exist.
- The single dataset file remains `evals/clef-flash.jsonl`; a share-alike file and a
  multi-file content hash (the projection makes it a concatenation of sorted items, so the
  rule is already defined) are introduced by the first phase that imports such a source.
- FR-044's credential guard (R24) runs over every item from Phase 0; the import-time
  description check (an imported record contradicting its source's description) lands with
  the first `used` register row (Phase 3).
- Policy slots are declared but no text is substituted into instructions until Phase 3.

## R21. Consistency and per-source-kind summaries (FR-036, FR-037, SC-017)

**Decision**: `aggregate()` adds two more blocks beside `risk` and `tokens`, both computed
from the dataset metadata the trace rows carry:

- `consistency[category] = {groups, agreement}` — a *variant group* is an original item plus
  every `perturbed` item whose `parent_id` points at it and whose `source.perturbation` is
  `paraphrase` or `format` (the convention for the `variant` item kind); `agreement` is the
  share of groups whose every member received the same predicted label on every question.
  `None` for a recipe with no groups.
- `by_source_kind[category][kind] = {items, accuracy, item_accuracy}` — present only when a
  recipe holds more than one source kind, so the imported-versus-authored split is visible
  the moment the first import lands.

The report renders a "Consistency" row (groups, agreement) and a "By source" table per
recipe when the blocks are non-empty.

**Rationale**: Both are `aggregate`-level additions of the same shape as `risk` and
`tokens`; adding them now costs two small functions and avoids reopening `metrics.py` when
Phase 3 imports its first records and Phase 7 produces its first variants. Reusing
`parent_id` + `source.perturbation` for the variant link adds no field (§15.3).

**Alternatives considered**: a dedicated `variant_of` field (a second link for the same
relationship); deferring both to Phases 3/7 (reopens a module this phase is paying debt down
on).

## R22. The changelog names the dataset hash each release benchmarks against (FR-034)

**Decision**: The release workflow (`.github/workflows/release-ember.yml`) adds one step
after the version bump: it runs `python3 -m evals.dataset.hashes --json`, prepends
`Benchmark dataset: <dataset_sha256>` to the new version's section in `CHANGELOG.md` before
the bump commit is pushed, and includes the same line in the GitHub Release notes. The
workflow stays SHA-pinned and `uvx zizmor@1.30.1 .github/` is run before pushing it;
pushing the change needs a token with the `workflow` scope (AGENTS.md watch-out).

**Rationale**: commitizen generates `CHANGELOG.md` from commits and knows nothing about the
dataset; the hash is a fact of the release, so the release flow is the only place that can
record it without a human remembering to.

**Alternatives considered**: a hand-written line in the bump PR (forgettable); recording the
hash only in the dataset card (not a per-release record).

## R23. Difficulty tiers are computed by a tool from the leaderboard, never by hand (FR-032)

**Decision**: Trace rows carry the item annotations `aggregate` needs — `kind`, `tier`,
`source_kind`, `parent_id`, `perturbation` — copied from the dataset at scoring time (and
joined by id from the bundle's dataset on `--rebuild`). `evals/dataset/tiers.py` computes
tiers: given every leaderboard row on the current dataset version, an item is `easy` when
every row's producing run for that item's recipe scored it fully correct; `ember eval
dataset tier --from benchmark/ [--dataset PATH]` writes `tier: "easy"` into those items (and
clears the tag from items no longer qualifying), reports how many changed, and — because
`tier` is outside the hash projection — leaves the dataset version unchanged.
`aggregate` adds `tiers = {easy_items, easy_questions, non_easy: {items, questions,
accuracy, accuracy_ci}}` when any row carries a tier (`None` otherwise); the report shows
"All items" and "Non-easy" accuracy side by side; the card shows the easy count per recipe.

**Rationale**: FR-032 needs runs on the version; Phase 1 produces them. Shipping the tool
now means Phase 1 only runs it, and the report never shows a growing-easy-items headline
without its non-easy companion.

**Alternatives considered**: tagging from the two existing bundles alone (one model; the
rule would be trivially satisfied by one run — wait for the version's first controlled
pair); computing tiers at report time without writing them (loses the reviewable record).

## R24. A credential guard over every item (FR-044)

**Decision**: Lint rule `no-live-secret`, always enforced regardless of `LintMode`: every
item's `state` (string, or every string leaf of a dict state) is scanned for live-credential
formats — AWS access key ids (`AKIA`/`ASIA` + 16 uppercase alphanumerics), GitHub tokens
(`gh[pousr]_` + 36 chars), Slack tokens (`xox[abprs]-`), Google API keys (`AIza` + 35
chars), PEM private-key blocks (`-----BEGIN … PRIVATE KEY-----`), and signed web tokens
(three base64url segments starting `eyJ`). A match fails the build unless the exact value
appears in `evals/dataset/example_secrets.json`, the recorded list of vendor-documented
example values with their source URLs (seeded with AWS's `AKIAIOSFODNN7EXAMPLE` /
`wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`). The list is part of the register's provenance
(each entry carries `url` and `read_on`) and is validated like a register row.

**Rationale**: The spec's rule is "nothing real enters, whatever the source"; a format guard
with an allow-list is the only check that is both automatic and honest about what it can
know. Personal data stays a review-and-verdict matter: a regex cannot tell a synthetic
e-mail from a real one, and the `secret_exposure` recipe needs synthetic PII items.

**Alternatives considered**: running the future `secret_exposure` model recipe as a gate
(the model never labels, and the recipe does not exist yet); scanning only imported items
(an authored item can carry a pasted token just as easily).

No NEEDS CLARIFICATION remains.
