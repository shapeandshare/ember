# Quickstart: Mined Vault Recipes — Tag Assignment First

How a maintainer mines `tag_assignment`, verifies provenance, closes the phase gate, and updates the kit. The three later recipes (`memory_worthiness`, `note_placement`, `staleness`) follow the same flow with their own `--recipe`.

## Prerequisites

- This repository, synced: `uv sync --locked`.
- The sibling checkout `../oldgrowth` with the pinned commit present:
  `git -C ../oldgrowth cat-file -e 692f4bb58b7f62105aeb73fba8dfee12bfdecd53`.
- The permission grant on file (`../oldgrowth/LICENSES.md`, commit `422648d9`). **Without it the miner refuses and names the missing grant — by design (FR-012).**

## 1. Mine the items

```bash
uv run ember eval mine --recipe tag_assignment
```

Expect: 65 items with `source.kind = "mined"` appended to `evals/clef-flash.jsonl` (each carrying `register_row`, `artefact`, and the 40-hex commit), the sampling manifest and exclusion records written under `evals/mined/`, and new ids pinned in `evals/dataset/splits.lock`. The register row for the source already sits in `evals/dataset/register.json`; the miner never invents one.

Reproducibility check (SC-001): run the command again — the miner is idempotent, so `git status` shows no change. Different bytes are a bug, not a merge decision.

## 2. Verify provenance, lint, and record the version

```bash
uv run ember eval dataset lint     # full lint; no-live-secret is enforced
uv run ember eval dataset card     # regenerate card.json + CARD.md; appends the new version to versions.lock
uv run ember eval dataset check    # refuses any item without a used register row (FR-004); needs the version recorded
uv run ember eval dataset hash     # inspect the new content hash
```

Order matters: `check` fails until `card` has recorded the new version and every id is in the lock.

## 3. Close the gate (SC-002): run the benchmark

Local MPS leg:

```bash
ember start
uv run ember eval run --category tag_assignment
```

AWS deployment leg:

```bash
export EMBER_SERVER_URL="https://ember-default.tail5be351.ts.net"
export EMBER_AUTH_TOKEN="$(make -s aws-token)"
uv run ember eval run --category tag_assignment
unset EMBER_SERVER_URL EMBER_AUTH_TOKEN   # back to local
```

Snapshot the local run for the site, then tag tiers:

```bash
uv run ember eval snapshot
uv run ember eval dataset tier      # needs a benchmark bundle for the new version
```

The leaderboard renders one table per dataset version; the gate is closed when the new version's table shows the `tag_assignment` column.

## 4. Update the kit (after the first run)

- Take the new recipe's starting thresholds **from the run output** — never hand-typed (Article III §3.3).
- Update `ember/agent_kit/ember-advise/SKILL.md` with the recipe and its thresholds, then copy it byte-identical to `packages/claude-plugin/skills/ember-advise/SKILL.md` (`tests/test_distribution.py` fails until you do).
- `make check` — the agent-kit contract tests must pass.

## 5. Re-run and removal paths

- Re-mining is always safe: deterministic bytes, same ids.
- If the permission is revoked or narrowed: remove the affected items, re-mine without them, regenerate the card (a new dataset version is recorded), and commit — nothing is silently kept (FR-015).

## Notes

- The miner reads the pinned commit through read-only git; the sibling working tree's dirty state is irrelevant and never read.
- A note whose content trips `no-live-secret` is excluded (or redacted with the redaction recorded) by the declared rules — the rule is never relaxed.
- Excluded notes are recorded with a declared reason (`drift`, `non_content`, `oversize`, `secret`, `tag_set_bounds`); the manifest explains every count in the card.
- The ember-vault (MIT) source is mappable and its mechanism is tested (`tests/test_mined_provenance.py`); its items are deferred until a coverage gap is identified and recorded.
