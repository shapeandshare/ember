# Contract: Session Capture (Phase 1)

Tooling: `evals/dataset/capture.py`, `ember eval capture import`. Records:
`records/session_transcript.py`, `records/transcript_turn.py`, `records/redaction_record.py`,
`records/capture_outcome.py`. Output: `evals/dataset/candidates/<session-id>.jsonl`.

---

## Input: the transcript

```json
{
  "session_id": "2026-10-11-opencode-abc123",
  "turns": [
    {"role": "user", "content": "…"},
    {"role": "agent", "content": "…"}
  ],
  "reviewed_choice": "asked_for_confirmation",
  "acted_choice": "pushed_without_confirmation"
}
```

- `session_id` identifies the real session the item came from (`Source.session_id`).
- `reviewed_choice` is the choice endorsed on review — it becomes **gold**.
- `acted_choice` is what happened in the moment — it is kept as a **secondary** annotation.
- The transcript is the privacy boundary: the pipeline reads this file, never a live agent store
  and never a running process (Article IV).

## Input: the redaction record

```json
{
  "session_id": "2026-10-11-opencode-abc123",
  "redaction_sha256": "<64 hex>",
  "method": "…how redaction was done…",
  "redacted_on": "2026-10-11"
}
```

- `session_id` MUST equal the transcript's, else `refused_no_redaction`.
- `redaction_sha256` is copied onto `Source.redaction_sha256` (the field already validates 64-hex).

## Output: the candidate item

A schema-valid `Item` with:

| Field | Value |
|-------|-------|
| `source.kind` | `captured` |
| `source.session_id` | the transcript's |
| `source.redaction_sha256` | the redaction record's |
| `gold_labels` | `{<question>: reviewed_choice}` |
| `acted` | `{"choice": acted_choice}` |
| `acted_differs` | `reviewed_choice != acted_choice` |

Written to `evals/dataset/candidates/<session-id>.jsonl` — **never** to `evals/clef-flash.jsonl`.
A candidate becomes scored content only after review, at which point the content hash moves and
`versions.lock` records the new version.

## Refusal rules

| Outcome | Trigger | Effect |
|---------|---------|--------|
| `refused_no_redaction` | missing record, or `session_id` mismatch | exit `1`, nothing written, one actionable line |
| `refused_live_secret` | `secret_guard.no_live_secret` finds a match in the resulting state | exit `1`, nothing written, names the pattern |
| `converted` | otherwise | exit `0`, candidate written, prints the path |

The `no-live-secret` rule is never relaxed. If the source text legitimately contains a
vendor-documented example credential, its value is added to `example_secrets.json` with vendor +
URL + `read_on` — never by loosening a regex.

## Validation

- `capture import` refuses any transcript missing `session_id`, `reviewed_choice`, or `acted_choice`
  (malformed input → exit `2`).
- A test converts a fixture session end-to-end and asserts a schema-valid `Item` with the fields
  above (SC-006), and asserts a session without a redaction record is refused.
