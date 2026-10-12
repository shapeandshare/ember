# Phase 1 Data Model: Benchmark Hygiene

Entities the phase adds or fills. Records follow the existing conventions: Pydantic v2 models,
one class per file under `evals/dataset/records/` (and `evals/context/records/` for the probe),
`StrEnum` for every fixed set. None of these entities enters the dataset content hash except where
explicitly noted (only a gold-label change does, via `gold_labels`).

---

## 1. Added to an existing record

### `Scale.anchors` (modifies `evals/dataset/records/scale.py`)

| Field | Type | Rules |
|-------|------|-------|
| `anchors` | `list[str]` | One per level; length equals the question's `criteria` length; every entry non-empty; no entry equal to its neighbour. Required for `risk` and `effort` (and `alert_level`); enforced by the `scale-anchored` lint rule. |

Existing fields (`category`, `question`, `quantity`, `low`, `high`, `dangerous_end`,
`dangerous_from`, `since`) are unchanged. `low`/`high` remain the pole text and MUST equal
`criteria[0]`/`criteria[-1]` (the existing invariant); `anchors` is the per-level rubric between
them.

**Validation** (`anchors.py`): the count matches the item's criteria; each anchor is non-empty;
adjacent anchors differ. Failure names the scale and the level.

---

## 2. New records — stability

### `StabilityEntry` (`evals/dataset/records/stability_entry.py`)

| Field | Type | Meaning |
|-------|------|---------|
| `id` | `str` | The item id. |
| `category` | `str` | The recipe (e.g. `change_risk`). |
| `question` | `str` | The question within the recipe (e.g. `risk`). |
| `original` | `int` | The current gold level. |
| `relabel` | `int` | The blinded re-label (from the filled sheet). |
| `agrees` | `bool` | `relabel == original`. |
| `labelled_on` | `str` | ISO date the re-label was made. |

### `StabilityRound` (`evals/dataset/records/stability_round.py`)

| Field | Type | Meaning |
|-------|------|---------|
| `round_id` | `str` | e.g. `2026-10-11-risk-effort`. |
| `cooling_off` | `str` | The declared window (e.g. `7d`), stated plainly in the report. |
| `method` | `str` | How blinding was ensured (e.g. `original labels withheld`). |
| `labelled_on` | `str` | ISO date the round completed. |
| `entries` | `list[StabilityEntry]` | One per re-labelled item. |

### `StabilityResult` (`evals/dataset/records/stability_result.py`)

Computed, not stored per item:

| Field | Type | Meaning |
|-------|------|---------|
| `agreement` | `float` | Share of entries where `agrees` is true, per recipe. |
| `by_label` | `dict[str, float]` | Agreement per gold level, where a level has entries. |
| `unstable` | `list[str]` | Item ids that disagreed. |
| `rater_count` | `int` | `1` — the single-rater disclosure travels with the result. |

`StabilityResult` feeds the card's reserved `label_stability` field.

**Storage**: `evals/dataset/stability/<round-id>.json` (committed). The blinded sheet is an
artefact of `--emit` (not committed once ingested).

---

## 3. Kind and tier (no new schema — populated existing fields)

### `Item.kind` (`ItemKind`)

Values (existing enum): `positive`, `negative`, `control`, `hard_negative`, `near_miss`,
`adversarial`, `insufficient_context`, `variant`, `long_tier`. Each of the 475 items carries
exactly one. Minimum shares (`KIND_SHARES` in `lint.py`) are unchanged; a recipe's documented
absence uses `RecipeSpec.exemptions: dict[ItemKind, str]` (existing field).

### `Item.tier`

Unchanged: `Literal["easy"] | None`. `easy` = scored at least once on the current version and
never wrong (`tiers.easy_ids`). Non-easy = everything else.

Both are annotations and are excluded from `hashes.PROJECTED`/`PROJECTED_REQUIRED`: the content
hash is unchanged by tagging (asserted by the tier tool's own safety check and by the bundle
tests).

---

## 4. Probe shape

### `ProbeManifest.dataset_content_sha256` (modifies `evals/context/records/probe_manifest.py`)

| Field | Type | Meaning |
|-------|------|---------|
| `dataset_content_sha256` | `str` | The content hash of the items the probe scored, computed with `hashes.dataset_content_sha256`. The join key to a leaderboard row. |

Every other manifest field (`run_id`, `device`, `dtype`, `models`, `lengths`, `depths`) is
unchanged.

### `ProbeShape` (`evals/context/records/probe_shape.py`)

The row-facing projection of `ModelVerdict`:

| Field | Type | Source | Meaning |
|-------|------|--------|---------|
| `request_cap` | `int \| None` | `ModelVerdict.cap` | The request cap (longest passing length). |
| `first_drop_length` | `int \| None` | `ModelVerdict.first_failure_length` | First-drop length. |
| `worst_depth` | `Depth \| None` | `ModelVerdict.first_failure_depth` | Worst depth (`start`/`middle`/`end`). |

### Leaderboard row

`evals/leaderboard.py::_row()` gains `probe: ProbeShape | None`. Because the site serialises row
fields verbatim into `site/_data/benchmark.json`, only the HTML table needs a new cell. A row
whose `(model, device, dtype, dataset_content_sha256)` matches no snapshot has `probe = None`,
rendered as **"not measured"**.

**Match rule**: a snapshotted probe run in `evals/context/runs/<run_id>/summary.json` matches a
row when `device`, `dtype`, and `dataset_content_sha256` are equal and the row's model
(repo + revision) is one of the manifest's `models`. The newest matching snapshot wins.

---

## 5. Capture

### `SessionTranscript` (`evals/dataset/records/session_transcript.py`)

Input, read from a JSON file:

| Field | Type | Meaning |
|-------|------|---------|
| `session_id` | `str` | Identifier of the source session. |
| `turns` | `list[TranscriptTurn]` | The session's turns. |
| `reviewed_choice` | `str` | The choice endorsed at review (gold). |
| `acted_choice` | `str` | The choice made in the moment. |

### `TranscriptTurn` (`evals/dataset/records/transcript_turn.py`)

| Field | Type | Meaning |
|-------|------|---------|
| `role` | `str` | `user` or `agent`. |
| `content` | `str` | The turn text. |

### `RedactionRecord` (`evals/dataset/records/redaction_record.py`)

| Field | Type | Rules |
|-------|------|-------|
| `session_id` | `str` | Must equal the transcript's. |
| `redaction_sha256` | `str` | 64-hex; the `Source.redaction_sha256` written onto the item. |
| `method` | `str` | How redaction was performed (documented, not a credential). |
| `redacted_on` | `str` | ISO date. |

### `CaptureOutcome` (`evals/dataset/records/capture_outcome.py`)

A `StrEnum`: `converted`, `refused_no_redaction`, `refused_live_secret`.

### Emitted item (existing `Item` + `Source`)

`source.kind = captured`, `source.session_id`, `source.redaction_sha256`; `gold_labels` = the
reviewed choice; `acted = {"choice": <acted_choice>}`; `acted_differs = reviewed != acted`.
Candidates are written to `evals/dataset/candidates/<session-id>.jsonl` — never directly to the
dataset.

**Validation / refusal**: a transcript without a matching `RedactionRecord` is refused
(`refused_no_redaction`); any surviving live secret (per `secret_guard`) refuses
(`refused_live_secret`). Nothing is written on refusal.

---

## 6. Card hygiene edition (existing keys, filled)

| Card key | Today | After Phase 1 |
|----------|-------|---------------|
| `recipes.<cat>.label_stability` | hardcoded `None` | The `StabilityResult` for the recipe (or `None` for recipes with no round), plus the single-rater sentence at the card level. |
| `recipes.<cat>.inter_source_agreement` | hardcoded `None` | Stays `None`, with a stated reason (no imports yet). |
| `recipes.<cat>.rater_count` | hardcoded `1` | `1` (unchanged); drives the disclosure. |
| `recipes.<cat>.rubric_since` | present | Unchanged; anchors carry the same `since`. |
| `recipes.<cat>.kind_shares` / `easy_items` | present | Populated once kinds/tiers are assigned. |
| `register_sha256` | embedded | Unchanged (already embedded). |

`card.json` and `CARD.md` are regenerated and committed; `ember eval dataset card --check`
remains the freshness gate.

---

## Entity relationships

```
Scale (category, question) ──anchors──▶ per-level rubric text
Item.kind (ItemKind) ──counts──▶ RecipeSpec.exemptions (reasons)
Item.tier ("easy") ◀──derived from── leaderboard rows' traces (ember eval dataset tier)
StabilityRound ──entries──▶ Item.id ──▶ StabilityResult ──▶ card.label_stability
ProbeManifest.dataset_content_sha256 + device + dtype + models ──▶ ProbeShape ──▶ leaderboard row
SessionTranscript + RedactionRecord ──▶ candidate Item (source.kind=captured, acted/acted_differs)
```

Nothing here crosses the `ember/` layer seam; all entities live in `evals/` and travel as plain
files/JSON.
