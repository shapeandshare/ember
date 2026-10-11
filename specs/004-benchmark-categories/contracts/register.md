# Contract: Data-source register and audit

**Scope**: `evals/dataset/register.json`, `evals/dataset/register.py`,
`evals/dataset/records/register_row.py`, `scripts/audit_data_sources.py`,
`evals/dataset/register-audit.json`.

## `register.json`

```json
{
  "schema_version": 1,
  "recorded_on": "2026-10-10",
  "rows": [
    {
      "id": "nist-juliet",
      "name": "NIST Juliet Test Suite (SARD)",
      "urls": [{"url": "https://samate.nist.gov/SARD/test-suites/112", "read_on": "2026-10-10"},
               {"url": "https://zenodo.org/records/4701387", "read_on": "2026-10-10"}],
      "licence": {"reading": "Public domain (17 USC 105); CC0 1.0 for foreign rights",
                  "spdx": "CC0-1.0", "read_at": "https://zenodo.org/records/4701387",
                  "read_on": "2026-10-10", "class": "permissive"},
      "verdict": "candidate",
      "reason": "Permissive; downloadable without an application; no real secrets or PII.",
      "snapshot": null, "mirror": null, "transformation": null,
      "feeds": ["insecure_pattern"], "items_imported": 0,
      "attribution": null, "upstream_available": true, "notes": "Primary source for CWE-labelled code."
    }
  ]
}
```

Validation (unit suite, offline):
- unique `id`; every row has ≥ 1 URL with a date, a licence reading with a date and
  `class`, a `verdict`, and a `reason`;
- `verdict == "used"` ⇒ `snapshot`, `mirror`, `transformation` present and
  `mirror.sha256 == snapshot.sha256`; `items_imported` equals the count of dataset items
  whose `source.register_row == id`;
- `verdict != "used"` ⇒ `items_imported == 0` and no dataset item references the row;
- `class in {non_commercial, research_only, gated}` ⇒ `verdict == "excluded"`;
- `class == share_alike` and `used` ⇒ `attribution` present (and, when imports exist, the
  items live in the share-alike file defined by the phase that adds them); the row's
  `attribution` is also the notice a public mirror carries beside the files — there is no
  mirror-level notice field;
- `class == composite` ⇒ `verdict in {conditional, excluded, unconfirmed}` unless the row
  names the audited sub-source.

## First survey (Phase 0 content)

Every row of the spec's Candidate External Sources table, plus the Cloudflare Decision
Index members and TypeSafe's `evalsafe-*` datasets, with the licence readings and
2026-10-10 dates recorded there; general-knowledge benchmarks carry `verdict: excluded`,
`reason: "out of scope (FR-042)"`. No row is `used` in Phase 0.

## Pre-publication audit (`scripts/audit_data_sources.py`, network, not a test)

```text
python3 scripts/audit_data_sources.py [--rows id,id] [--timeout 20]
```

For each row: fetch each URL (HEAD then GET), record `url_ok`; re-read the licence page
and record whether the reading's SPDX/class still appears (`licence_reading_unchanged`,
heuristic: the SPDX id or licence name is present in the page text); for `used` rows,
retrieve the mirror and compare its SHA-256 (`mirror_ok`). Writes
`evals/dataset/register-audit.json` (`audited_on`, per-row results) atomically and exits 1
if any `used` row fails `mirror_ok` or any URL of a `used` row fails. A changed licence
reading is reported, never auto-applied.

## Example secrets (`example_secrets.json`, R24)

Beside the register: `{"schema_version": 1, "entries": [{"value", "vendor", "url",
"read_on"}]}` — the vendor-documented example credential values the `no-live-secret` lint
rule allow-lists. Validated in the unit suite with the register (all fields non-empty,
values unique); the pre-publication audit re-checks each `url`. Seeded with AWS's
`AKIAIOSFODNN7EXAMPLE` and `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`.

## Hash in runs

`register_sha256` is recorded in every run's manifest and `config` and shown in the report's
reproduction section.
