# Contract: Kinds and Tiers (Phase 1)

Ties together three existing mechanisms: `Item.kind` (`ItemKind`), `RecipeSpec.exemptions`, and
the `tier` tool (`evals/dataset/tiers.py`). No new schema.

---

## Kinds

**Vocabulary** (`records/item_kind.py`, unchanged): `positive`, `negative`, `control`,
`hard_negative`, `near_miss`, `adversarial`, `insufficient_context`, `variant`, `long_tier`.

**Rules**:

- Every item carries exactly one kind. `None` is allowed only transiently; the card and lint must
  never silently accept an untagged item at the phase's exit.
- Minimum shares (`KIND_SHARES`, `lint.py`) are unchanged: `negative` 20%, `control` 10%,
  `hard_negative` 15%, `near_miss` 10% (score-question items), `adversarial` 5%,
  `insufficient_context` 5%, `variant` 10%, `long_tier` 10% (for `failure_triage`/`change_risk`
  only). `positive` has no minimum.
- Where a recipe cannot meet a kind's minimum, `RecipeSpec.exemptions[kind] = "<reason>"` is set.
  The exemption is rendered in the card and consumed by `kind_shares()` — it does not relax any
  *other* rule.
- `kind` is an annotation and does not enter `hashes.PROJECTED`/`PROJECTED_REQUIRED`.

**Command**: `ember eval dataset kind [--json]` prints per-recipe counts, the untagged count, and
the shares against the minima (report mode; exit `0`).

**Enforcement**: `kind-shares` stays report-only until a recipe sets `lint=LintMode.enforce`; that
flip is out of scope for Phase 1 (the parent permits documented exemptions, and the vision recipes
cannot meet text-shaped shares).

---

## Tiers

**Rule** (unchanged, `tiers.easy_ids`): an item is `easy` iff it was scored by at least one run on
the current dataset version and **never** scored incorrect across those runs. Non-easy is
everything else. `Item.tier` stays `Literal["easy"] | None`.

**Command** (unchanged): `ember eval dataset tier [--from BENCHMARK_DIR] [--dataset PATH]`.

**Invariants the tool already enforces**:

- It errors if no leaderboard row exists for the current content hash.
- It re-hashes after tagging and refuses to write if the content hash changed (annotations only).
- It writes atomically via `write_items`, and prints `easy: <n> (+<added> / -<removed>)`.

**Reporting**: `metrics_phase0.tiers()` publishes easy vs non-easy accuracy per recipe; each
leaderboard row exposes it. Phase 1 confirms it renders for the current version once tiers exist.

---

## Expected outcome on the current dataset

- Kinds: 475/475 tagged; kind-share gaps closed or carry exemptions per recipe.
- Tiers: `easy` assigned from the committed bundles (`benchmark/`), so `easy_items` is a real
  count, and the card's `easy_items` and the report's non-easy accuracy are populated.
- The dataset content hash is unchanged by either pass (both are annotations).
