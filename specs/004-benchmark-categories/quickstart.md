# Quickstart: validating Phase 0 (Foundations)

**Spec**: [spec.md](./spec.md) · **Contracts**: [contracts/](./contracts/)

This is a validation run book, not an implementation guide. Each step names what to run
and what you must see. Steps 1–6 need no model; steps 7–9 need weights and a running
server.

## Prerequisites

```bash
make setup            # deps only
make download         # pinned weights (steps 7–9)
```

## 1. Fast gates

```bash
make check            # compile + unit tests: lint (report mode), card freshness, register, provenance
make pr-ready         # format, lint, mypy (now covering evals/dataset and evals/risk_metrics), bandit
```

Expect: green. `tests/test_dataset_tooling.py`, `tests/test_data_source_register.py`,
`tests/test_risk_metrics.py`, `tests/test_site_benchmark.py` are new and all pass.

## 2. Direction checks (FR-003)

```bash
.venv/bin/pytest tests/test_eval_benchmark.py -k "scale or monotonic" -q
.venv/bin/pytest tests/test_eval_report.py -k legend -q
```

Expect: every score question has a registry entry whose poles match the dataset; the
scorer is monotonic with adjacent-level error exactly 1.0; the HTML and Markdown bundles
both contain `0 Negligible → 3 High`, `0 Trivial (minutes) → 3 Large (a day or more)`,
and `0 No alert (calm green) → 3 High (red)`.

Then break it on purpose and watch it fail: copy the dataset to a scratch file, swap the
first and last `criteria` of one `risk` item there, and lint the copy:

```bash
cp evals/clef-flash.jsonl /tmp/scratch.jsonl   # edit one change_risk item's criteria order
.venv/bin/ember eval dataset lint --dataset /tmp/scratch.jsonl --json
```

Expect: `scale-declared` fails naming `change_risk/risk`; the committed dataset is untouched.

## 3. Dataset tooling (contracts/dataset.md)

```bash
.venv/bin/ember eval dataset hash --json
.venv/bin/ember eval dataset lint --json
.venv/bin/ember eval dataset card --check
.venv/bin/ember eval dataset check
```

Expect: the content hash (the dataset version), the file hash, nine per-recipe hashes, and
the register hash; lint reports gaps for the nine grandfathered recipes (size target,
untagged kinds) with exit 0 and no `no-live-secret` finding; the committed card is fresh;
the provenance check passes (every `source` is an object that resolves; every id is in
`splits.lock`; `example_secrets.json` validates).

Annotation stability: in a scratch copy, change one item's `rationale` and run `hash`
again — the content hash and every per-recipe hash are unchanged while the file hash
differs; change one item's gold label — the content hash and that recipe's hash change.

Credential guard: paste `AKIAIOSFODNN7EXAMPLE` into a scratch item's state — lint passes
(documented example); change one character — `no-live-secret` fails the lint with exit 1
even though the recipe is in `report` mode.

Pinning: append a scratch item to a copy of the dataset and run `splitting.assign_new`; expect
it lands in the split that moves its label toward 40/60 and the lock gains one line, and that
running it twice gives the same answer. Change an existing id's split in the copy; expect
`split-pinned` to fail.

## 4. Register (contracts/register.md)

```bash
.venv/bin/pytest tests/test_data_source_register.py -q
python3 -c "import json;r=json.load(open('evals/dataset/register.json'));print(len(r['rows']), sorted({x['verdict'] for x in r['rows']}))"
```

Expect: all rows validate; the row count equals the spec's candidate table plus the
Decision Index and TypeSafe rows; no row is `used`; every `excluded` row has a reason.

Optional (network, minutes):

```bash
make audit-sources
```

Expect: `evals/dataset/register-audit.json` written; exit 0 (no `used` rows yet).

## 5. Asymmetric metrics (contracts/report-and-leaderboard.md)

```bash
.venv/bin/pytest tests/test_risk_metrics.py -q
```

Expect: hand-built records give the expected dangerous recall, at-threshold recall, missed
count, safe precision; a recipe below its bar reports `met: false`; a non-risk recipe
produces no `risk` block.

## 6. Rebuild the committed bundles and check the gate (FR-012, SC-001, SC-004)

```bash
for run in benchmark/*/; do .venv/bin/ember eval snapshot --rebuild "$(basename "$run")"; done
git diff --stat benchmark/
python3 - <<'EOF'
import json, subprocess
for run in ["clef-flash_20261003T203810Z", "Cloudflare__clef-flash_20261010T192756Z"]:
    new = json.load(open(f"benchmark/{run}/results.json"))["summary"]
    old = json.loads(subprocess.check_output(["git", "show", f"HEAD:benchmark/{run}/results.json"]))["summary"]
    assert new["categories"] == old["categories"], run
    assert new["questions"] == old["questions"], run
    print(run, "overall", old["overall"]["accuracy"], "->", new["overall"]["accuracy"],
          "capability", new["capability"] and new["capability"]["accuracy"])
EOF
```

Expect: per-recipe and per-question figures identical; `overall` changes only by the
vision exclusion; `capability` holds the vision figures; `model.json["meta"]` carries
`dataset_content_sha256`, `recipe_sha256`, and `tokens_available: false`, and the rebuilt
report says the token split is unavailable for these pre-Phase-0 traces. The 2026-10-10
bundle's content hash equals the current dataset's (the source migration changed no scored
content); the 2026-10-03 bundle scored the earlier 264-item dataset, so its hash
(`913e1b65…`) is its own version.

## 7. Token split end to end (contracts/http-api.md; needs a server)

```bash
.venv/bin/ember start
curl -s localhost:8765/v1/systemone -H 'content-type: application/json' -d '{
  "model":"clef-flash","state":"tests fail after the dependency bump",
  "questions":{"retry":{"type":"noul","instructions":"Is simply re-running likely to make it pass?"}}}' \
  | python3 -c "import json,sys;u=json.load(sys.stdin)['usage'];print(u);assert u['state_tokens']+u['fixed_tokens']+u['media_tokens']==u['input_tokens']"
```

Expect: the three keys present and summing to `input_tokens`. Then:

```bash
make test             # model-backed: test_http_api, test_runtime_unit, test_mcp_tool cover the split
```

## 8. A run with the new artifacts, interrupted and resumed (contracts/run-artifacts.md)

```bash
.venv/bin/ember eval run --category routing          # Ctrl-C after a few items
ls results/*_run.json results/*_trace.jsonl
.venv/bin/ember eval run --resume <run-id>
```

Expect: the manifest exists from the start; after resume the trace has every routing item
exactly once; `results.json` has `resumed: true`, `dataset_content_sha256`, `recipe_sha256`,
`register_sha256`, `settings`; every trace row has `tokens` whose parts sum to `total` and
the annotation fields (`kind`, `tier`, `source_kind`, `parent_id`, `perturbation`).

Negative: stop the server, restart it with `EMBER_MAX_REQUEST_LENGTH=4096`, run
`--resume` again. Expect: refusal naming `max_request_length`. Positive: edit one item's
`rationale` between the interruption and the resume. Expect: the resume proceeds (content
hash unchanged).

## 9. Leaderboard, tiers, and site

```bash
.venv/bin/ember eval snapshot results/<run-id>_results.json
python3 scripts/build_site_benchmark.py
python3 -c "import json;d=json.load(open('site/_data/benchmark.json'));print([ (v['dataset_content_sha256'][:8], len(v['rows'])) for v in d['leaderboard']['versions']]);print(d['headline']['scope'])"
make site             # optional, needs Docker; open /results/
```

Expect: **two** versions, newest first: the current content hash (the 2026-10-10 bundle
and the fresh run) and the 2026-10-03 bundle's older dataset. The fresh local-MPS run is a
new row in the current version (the only complete run there is the remote CUDA one, a
different deployment), with only `routing` filled, a `—` headline whose `title` names the
four unscored recipes, `incomplete: true`, and its `routing` cell linking to the fresh run;
`headline.scope == "coding"`; the landing headline still comes from the newest *complete*
run, and the leaderboard page shows the capability panel. A second `--category` run on the
same deployment and settings refreshes that column in the same row; one on different
settings (`EMBER_MAX_REQUEST_LENGTH=4096`) adds another incomplete row.

Validation residue: delete the snapshotted scratch bundle from `benchmark/` afterwards (it
is a partial run, not a publication) and rebuild the site data.

Tiers (the tool; tagging proper happens in Phase 1 once the version has its controlled
runs):

```bash
.venv/bin/ember eval dataset tier --from benchmark/ --dataset /tmp/scratch.jsonl
.venv/bin/ember eval dataset hash --dataset /tmp/scratch.jsonl --json
```

Expect: items every row's producing run got fully right are tagged `tier: "easy"` in the
scratch copy; the count is printed; the content hash is unchanged; a run over the scratch
copy renders "All items" and "Non-easy" accuracy side by side.

## 10. Documentation and governance

- README Benchmark section, AGENTS.md, COMPATIBILITY.md updated (grep for `state_tokens`,
  `splits.lock`, `register.json`, `Benchmark dataset:`).
- `.github/workflows/release-ember.yml` has the changelog-hash step; `uvx zizmor@1.30.1
  .github/` is clean; `make release-dry` still previews the bump.
- Constitution PATCH Sync Impact Report lists the §10.18 entries removed and the 793 → 826
  growth of `evals/analysis.py` before its split; `wc -l` of every split module is under 400.
- `make vault-audit` passes with the new decision note and session log linked from
  `vault/ember.md`.
