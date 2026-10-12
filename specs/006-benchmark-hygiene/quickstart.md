# Quickstart: Benchmark Hygiene (Phase 1)

A run book that proves Phase 1 works end to end. Commands are real; expected output is stated so
each step is falsifiable. Details live in [contracts/](./contracts/) and [data-model.md](./data-model.md).

## Prerequisites

- The repository checkout (not the installed wheel — `ember eval` reads `evals/`).
- `make setup` (deps). Weights for the comparison: `make download` (MPS) and the AWS deployment
  for the CUDA half — or any reachable CUDA server with the pinned model.
- `EMBER_AUTH_TOKEN` exported for the CUDA half (`make -s aws-token` when using the AWS
  deployment).

## 1. Anchors are declared and enforced

```bash
.venv/bin/ember eval dataset lint --json | python3 -c "import json,sys; d=json.load(sys.stdin); print([f for f in d if f['rule']=='scale-anchored'])"
```

- **Expected**: no `scale-anchored` findings; every level of `risk`, `effort`, and `alert_level`
  has a non-empty anchor distinct from its neighbour.
- **Negative check**: temporarily blank one `Scale.anchors` entry and re-run `make check`; it MUST
  fail naming the scale and level. Restore before continuing.

## 2. The stability pass publishes an agreement

```bash
# Emit the blinded sheet (original labels withheld)
.venv/bin/ember eval dataset stability --emit --out /tmp/stability-sheet.json

# Fill each "relabel" (a second sitting, after the cooling-off window), then:
.venv/bin/ember eval dataset stability --ingest /tmp/stability-sheet.json

# Inspect
.venv/bin/ember eval dataset stability --report
.venv/bin/ember eval dataset card          # regenerates card.json / CARD.md
.venv/bin/ember eval dataset card --check  # must print "dataset card is fresh"
```

- **Expected**: the round record lands at `evals/dataset/stability/<round-id>.json`; `--report`
  prints agreement per recipe and the unstable count; the card's `label_stability` is non-null and
  the single-rater sentence appears.
- **Refusal check**: an unfilled `relabel` makes `--ingest` exit `1` naming the item; an id not in
  the dataset exits `1`.

## 3. Every item carries a kind

```bash
.venv/bin/ember eval dataset kind
```

- **Expected**: `untagged: 0`; per-recipe shares meet `KIND_SHARES` or the recipe carries an
  exemption. The card renders the kind shares and exemptions.
- **Invariant**: `ember eval dataset hash` is unchanged by tagging.

## 4. Tiers are derived and the report shows non-easy accuracy

```bash
.venv/bin/ember eval dataset tier
.venv/bin/ember eval run --dry-run >/dev/null   # sanity: the harness sees the dataset
```

- **Expected**: `easy: <n> (+<added> / -<removed>)`; if no bundle exists on the current version the
  tool exits `1` naming the version. The report's tier block shows easy vs non-easy accuracy.

## 5. The controlled comparison is committed (the gate)

```bash
# MPS half (this machine)
EMBER_SERVER_URL=http://127.0.0.1:8765 .venv/bin/ember eval run --deployment-label "Local (MPS)"
.venv/bin/ember eval snapshot

# CUDA half (the AWS deployment) — already committed for the current version
export EMBER_SERVER_URL=https://ember-default.tail5be351.ts.net
export EMBER_AUTH_TOKEN="$(make -s aws-token NAME=default)"
.venv/bin/ember eval run --deployment-label "Remote hosted — AWS g5.2xlarge, NVIDIA A10G, 24 GB VRAM (us-west-2)"
.venv/bin/ember eval snapshot

# Render the comparison and the gate
.venv/bin/ember eval report --compare results/<mps>_results.json results/<cuda>_results.json
.venv/bin/python -m pytest tests/test_benchmark_comparison.py -q
```

- **Expected**: two bundles on the same `dataset_content_sha256`, both `dtype: float16`, differing
  only in `device`; the comparison renders side by side; the gate test passes.

## 6. Every row carries the probe shape (or "not measured")

```bash
# Snapshot a probe run, then rebuild the site data
.venv/bin/ember eval context --models flash
.venv/bin/ember eval context --snapshot <run_id>
.venv/bin/python scripts/build_site_benchmark.py
python3 -c "import json; b=json.load(open('site/_data/benchmark.json')); print([r.get('probe') for r in b['leaderboard']['rows']])"
```

- **Expected**: every row has a `probe` block (`request_cap`, `first_drop_length`, `worst_depth`)
  or `null`; the site table renders the figures or "not measured" — never blank.

## 7. Capture converts a session, and refuses unsafe input

```bash
# A fixture transcript with a matching redaction record
.venv/bin/ember eval capture import tests/fixtures/session.json tests/fixtures/session.redaction.json
# A transcript with no redaction record
.venv/bin/ember eval capture import tests/fixtures/session.json /tmp/missing.json; echo "exit=$?"
```

- **Expected**: the first writes `evals/dataset/candidates/<session-id>.jsonl` with
  `source.kind=captured`, gold = the reviewed choice, `acted` set, `acted_differs` true when they
  differ; the second exits `1` with `refused_no_redaction` and writes nothing.

## 8. The whole gate stays green

```bash
make check                     # unit suite incl. the new gate test
make test                      # model-backed (MPS) — for runtime-affecting changes
.venv/bin/ember eval dataset check
.venv/bin/ember eval dataset lint
.venv/bin/ember eval dataset card --check
make vault-audit
make pr-ready
```

- **Expected**: `dataset check` reports `0 problems`; `dataset lint` reports `0 enforced` (report
  gaps allowed only where a documented exemption exists); `card --check` says fresh; the vault
  audit is clean; `pr-ready` is green.

## Failure playbook

| Symptom | Cause | Fix |
|---------|-------|-----|
| `scale-anchored` finding | a level lacks a distinct anchor | add it on the `Scale`, regenerate the card |
| `--ingest` exits 1 | an unfilled/unmatched `relabel` or a changed gold | fix the sheet; if gold legitimately changed, ingest against the value the item carries now and record the new version |
| `tier` exits 1 | no leaderboard bundle on the current hash | snapshot a run for the current version first |
| every `probe` is null | no canonical probe snapshot | run `ember eval context --snapshot` |
| `card --check` fails | card not regenerated after a change | `ember eval dataset card` |
