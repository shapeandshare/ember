---
title: "Generic deployment labels on the benchmark leaderboard and report, not raw URLs"
type: decision
tags:
  - type/decision
  - domain/tooling
  - status/draft
created: "2026-10-10"
updated: "2026-10-10"
code-refs:
  - evals/eval/run_evals.py
  - evals/eval/snapshot_evals.py
  - evals/analysis.py
  - evals/leaderboard.py
  - evals/sections/sections_front.py
  - scripts/build_site_benchmark.py
---

# Generic deployment labels on the benchmark leaderboard and report, not raw URLs

Part of [[ember]]. The published benchmark leaderboard and per-run report showed a real
server URL (a hosted deployment's actual Outerbounds hostname), a real S3 bucket path, and
a local run's real filesystem path (with the operator's username) — all committed, public
data on the tracked `benchmark/` tree and rendered on the live site. A same-day earlier
change made the Outerbounds deployment YAMLs (`deployment/flash.yaml`,
`deployment/full.yaml`) generic in the same way; this decision applies the same principle to
the data the benchmark runs themselves produce.

## Context

Direct follow-up request after the leaderboard shipped
([[2026-10-10-leaderboard-style-benchmark-reporting]]): "we are reporting for deployment the
urls, we need to make these more generic (local hosted, remote hosted, gpu backed, make
instance size, hardware etc) but not the actual urls." Auditing the committed data found the
leak was not limited to the one field the leaderboard table renders —`meta.server`— but
present in four separate places that had each independently captured or copied real location
data: the run's recorded `engine.model` (a real S3 URI) and, for an old local run,
`engine.model_dir` (a real filesystem path with a username); the per-item `trace.jsonl`'s
`model` field (the server echoes its own loaded identity — the same S3 URI — in every
`/v1/systemone` response); and `snapshot_evals.py` copying the raw `results.json`
byte-for-byte into the committed bundle, re-leaking whatever `config.server`/`config.engine`
held even after `analysis.build()`'s report model (`model.json`) was scrubbed.

ember has no way to query the specific GPU model or AWS instance size from `/health` — only
the torch device type (`cuda`/`mps`/`cpu`). That information exists today only in deployment
YAML comments, nowhere in a run's recorded data, so a literal "instance size, hardware" label
needs an operator to supply it.

## Decision

- **`evals/eval/run_evals.py` gains `_deployment_label(explicit, server, device)`**: an
  operator-supplied label (`--deployment-label` CLI flag, falling back to
  `$EMBER_DEPLOYMENT_LABEL`) always wins, e.g. `"Remote hosted (GPU, CUDA) — NVIDIA A10G,
  24 GB VRAM, g5.4xlarge"`. Without one, a generic fallback derives from
  `ember.cfg.endpoint.is_loopback_host(server)` plus the reported `device`: `"Local (Apple
  Silicon, MPS)"`, `"Remote hosted (GPU, CUDA)"`, etc. The server URL itself is used only for
  this loopback classification — it is never returned.
- **`server` is recorded in the run's config but never published**: `run_evals()` still
  writes `config["server"]` into the private, gitignored `results/*_results.json` (useful for
  the operator's own debugging), but `evals/analysis.py::build()` — whose return value is
  written verbatim to the committed, public `benchmark/<run-id>/model.json` — no longer reads
  it at all; `meta.deployment_label` replaces it.
- **`analysis.py` also strips `engine.model`/`engine.model_dir`** (`_public_engine`) before
  publishing: these can be a real S3 URI or a real local filesystem path; `device`/`dtype`/the
  limit fields are unaffected.
- **The leaderboard's grouping key moves from `(server, device)` to `(deployment_label,
  device)`** (`evals/leaderboard.py::deployment_key`): grouping behavior is unchanged in
  practice (a real deployment still gets its own label), but the key itself is no longer a
  URL, consistent with the row data (`deployment_label` replaces `server` in
  `leaderboard._row`).
- **The report's "System under test" table's "Server" fact becomes "Deployment"**
  (`evals/sections/sections_front.py`), showing `meta.deployment_label`.
- **`snapshot_evals.py` scrubs the raw `results.json` before committing it**
  (`_public_results`): previously `copy_atomic`'d byte-for-byte, re-leaking `config.server`
  and `config.engine`'s location fields even after `model.json` was scrubbed. Now mirrors
  `analysis._public_engine`'s rule and writes the scrubbed copy with `write_atomic`.
- **The per-item `trace.jsonl`'s `model` field is derived with the same `_model_name()`
  helper** already used for the run-level `model` field, rather than recording the server's
  raw echoed identity verbatim: a hosted server's `/v1/systemone` response legitimately
  contains its own loaded model's real S3 URI (`Engine.advise` passes `self.model_name` —
  `hosted_source.uri` for a hosted deployment — into every response, by design, for
  traceability; see `ember/serving/runtime.py`), and without this fix every one of 475 trace
  lines in a hosted run carried the real bucket path.
- **Existing committed snapshots fixed, not just future runs**, with the fix method matched
  to what each bundle could safely tolerate:
  - `benchmark/Cloudflare__clef-flash_20261010T192756Z/` (recorded its own `dataset_file`
    snapshot) was safely re-run through the real pipeline: its local `results/` source was
    patched with the derived `deployment_label`, then `snapshot_evals.py` regenerated
    `model.json`, `results.json`, and `trace.jsonl` end-to-end with every fix applied.
  - `benchmark/clef-flash_20261003T203810Z/` (an older run, from before the `dataset_file`
    snapshot existed) could NOT be safely re-run the same way: `analysis.dataset_for()`
    falls back to the checkout's *current* `evals/clef-flash.jsonl` for a run with no
    recorded `dataset_file`, which has grown from 264 to 443 items since this run — re-running
    `analysis.build()` against it would have silently overwritten the correctly-preserved
    264-item dataset this run actually scored, and drifted unrelated narrative/architecture
    text to the current checkout's wording. Fixed by hand-editing only the two sensitive
    fields directly in the committed `model.json`/`results.json` (`engine.model_dir` removed,
    `server` replaced with the derived `deployment_label`), leaving every other byte — the
    dataset snapshot, the narrative text, the scored trace — untouched.
  - General principle for any future old-format bundle found to need the same fix: prefer the
    real `snapshot_evals.py` pipeline when the bundle's own `dataset_file` makes that safe;
    otherwise hand-patch only the specific leaking fields rather than risk corrupting
    unrelated historical content by regenerating against today's checkout. A sufficiently
    stale or low-value old bundle may instead simply be deprecated/removed rather than
    patched, per direct guidance ("keep a clean format moving forward, we can deprecate old
    ones as needed") — not every historical run needs to be preserved indefinitely.
  - The public git history for these specific files no longer shows the real values as of
    this change (prior commits and tags are unaffected; this is a forward fix, not a history
    rewrite).

## Consequences

- A real deployment that wants the specific GPU model/instance size shown on the leaderboard
  must pass `--deployment-label`/`EMBER_DEPLOYMENT_LABEL` explicitly when running the
  benchmark; without it, the leaderboard shows only the generic local/remote-plus-device
  fallback. This is a real, if small, extra step for whoever runs the benchmark against a new
  hosted deployment going forward.
- `leaderboard.build()`'s behavior is unchanged for grouping/sorting/latest-run-selection —
  only the field name and its value changed from a URL to a label.
- The private, gitignored `results/` directory (an operator's own local run artifacts, export
  bundles, reports) still carries the real server URL and model location in its raw
  `*_results.json`/`*_trace.jsonl` — this is intentional and was never in scope; only the
  tracked `benchmark/` tree (committed, public) and the data it feeds to the site are scrubbed.

## References

- `evals/eval/run_evals.py::_deployment_label`, `_model_name` — the label derivation and
  trace-line scrubbing.
- `evals/analysis.py::_public_engine` — the engine-field scrubbing applied to the published
  report model.
- `evals/eval/snapshot_evals.py::_public_results` — the same scrubbing rule applied to the
  committed raw `results.json`.
- `evals/leaderboard.py::deployment_key` — the grouping key, now label-based.
- `evals/sections/sections_front.py::system` — the report's "Deployment" fact.
- Tests: `tests/test_run_evals.py` (label derivation, trace scrubbing),
  `tests/test_eval_report.py` (`meta` never carries `server` or a raw engine location),
  `tests/test_leaderboard.py` (row never carries a raw URL),
  `tests/test_sections_front_system.py` (table shows the label, never a URL),
  `tests/test_snapshot_evals.py` (committed `results.json` scrubbing).
- [[2026-10-10-leaderboard-style-benchmark-reporting]] — the leaderboard feature this decision
  amends.
