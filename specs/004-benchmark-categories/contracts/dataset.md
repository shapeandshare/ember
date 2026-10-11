# Contract: Dataset schema and tooling

**Scope**: `evals/clef-flash.jsonl`, `evals/dataset/`, `ember eval dataset`, make targets.

## Item line (JSONL)

Every line validates as `Item` ([data-model.md](../data-model.md)). Changes from today:

| Field | Before | After |
| --- | --- | --- |
| `source` | `"curated"` \| `"skill_md"` | object: `{"kind": ..., ...refs}` (seven kinds) |
| `kind` | — | optional `ItemKind` until Phase 1 |
| `parent_id`, `template_family`, `external_label`, `acted`, `acted_differs`, `second_review`, `second_pass`, `tier` | — | optional, absent in Phase 0 unless noted |

Unchanged: `id`, `category`, `split`, `state`, `questions`, `gold_labels`, `rationale`,
`images`, `videos`, `media_kwargs`. Each recipe's `questions` must be byte-identical across
its items (existing test).

## Invariants checked on every build (unit suite)

| Check | Where |
| --- | --- |
| Every `score` question has a `Scale`; `criteria[0] == low`, `criteria[-1] == high`; every `Scale` names an existing question | `tests/test_eval_benchmark.py`, lint `scale-declared` |
| Every item's `source` validates for its kind and resolves (mined commit is 40 hex; imported row exists and is `used`; perturbed parent exists; captured redaction hash is 64 hex) | `tests/test_dataset_tooling.py`, lint `source-resolves` |
| No exact duplicate normalised `state` (whitespace-collapsed, lower-cased JSON canonical form); near-duplicates (token-set Jaccard ≥ 0.85) only with differing gold | lint `near-duplicate-gold` |
| Perturbation parent and children, template family members, items from one external record: same split | lint `family-split` |
| Every id in `splits.lock` keeps its split; every dataset id is in the lock | lint `split-pinned` |
| No item's `state` (string, or any string leaf of a dict) matches a live-credential format — AWS access key id, GitHub token, Slack token, Google API key, PEM private-key block, signed web token — unless the exact value is in `example_secrets.json`; enforced for every recipe regardless of `LintMode` | lint `no-live-secret` |
| Every recipe in `RECIPES` with items; every item's category in `RECIPES` | `tests/test_dataset_tooling.py` |
| `card.json` and `CARD.md` regenerate byte-identically | `tests/test_dataset_tooling.py` |
| `register.json` validates; every `used` row has snapshot, mirror (hash equal), transformation; every imported item resolves to a `used` row; `example_secrets.json` validates (unique values, vendor, URL, date) | `tests/test_data_source_register.py` |
| The dataset content hash is unchanged by annotation edits (kind, tier, source, rationale) and changed by a state, gold, question, or split edit | `tests/test_dataset_tooling.py` |

`LintMode.enforce` recipes fail the build on any rule; `report` recipes list findings in
the card's `gaps`; `no-live-secret` fails the build for every recipe.

## Lint rules

| Rule | Passes when |
| --- | --- |
| `size-target` | items ≥ 300 (≥ 400 if `risk`) |
| `label-in-both-splits` | every label of every question appears in `dev` and `test`; `test` has ≥ 40 per label |
| `kind-shares` | negative ≥ 20%, control ≥ 10%, hard_negative ≥ 15%, near_miss ≥ 10% of score items, adversarial ≥ 5%, insufficient_context ≥ 5%, variant ≥ 10%, long_tier ≥ 10% for log/diff recipes — or an exemption is recorded; untagged items are a finding |
| `template-share` | templated items ≤ 30% |
| `scale-declared` | as above |
| `dangerous-set-declared` | `risk` recipes declare an unsafe partition for every question |
| `source-resolves`, `family-split`, `split-pinned`, `near-duplicate-gold` | as above |
| `no-live-secret` | as above; always enforced |

## CLI

```text
ember eval dataset lint  [--dataset PATH] [--enforce-all] [--json]   # exit 1 on any enforced failure (no-live-secret always counts)
ember eval dataset card  [--dataset PATH] [--check]                  # regenerate card.json + CARD.md; --check: exit 1 if stale
ember eval dataset hash  [--dataset PATH] [--json]                   # content (version), file, per-recipe, register hashes
ember eval dataset check [--dataset PATH]                            # provenance check: sources, register, hashes, lock, example secrets
ember eval dataset tier  --from benchmark/ [--dataset PATH]          # tag `easy` items from the current version's leaderboard rows (R23)
```

`--dataset` defaults to `evals/clef-flash.jsonl` (as `ember eval run --dataset` does) so a
scratch copy can be linted or hashed without touching the committed file. `tier` rewrites
the dataset's annotations only and asserts the content hash is unchanged. Make:
`make dataset-lint`, `make dataset-card`. `make check` covers them through the unit suite.

## Files

```text
evals/dataset/
  __init__.py            # bare
  records/               # one class per file (see data-model.md)
  recipes.py             # RECIPES
  scales.py              # SCALES
  io.py                  # read_items(), write_items(), legacy source shim
  hashes.py              # projection(), dataset_content_sha256, recipe_sha256, dataset_sha256 (file), register_sha256
  splitting.py           # assign_new(), lock read/append (not `split.py`: records/split.py holds the Split enum)
  dedup.py               # exact + near-duplicate detection
  leakage.py             # family/import/pinning checks
  lint.py                # rules, modes, findings (incl. no-live-secret)
  card.py                # card.json, CARD.md
  register.py            # load/validate register.json and example_secrets.json
  tiers.py               # easy_ids(), apply(), main() (R23)
  check.py               # provenance check entry point
  splits.lock            # committed {id: split}
  register.json          # committed data-source register
  example_secrets.json   # committed vendor-documented example credential values with URLs
  card.json, CARD.md     # committed, generated
```
