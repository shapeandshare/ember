# Implementation Plan: Remote Inference Servers

**Branch**: `001-remote-inference-servers` | **Date**: 2026-10-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-remote-inference-servers/spec.md`

## Summary

Add support for pointing ember's MCP client and CLI at a non-local inference server while
preserving a local-default workflow.

- The client supports credentials as either a bearer token or a custom header (e.g.
  `X-API-KEY`), sourced from env or config with env precedence.
- The server gains an **opt-in** remote-serving mode with optional bearer-token authentication
  that can be disabled so hosters can supply their own auth layer.
- TLS termination remains the operator's responsibility (proxy/gateway). The client rejects
  plaintext connections to non-local endpoints by default unless an explicit insecure override
  is set.

## Technical Context

**Language/Version**: Python 3.12 (uv-managed)

**Primary Dependencies**:

- FastAPI + uvicorn (HTTP server)
- httpx (client + lifecycle probes)
- prometheus-client (metrics)
- pydantic (wire models)
- mcp (stdio server)

**Storage**: JSON config file at `ember config path` (`ember/cfg/config.py` + `ember/cfg/paths.py`)

**Testing**: pytest (unit + integration), mypy strict, ruff, bandit

**Target Platform**:

- Server: macOS Apple Silicon (MPS), CPU fallback
- Client (CLI + MCP): any supported Python host (no model load in MCP)

**Project Type**: CLI tool + local/remote HTTP inference service + MCP stdio server

**Performance Goals**:

- Preserve existing local performance characteristics
- Remote mode: bounded waits and actionable errors (no hangs), rather than a strict latency target

**Constraints**:

- No new major dependencies unless justified (Article XV)
- Default remains local-only / loopback endpoint
- Remote endpoints allowed, but non-local plaintext is rejected unless explicitly overridden
- Credentials must never appear in logs or agent-visible output
- Tests must bind random free ports (never 8765) and stop only processes they started (Article IV)

**Scale/Scope**:

- Single configurable endpoint (no profiles)
- One remote server per client configuration
- Server remote-serving is opt-in and expected to be fronted by an operator-managed proxy

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Gate Results (pre-design)

- **Article I — Local-First and Private**: **FAIL (requires amendment)**.
  This feature explicitly enables sending `state`/questions/answers over the network to a
  configured endpoint, and requires removing the “never leaves your machine” guarantee.
  Per Governance, principle changes must be human-approved amendments with a Sync Impact Report
  and version bump. The design includes this amendment as a prerequisite artifact.
- **Article III — Agent-Legible Contract**: PASS with required updates (README + kit). Must
  keep `instructions.md` ≤ 2048 bytes.
- **Article IV — Lazy, Non-Interfering Lifecycle**: PASS with design constraints: remote
  endpoints must not trigger autostart; tests must use random ports.
- **Articles XI–XV** (TDD, async-first, layering, pit of success, YAGNI): PASS with planned
  tests, minimal surface area, and strict layer boundaries.

## Project Structure

### Documentation (this feature)

```text
specs/001-remote-inference-servers/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
ember/
  cfg/
    config.py            # defaults + resolve precedence
    paths.py             # config/pid/log paths
  mcp/
    mcp_server.py        # MCP client -> HTTP inference endpoint
    mcp_types.py         # AdviseInput schema
  serving/
    server.py            # HTTP API + optional server-side auth
    process.py           # warm-server lifecycle (local) + health probes
    runtime.py           # model I/O (no network)

tests/
  test_mcp_tool.py       # MCP protocol integration
  test_http_api.py       # HTTP API integration
  test_cli.py            # CLI paths: status/doctor/config
  test_runtime_unit.py   # runtime helpers
```

**Structure Decision**: Single Python package (`ember/`) with three layers: MCP → HTTP → Engine.

## Phase 0: Outline & Research

> **Status**: COMPLETE → [research.md](./research.md). All Technical Context unknowns resolved;
> no `NEEDS CLARIFICATION` remains. No new dependencies.

**Outcome**: Ten decisions (D1–D10) covering the Article I amendment, endpoint config keys,
credential header scheme, transport security, the client failure taxonomy (httpx has no distinct
`SSLError`), server-side optional auth, autostart/fallback, async posture, model-mismatch
reporting, and secret masking.

## Phase 1: Design & Contracts

> **Status**: COMPLETE.

**Artifacts**:
- [data-model.md](./data-model.md) — Inference endpoint, Endpoint credentials, Remote-serving
  configuration, Endpoint status; validation rules and requirement traceability.
- [contracts/http-api.md](./contracts/http-api.md) — `/health`, `/metrics`, `/v1/systemone`
  auth semantics (`401` + `WWW-Authenticate: Bearer`; no oracle).
- [contracts/config.md](./contracts/config.md) — new keys, precedence, secret masking.
- [contracts/mcp-tool.md](./contracts/mcp-tool.md) — unchanged tool schema; new error semantics.
- [quickstart.md](./quickstart.md) — six runnable end-to-end validation scenarios.

### Modules to change

| Module | Change |
|--------|--------|
| `ember/cfg/config.py` | Add `server_url`, `auth_token`, `auth_header`, `allow_insecure_transport`, `server_auth_token`, `request_timeout` to `DEFAULTS` |
| `ember/cfg/endpoint.py` (new) | Endpoint resolution, loopback classification, insecure-transport guard, credential-header construction, endpoint error types |
| `ember/mcp/mcp_server.py` | Async `advise` (`async def` + `httpx.AsyncClient`); endpoint resolution; credential header; error taxonomy; loopback-only autostart offloaded via `anyio.to_thread`; model-mismatch warning; remove `validate_server_url` |
| `ember/serving/server.py` | Additive `/health` `version` + `auth_required`; optional `HTTPBearer(auto_error=False)` dependency on `/v1/systemone`; `secrets.compare_digest`; `401` both cases; `/health` + `/metrics` stay open |
| `ember/cli.py` | `status`/`doctor` report endpoint kind/reachability/`auth_required`/`auth_configured`/local-server fields; `config show` masks secrets; `--server-url` flag |
| `packages/opencode-plugin/index.js` | Forward `EMBER_SERVER_URL`/`EMBER_AUTH_TOKEN`/`EMBER_AUTH_HEADER`/`EMBER_ALLOW_INSECURE_TRANSPORT`/`EMBER_REQUEST_TIMEOUT` into the MCP child env |
| `ember/mcp/mcp_types.py` | **Unchanged** (schema stays stable) |
| `README.md`, `SECURITY.md`, `RESPONSIBLE_USE.md`, `ember/agent_kit/*` | Document remote trust model; remove "never leaves your machine" prose |
| `.specify/memory/constitution.md` | Article I amendment + Sync Impact Report + version bump (prerequisite) |

### Tests to add

| Test file | Coverage |
|-----------|----------|
| `tests/test_endpoint.py` (new) | loopback classification, insecure-transport guard, header construction, timeout resolution, precedence (supersedes the removed `validate_server_url` tests) |
| `tests/test_http_api.py` | server auth on/off, `401` semantics, `/health`+`/metrics` open, `/health` `version`+`auth_required` |
| `tests/test_mcp_tool.py` | remote advise (bearer + custom header), media parity, single-destination, error taxonomy, model-mismatch warning, no remote autostart |
| `tests/test_cli.py` | status/doctor remote reporting, `config show` masking, local↔remote reversibility |
| `packages/opencode-plugin/index.test.js` | forwarded remote/auth env vars |

## Constitution Check — Post-Design Re-Evaluation

- **Article I**: still requires the planned amendment; a `Complexity Tracking` entry documents
  it. No other article is weakened.
- **Article III (agent contract)**: MCP tool schema unchanged; kit updates stay within the
  2048-byte instructions cap; README + tests updated together. PASS.
- **Article IV (lifecycle)**: autostart restricted to loopback; tests use random ports; no
  process killed by pattern. PASS.
- **Article V (pins)**: no dependency or model change. PASS.
- **Article VII / XI (verification, TDD)**: new tests land with the code; `make check` +
  `make test` gates. PASS.
- **Article XII (async-first)**: the MCP advise tool is converted to `async def` +
  `httpx.AsyncClient`; blocking autostart is offloaded via `anyio.to_thread` and tagged; the
  new server auth dependency is pure (no I/O); the engine route keeps its documented sync
  exception. PASS.
- **Article XIII (layering)**: shared endpoint helper lives in `cfg/`; server auth in
  `serving/`; MCP never imports torch/Engine. PASS.
- **Article XIV (pit of success)**: defaults unchanged; `401`/remote errors actionable; no
  crash when unconfigured. PASS.
- **Article XV (simplicity/YAGNI)**: single endpoint, single token, no new dependency, no
  profiles. PASS.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Article I — Local-First and Private | Remote inference requires sending `state` over the network and removing the “never leaves your machine” guarantee | Not supporting remote inference does not satisfy the feature requirement |
