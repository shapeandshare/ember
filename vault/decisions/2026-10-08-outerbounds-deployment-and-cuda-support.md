---
title: "Outerbounds deployment artifacts, CUDA support, and the ember serve hosted-URI bug"
type: decision
tags:
  - type/decision
  - domain/models
  - domain/runtime
  - domain/server
  - domain/cli
  - domain/governance
code-refs:
  - ember/serving/runtime.py
  - ember/commands/lifecycle.py
  - deployment/flash.yaml
  - deployment/requirements.txt
  - deployment/README.md
  - shared/release.mk
created: "2026-10-08"
updated: "2026-10-08"
status: draft
---

# Outerbounds deployment artifacts, CUDA support, and the ember serve hosted-URI bug

Part of [[ember]]. Added a complete Outerbounds App deployment contract
(`deployment/deploy.yaml`, generated `requirements.txt`, `README.md`, a
`make deployment-requirements` target) modeled on `../model-foundry`'s own deployment
pattern, added real CUDA device support (constitution Article VI amended: "Apple Silicon
First" → "Apple Silicon and CUDA"), and fixed a real bug found along the way: `ember serve`
never checked `EMBER_MODEL_S3_URI` at all, only `ember start`/`server.py`'s `lifespan()` did.

## Context

Direct maintainer request: deploy ember to Outerbounds, with client-side `x-api-key` support
required and GPU support "absolutely" wanted, "full in scope."

**x-api-key**: investigated `ember/cfg/endpoint.py::build_auth_headers()` and found it
already general-purpose — `EMBER_AUTH_HEADER` accepts any header name (not hardcoded to
`Authorization`), and `ember init --auth-header` already plumbs it through to
`opencode.json`/the plugin config end-to-end, confirmed by existing tests
(`tests/test_endpoint.py::test_build_auth_headers_custom_header`). No code change was
needed — only documentation and the deployment example actually using it.

**GPU/CUDA**: constitution Article VI explicitly scoped CUDA out "until this Article is
amended." Flagged this conflict and got explicit confirmation to implement CUDA support now
(not CPU-only-for-now), given Outerbounds compute is Linux and has no MPS — CPU-only would
mean no GPU acceleration at all for the hosted deployment, defeating much of the point.

**The `ember serve` bug**: while building the deployment config, traced the actual code path
`commands: [ember serve]` (the correct foreground, container-appropriate command — not
`ember start`, which is a background+pidfile lifecycle meant for a developer's own machine)
and found `ember/commands/lifecycle.py::_apply_server_env` unconditionally called
`models.resolve_dir(name)` and raised `SystemExit` if it returned `None` — with **no check
of `ember.serving.hosted.resolve()` at all**. `EMBER_MODEL_S3_URI` only worked through
`process.start()` (`ember start`) and `server.py`'s `lifespan()` (direct `ember serve`
*would* have reached `lifespan()`, but `cmd_serve` crashed before `server.main()` ever ran).
This would have broken the deployment config being built in the very same session — found
and fixed via TDD before it could ship broken.

## Decision

- **Constitution Article VI amended** (3.0.1 → 3.1.0, MINOR — a device added, not a
  principle redefined): retitled "Apple Silicon and CUDA." Three devices: MPS (Apple
  Silicon, float16, local-first default), CUDA (NVIDIA GPUs, float16, the hosted-deployment
  path), CPU (float32, universal fallback). The MPS-specific `device_map={"": "mps"}`
  segfault workaround is now explicitly scoped as MPS-only — CUDA has no equivalent issue
  and loads via the same CPU-then-`.to(device)` path for simplicity (Article XV), not
  because it needs the workaround.
- **`ember/serving/runtime.py::pick_device()`** gains a CUDA branch: MPS first (unchanged
  default), then CUDA (`torch.cuda.is_available()`), then CPU. `pick_dtype()` returns
  `float16` for both `"mps"` and `"cuda"`, `float32` otherwise. `load_clef()`'s actual
  load path (`device_map={"": "cpu"}` then `.to(device)`) needed **zero changes** — it was
  already device-agnostic past the `pick_device`/`pick_dtype` resolution point; `"cuda"`
  flows through `backbone.to("cuda")`/`head.to(device="cuda", dtype=torch.float16)` as
  completely standard PyTorch operations.
- **No `pyproject.toml` dependency change needed.** Confirmed via web search and a local
  `uv export` test: PyPI's default `torch` wheel already bundles CUDA 13.2 support on Linux
  x86_64/aarch64 (since PyTorch 2.11) — no special index, extra, or platform marker required.
  `uv export`'s generated `requirements.txt` confirms this: `nvidia-cublas`,
  `nvidia-cudnn-cu13`, `triton`, etc. all resolve automatically as
  `sys_platform == 'linux'`-conditional dependencies.
- **Real bug fixed via TDD**: `ember/commands/lifecycle.py::_apply_server_env` now checks
  `ember.serving.hosted.resolve()` first, exactly mirroring the precedence already used by
  `server.py`'s `lifespan()` and `ember/serving/process.py::start()`. A new regression test
  (`tests/test_commands.py::test_cmd_serve_uses_hosted_model_dir_when_configured`) asserts
  `models.resolve_dir` is never even consulted when the hosted path resolves successfully.
- **`deployment/deploy.yaml`**: an Outerbounds App contract for `ember serve` itself as the
  deployed service (not a client) — `EMBER_MODEL_S3_URI`, `EMBER_DEVICE=cuda`,
  `EMBER_AUTOSTART=0`, a GPU `compute_pools` placeholder, `resources.gpu: "1"`, sized for
  `flash` on CUDA float16. `auth: {type: None}` (API server, not a browser app — contrast
  with model-foundry's `Browser` auth, which is a human-facing UI).
- **`deployment/requirements.txt`**: generated via `uv export --format requirements.txt
  --no-dev --no-editable --no-hashes`, not hand-maintained — `--no-hashes` because hashes
  pin to this dev machine's resolved wheel set, which may differ from what Outerbounds'
  Fast Bakery resolves for its own platform; `--no-editable` so the export installs ember
  itself from the packaged source tree (`pip install .`) rather than referencing a dev-only
  editable path that won't exist in the deployed pod.
  **Correction (2026-10-10):** this claim was wrong — see
  [[2026-10-10-fast-bakery-strips-ember-advise-from-deploy-requirements]]. The actual export
  command also passes `--no-emit-project`, which omits `ember-advise` from the file
  entirely; Fast Bakery never runs `pip install .` on the packaged source tree, so the
  deployed container had no `ember` executable at all (`ember serve` failed with `command
  not found`). `scripts/freeze_deployment_requirements.py` now explicitly re-adds
  `ember-advise==<version>` after resolving markers.
- **`make deployment-requirements`** (`shared/release.mk`): the one-command way to regenerate
  it, documented as a required pre-deploy step in `deployment/README.md`.
- **`deployment/README.md`**: prerequisites (GPU pool, S3 bucket with the model's files,
  secret integration, Outerbounds CLI), the deploy command, how a remote client connects
  (`ember init --opencode --server-url ... --auth-header x-api-key` +
  `EMBER_AUTH_TOKEN` exported, never written to config), and a CPU-only fallback variant.

## Consequences

- `ember serve`/`ember start` both now correctly support `EMBER_MODEL_S3_URI` — this was a
  real, previously-undetected gap (no test exercised `cmd_serve` against the hosted path
  before this session) that would have made the exact deployment config this session built
  non-functional.
- CUDA support exists and is unit-tested but **not yet verified against real NVIDIA
  hardware** — COMPATIBILITY.md explicitly records this (mirroring the existing precedent
  for `full` on MPS: "not yet verified"), not asserted as fact. Update COMPATIBILITY.md once
  a real CUDA run is recorded.
- x-api-key (or any custom header name) required no new code — it was already a general
  capability; this session's value-add was confirming that, documenting it in the deployment
  context, and using it correctly in `deployment/README.md`'s example.
- Three devices now share the identical CPU-then-move load path in `load_clef()` — this is a
  deliberate simplicity choice (Article XV §15.3: don't build two load paths when one works
  for both), not an oversight that MPS's segfault workaround "accidentally" also protects
  CUDA.
