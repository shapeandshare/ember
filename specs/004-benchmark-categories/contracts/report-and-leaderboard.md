# Contract: Report, leaderboard, and site

**Scope**: `evals/metrics.py`, `evals/risk_metrics.py`, `evals/analysis*.py`,
`evals/sections/*`, `evals/charts/charts_tokens.py`, `evals/leaderboard.py`,
`scripts/build_site_benchmark.py`, `site/index.md`, `site/_data/benchmark.json`.

## Summary (`results.json["summary"]`, `model.json["summary"]`)

| Key | Change |
| --- | --- |
| `overall` | computed over headline recipes only (`RecipeSpec.headline`) |
| `capability` | new: `{items, questions, accuracy, accuracy_ci, categories{}}` for non-headline recipes; `null` when none were scored |
| `risk` | new: per `risk` recipe `{dangerous_recall, dangerous_recall_at_threshold, safe_precision, safe_precision_at_threshold, missed_dangers, unsafe_n, bar, met}`; `{}` when none |
| `tokens` | new: `{median_state, max_state, state_bins[{low, high, n, accuracy, brier}]}`; `None` when no row carries `tokens` (a pre-Phase-0 bundle), and the report then states the split is unavailable |
| `consistency` | new: per recipe `{groups, agreement}` over variant groups (R21); `None` for a recipe without groups |
| `by_source_kind` | new: per recipe, per source kind `{items, accuracy, item_accuracy}`; present only when a recipe holds more than one source kind |
| `tiers` | new: `{easy_items, easy_questions, non_easy: {items, questions, accuracy, accuracy_ci}}` when any row carries `tier`; `None` otherwise (R23) |
| `categories`, `questions`, `choice`, `noul`, `score`, `misses` | unchanged |

## Report sections

| Section | Change |
| --- | --- |
| Summary (KPIs) | headline note: "over coding recipes; vision in the capability panel" |
| Benchmark design | recipe cards show `family`, `risk`, compliance refs when present; the generated dataset card table per recipe; "Labelling protocol" gains the two direction bullets |
| Results | after "By question type": a `Definitions` block **Scales** — one line per score question: `` `risk` — 0 Negligible → 3 High (dangerous end: high) ``; a **Capability panel** table (vision recipes) after "By recipe"; for `risk` recipes a **Dangerous recall** table (recall at threshold, missed dangers, bar, met / **not met**); a **Consistency** row per recipe with variant groups (groups, agreement); a **By source** table per recipe with more than one source kind; an **All items / Non-easy** accuracy pair when `summary.tiers` is present |
| Ordinal | each score table is preceded by its legend line |
| Calibration | unchanged |
| New figure | `fig-tokens`: accuracy and Brier against state tokens (binned); caption states the median and maximum state length; omitted, with a sentence saying the split is unavailable, for a pre-Phase-0 bundle |
| Limitations | "One annotation team" bullet becomes "Single rater" and cites label stability as pending (Phase 1) |

Markdown and HTML carry the same text; tests grep both.

## Leaderboard (`evals/leaderboard.build`)

Returns `{"versions": [...]}` (see [data-model.md](../data-model.md)). Rules:
- grouping key `(model_key, deployment_key, settings_key)`; latest run per recipe whose
  `recipe_sha256` matches the version's;
- `headline` only when every headline recipe is assembled on this version; else
  `incomplete: true` and `headline: null`;
- `recipes[category].run_id` names the run behind each column; the row's `run_id` is the
  newest contributing run and is the target of the Model cell link;
- a run without `dataset_content_sha256` (pre-Phase-0 snapshot that was not rebuilt)
  belongs to its own version keyed by its file `dataset_sha256` with per-recipe hashes
  `null`; it is never merged with another run;
- versions are keyed by `dataset_content_sha256` (the scoring projection), so annotation
  changes — kind tags, tiers, source migration, rationale edits — never create a version.

## Site

- `site/_data/benchmark.json`: `{"leaderboard": {"versions": [...]}, "runs": {...},
  "headline": headline(newest row with a headline)}`; `headline()` adds `scope: "coding"`
  and `capability: {...}`.
- `/results/`: one table per version, newest first, titled by dataset hash prefix and
  item count; columns Model · Deployment · Device · Headline · Items correct · per-recipe
  columns · Capability · Dangerous recall (risk recipes) · Latency p50 · version · Run at;
  an `incomplete` row shows "—" for the headline with a tooltip naming missing recipes;
  every recipe cell links to the run that produced it and the Model cell to the row's
  `run_id`.
- `site/index.md` "Measured, not promised": states the headline scope and links the
  capability panel.

## Tests

| File | Covers |
| --- | --- |
| `tests/test_eval_benchmark.py` | registry matches dataset; monotonic scorer; source objects validate |
| `tests/test_metrics_aggregate.py` (new) | `aggregate` additions: headline-only `overall`, `capability`, `risk` empty without risk recipes, `tokens` (and `None` without rows), `consistency`, `by_source_kind`, `tiers` (and `None` without tiered rows) |
| `tests/test_risk_metrics.py` (new) | partitions per type; recall/precision/at-threshold/missed with hand-built records; bar and `met`; recipes without `risk` get no block |
| `tests/test_eval_report_phase0.py` (new; shares `synthetic_run`/`report`/`bundle` through `tests/conftest.py`) | legend in HTML and Markdown; Scales block; capability panel present and vision absent from the headline note; dangerous-recall table for a synthetic risk recipe; Consistency and By-source rows; `fig-tokens` exists and is valid SVG, or the unavailable sentence appears |
| `tests/test_leaderboard.py` | versions; assembly across runs; `incomplete`; pre-Phase-0 runs isolated; sorting; the row `run_id` is the newest contributing run |
| `tests/test_site_benchmark.py` (new) | `headline()` scope and capability; per-version tables; incomplete row rendering (string assertions on the generated page body) |
