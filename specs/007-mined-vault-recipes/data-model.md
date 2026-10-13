# Data Model: Mined Vault Recipes — Tag Assignment First

## Changed record types

### `Source` — `evals/dataset/records/source.py`

`REQUIRED[SourceKind.mined]` becomes `{"artefact", "commit", "register_row"}` (was `{artefact, commit}`). The existing guards stay: a field outside the allowed set raises, and `commit` must match `^[0-9a-f]{40}$`.

| Field | Type | Notes |
| --- | --- | --- |
| `artefact` | `str` | Source-repo-relative note path (`docs/vault/Decisions/X.md`) |
| `commit` | `str` | 40-hex; validated by `_HEX40` and again in `check.run` |
| `register_row` | `str` | Id of the `used` `RegisterRow` (`oldgrowth-vault`) |

`tests/test_dataset_tooling.py`'s mined fixture gains `register_row`.

### `RegisterRow` — `evals/dataset/records/register_row.py`

New optional field `permission: str | None = None`. `_verdict_is_consistent` gains:

```python
if (
    self.verdict is Verdict.used
    and self.licence.class_ is LicenceClass.custom_permissive
    and not self.permission
):
    raise ValueError(f"{self.id}: a custom-permissive used row needs the permission it rests on")
```

This requires the grant reference for the all-rights-reserved Old Growth source (FR-004) while leaving the ember-vault (MIT, `permissive`) source permission-free (FR-013).

### `RegisterRow` — the Old Growth row (data in `register.json`)

| Field | Value |
| --- | --- |
| `id` | `oldgrowth-vault` |
| `name` | `Old Growth vault` |
| `urls` | `[UrlReading(url="https://github.com/shapeandshare/oldgrowth", read_on=<date>)]` |
| `licence.reading` | "All rights reserved; written permission granted for the ember benchmark dataset" |
| `licence.class_` | `custom_permissive` |
| `licence.spdx` | as read (no SPDX id for a proprietary licence; exact value set at implementation) |
| `licence.read_at` / `read_on` | `LICENSES.md` / `<date>` |
| `verdict` | `used` |
| `reason` | why it may be used |
| `permission` | `LICENSES.md §Exception — ember benchmark reproduction (commit 422648d9)` |
| `snapshot.version` | `692f4bb58b7f62105aeb73fba8dfee12bfdecd53` |
| `snapshot.sha256` | the tree digest |
| `snapshot.retrieved_on` | `<date>` |
| `mirror.location` | `shapeandshare/oldgrowth @ 692f4bb5 (private)` |
| `mirror.sha256` | equals `snapshot.sha256` (validator) |
| `mirror.public` | `false` |
| `transformation` | "Vault notes extracted into mined benchmark items" |
| `attribution` | "Old Growth — distributed in the ember benchmark dataset with written permission" |
| `items_imported` | the count `register.validate` computes (65 once `tag_assignment` lands) |

## New value types (`evals/dataset/mined/`)

| Type | Module | Shape |
| --- | --- | --- |
| `VaultSnapshot` | `snapshot.py` | `.commit`, `.tree_digest() -> str`, `.read(path) -> str`, `.files() -> Iterator[SnapshotFile]`; reads through read-only git |
| `NoteFrontmatter` | `frontmatter.py` | frozen Pydantic, `extra="allow"`: `title`, `type`, `tags`, `created`, `updated` + extras |
| `TagVocabulary` | `vocabulary.py` | `.axes: Mapping[str, frozenset[str]]` (type/domain/status/layer/concept), `.contains(tag)`, `.as_state_block() -> str` — each value with its as-read one-line description (FR-017) |
| `ExclusionReason` | `exclusion_reason.py` | `StrEnum`: `out_of_scope`, `non_content`, `drift`, `tag_set_bounds`, `secret` |
| `ExclusionRecord` | `exclusion_record.py` | frozen: `artefact: str`, `reason: ExclusionReason` |
| `SamplingManifest` | `selection.py` | `source_commit`, `seed`, the rule constants (`word_floor`, `candidate_cap = 16`), `exclusions`, `item_ids` |
| `CandidateNote` | `candidate_note.py` | frozen dataclass: `artefact`, `title`, `type`, `tags`, `body` |
| item builder | `tag_assignment.py` | produces a standard `Item` (no new wire type) |

## Entities → artifacts

| Entity | Lives in |
| --- | --- |
| the 65 items | `evals/clef-flash.jsonl` (through `write_items`) |
| sampling manifest + exclusions | a committed JSON beside the dataset artifacts (`evals/mined/<recipe>.json`) |
| split pins | `evals/dataset/splits.lock` (via `assign_new` + `append_lock`) |
| register row | `evals/dataset/register.json` |
| dataset version | `evals/dataset/versions.lock` (via `ember eval dataset card`) |
| dataset card | `evals/dataset/card.json` + `CARD.md` (regenerated) |

## Recipe specs (`evals/dataset/recipes.py`)

A new `_mined_vault(category, title, when, state, decides)` helper returns
`RecipeSpec(..., family=Family.mined_vault, phase=2)`, mirroring `_coding`/`_vision` —
no new machinery. `tag_assignment` registers this change; `memory_worthiness`,
`note_placement`, and `staleness` register as they land. By the family rule
(`family not in (vision, integration)`), `mined_vault` recipes are headline members
(FR-006), which is flagged as a consequence in `research.md`.

## Invariants

- Re-mining is byte-identical: deterministic ids, seed, and distractor sets.
- Every mined item's `register_row` resolves to a `used` row (`register.validate`), and its `commit` is 40-hex (`check.run`).
- The current content hash is recorded in `versions.lock`, and every item id is in `splits.lock`.
- No mined item's state trips `no-live-secret`.
- `mirror.sha256 == snapshot.sha256` (RegisterRow validator).
