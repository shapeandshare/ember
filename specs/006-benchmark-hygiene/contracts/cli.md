# Contract: CLI (Phase 1)

New and changed command surfaces. All handlers live in `ember/commands/eval.py` and dispatch
through the existing patterns (`dataset` subcommands via the `modules` dict; `capture` as a
top-level subcommand). `evals/` stays checkout-only; handlers raise the existing
`_EVAL_CHECKOUT_ERROR` when it is absent. No new `make` target.

---

## `ember eval dataset stability`

Emits a blinded re-label sheet, or ingests a filled one. Wired into `register_eval()`'s
`dataset` subparser and `cmd_eval_dataset`'s `modules` map.

```
ember eval dataset stability --emit   [--round ROUND_ID] [--dataset PATH] [--out PATH]
ember eval dataset stability --ingest SHEET.json [--round ROUND_ID] [--dataset PATH]
ember eval dataset stability --report [--dataset PATH] [--json]
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--emit` | — | Write the blinded sheet (item ids + criteria text, **original labels withheld**). |
| `--ingest` | — | Read a filled sheet and write the round record + recompute. |
| `--report` | — | Print the current agreement (per recipe, per label) without writing. |
| `--round` | derived from date + scope | The round id (`<YYYY-MM-DD>-risk-effort`). |
| `--dataset` | `evals/clef-flash.jsonl` | The dataset. |
| `--out` | stdout | Where `--emit` writes the sheet. |

Exit codes: `0` success; `1` on a sheet that references an unknown item, a round whose entries
duplicate an item, or an ingest with no matching dataset item. `--report` never writes.

---

## `ember eval dataset kind`

Audits `Item.kind` coverage (the tagging itself is an editorial pass on the dataset file; this
command reports, and the `kind-shares` lint stays the enforced-shape check once a recipe opts in).

```
ember eval dataset kind [--dataset PATH] [--json]
```

Prints, per recipe: the kind counts, the untagged count, and the shares against `KIND_SHARES`
minima. Exit `0` always (report mode); `--json` emits the same as JSON.

---

## `ember eval dataset tier`

Unchanged (`--from BENCHMARK_DIR`, `--dataset PATH`). Phase 1 runs it against the committed
bundles; see [kinds-and-tiers.md](./kinds-and-tiers.md) for the invariants it enforces.

---

## `ember eval capture import`

A top-level subcommand (mirrors `run`/`export`): it authors candidates, it does not check the
dataset.

```
ember eval capture import TRANSCRIPT.json REDACTION.json [--out DIR]
```

| Argument | Meaning |
|----------|---------|
| `TRANSCRIPT.json` | A `SessionTranscript` (see [capture.md](./capture.md)). |
| `REDACTION.json` | A `RedactionRecord` whose `session_id` matches the transcript. |
| `--out` | Candidate directory; default `evals/dataset/candidates/`. |

Exit codes: `0` when a candidate is written (prints the output path and `converted`);
`1` with one actionable line when refused (`refused_no_redaction`, `refused_live_secret`); `2`
on a malformed transcript/redaction file. Nothing is written on a non-zero exit.

---

## Changed commands

| Command | Change |
|---------|--------|
| `ember eval dataset card [--check]` | The generated card now carries `label_stability` and the single-rater sentence (see [card-and-report.md](./card-and-report.md)). `--check` stays the freshness gate. |
| `ember eval report --compare A B` | Unchanged; it is the rendering used by the controlled comparison (see [card-and-report.md](./card-and-report.md)). |
| `ember eval snapshot` / `ember eval context --snapshot` | Unchanged; the probe snapshot is the prerequisite for probe-shaped rows (see [probe-shape.md](./probe-shape.md)). |

`ember eval run` gained `--deployment-label` earlier (commit `6b5bdb5`); Phase 1 relies on it for
distinct rows in the controlled comparison.
