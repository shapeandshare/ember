---
title: expose Prometheus metrics on the model server
type: decision
tags:
  - type/decision
  - domain/server
  - domain/tooling
  - status/draft
created: 2026-10-02
updated: 2026-10-02
code-refs:
  - ember/serving/server.py
  - pyproject.toml
---

# expose Prometheus metrics on the model server

Part of [[ember]]. The warm model server now serves Prometheus metrics at `GET /metrics`,
so advise throughput, latency, and token usage can be scraped and graphed.

## Context

The model server is a long-lived local process, but the only way to see request rate,
latency, or token consumption was to read the log. Agents and users have no machine-readable
signal that the server is healthy and being used.

## Decision

- Add `prometheus-client` as a pinned dependency and expose `GET /metrics` on the same
  loopback address as the rest of the API.
- Export `ember_advise_requests_total{status}`, `ember_advise_latency_seconds`,
  `ember_advise_input_tokens_total`, `ember_advise_output_tokens_total`, and
  `ember_model_info{model,device,dtype}`.
- Instrument `/v1/systemone` in an HTTP middleware so every request is counted and timed
  by status — including schema-validation 422s, 503s, and 500s; `/health` and `/metrics`
  are cheap and are intentionally not counted.
- Register the metrics in a dedicated `CollectorRegistry`, so `/metrics` exposes only ember
  metrics and not the standard `python_*`/`process_*` collectors.

## Consequences

- No authentication: `/metrics` is reachable wherever the server is bound. The default is
  loopback, so changing `EMBER_HOST` already exposes the whole API.
- The metric names and labels are public API; change them together with the README and tests.
- `ember_model_info` is set when the engine loads and cleared when it unloads, so it tracks
  `/health` readiness rather than reporting a stale model.

## Alternatives considered

- A hand-rolled JSON stats route on `/health`: no standard scraper, no histograms.
- `prometheus-fastapi-instrumentator`: an extra dependency for per-endpoint HTTP metrics that
  ember does not need.

## References

- `ember/server.py` (metric definitions, `/metrics`, instrumentation)
- `tests/test_metrics.py`
