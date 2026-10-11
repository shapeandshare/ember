# Implementation Plan: Benchmark Categories — Phase 0 (Foundations)

**Branch**: `004-benchmark-categories` | **Date**: 2026-10-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-benchmark-categories/spec.md` — the
programme specification. Per its Delivery Series, this plan implements **Phase 0
(Foundations)**: the infrastructure every later phase depends on. Phases 1–12 are delivered
by their own specifications, each citing the programme spec as parent.

## Summary

Phase 0 makes the benchmark's numbers carry their direction, their risk, and their
provenance, and builds the dataset tooling the forty-recipe programme needs:

- **Direction is declared and enforced.** A scale registry names each score question's
  poles and dangerous end; two protocol sentences fix score direction and the cautious
  pole of yes/no questions; three checks (registry matches dataset, monotonic scorer,
  legend rendered) fail the build on a reversed scale or a number shown without its
  meaning.
- **Recipes carry risk, compliance, policy, and family.** One `RecipeSpec` registry
  replaces the prose-only `report_text.RECIPES`; risk recipes get dangerous recall, safe
  precision, and a missed-danger count against the kit's acting thresholds.
- **Every row is accounted for.** The server returns the state/fixed/media token split in
  `usage`; the harness records it per item and plots accuracy and Brier against state
  length. Every item's `source` is a typed object with a regeneration reference.
- **The headline is coding only.** Vision recipes move to a capability panel; the two
  committed bundles are rebuilt from their own traces, proving per-recipe figures did not
  move.
- **Dataset tooling.** A new `evals/dataset/` package: seven source kinds, a stratified
  split with a committed pin lock, exact and near de-duplication, a generated dataset card,
  a lint with report/enforce modes, a data-source register with its first licence-verified
  survey, and a provenance check — all under `make check`.
- **Versions and resume.** Runs record a content-based dataset hash (what the model is
  scored on — not annotations, so re-tagging never orphans a run), per-recipe and register
  hashes, and a start manifest; `--resume` continues an interrupted run; the leaderboard
  groups rows by dataset version and assembles per-recipe columns across runs. A tier tool
  tags `easy` items from the version's rows, and a credential guard scans every item.

## Technical Context

**Language/Version**: Python 3.12 (uv)

**Primary Dependencies**: existing only — Pydantic v2 (records), httpx (harness client),
FastAPI (unchanged route), prometheus-client (unchanged). No new dependency.

**Storage**: Files — `evals/clef-flash.jsonl` (dataset, structured `source`),
`evals/dataset/splits.lock`, `evals/dataset/register.json`, `evals/dataset/card.json` +
`CARD.md`, `results/<run>_run.json` manifests, tracked `benchmark/<run>/` bundles.
External snapshot mirrors live outside the repository (storage chosen when the first
import happens; none in Phase 0).

**Testing**: pytest and pytest-cov. New unit files: `test_dataset_tooling.py`,
`test_data_source_register.py`, `test_risk_metrics.py`, `test_metrics_aggregate.py`,
`test_eval_report_phase0.py`, `test_cli_eval_dataset.py`, `test_run_evals.py`,
`test_benchmark_bundles.py`, `test_site_benchmark.py`; extended: `test_eval_benchmark.py`,
`test_leaderboard.py`, `test_snapshot_evals.py`, `test_runtime_unit.py`,
`test_http_api.py`, `test_mcp_tool.py`, `test_context_probe.py`. The report fixtures
(`synthetic_run`, `report`, `bundle`) move from `test_eval_report.py` to `tests/conftest.py`
so the new report tests do not grow a module already over 400 lines (`test_eval_report.py`
is 568; `test_cli.py` is 829 — Article X §10.3 applies to `tests/` too). The audit script
is network-bound and never a test.

**Target Platform**: macOS on Apple Silicon for the model-backed checks; the tooling,
lint, register, and leaderboard are platform-independent and run in CI.

**Project Type**: Python package (server, MCP, CLI) plus a checkout-only eval harness.

**Performance Goals**: The spec sets no budget. The lint, card, hashes, and provenance
check over the 475-item dataset run in the unit suite and must stay well under the
suite's existing wall clock (target: < 2 s combined). Near-duplicate detection is
O(n²) on token sets at 475 items; the plan accepts that and revisits (MinHash) only when
the dataset passes ~5,000 items (a later phase).

**Constraints**:
- `evals/report_text.py`, `metrics.py`, `analysis.py`, `sections_results.py`,
  `eval/run_evals.py` are over 400 lines and must not grow; each is split when touched
  (R19). The oversize test modules `tests/test_eval_report.py` and `tests/test_cli.py` are
  not grown either: new tests go to new modules.
- The `usage` change is an Article II response-field change: README, COMPATIBILITY, and
  tests land with it; MCP passes it through untouched.
- No test touches the network, port 8765, or the opencode CLI (Article IV).
- Phase 0 changes the dataset *file* hash (source migration) but neither the dataset
  *content* hash — the version, which excludes annotations — nor any per-recipe figure of
  a committed run (FR-012).
- Editing `.github/workflows/release-ember.yml` (R22) needs a token with the `workflow`
  scope and a clean `uvx zizmor@1.30.1 .github/` run.

**Scale/Scope**: 475 items / 9 recipes today; the tooling is sized for 10,000–14,000
items / ~40 recipes by programme end. ~20 new modules, ~12 modified, 5 debt splits.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Gate Results (pre-design)

| Article | Gate | Result |
|---------|------|--------|
| I Local-first by default | No new network path in ember; the harness still calls the configured endpoint; the audit script is an explicit, operator-run tool | ✅ PASS |
| II Typed decisions, not text | No new question types. `usage` gains three integer fields — an additive response-field change, treated as an API change with README + tests (R8) | ✅ PASS (API change recorded) |
| III Agent-legible contract | Kit text untouched in Phase 0 (no new recipes); `instructions.md` unchanged | ✅ PASS |
| IV Non-interfering lifecycle | Tests use random ports and fixtures; no CLI of a harness is invoked; the resume manifest never kills anything | ✅ PASS |
| V Model loading | Untouched | ✅ PASS |
| VI Apple Silicon and CUDA | Token split is device-independent; `settings` records dtype for the leaderboard grouping | ✅ PASS |
| VII Verification over assertion | Quickstart exercises HTTP, CLI, resume, snapshot rebuild, and the site build for real | ✅ PASS |
| VIII Tooling | ruff, mypy strict (scope extended to `evals/dataset`, `evals/risk_metrics.py`), bandit, compile, tests | ✅ PASS (R18) |
| IX Vault | A decision note for R1/R8/R9/R11/R19 lands with the implementation; `make vault-audit` | ✅ PASS |
| X Python conventions | Pydantic records one per file; enums for every fixed set; relative imports inside `evals/`; every touched oversize module split below 400 and removed from §10.18 | ✅ PASS (R19) |
| XI TDD and coverage | Red-green per task; floor 81% unchanged or raised | ✅ PASS |
| XII Async-first | No new route; `Engine.advise` stays sync behind the lock; `usage` assembled where `RequestSize` already is | ✅ PASS |
| XIII Layers | The split is computed in the engine layer and travels as plain dict fields; MCP untouched; `evals/` imports `ember.cfg` only (as today) | ✅ PASS |
| XIV Pit of success | A server without the split → one actionable error; a stale card → one message; `--resume` mismatch → the mismatch named | ✅ PASS |
| XV Simplicity | Reuses `RequestSize`, `rows_file`, `write_atomic`, `Definitions` blocks, the `provenance.json` pattern; one registry, not two; no new dependency | ✅ PASS (see Complexity Tracking) |

## Project Structure

### Documentation (this feature)

```text
specs/004-benchmark-categories/
├── spec.md                  # programme specification (phases 0–12)
├── plan.md                  # this file — Phase 0
├── research.md              # R1–R20
├── data-model.md            # records, registries, hashes, lock, manifest, leaderboard model
├── quickstart.md            # validation run book
├── contracts/
│   ├── dataset.md           # item schema, invariants, lint rules, CLI, files
│   ├── http-api.md          # usage token split (Article II API change)
│   ├── run-artifacts.md     # manifest, trace, resume, snapshot --rebuild, gate check
│   ├── report-and-leaderboard.md  # summary keys, sections, leaderboard versions, site
│   ├── register.md          # register.json, validation, first survey, audit script
│   └── cli.md               # ember eval additions, make, docs
├── checklists/requirements.md
└── tasks.md                 # Phase 2 (/speckit.tasks)
```

### Source Code (repository root)

```text
ember/
  serving/runtime.py              # MOD  usage gains state_tokens / fixed_tokens / media_tokens from RequestSize
  commands/eval.py                # MOD  cmd_eval_dataset_{lint,card,hash,check}; run --resume; snapshot --rebuild
  commands/parser.py              # MOD  `ember eval dataset` sub-parser; new flags
  cli.py                          # MOD  wire the handlers
evals/
  metric_functions.py             # NEW  macro_f1, reliability, calibration_error, brier_*, rps, bootstrap_ci (moved from metrics.py)
  metrics.py                      # MOD  scoring + aggregate: headline-only overall, capability, risk, tokens, consistency, by_source_kind; < 400 lines
  risk_metrics.py                 # NEW  unsafe partitions; dangerous recall / safe precision (plain and at threshold); missed dangers; bar
  analysis.py                     # MOD  reads RECIPES/SCALES; legends; capability; tokens; < 400 lines
  analysis_design.py              # NEW  _recipes, _composition (per-kind sources), dataset-card assembly (moved)
  analysis_findings.py            # NEW  _findings (moved)
  report_text.py                  # MOD  RECIPES removed; two PROTOCOL bullets; limitations wording; < 400 lines
  report_references.py            # NEW  REFERENCES (moved)
  leaderboard.py                  # MOD  versions, settings_key, per-recipe assembly, incomplete rows
  sections/sections_results.py    # MOD  Scales block, capability panel, dangerous-recall table, fig-tokens; < 400 lines
  sections/sections_scores.py     # NEW  ordinal (with legends) and confusion (moved)
  sections/sections_front.py      # MOD  recipe cards show family/risk/compliance; generated card table
  charts/charts_tokens.py         # NEW  accuracy and Brier vs state tokens
  eval/run_evals.py               # MOD  manifest, tokens per row, hashes in config, --resume, token-split requirement; < 400 lines
  eval/client.py                  # NEW  _resolve_server, _deployment_label, _model_name, _health, _advise (moved)
  eval/resume.py                  # NEW  RunManifest write/read/compare; skip-done
  eval/snapshot_evals.py          # MOD  --rebuild
  dataset/                        # NEW  package (contracts/dataset.md)
    __init__.py
    records/                      #      one class per file: dangerous_end, family, lint_mode, compliance_framework,
                                  #      source_kind, item_kind, split, verdict, licence_class, lint_rule,
                                  #      scale, compliance_ref, recipe_spec, source, item, register_row, lint_finding
    recipes.py  scales.py  io.py  hashes.py  splitting.py  dedup.py  leakage.py  lint.py  card.py  register.py  tiers.py  check.py
    splits.lock  register.json  example_secrets.json  card.json  CARD.md
  clef-flash.jsonl                # MOD  source → objects (migration), nothing else
scripts/
  build_site_benchmark.py         # MOD  versions, capability, headline scope, incomplete rows
  audit_data_sources.py           # NEW  network audit of register rows (not a test)
site/index.md                     # MOD  headline scope + capability link
shared/testing.mk                 # MOD  dataset-lint, dataset-card, audit-sources
pyproject.toml                    # MOD  mypy files += evals/dataset, evals/risk_metrics.py
.github/workflows/release-ember.yml   # MOD  changelog + release-notes line "Benchmark dataset: <hash>" (R22)
benchmark/<two bundles>/          # MOD  results.json summary + model.json rebuilt (--rebuild)
tests/
  conftest.py                     # MOD  synthetic_run / report / bundle fixtures moved here from test_eval_report.py
  test_dataset_tooling.py         # NEW
  test_data_source_register.py    # NEW
  test_risk_metrics.py            # NEW
  test_metrics_aggregate.py       # NEW
  test_eval_report_phase0.py      # NEW
  test_cli_eval_dataset.py        # NEW
  test_run_evals.py               # NEW
  test_benchmark_bundles.py       # NEW
  test_site_benchmark.py          # NEW
  test_eval_benchmark.py, test_eval_report.py (fixtures out), test_leaderboard.py, test_snapshot_evals.py,
  test_runtime_unit.py, test_http_api.py, test_mcp_tool.py, test_context_probe.py                 # MOD
README.md, COMPATIBILITY.md, AGENTS.md                                                           # MOD
.specify/memory/constitution.md   # MOD  PATCH: §10.18 entries removed for the split modules
vault/decisions/2026-10-10-benchmark-foundations-token-split-and-registries.md                  # NEW
```

**Structure Decision**:
- **`evals/dataset/`** is a new peer of `evals/context/` and `evals/eval/`, with a
  `records/` sub-package for its Pydantic models and enums, exactly the pattern
  `evals/context/records/` set. Registries (`recipes.py`, `scales.py`) live there because
  they describe the dataset; `metrics.py`, `analysis*.py`, and `leaderboard.py` import
  them.
- **Risk metrics** are a sibling module of `metrics.py`, not inside it (debt ceiling) and
  not inside `dataset/` (they are scoring, not schema).
- **The `usage` change** is the one `ember/` runtime touch; it is a few lines in
  `Engine.advise` where `RequestSize` is already in hand.

## Phase 0: Outline & Research

[research.md](./research.md) resolves every unknown:

| Decision | Topic |
|----------|-------|
| R1 | One recipe registry in `evals/dataset/`; `report_text.RECIPES` retired |
| R2 | `Scale` shape, `(category, question)` key, `dangerous_from` |
| R3 | Two protocol sentences |
| R4 | The three direction checks |
| R5 | Legends flow through `analysis` into `Definitions` blocks |
| R6 | `RecipeSpec` fields; `LintMode` for grandfathering |
| R7 | Asymmetric metrics: plain and at-threshold recall, missed dangers, bars |
| R8 | Token split returned in `usage`; harness requires it |
| R9 | Structured `source`, seven kinds, legacy shim, migration |
| R10 | Vision out of the headline; `snapshot --rebuild`; gate check |
| R11 | Content hashes (scoring projection); leaderboard versions and per-recipe assembly |
| R12 | Resumable runs via a start manifest |
| R13 | Dataset tooling package and CLI |
| R14 | Split pinning via `splits.lock` |
| R15 | Register file, validation, audit script, first survey |
| R16 | Generated, committed dataset card |
| R17 | Lint rules and modes |
| R18 | mypy scope |
| R19 | §10.18 debt paydown on touched modules |
| R20 | What waits for later phases (tier tagging runs in Phase 1; import-time description check in Phase 3) |
| R21 | Consistency and per-source-kind summaries (FR-036, FR-037) |
| R22 | The changelog names the dataset hash each release benchmarks against (FR-034) |
| R23 | Difficulty tiers computed by a tool from the leaderboard (FR-032) |
| R24 | Credential guard over every item (FR-044) |

No NEEDS CLARIFICATION remains.

## Phase 1: Design & Contracts

- **[data-model.md](./data-model.md)**: enums, `Scale`, `RecipeSpec`, `Source`, `Item`,
  hashes, the split lock, manifest and trace additions, summary additions, the leaderboard
  model, `RegisterRow`, the card, and state transitions.
- **[contracts/](./contracts/)**: dataset schema and tooling; HTTP `usage`; run artifacts
  and resume; report, leaderboard, and site; register and audit; CLI and make.
- **[quickstart.md](./quickstart.md)**: ten validation steps from `make check` to the
  rebuilt bundles, an interrupted-and-resumed run, and the versioned leaderboard.

### Delivery order

1. **Records and registries** — `evals/dataset/records/*`, `recipes.py`, `scales.py`;
   `report_text.RECIPES` retired; `analysis` consumers moved to `analysis_design.py`;
   `report_references.py` split. Tests: registry matches dataset; every recipe registered.
2. **Direction** — protocol bullets; monotonic scorer test; legends in `analysis` and the
   Results/ordinal sections (`sections_scores.py` split); legend test on the bundle.
3. **Structured `source` and the dataset package core** — `Source`, `Item`, `io.py`
   (shim), `hashes.py` (scoring projection; content, per-recipe, file, register hashes);
   migrate the 475 sources; `splits.lock` generated from the current splits;
   `splitting.py`, `leakage.py`, `dedup.py`, `lint.py` (report mode; `no-live-secret` always
   enforced; `example_secrets.json`), `card.py`, `tiers.py`, `check.py`; `ember eval dataset …`;
   make targets; unit tests.
4. **Register** — `RegisterRow`, `register.py`, `register.json` with the first survey;
   validation tests; `scripts/audit_data_sources.py`.
5. **Metrics** — `metric_functions.py` split; `risk_metrics.py`; `aggregate` adds
   headline-only `overall`, `capability`, `risk`, `tokens`, `consistency`,
   `by_source_kind`, and `tiers`; `analysis.build` copies `dataset_content_sha256`,
   `recipe_sha256`, `register_sha256`, `settings`, and `tokens_available` into `meta`;
   tests with synthetic records.
6. **Token split** — `Engine.advise` → `usage`; HTTP/MCP/runtime tests; README and
   COMPATIBILITY; harness requirement and per-row `tokens`; `charts_tokens.py`; report
   figure and test.
7. **Run artifacts** — `client.py` and `resume.py` splits; manifest; content, per-recipe,
   and register hashes and `settings` in `config`; per-row `tokens` and item annotations;
   `--resume`; `snapshot --rebuild`; rebuild both committed bundles (they land on the current
   version); the gate check from quickstart step 6 as a test over the bundles.
8. **Leaderboard and site** — versions, assembly, incomplete rows; `build_site_benchmark.py`
   and `site/index.md`; `test_leaderboard.py`, `test_site_benchmark.py`.
9. **Docs and governance** — README, AGENTS.md, COMPATIBILITY; the release-workflow
   changelog step (R22); constitution PATCH for §10.18 (recording `analysis.py`'s unrecorded
   growth to 826 lines); vault decision note and session log; `make pr-ready`, `make test`,
   `make vault-audit`.

### Modules to change

| Module | Change |
|--------|--------|
| `ember/serving/runtime.py` | `advise()` copies `size.state/fixed/media` into `usage` (R8) |
| `ember/commands/{eval,parser}.py`, `ember/cli.py` | `ember eval dataset {lint,card,hash,check}`; `run --resume`; `snapshot --rebuild` |
| `evals/dataset/**` (new) | contracts/dataset.md; data-model.md |
| `evals/metric_functions.py` (new), `evals/metrics.py` | formulas moved; `aggregate` additions (`capability`, `risk`, `tokens`, `consistency`, `by_source_kind`, `tiers`); importers follow (`context/scoring.py`, `context/reproduce.py`, tests) |
| `evals/risk_metrics.py` (new) | R7 |
| `evals/analysis.py`, `analysis_design.py` (new), `analysis_findings.py` (new) | registry-driven recipes/composition; legends; capability; tokens; consistency; by-source; tiers; card data; `meta` gains `dataset_content_sha256`, `recipe_sha256`, `register_sha256`, `settings`, `tokens_available` |
| `evals/report_text.py`, `report_references.py` (new) | RECIPES removed; PROTOCOL bullets; limitations wording; references moved |
| `evals/sections/sections_results.py`, `sections_scores.py` (new), `sections_front.py` | Scales block; capability panel; dangerous-recall table; fig-tokens; recipe cards; card table |
| `evals/charts/charts_tokens.py` (new) | binned accuracy/Brier vs state tokens |
| `evals/leaderboard.py` | versions; settings key; assembly; incomplete |
| `evals/eval/run_evals.py`, `client.py` (new), `resume.py` (new) | manifest; tokens; hashes; resume; split requirement |
| `evals/eval/snapshot_evals.py` | `--rebuild` |
| `scripts/build_site_benchmark.py`, `site/index.md` | versions; capability; headline scope |
| `scripts/audit_data_sources.py` (new) | contracts/register.md |
| `shared/testing.mk`, `pyproject.toml` | targets; mypy scope |
| `.github/workflows/release-ember.yml` | one step: `Benchmark dataset: <hash>` into the new `CHANGELOG.md` section and the release notes (R22) |
| `evals/clef-flash.jsonl`, `benchmark/*/` | source migration; rebuilt summaries |
| `README.md`, `COMPATIBILITY.md`, `AGENTS.md`, constitution, vault | contracts/cli.md |

### Tests to add or change

| Test file | Coverage |
|-----------|----------|
| `tests/test_dataset_tooling.py` (new) | `Source` per-kind validation and the legacy shim; `Item` validation; the scoring projection and hashes (annotation edits leave the content and per-recipe hashes unchanged; a gold/state edit changes them; per-recipe isolation); `splitting.assign_new` restores 40/60, is deterministic, and appends to the lock; pinning violation fails; family/import leakage fails; exact and near-dedup (gold-differs exception); every lint rule passes and fails on constructed datasets incl. `no-live-secret` with the example allow-list; report vs enforce modes; `tiers.easy_ids`/`apply` on synthetic leaderboard rows and the unchanged-hash assertion; card regeneration byte-identical; `check` end to end on the real dataset |
| `tests/test_data_source_register.py` (new) | schema; `used` requirements; class→verdict constraints; item references; the committed register validates and contains no `used` row; row count matches the spec's table; `example_secrets.json` validates |
| `tests/test_risk_metrics.py` (new) | partitions for `noul`/`choice`/`score`; recall, at-threshold recall, missed dangers, safe precision on hand-built records; bar 0.95 vs 0.98 selection; `met`; empty and all-safe edge cases |
| `tests/test_metrics_aggregate.py` (new) | `aggregate`: headline-only `overall`; `capability`; `risk` empty without risk recipes; `tokens` and its `None` case; `consistency` over variant groups; `by_source_kind` only for mixed recipes; `tiers` and its `None` case |
| `tests/test_eval_benchmark.py` | registry matches dataset (both directions); monotonic scorer; every item's `source` is an object; existing invariants kept; metric tests follow the `metric_functions` move; the audit script answers `--help` |
| `tests/test_eval_report_phase0.py` (new; fixtures via `tests/conftest.py`) | legends in HTML and Markdown; Scales block; capability panel; headline note; dangerous-recall table for a synthetic risk recipe (fixture injects a `RecipeSpec`); Consistency and By-source rows; `fig-tokens` valid SVG or the unavailable sentence; limitations wording |
| `tests/test_leaderboard.py` | versions ordering; grouping with settings; per-recipe assembly; incomplete rows; pre-Phase-0 isolation; row `run_id` is the newest contributing run |
| `tests/test_site_benchmark.py` (new) | `headline()` scope/capability; per-version tables; incomplete cell; recipe and Model links |
| `tests/test_snapshot_evals.py` | `--rebuild` reproduces categories/questions, reads the bundle dataset through the shim with the bundle's file hash, joins item annotations into the rows, adds `dataset_content_sha256` and `recipe_sha256` to `config` and `meta`, sets `tokens_available: false`; scrub unchanged |
| `tests/test_benchmark_bundles.py` (new) | the permanent FR-012 gate over every committed bundle, including `meta.dataset_content_sha256` equal to the current dataset's content hash |
| `tests/test_run_evals.py` (new) | token-split requirement; per-row `tokens` and annotations; manifest before the first request; `--resume` skip, refusal, and acceptance after an annotation-only edit |
| `tests/test_cli_eval_dataset.py` (new) | dispatch of `ember eval dataset {lint,card,hash,check,tier}` with `--dataset`, `run --resume`, `snapshot --rebuild` |
| `tests/test_runtime_unit.py`, `test_http_api.py`, `test_mcp_tool.py` | `usage` split (unit with a fake `RequestSize`; `@model` end to end) |
| `tests/test_context_probe.py` | imports follow the `metric_functions` move |

## Constitution Check — Post-Design Re-Evaluation

| Article | Result | Notes |
|---------|--------|-------|
| I | ✅ PASS | Nothing in ember reaches the network; the audit is a separate operator script |
| II | ✅ PASS | The `usage` fields are additive integers; the answer schema is unchanged; documented as an API change |
| III | ✅ PASS | Kit untouched |
| IV | ✅ PASS | — |
| V | ✅ PASS | — |
| VI | ✅ PASS | — |
| VII | ✅ PASS | Quickstart steps 6–9 run the real paths |
| VIII | ✅ PASS | mypy scope widened, not narrowed |
| IX | ✅ PASS | Decision note in delivery step 9 |
| X | ✅ PASS | Five oversize modules split and removed from §10.18; new records one per file; enums for kinds, families, verdicts, classes, rules, modes |
| XI | ✅ PASS | Every new module has a test file; model-backed tests exist for the split |
| XII | ✅ PASS | — |
| XIII | ✅ PASS | Engine → HTTP → harness as plain dict fields; no torch in `evals/dataset` |
| XIV | ✅ PASS | Actionable refusals for missing split, stale card, resume mismatch, lint failures |
| XV | ✅ PASS | Deviations recorded below |

## Complexity Tracking

| Deviation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| `evals/dataset/` has 12 peer modules plus a `records/` sub-package of 22 one-class files (§10.3 asks to evaluate decomposition at 6) | One class per file for the records; each top-level module is one responsibility the contracts name (splitting, dedup, leakage, lint, card, register, tiers, check, io, hashes, registries) | Merging modules pushes `lint.py`/`card.py` toward 400 lines; a third nesting level adds ceremony without clarity |
| Resumability and per-recipe leaderboard assembly ship in Phase 0 although the 475-item dataset does not yet need them | Phase 1's device comparison and every later phase change the dataset hash; without versions and assembly the leaderboard would empty after each phase, and runs grow past an hour from Phase 2 | Deferring to Phase 1 would re-open `run_evals.py` and `leaderboard.py` immediately after Phase 0 splits them |
| The harness refuses to run against a server that lacks the token split (no override flag) | SC-005 requires 100% of trace rows to carry the split; a `null` path would make the criterion unmeasurable | An `--allow-missing-token-split` knob is speculative configuration (§15.3) for a server the maintainer controls |
| Both committed bundles are rewritten (`results.json` summary, `model.json`) | FR-011/FR-012 need vision out of the headline for runs that already exist, and the gate must prove per-recipe figures did not move | Leaving old bundles as they are would show two different headline definitions on one leaderboard |
