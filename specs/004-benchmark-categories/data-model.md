# Data Model: Benchmark Categories — Phase 0 (Foundations)

**Spec**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Pydantic models and enums live in `evals/dataset/records/`, one class per file, frozen.
Registries are plain module-level mappings in `evals/dataset/recipes.py` and
`evals/dataset/scales.py`.

## Enums (`evals/dataset/records/`)

| Enum | File | Values |
| --- | --- | --- |
| `DangerousEnd` | `dangerous_end.py` | `low`, `high`, `none` |
| `Family` | `family.py` | `coding`, `vision`, `mined_vault`, `risk_trio`, `harm_security`, `spec_kit`, `grounding`, `long_tier`, `boundary`, `memory_loop`, `low_priority`, `integration` |
| `LintMode` | `lint_mode.py` | `report`, `enforce` |
| `ComplianceFramework` | `compliance_framework.py` | `owasp_llm_top10`, `mitre_atlas`, `nist_ai_rmf`, `eu_ai_act`, `iso_42001`, `enkrypt` |
| `SourceKind` | `source_kind.py` | `authored`, `mined`, `captured`, `perturbed`, `templated`, `drafted`, `imported` |
| `ItemKind` | `item_kind.py` | `positive`, `negative`, `control`, `hard_negative`, `near_miss`, `adversarial`, `insufficient_context`, `variant`, `long_tier` |
| `Split` | `split.py` | `dev`, `test` |
| `Verdict` | `verdict.py` | `candidate`, `conditional`, `excluded`, `unconfirmed`, `used` |
| `LicenceClass` | `licence_class.py` | `permissive`, `share_alike`, `custom_permissive`, `non_commercial`, `research_only`, `gated`, `composite`, `unconfirmed` |
| `LintRule` | `lint_rule.py` | `size-target`, `label-in-both-splits`, `kind-shares`, `template-share`, `scale-declared`, `dangerous-set-declared`, `source-resolves`, `family-split`, `split-pinned`, `near-duplicate-gold`, `no-live-secret` (always enforced) |

## Scale (`records/scale.py`) and `SCALES` (`scales.py`)

| Field | Type | Rule |
| --- | --- | --- |
| `category` | str | a key of `RECIPES` |
| `question` | str | a `score` question of that recipe |
| `quantity` | str | what the scale measures ("risk of shipping unreviewed") |
| `low` | str | must equal `criteria[0]` in the dataset |
| `high` | str | must equal `criteria[-1]` |
| `dangerous_end` | `DangerousEnd` | — |
| `dangerous_from` | int \| None | first dangerous level index; required iff `dangerous_end != none`; within `range(len(criteria))` |

`legend(levels: int)` → `"0 {low} → {levels - 1} {high}"` (the level count comes from the
dataset's `criteria`, not the `Scale`). `SCALES` is keyed by `(category, question)`.
Initial rows: `("change_risk","risk")` high from 2; `("effort_approach","effort")` none;
`("vision_score","alert_level")` high from 2.

## ComplianceRef (`records/compliance_ref.py`)

`framework: ComplianceFramework`, `ref: str` (e.g. `LLM06`), `title: str`. Never invented:
the registry holds only references the spec names.

## RecipeSpec (`records/recipe_spec.py`) and `RECIPES` (`recipes.py`)

| Field | Type | Phase 0 value for existing recipes |
| --- | --- | --- |
| `category` | str | the dataset `category` |
| `title`, `when`, `state`, `decides` | str | moved from `report_text.RECIPES`; vision four get short titles |
| `family` | `Family` | `coding` for the five, `vision` for the four |
| `phase` | int | 0 |
| `risk` | bool | False |
| `compliance` | tuple[ComplianceRef, ...] | () |
| `policy_slot` | bool | False |
| `dangerous_options` | dict[str, frozenset[str]] | {} (required for every `choice` question of a `risk` recipe) |
| `lint` | `LintMode` | `report` (grandfathered) |
| `exemptions` | dict[ItemKind, str] | {} — documented reasons a kind cannot be filled |
| `headline` (property) | bool | `family not in {vision, integration}` |

Validation: a `risk` recipe must declare `dangerous_options` for each `choice` question and a
`Scale` with a dangerous end for each `score` question (`dangerous-set-declared`).

## Source (`records/source.py`)

`kind: SourceKind` plus kind-specific required fields; a validator rejects missing or
foreign fields.

| Kind | Required references |
| --- | --- |
| `authored` | `dataset_version` (whole-dataset SHA-256 that introduced the item); optional `note` |
| `mined` | `artefact` (repo path), `commit` (SHA) |
| `captured` | `session_id`, `redaction_sha256` |
| `perturbed` | `parent_id`, `perturbation` — `perturbation ∈ {paraphrase, format}` marks a *variant* of the parent (the `variant` item kind and the consistency measure); other values are ordinary perturbations |
| `templated` | `family`, `template_version` |
| `drafted` | `draft_id`, `adjudicated` (must be `True`) |
| `imported` | `register_row` (register `id`), `record_id` |

Legacy shim (`io.py`): a bare string `"curated"` reads as `authored`; `"skill_md"` as
`authored` with the SKILL.md note. Used only when reading snapshots' `dataset.jsonl`.

## Item (`records/item.py`)

| Field | Type | Notes |
| --- | --- | --- |
| `id` | str | unique |
| `category` | str | key of `RECIPES` |
| `split` | `Split` | pinned by `splits.lock` |
| `state` | str \| dict | as today |
| `images`, `videos`, `media_kwargs` | optional | as today |
| `questions` | dict[str, dict] | the recipe's fixed set (validated identical across the recipe) |
| `gold_labels` | dict[str, bool \| str \| int] | one per question |
| `rationale` | str | non-empty |
| `source` | `Source` | — |
| `kind` | `ItemKind` \| None | None = untagged (Phase 1 fills) |
| `parent_id` | str \| None | perturbed items |
| `template_family` | str \| None | templated items |
| `external_label` | dict \| None | imported items (FR-043) |
| `acted` | dict \| None | captured items (FR-024) |
| `acted_differs` | bool | default False |
| `second_review` | bool | default False (queue flag) |
| `second_pass` | dict \| None | the blinded re-label (Phase 1) |
| `tier` | `"easy"` \| None | written only by `ember eval dataset tier` (R23); outside the hash projection |

## Scoring projection and hashes (`hashes.py`)

The *scoring projection* of an item is the dict of exactly: `id`, `category`, `split`,
`state`, `images`, `videos`, `media_kwargs` (absent keys omitted), `questions`,
`gold_labels`. Annotations — `source`, `rationale`, `kind`, `tier`, `parent_id`,
`template_family`, `external_label`, `acted`, `acted_differs`, `second_review`,
`second_pass` — are never hashed.

- `projection(item) -> dict`.
- `dataset_content_sha256(items)`: SHA-256 of `"\n".join(json.dumps(projection(i),
  sort_keys=True, ensure_ascii=False) for i in sorted(items, key=id))` — the **dataset
  version**.
- `recipe_sha256(items)`: the same over one recipe's items.
- `dataset_sha256(path)`: SHA-256 of the file bytes (today's field; provenance only).
- `register_sha256(path)`: SHA-256 of `register.json` bytes.

## Example secrets (`example_secrets.json`, R24)

`{"schema_version": 1, "entries": [{"value": "AKIAIOSFODNN7EXAMPLE", "vendor": "AWS",
"url": "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html",
"read_on": "2026-10-10"}, ...]}` — validated by `ExampleSecret` (`records/example_secret.py`):
non-empty `value`, `vendor`, `url`, `read_on: date`; values unique. The `no-live-secret`
rule allow-lists exactly these values.

## Split lock (`splits.lock`, JSON `{id: split}`)

Append-only. `splitting.py` assigns new ids and appends; `leakage.py` fails on any id whose
split differs from the lock, on a perturbation family or template family across splits, and
on items imported from one external record across splits.

Assignment rule (deterministic, no randomness): unassigned items are visited in id order;
each goes to the split that most reduces the maximum deviation from the 40/60 target across
the item's own labels (one stratum per `(category, question, label)`), ties to `test`; a
perturbed item follows its parent, a templated item the first member of its family, an
imported item any earlier item from the same external record.

## Run manifest and trace additions (`evals/eval/resume.py`, `run_evals.py`)

`results/<run-id>_run.json` (written before the first request):
`run_id, model, deployment_label, settings{dtype, max_length, max_request_length},
dataset_sha256 (file), dataset_content_sha256 (version), recipe_sha256{}, register_sha256,
split, category, started_at`.

Trace row additions: `tokens: {total, state, fixed, media}` (ints; parts sum to total) and
the item annotations copied from the dataset at scoring time — `kind`, `tier`,
`source_kind`, `parent_id`, `perturbation` (`null` when absent). `--rebuild` joins them by
id from the bundle's `dataset.jsonl`.

`results.json` `config` additions: `dataset_content_sha256`, `recipe_sha256`,
`register_sha256`, `settings`, `policy: {}` (category → text; empty in Phase 0),
`resumed: bool`.

`model.json` `meta` additions (copied from `config` by `analysis.build`; `null` when a
pre-Phase-0 bundle lacks them): `dataset_content_sha256`, `recipe_sha256`,
`register_sha256`, `settings`, `tokens_available: bool`. `meta.dataset` keeps `sha256`
(file), `current_sha256`, `matches`, and gains `content_sha256`. The leaderboard reads
these from `meta`, never from `results.json`.

## Summary additions (`metrics.aggregate`)

- `overall` is computed over headline recipes only.
- `capability: {items, questions, accuracy, accuracy_ci, categories: {...}}` for
  non-headline recipes (empty when none scored).
- `risk: {category: {dangerous_recall, dangerous_recall_at_threshold, safe_precision,
  safe_precision_at_threshold, missed_dangers, unsafe_n, bar, met}}` for `risk` recipes
  only.
- `tokens: {state_bins: [{low, high, n, accuracy, brier}], median_state, max_state}`;
  `None` when no row carries `tokens` (pre-Phase-0 bundles).
- `consistency: {category: {groups, agreement}}` — variant groups per R21; `None` per
  recipe without groups.
- `by_source_kind: {category: {kind: {items, accuracy, item_accuracy}}}` — only for recipes
  holding more than one source kind.
- `tiers: {easy_items, easy_questions, non_easy: {items, questions, accuracy,
  accuracy_ci}}` — when any row carries `tier`; `None` otherwise (R23).

## Leaderboard model (`leaderboard.build`)

```text
{"versions": [
  {"dataset_content_sha256": "...", "newest": true,
   "rows": [{"model_key", "deployment_key", "settings_key",
             "run_id" (the newest contributing run; target of the Model cell link),
             "headline": {"accuracy", "accuracy_ci", "item_accuracy", "items", "questions"} | null,
             "incomplete": bool,
             "recipes": {"category": {"accuracy", "item_accuracy", "items",
                                      "recipe_sha256", "run_id", "run_at"}},
             "capability": {...} | null,
             "risk": {"category": {"dangerous_recall_at_threshold", "missed_dangers", "met"}},
             "tiers": {"non_easy_accuracy"} | null,
             "single_rater": true,
             "latency_p50", "latency_p95", "ember_server_version", "ember_client_version",
             "run_at"}]}
]}
```

Grouping key: `(model_key, deployment_key, settings_key)`. Assembly: per recipe, the latest
run in the group whose `recipe_sha256[category]` equals the version's; `headline` present
only when every headline recipe is assembled from runs on this version's hashes. A run
with no `dataset_content_sha256` (pre-Phase-0, not rebuilt) forms its own version keyed by
its file `dataset_sha256`.

## Difficulty tiers (`tiers.py`, R23)

`easy_ids(versions, current) -> set[str]`: over every row of the current version, an item
is easy when, for each row, the run producing that item's recipe column scored the item
fully correct (`correct == True` in its trace). `apply(items, easy_ids) -> list[Item]` sets
`tier="easy"` on those and clears it elsewhere. `main(argv)` (`--from benchmark/`,
`--dataset PATH`) rewrites the dataset, prints counts, and asserts the content hash is
unchanged.

## RegisterRow (`records/register_row.py`) and `register.json`

| Field | Type | Rule |
| --- | --- | --- |
| `id` | str | slug, unique |
| `name` | str | — |
| `urls` | list[{url, read_on}] | ≥ 1 |
| `licence` | {`reading`: str, `spdx`: str \| None, `read_at`: str (URL), `read_on`: date, `class`: `LicenceClass`} | required |
| `verdict` | `Verdict` | — |
| `reason` | str | required |
| `snapshot` | {`version`: str, `sha256`: str, `retrieved_on`: date} \| None | required when `used` |
| `mirror` | {`location`: str, `sha256`: str, `public`: bool} \| None | required when `used`; `sha256 == snapshot.sha256`; the licence and attribution notice a public mirror must carry is the row's `attribution` (there is no separate mirror-level field) |
| `transformation` | str \| None | required when `used` |
| `feeds` | list[str] | recipe categories |
| `items_imported` | int | 0 unless `used` |
| `attribution` | str \| None | required when the licence class requires it |
| `upstream_available` | bool | set by the audit |
| `notes` | str \| None | — |

`register-audit.json` (written by `scripts/audit_data_sources.py`, not a test):
`audited_on`, per row `{url_ok, licence_reading_unchanged, mirror_ok}`.

## Dataset card (`card.json`, `CARD.md`)

Per recipe: `items`, `per_label_per_split`, `kind_shares` (+ `untagged`), `source_shares`,
`easy_items`, `external_sources` (register ids with licence reading and attribution),
`label_stability` (null), `inter_source_agreement` (null), `rater_count` (1),
`second_review_pending`, `acted_differs_share` (null), `recipe_sha256`, `gaps` (lint
findings in `report` mode), `exemptions`. Top level: `dataset_content_sha256`,
`dataset_sha256` (file), `register_sha256`, `generated_from`.

## State transitions

### Item lifecycle (Phase 0 view)

```text
authored/mined/… → validated (Source, questions identical per recipe, gold valid, no live secret)
                 → split assigned once (splits.lock) → in dataset version V (content hash)
                 → scored in runs on V (recipe hash) → [Phase 1+: tagged by kind, tiered by tool, second pass]
```

An item never changes split. Annotations (kind, tier, source, rationale, review fields)
change without changing V; a change to state, media, questions, gold, or split creates a
new version. A source re-verdicted `excluded` removes its items in the next version
(recorded in the card's change log).

### Register row

```text
unconfirmed → candidate | conditional | excluded   (survey; licence read + dated)
candidate/conditional → used   (snapshot + mirror + transformation recorded; items imported)
used → excluded   (licence re-read fails; items retired next version)
any → upstream_available=false   (audit; items and mirror stay)
```

### Run

```text
started (manifest written) → scoring (trace appended) → complete (results.json)
interrupted → resumed (same run id; manifest matches live server and dataset) | refused
```
