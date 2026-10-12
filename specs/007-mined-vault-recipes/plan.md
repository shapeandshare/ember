# Implementation Plan: Mined Vault Recipes — Tag Assignment First

**Branch**: `007-mined-vault-recipes` | **Date**: 2026-10-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-mined-vault-recipes/spec.md`

**Parent programme**: `specs/004-benchmark-categories/spec.md` (Phase 2, Mined vault recipes). Phase 1 (`specs/006-benchmark-hygiene/`) is green. Every parent rule — the register, the two hashes, pinned splits, protocol rules, `no-live-secret` — applies unchanged.

## Summary

Mine the Old Growth vault (sibling repository, pinned at `692f4bb58b7f62105aeb73fba8dfee12bfdecd53`, all-rights-reserved; the copyright holder's written permission is recorded in `../oldgrowth/LICENSES.md` at commit `422648d9`) into the benchmark as a new recipe family, `mined_vault`, starting with `tag_assignment` (65 items, the phase gate), then `memory_worthiness`, `note_placement`, `staleness`.

A new deterministic miner — `ember eval mine` — reads the pinned tree through read-only git (never the working tree), builds the as-read vocabulary from `docs/vault/_meta/tags.md`, excludes non-content, drift, secret, and out-of-bounds notes by declared rules, samples 65 notes seeded across `type/*` and `domain/*`, and emits items (`source.kind=mined`, `register_row`, `artefact`, `commit`). Each `tag_assignment` item asks one `noul` per candidate tag; gold is exactly the note's own vocabulary tags. Two small, additive evals-internal schema changes carry the provenance the parent register demands: `Source.mined` gains `register_row` and `register.validate()` gains a `mined` branch (a mined item whose source has no `used` row fails the check), and `RegisterRow` gains `permission`, required for any non-permissive `used` source. The source's single `used` row records the licence as read, the grant reference, the snapshot tree hash, and the source tree itself as its hash-equal mirror. Adding items records a new dataset version through the existing card flow. After the first full run, the kit gains the recipe with thresholds re-measured from that run — never hand-typed.

## Technical Context

**Language/Version**: Python 3.12 (uv-managed, `.python-version`).

**Primary Dependencies**: none new. PyYAML is already a dependency; the frontmatter parse reuses the `scripts/vault_audit.py` pattern (header regex + `yaml.safe_load` + Pydantic validation). Otherwise stdlib (`hashlib`, `pathlib`, `re`, `json`, `subprocess` for read-only git) plus the existing `evals/dataset/*` machinery (records, io, hashes, splitting, register, lint, check).

**Storage**: files only. Items land in `evals/clef-flash.jsonl` through `write_items`/`dump_item`; the sampling manifest and exclusion records are committed JSON under `evals/dataset/`; `splits.lock` is extended through the existing `assign_new` + `append_lock`; the register row lives in `evals/dataset/register.json`; a new dataset version is appended to `versions.lock` by `ember eval dataset card`. No database, no network.

**Testing**: pytest, host-isolated. A synthetic fixture vault (a throwaway `git init` repository with seeded notes in `tmp_path`) — tests never read the real sibling checkout. Determinism tests (two mines → identical bytes), exclusion-rule tests per reason, tests for the two new schema validators, register/check failure tests (missing grant; missing `used` row), and a gate test that `tag_assignment` renders on the leaderboard for the current version. No model-backed tests are required for the miner itself; the scored run happens manually on MPS and on the AWS deployment.

**Target Platform**: macOS (Apple Silicon, development) and Linux (CI); pure file/text tooling.

**Project Type**: single project — `evals/` dataset tooling plus `ember/commands/` CLI wiring; `evals/` ships with the repo, not the wheel.

**Performance Goals**: seconds for a full mine over ~1,098 notes; idempotent and deterministic by construction.

**Constraints**: byte-for-byte reproducibility from the pinned commit (FR-001/SC-001); no new dependencies; ≤400 lines/module (Article X §10.3); annotations never move the content hash; no live secrets; register invariants enforced at dataset-check time (`mirror.sha256` must equal `snapshot.sha256`); the miner refuses without the permission grant (FR-012).

**Scale/Scope**: the vault's ~1,098 notes, of which the non-spec memory notes form the candidate pool → 65 `tag_assignment` items this change; the miner accepts a different commit as a different source without schema changes; the three later recipes reuse the miner with their own extractors, landing incrementally.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Article I (Local or Remote, Never Silent)** — no network access anywhere in this feature; the only external read is the local sibling checkout at a pinned commit. ✓
- **Article III (Agent-Legible Contract)** — the kit gains the new recipe only with thresholds re-measured from a real run (§3.3), and the Claude-plugin skill copy stays byte-identical (existing `test_distribution.py` gate). ✓
- **Article IV (Lazy, Non-Interfering Lifecycle)** — tests never touch the real oldgrowth repo or any network; the miner signals no processes and binds no ports. ✓
- **Article VII (Verification Over Assertion)** — determinism, the refusals, and the two new validators are tested, not asserted; one real mine run is exercised end-to-end before the gate closes. ✓
- **Article VIII / Article X (Tooling and Python conventions)** — ruff, mypy strict, bandit; NumPy docstrings on the new `evals/` modules; one class per file; exceptions as enums; atomic writes for emitted artifacts. ✓
- **Article XI (TDD and the coverage ratchet)** — every module and schema change ships with its tests in the same commit; floor 94 stays. ✓
- **Article XV (Simplicity First / YAGNI)** — reuse `evals/dataset/*` and the vault-audit parse pattern; no new dependency, no configuration knobs; exclusion rules are declared data, not machinery. The snapshot-by-commit mechanism is required by reproducibility (FR-001), the one complexity this feature needs. ✓
- **Additional constraints (MIT repo)** — redistribution of vault content is covered by the recorded permission grant (attribution on the register row and the data card; FR-016); no weights are touched. ✓
- **Article IX (Project Memory Vault)** — a decision note for the miner design and a session log land with the work; the hub links them. ✓

No violations — Complexity Tracking stays empty. The two schema changes are additive (a required reference on `mined`, an optional `permission` on the register row) and are justified by FR-004; they are recorded here rather than as violations.

## Project Structure

### Documentation (this feature)

```text
specs/007-mined-vault-recipes/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── checklists/
│   └── requirements.md  # Spec quality checklist (16/16 on 2026-10-11)
└── contracts/           # Phase 1 output
    ├── mine-cli.md      # `ember eval mine` behaviour contract
    └── provenance.md    # source + register + check contracts
```

### Source Code (repository root)

```text
evals/dataset/mine.py           # CLI entry (main) + the MinedMiner composition root
evals/dataset/mined/
├── __init__.py                 # bare package marker (Article X §10.1)
├── snapshot.py                 # VaultSnapshot: read docs/vault at a pinned commit (read-only git)
├── frontmatter.py              # note frontmatter parse (vault-audit pattern)
├── vocabulary.py               # as-read tags.md → TagVocabulary (five axes)
├── exclusions.py               # ExclusionReason StrEnum + the declared selection rules
├── selection.py                # seeded deterministic sampling across type/domain
├── tag_assignment.py           # gold = the note's tags; deterministic candidate set
└── emit.py                     # Item construction + write_items / lock integration

evals/dataset/records/source.py        # change: `register_row` required for `mined`
evals/dataset/records/register_row.py  # change: optional `permission` + used-row rule
evals/dataset/register.py              # change: validate() resolves mined items too
evals/dataset/check.py                 # already checks the mined commit; now also cross-checks rows

ember/commands/parser.py            # add a `mine` passthrough subcommand (capture/context pattern)
ember/commands/eval.py              # cmd_eval_mine → evals.dataset.mine.main

tests/
├── test_mined_miner.py             # determinism, exclusion rules, refusal without the grant
├── test_mined_provenance.py        # new validators; check failure/success; leaderboard gate
└── test_dataset_tooling.py         # fixture updated for the mined `register_row`
```

**Structure Decision**: a new `evals/dataset/mined/` sub-package inside the existing dataset tooling, with module boundaries by responsibility (snapshot, vocabulary, exclusions, selection, extraction, emission), and one top-level CLI entry (`evals/dataset/mine.py`) wired like `capture`/`context`. No `ember/` runtime or serving-layer changes. Register, lint, hash, and check behaviour reuse the existing modules; the only schema change is additive. The miner emits standard items and standard register rows, so scoring machinery is untouched.

## Complexity Tracking

> Empty — the Constitution Check reports no violations. The two additive schema changes (`Source.mined.register_row`, `RegisterRow.permission`) are recorded in the Summary and research R7, each justified by FR-004 and tested in the same commit.
