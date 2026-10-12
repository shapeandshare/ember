# Contract: Card and Report Hygiene Edition (Phase 1)

Files: `evals/dataset/card.py` (+ regenerated `card.json`/`CARD.md`), the report renderers
(unchanged sections; confirmed to render for the current version), and the comparison view
(`evals/eval/report_compare.py`, unchanged).

---

## The card

`card.json` keys are unchanged (`generated_from`, `dataset_content_sha256`, `register_sha256`,
`items`, `protocol`, `recipes`). Per recipe, the reserved hygiene keys gain values:

| Key | Before | After |
|-----|--------|-------|
| `label_stability` | `null` | The recipe's `StabilityResult` (agreement, by-label, unstable count) or `null` when no round covers it, with the round's `cooling_off`/`method` reflected. |
| `inter_source_agreement` | `null` | Stays `null`, with a stated reason (`no imports yet`). |
| `rater_count` | `1` | `1`, and the card renders the single-rater sentence. |
| `kind_shares` | real counts, all `untagged` | Real counts with kinds assigned; exemptions rendered from `RecipeSpec.exemptions`. |
| `easy_items` | count | Real count once `ember eval dataset tier` has run on the committed bundles. |
| `rubric_since` | present | Unchanged; anchors carry the same `since`. |
| `source_shares` | real | Unchanged (all `authored`). |
| `external_sources` | empty | Unchanged (register rows with `items_imported > 0`; none yet). |

**Single-rater sentence** (card-level, mirrored in the report):

> Gold is labelled by a single maintainer. Label stability above is one person's blinded re-label
> after a cooling-off period, not inter-rater agreement; the model never labels.

**Freshness**: `card.is_fresh()` is byte-exact over `card.json` and `CARD.md`;
`ember eval dataset card` regenerates and records the version; `--check` fails while stale. Both
files are committed in the same change as the values they carry.

## The report

- The stability block prints each recipe's agreement, the unstable count, the cooling-off window,
  and the single-rater sentence.
- The tier block (`metrics_phase0.tiers()`) prints easy vs non-easy accuracy per recipe for the
  current version.
- The comparison view (`ember eval report --compare <MPS> <CUDA>`) renders the controlled
  comparison; it names any per-recipe difference with the numerics note (MPS may differ slightly
  from CUDA). No new renderer.

## The controlled comparison (gate artefact)

- Two committed bundles on the current content hash: one MPS (`device: mps`) and one CUDA
  (`device: cuda`), both `dtype: float16`, with identical `settings` except the device.
- `tests/test_benchmark_comparison.py` asserts the pair exists and the equality of
  dataset hash + settings, so the phase gate is mechanically checkable (FR-018, SC-008).
- The comparison never adjusts labels to reduce a difference (spec edge case).
