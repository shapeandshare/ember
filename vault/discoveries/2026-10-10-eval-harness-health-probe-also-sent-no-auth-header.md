---
title: "The benchmark runner's /health probe also sent no auth header"
type: discovery
tags:
  - type/discovery
  - domain/cli
  - status/draft
created: "2026-10-10"
updated: "2026-10-10"
code-refs:
  - evals/eval/run_evals.py
  - tests/test_run_evals.py
---

# The benchmark runner's /health probe also sent no auth header

Part of [[ember]]. `evals/eval/run_evals.py` (`ember eval run` / `make eval-run`) lost its
`engine`/`model` provenance on every run against the Outerbounds hosted endpoint — the
*benchmark itself* scored correctly (0 errors, real answers from `/v1/systemone`), but the
recorded run metadata showed `"model": "unknown"` and `"engine": {}`, even though
`/v1/systemone` succeeded for all 475 items. This is the same class of bug as
[[2026-10-10-remote-health-probe-sent-no-auth-header]], found independently while running the
hosted benchmark for the first time, in a third, separate HTTP call site.

## What was tested

Ran `python evals/eval/run_evals.py` against the Outerbounds endpoint
(`EMBER_SERVER_URL`, `EMBER_AUTH_HEADER=x-api-key`, `EMBER_AUTH_TOKEN` exported). The run
completed cleanly (`errors=0`, 82.7% question accuracy) but
`results/unknown_<ts>_results.json`'s `config.engine` was `{}` and `config.model` was
`"unknown"`. A direct `curl` without the header returned `403`; with
`-H "x-api-key: $TOKEN"` it returned `200` with the real `engine` object.

Traced `evals/eval/run_evals.py::_engine()`: it calls
`httpx.get(f"{server}/health", timeout=5.0)` with no `headers` argument, unlike `_advise()`
a few lines below it, which already calls `build_auth_headers()`. A `403` JSON body has no
`"engine"` key, so `.get("engine")` silently returns `None` and `_engine()` degrades to `{}`
— no exception, no warning.

A second, independent bug sits downstream: even once `/health` is reached, `Engine.describe()`
(`ember/serving/runtime.py:380`) was changed to report the field as `"model"`, not
`"model_dir"` (the latter is intentionally omitted — a filesystem path should not leak to any
loopback caller, per I-001). `run_evals.py` still read the old `"model_dir"` key, so even a
successful authenticated `/health` call would have produced `"unknown"`. And for a hosted/S3
deployment, `Engine.model_name` is deliberately set to the full `s3://bucket/.../<model>/
artifacts/<file>` URI (`ember/serving/server.py:161-168`), so a naive `Path(...).name` on that
value yields the trailing filename (`"model_file"`), not the model identifier.

## Finding

Three independent gaps compounded into one symptom ("model: unknown" in hosted benchmark
runs):

1. `_engine()` never sent `build_auth_headers()` — any gateway-authenticated hosted
   deployment (Outerbounds `auth.type: API`, or ember's own `EMBER_SERVER_AUTH_TOKEN`) made
   `/health` return a non-2xx body with no `engine` key.
2. `run_evals.py` read a `"model_dir"` key that `Engine.describe()` no longer emits (removed
   deliberately for I-001; the live field is `"model"`).
3. `"model"` is not always a short name: for a hosted/S3 model source it is the full S3 URI,
   and a plain `Path(...).name` extracts the wrong segment (the artifact filename, not the
   model identifier).

## Relevance

Fixed in `evals/eval/run_evals.py`: `_engine()` now sends `build_auth_headers()`; a new
`_model_name()` helper reads the `"model"` key and, for `s3://` URIs, returns the path segment
immediately before `artifacts` (e.g. `Cloudflare__clef-flash`) instead of the trailing
filename. `model_spec_info()` is now called with the derived short name instead of the
nonexistent `model_dir` key. Regression tests:
`tests/test_run_evals.py::test_engine_sends_auth_headers_when_configured`,
`test_engine_returns_empty_dict_on_403`, `test_model_name_handles_local_and_s3_engine_values`.

This is the same root cause as [[2026-10-10-remote-health-probe-sent-no-auth-header]] (missed
`build_auth_headers()` on `/health`) recurring in a third call site —
`ember/commands/endpoint.py::remote_health()`, `ember/mcp/mcp_server.py`'s advise path, and now
`evals/eval/run_evals.py::_engine()` each independently decide whether to attach credentials.
Any future HTTP call to a configured remote endpoint should default to sending
`build_auth_headers()` unless there's a specific reason not to — this is the third time the
same omission has shipped.

A related, distinct bug was found and fixed in the same session:
`scripts/build_site_benchmark.py::_latest_model()` picked the "latest" tracked
`benchmark/<run-id>/` bundle by sorting directory names lexicographically, not
chronologically. A hosted run's directory is named after its derived model identifier
(`Cloudflare__clef-flash_<ts>`), which can sort before an older local run's directory
(`clef-flash_<ts>`) in plain ASCII order (uppercase < lowercase), silently keeping a stale
run live on the public site after a newer one was snapshotted. Fixed by sorting on each
bundle's `meta.run_at` instead. Regression test:
`tests/test_site_benchmark.py::test_latest_model_picks_the_chronologically_newest_run`.

## References

- `evals/eval/run_evals.py::_engine`, `_model_name` — the fixes.
- `ember/serving/runtime.py::Engine.describe` — the `model`/`model_dir` field history (I-001).
- `ember/serving/server.py` — hosted `model_name=hosted_source.uri` assignment.
- `scripts/build_site_benchmark.py::_latest_model` — the site-selection fix.
- [[2026-10-10-remote-health-probe-sent-no-auth-header]] — the first instance of this bug class.
- [[2026-10-10-remove-t004-non-loopback-auth-check]] — the Outerbounds deployment this was
  found against.
