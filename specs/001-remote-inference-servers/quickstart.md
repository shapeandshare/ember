# Quickstart Validation: Remote Inference Servers

**Feature**: `001-remote-inference-servers`
**Date**: 2026-10-06

Runnable scenarios that prove the feature end-to-end. This is a validation/run guide; it does
**not** contain implementation bodies or the full test suite (those belong in `tasks.md` and
the implementation phase). See [contracts/](./contracts/) and [data-model.md](./data-model.md)
for exact semantics.

## Prerequisites

- Apple Silicon macOS with the pinned weights pulled (`make download`) — the model server
  tested here runs locally but is treated as "remote" by pointing the client at a random port.
- Dev environment ready: `uv sync` (or `make setup`).
- **Isolation rules (Article IV)**: never use port `8765`; bind a random free port; start/stop
  only processes you launched.

## Scenario 1 — Client → remote endpoint with a bearer token

1. Start a server on a random port with server-side auth enabled:
   ```bash
   PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')
   EMBER_PORT=$PORT EMBER_SERVER_AUTH_TOKEN=secret-token ember serve &
   ```
2. Point the client at it with a bearer token:
   ```bash
   EMBER_SERVER_URL="http://127.0.0.1:$PORT" \
   EMBER_AUTH_TOKEN=secret-token \
   EMBER_AUTOSTART=0 \
   python -m ember.mcp.mcp_server   # driven by an MCP client (or the CLI path)
   ```
   Or exercise the CLI status path:
   ```bash
   EMBER_SERVER_URL="http://127.0.0.1:$PORT" EMBER_AUTH_TOKEN=secret-token \
     ember status --server-url "http://127.0.0.1:$PORT"
   ```
3. **Expected**: the advise call succeeds; the credential is sent as
   `Authorization: Bearer secret-token` (per [contracts/config.md](./contracts/config.md)); no
   token appears in any log, status output, or tool output.

## Scenario 2 — Custom header credential (`X-API-KEY`)

ember's built-in server validates only `Authorization: Bearer`, so this scenario targets a
**stub/proxy that accepts the custom header** (as a gateway in front of ember would).

1. Start a stub HTTP endpoint on a random port that records the received `X-API-KEY` header
   (the automated test uses a small in-test server).
2. Configure the client:
   ```bash
   EMBER_AUTH_HEADER=X-API-KEY EMBER_AUTH_TOKEN=secret-token \
   EMBER_SERVER_URL="http://127.0.0.1:$PORT" EMBER_AUTOSTART=0 ...
   ```
3. **Expected**: the credential is sent as `X-API-KEY: secret-token` (not
   `Authorization: Bearer …`), and the stub observes it.

## Scenario 3 — Auth enabled: valid vs missing token

1. With the Scenario 1 server (auth enabled), `POST /v1/systemone` without a token:
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' -X POST "http://127.0.0.1:$PORT/v1/systemone" \
     -H 'content-type: application/json' \
     -d '{"state":"x","questions":{"q":{"type":"noul"}}}'
   ```
2. **Expected**: `401`, with `WWW-Authenticate: Bearer`. With a valid token the same call
   returns `200`. Missing and wrong tokens are indistinguishable (both `401`).

## Scenario 4 — Auth disabled: delegate to upstream

1. Start a server on a random port **without** `EMBER_SERVER_AUTH_TOKEN`.
2. `POST /v1/systemone` with no credential.
3. **Expected**: `200` (no ember-side check); behavior identical to today. Status/doctor reports
   authentication as not required / delegated.

## Scenario 5 — Plaintext non-local rejection and explicit override

1. Point the client at a non-loopback `http://` endpoint (e.g. `http://192.0.2.1:8765`):
   ```bash
   EMBER_SERVER_URL="http://192.0.2.1:8765" EMBER_AUTOSTART=0 ... advise ...
   ```
2. **Expected**: refused with an actionable insecure-transport message; no request is sent.
3. Re-run with `EMBER_ALLOW_INSECURE_TRANSPORT=true`:
   **Expected**: the guard is bypassed (the connection may then fail as unreachable, which is a
   distinct message).

## Scenario 6 — Remote failure taxonomy

Start the client pointed at a closed port on loopback (`http://127.0.0.1:<closed>`), an
`https` endpoint with a bad certificate, a mock endpoint returning non-JSON, and a slow
endpoint with `EMBER_REQUEST_TIMEOUT=1`.
**Expected**: distinct actionable messages (unreachable / certificate / incompatible response /
timeout naming the configured 1 s), and **no** fallback to local inference. Autostart is never
attempted for a remote endpoint.

## Automated coverage (implemented in `tasks.md`)

| Test file | Scenarios |
|-----------|-----------|
| `tests/test_endpoint.py` (new) | loopback classification, insecure-transport guard, header construction, config precedence (1, 2, 5) |
| `tests/test_http_api.py` | server auth on/off, 401 semantics, `/health` + `/metrics` open (3, 4) |
| `tests/test_mcp_tool.py` | remote advise with bearer/custom header, error taxonomy, no autostart (1, 2, 6) |
| `tests/test_cli.py` | status/doctor remote reporting, `config show` masking (3, 4) |

Run the gates: `make check` (fast) then `make test` (model-backed, local only).

## Success signal

All six scenarios behave as described, `make test` passes, and the docs (`SECURITY.md`,
`RESPONSIBLE_USE.md`, README, agent kit) describe the remote trust model with no residual
"never leaves your machine" claim.
