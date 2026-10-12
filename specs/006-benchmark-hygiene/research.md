# Phase 0 Research: Benchmark Hygiene

Decisions behind `plan.md`. Every decision is grounded in the current code (file paths as they
exist today) and in the parent programme's rules.

---

## R1 — The stability pass is a committed round record, not a per-item field

**Decision**: A stability round is a committed file `evals/dataset/stability/<round-id>.json`
holding one entry per re-labelled item (`id`, `category`, `question`, `original`, `relabel`,
`agrees`, `labelled_on`), produced by `ember eval dataset stability --emit` (a **blinded
sheet**: original labels withheld) and ingested by `ember eval dataset stability --ingest`.
Agreement is computed from the records into the card's reserved `label_stability` field. No item
schema change.

**Rationale**: The parent requires the *publication* of label stability, not a per-item field on
`Item`, and `Item` already reserves its review fields for a second reviewer
(`second_review`, `second_pass`) — reusing them for a self re-label would misrepresent them. The
card's `label_stability` is already a reserved key (`card.py` sets it to `None` today), so the
publication target exists. Items stay untouched, so the content hash cannot move (R10).

**Alternatives considered**: (a) a `stability` field on `Item` — rejected: the parent's units are
recipe/label stability, and a per-item boolean would duplicate what the round record holds;
(b) writing directly into `card.json` with no record — rejected: the pass must be "reproducible
from committed evidence" (FR-002), which needs the rounds kept.

---

## R2 — Per-level rubric anchors live on `Scale`, enforced by a new always-on lint rule

**Decision**: `records/scale.py` gains `anchors: list[str]` (one per level, matching the
question's `criteria` length), validated so every anchor is non-empty and no anchor equals its
neighbour. A new `LintRule` value `scale-anchored` (`scale-anchored`) is added and enforced
alongside `scale-declared`/`dangerous-set-declared` in `lint.scale_rules`. `risk` and `effort`
anchors are written first; `alert_level` follows.

**Rationale**: Today `Scale` holds only `low`/`high` poles (`records/scale.py`), and the
intermediate level meanings exist only inside each question's `criteria` strings — so a labelled
level has no shared definition to re-label against, which is exactly what makes the stability
pass meaningful. Placing anchors on `Scale` keeps one registry and reuses the existing
`legend()` and `rubric_since` machinery. Enforcement belongs with the other scale rules, which
are always-on regardless of a recipe's lint mode.

**Alternatives considered**: (a) a separate anchors registry — rejected: two places would define
a scale (§15.4); (b) folding anchors into `question.criteria` — rejected: those are per-item
option labels, not shared rubric text, and changing them would change `questions` and therefore
the content hash.

---

## R3 — The controlled comparison is two committed bundles plus a gate test

**Decision**: Commit an **MPS** full run on the current dataset version (the maintainer's Mac,
`EMBER_DEVICE=mps`, float16) to sit beside the already-committed **CUDA** run
(`benchmark/17f0b0ad…_20261012T012758Z/`). Add `tests/test_benchmark_comparison.py`: it finds the
newest MPS bundle and the newest CUDA bundle on the **current** content hash, asserts both were
run at `dtype=float16` with identical `settings` except the device, and asserts the comparison
view renders (`report_compare`). The view itself is the existing `ember eval report --compare`.

**Rationale**: The parent requires "the same dataset rerun at float16 on MPS and CUDA", committed
as one controlled comparison. The MPS and CUDA runs are ordinary `ember eval run` invocations;
the only new artefact is the gate. Bundles already record `dataset_content_sha256`, `settings`,
and `engine.device`, so the equality checks are exact and need no new fields.

**Alternatives considered**: (a) a bespoke comparison document — rejected: the report's
`--compare` renders two runs side by side already (`eval/report_compare.py`); (b) committing only
the CUDA side — rejected: the parent's gate names the *comparison*, not one run.

---

## R4 — Kinds are tagged on items; exemptions carry the reasoned absences

**Decision**: Assign `Item.kind` (from the existing `ItemKind` vocabulary) to all 475 items,
using the existing `kind_shares` lint rule for coverage; where a recipe structurally cannot
produce a kind's minimum share, populate `RecipeSpec.exemptions: dict[ItemKind, str]` with the
reason. Add `ember eval dataset kind` (a small audit/report command) if a dedicated check is
wanted beyond the lint.

**Rationale**: `Item.kind: ItemKind | None` is already in the schema and unpopulated, and the
lint already reports the exact gaps (`negative 0%`, `variant 0%`, `8 of 8 items have no kind`).
The exemption mechanism already exists and is consumed by `kind_shares()`, and the card already
renders `exemptions`. Nothing new is needed beyond the editorial tagging and the exemption text.

**Alternatives considered**: (a) a new kind vocabulary — rejected: nine values already exist and
match the recipes' intent; (b) enforcing `kind-shares` outright — rejected at this phase: the
parent allows a documented exemption, and some recipes (vision) cannot meet text-shaped shares.

---

## R5 — Tiers reuse the existing easy/non-easy machinery; Phase 1 executes it

**Decision**: Keep `Item.tier: Literal["easy"] | None`; run `ember eval dataset tier` against the
now-committed bundles so the current version has tiers; confirm `metrics_phase0.tiers()` (easy vs
non-easy accuracy) renders in the report and that each leaderboard row surfaces it. Do not expand
the tier vocabulary.

**Rationale**: "Difficulty tier" in this programme is derived, not authored: `tiers.py` marks an
item `easy` iff it was scored at least once and never wrong; `metrics_phase0.tiers()` already
breaks accuracy into easy/non-easy. The tool has a hash-invariance safety check. Earlier work
could not produce tiers because no bundle existed on the current version; that blocker is gone.

**Alternatives considered**: (a) a graded `easy/medium/hard` enum — rejected as YAGNI (§15.3):
the parent asks for `easy`/non-easy reporting, and a rule for "medium" is not declared; (b)
hand-authored tiers — rejected: tiers are a property of observed runs, not opinion.

---

## R6 — The probe joins a row by (model, device, dtype, dataset content hash)

**Decision**: Add `dataset_content_sha256` to `ProbeManifest` (computed from the items the probe
scored). Add `evals/context/link.py` with `probe_shape(summary, row) -> dict | None` returning
`{"request_cap", "first_drop_length", "worst_depth"}` from `ModelVerdict` (`cap`,
`first_failure_length`, `first_failure_depth`). `leaderboard._row()` calls it over the
snapshotted runs in `evals/context/runs/` and sets `probe` to that dict or `None`.
`scripts/build_site_benchmark.py` adds a table column rendering the three figures or
"not measured".

**Rationale**: `ModelVerdict` already produces exactly the three figures the spec names; the only
gap is a shared key. The row's identity is `(model_key, deployment_key, settings_key, version)`;
`deployment_key` embeds `device`, and `settings_key` covers dtype — so matching on
**model repo+revision, device, dtype, and `dataset_content_sha256`** is precise and needs only
the one new field. "Not measured" falls out naturally: `evals/context/runs/` is empty today, so
every row reports it until a snapshot exists.

**Alternatives considered**: (a) matching at site-build time by git hash — rejected: git hashes
differ between runs of the same model/device and would miss matches; (b) adding
`deployment_label` to the probe manifest — rejected for now: FR-012 says model/device/settings,
not deployment, and the probe is device-level; revisit if two deployments share a device.

---

## R7 — Capture converts a consented transcript into candidate items, refusing unsafe input

**Decision**: Add `evals/dataset/capture.py` and the records `SessionTranscript`,
`RedactionRecord`, `CaptureOutcome`. `ember eval capture import <transcript.json> <redaction.json>`
reads a transcript (a defined JSON shape: turns with the agent's action and the reviewed choice),
verifies the redaction record (`session_id` + `redaction_sha256`, 64-hex), runs
`secret_guard.no_live_secret` over the resulting state, and writes candidate items to
`evals/dataset/candidates/<session-id>.jsonl` with `source.kind=captured`, `session_id`,
`redaction_sha256`, gold = the reviewed choice, and `acted` = the in-session choice
(`acted_differs=True` when they differ). A candidate with a surviving secret, or without a
redaction record, is refused with one actionable message and nothing is written.

**Rationale**: `Source` already models `captured` with exactly `session_id` and
`redaction_sha256` (validated hex64), and `Item` already carries `acted`/`acted_differs` — the
parent's "reviewed choice is gold, acted kept, disagreements tagged" maps onto existing fields.
Candidates land in their own file, not the dataset, so a human merges reviewed candidates (and
the content hash moves only then, with a new version recorded).

**Alternatives considered**: (a) reading opencode's session store directly — rejected: coupling
to a third-party store format, and the privacy boundary is clearer with an explicit transcript
file (Article I); (b) writing straight into `evals/clef-flash.jsonl` — rejected: capture is an
authoring step that must be reviewed before it becomes scored content.

---

## R8 — The card's hygiene edition fills the reserved fields and states single-rater

**Decision**: `card.py` fills `label_stability` from R1's rounds and keeps
`inter_source_agreement` as `None` with a stated reason (no imports yet); `rater_count` remains
`1` and the card renders a single-rater sentence. `card.json`/`CARD.md` are regenerated in the
same change; `ember eval dataset card` continues to record the version.

**Rationale**: `label_stability`, `inter_source_agreement`, and `rater_count` are already keys in
`_recipe_card()`, currently hardcoded — the schema does not change, only the values. `is_fresh()`
is byte-exact, so regeneration is required and already wired to `--check`.

**Alternatives considered**: a new card format/version — rejected: the reserved keys were added
in Phase 0 precisely for this.

---

## R9 — New commands follow the two existing CLI patterns, preferring `dataset`

**Decision**: `stability` and `kind` are `ember eval dataset …` subcommands (the `dataset`
namespace already carries `--dataset`/`--from` and dispatches through one handler's `modules`
dict — the `tier` pattern). `capture` is a top-level `ember eval capture …` subcommand (it
authors candidates, not a dataset check). Both are wired in `parser.py::register_eval()` and its
`cli.py` call site.

**Rationale**: `tier` proves the `dataset` pattern for a tool that reads bundles/traces; `capture`
is an authoring pipeline, closer to `run`/`export` than to a validation check.

**Alternatives considered**: all top-level, or all `dataset` — rejected: match the existing
grouping so `ember eval dataset` stays "checks and tags" and top-level stays "produce artefacts".

---

## R10 — Annotations never move the hash; only a gold change does, and it appends a version

**Decision**: Kinds, tiers, anchors, and stability are annotations and MUST NOT change
`dataset_content_sha256` (the projection is `id, category, split, state, images, videos,
media_kwargs, questions, gold_labels`). If a stability adjudication changes a gold label, the
change alters `gold_labels`, so a new content hash results: `ember eval dataset card` records it
in the append-only `versions.lock`, and the item's pinned split is preserved
(`splits.lock` is untouched). New protocol rules and scale `since` values are dated at the
version they first apply to; the current version is the HEAD of `versions.lock`.

**Rationale**: This is the parent's two-hash rule, already implemented in `hashes.py` and
enforced by `ember eval dataset tier`'s own safety check. Anchors and stability records are
tooling/registry data outside the projection, so they are dated at the current recorded version.

**Alternatives considered**: dating anchors at a fresh version — rejected: no scored content
changed, so no new version exists to date them at.

---

## R11 — The stability pass covers `risk` and `effort` first

**Decision**: Run the re-label round on `change_risk`/`risk` and `effort_approach`/`effort`
items only; the tooling is general so later recipes can join a round.

**Rationale**: The parent names these two (the weakest recipes: `risk` ~52%, `effort` ~42%
exact), and they are the two scales whose levels most need anchors.

**Alternatives considered**: every recipe now — rejected: 475 items is a large single sitting and
the parent scopes the phase to these two.

---

## R12 — No new dependency; reuse is the spec

**Decision**: Reuse `write_atomic`/`write_items` (`dataset/io.py`, `atomic.py`), the
`Scale.since`/`protocol.RULES` versioning, `RecipeSpec.exemptions`, the `tier` tool's
`--from`/trace pattern, `ModelVerdict`, `secret_guard`, `register.py` validators, the card's
reserved keys, and the site's `_risk_cell`/`_recipe_cell` render pattern. Add no package.

**Rationale**: Article XV — the three genuinely missing mechanisms (stability, capture, probe
join) are small tools over existing data; everything else is populating slots Phase 0 built.

**Alternatives considered**: a new `evals/hygiene/` package — rejected: the work belongs beside
the dataset tooling it extends (`evals/dataset/`) and the probe it joins (`evals/context/`).
