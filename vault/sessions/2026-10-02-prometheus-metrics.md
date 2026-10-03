---
title: prometheus metrics endpoint
type: session-log
tags:
  - type/session-log
  - domain/server
  - domain/tooling
created: 2026-10-02
updated: 2026-10-02
---

# prometheus metrics endpoint

Part of [[ember]]. A short session adding a Prometheus `/metrics` endpoint to the model
server.

## What happened

- Added `prometheus-client` as a pinned dependency (`uv add` updated `uv.lock`).
- Defined the advise counters, latency histogram, and model info gauge in `ember/server.py`
  and exposed `GET /metrics`.
- Instrumented `/v1/systemone` to count requests by status and observe latency and tokens.
- Added `tests/test_metrics.py` (endpoint without the model; instrumentation with it) and
  documented the endpoint in the README and AGENTS.md.

## Decisions and discoveries written back

- [[2026-10-02-expose-prometheus-metrics-on-the-server]]

## Follow-ups

- Add a label or extra histogram if more than one model is served from one process.
- Consider scraping in the self-hosted CI runner once metrics matter there.
