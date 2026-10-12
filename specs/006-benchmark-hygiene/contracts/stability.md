# Contract: Label Stability (Phase 1)

Tooling: `evals/dataset/stability.py`, `ember eval dataset stability`. Records:
`evals/dataset/records/stability_entry.py`, `records/stability_round.py`,
`records/stability_result.py`. Storage: `evals/dataset/stability/<round-id>.json` (committed).

---

## The blinded sheet (`--emit`)

A JSON document the maintainer fills in a second sitting:

```json
{
  "round_id": "2026-10-11-risk-effort",
  "cooling_off": "7d",
  "method": "original labels withheld",
  "items": [
    {
      "id": "change_risk_012",
      "category": "change_risk",
      "question": "risk",
      "criteria": ["Negligible", "Low", "Medium", "High"],
      "anchors": ["...", "...", "...", "..."],
      "state": "…the item's state…",
      "relabel": null
    }
  ]
}
```

**Invariants of the sheet**:

- It MUST NOT contain the item's current `gold_label` for the question (blinding).
- `criteria` and `anchors` come from the dataset and the scale registry, so the maintainer
  re-labels against the rubric, not memory.
- `relabel` is filled with an integer level index; an unfilled entry makes `--ingest` exit `1`
  naming the item.
- The sheet covers only the scoped recipes (`change_risk`/`risk`, `effort_approach`/`effort`).

---

## The round record (`--ingest`)

```json
{
  "round_id": "2026-10-11-risk-effort",
  "cooling_off": "7d",
  "method": "original labels withheld",
  "labelled_on": "2026-10-18",
  "entries": [
    {"id": "change_risk_012", "category": "change_risk", "question": "risk",
     "original": 2, "relabel": 2, "agrees": true, "labelled_on": "2026-10-18"}
  ]
}
```

**Validation rules**:

- Every `id` MUST resolve to an item in the dataset, and its `category`/`question` MUST match.
- No item appears twice in a round.
- `original` is read from the dataset's `gold_labels` at ingest time and MUST equal the value the
  item carried when the sheet was emitted (a changed gold between emit and ingest is an error,
  not a silent update).
- `agrees` is computed, not provided.
- Nothing is written if any rule fails.

---

## The computed result (`--report`, and the card)

```json
{
  "change_risk": {
    "agreement": 0.93,
    "by_label": {"0": 1.0, "1": 0.95, "2": 0.86, "3": 0.92},
    "unstable": ["change_risk_041", "change_risk_077"],
    "rater_count": 1
  },
  "effort_approach": {"agreement": 0.88, "by_label": {"…": "…"}, "unstable": ["…"], "rater_count": 1}
}
```

- `agreement` is `agrees` count ÷ entries, per recipe.
- `by_label` is computed when a gold level has at least one entry, keyed by the level's
  index; levels without entries are omitted.
- `unstable` lists the item ids that disagreed and stays available for the tracked review queue
  (`Item.second_review` remains for a genuine second human; the model never re-labels).
- The published form carries `rater_count: 1` and the single-rater sentence (see
  [card-and-report.md](./card-and-report.md)).

---

## Publication

- The result fills the card's reserved `recipes.<category>.label_stability` field, and the card
  renders the single-rater sentence.
- The report states the cooling-off window and method from the round record; a shortened window is
  disclosed, never presented as a full pass (spec edge case).
- A stability adjudication that changes a gold label changes `gold_labels`; the content hash then
  moves, the new version is recorded in `versions.lock`, and the item's pinned split is preserved.
