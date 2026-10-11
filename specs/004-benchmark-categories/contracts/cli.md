# Contract: CLI and make

**Scope**: `ember/commands/eval.py`, `ember/commands/parser.py`, `ember/cli.py`,
`shared/testing.mk`, `README.md`, `AGENTS.md`.

## `ember eval` additions

| Command | Flags | Exit |
| --- | --- | --- |
| `ember eval run` | existing flags + `--resume RUN_ID` | 1 on a manifest mismatch or a server without the token split |
| `ember eval snapshot` | existing + `--rebuild RUN_ID` (mutually exclusive with `results_file`) | 1 when the bundle lacks `trace.jsonl` or `dataset.jsonl` |
| `ember eval dataset lint` | `--dataset PATH`, `--enforce-all`, `--json` | 1 on an enforced failure |
| `ember eval dataset card` | `--dataset PATH`, `--check` | 1 when stale (with `--check`) |
| `ember eval dataset hash` | `--dataset PATH`, `--json` | 0 |
| `ember eval dataset check` | `--dataset PATH` | 1 on any provenance failure |
| `ember eval dataset tier` | `--from DIR` (default `benchmark/`), `--dataset PATH` | 1 when the content hash would change or no row exists on the current version |

All follow `register_eval()`'s pattern: a sub-parser in `parser.py`, a `cmd_eval_*`
handler in `commands/eval.py` that lazy-imports the `evals` module behind
`_EVAL_CHECKOUT_ERROR` (the existing, justified pattern for the checkout-only harness),
wired in `cli.py`. `tests/test_cli_eval_dataset.py` (new, so `tests/test_cli.py` does not
grow past its 829 lines) covers dispatch of each.

## Make

```make
dataset-lint:   $(PY) -m evals.dataset.lint            # report mode; exits 1 on enforced failures
dataset-card:   $(PY) -m evals.dataset.card            # regenerate card.json + CARD.md
audit-sources:  python3 scripts/audit_data_sources.py  # network; before a dataset publication
```

`make check` (compile + unit tests) already covers lint, card freshness, register
validation, and the provenance check through the unit suite.

## Release workflow (FR-034, R22)

`.github/workflows/release-ember.yml` gains one step after the version bump: run
`python3 -m evals.dataset.hashes --json`, prepend `Benchmark dataset: <dataset_sha256>` to
the new version's section of `CHANGELOG.md` before the bump commit is pushed, and put the
same line in the GitHub Release notes. Every `uses:` stays SHA-pinned; run
`uvx zizmor@1.30.1 .github/` before pushing; pushing needs a token with the `workflow` scope.

## Documentation

- README "Benchmark": the `usage` split, structured `source`, dataset tooling commands,
  the register, dataset versions on the leaderboard, resume, the changelog hash line.
- AGENTS.md: project structure (`evals/dataset/`, new modules from the §10.18 split),
  commands table, watch-outs ("`usage` carries the token split; the harness requires it",
  "`splits.lock` is append-only", "the register is the source of truth for external data;
  never import without a `used` row", "the release workflow writes the dataset hash into the
  changelog"), Recent Changes.
- `.specify/memory/constitution.md`: PATCH Sync Impact Report removing the split modules
  from §10.18 and recording that `evals/analysis.py` had grown from the recorded 793 lines
  to 826 before the split.
- `vault/decisions/2026-10-10-benchmark-foundations-token-split-and-registries.md`: the
  planning decisions R1, R8, R9, R11, R19, R21, R22.
