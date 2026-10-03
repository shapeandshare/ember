---
title: self-hosted VMs cannot hold the model, so model tests are local-only
type: discovery
tags:
  - type/discovery
  - domain/tooling
  - domain/runtime
  - status/draft
created: 2026-10-03
updated: 2026-10-03
code-refs:
  - .github/workflows/ci.yml
  - tests/conftest.py
---

# self-hosted VMs cannot hold the model, so model tests are local-only

Part of [[ember]]. The org's self-hosted macOS Apple Silicon runners are 8 GiB Tart VMs,
which cannot load the 9B fp16 model, so model-backed tests stay a local-only gate.

## What was tested

- Dispatched the `ci` workflow on `main` and inspected the job's runner: it routed to the
  org pool (`runner-95b29851`, group `default`, labels `self-hosted,macOS,arm64`).
- The model server crashed at startup with
  `RuntimeError: MPS backend out of memory (MPS allocated: 9.01 GiB, max allowed: 9.07 GiB)`
  in `ember/runtime.py` (`backbone.to(device)`).
- A runner diagnostics line reported `mem_bytes=8589934592` (8 GiB) with 31 GiB disk free;
  `gh-runner-standalone/docs/guides/macos.html` documents "4 CPU cores, 8 GB RAM per VM".

## Finding

- The pool is provisioned at 8 GiB per VM; the fp16 model needs ~18–20 GB. The MPS allocator
  caps at ~9 GiB on that VM, so the server exits `3` and every model test errors.
- `PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0` (suggested by the error) is not a fix: the VM has
  only 8 GiB physical memory.

## Relevance

- Model-backed tests (`make test`, `make test-strict`) are removed from CI and run locally
  only. CI keeps `make check` (unit) plus a build/install smoke.
- The fix, if ever wanted, is to raise `[tart] memory` in
  `shapeandshare/gh-runner-standalone/macos/config.toml` to at least 32 GiB and restart the
  scaler — a shared-infra change that needs host RAM headroom.
- `tests/conftest.py` now dumps the spawned `server.log` tail when the server exits early,
  so a future `rc=3` is diagnosable without a runner filesystem.

## References

- `.github/workflows/ci.yml` (model job removed, reason documented)
- `tests/conftest.py` (`_server_log_tail`)
- `shapeandshare/gh-runner-standalone` (`macos/config.toml`, `docs/guides/macos.html`)
