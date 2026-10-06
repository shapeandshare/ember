# Contract: ember HTTP API (remote-serving changes)

**Feature**: `001-remote-inference-servers`
**Date**: 2026-10-06
**Scope**: Additions/changes to `ember/serving/server.py`. The request/response bodies are
otherwise unchanged from today.

## Endpoints

### `GET /health`

- **Auth**: never required.
- **Response `200`**: `{"status": "ok" | "loading", "pid": <int>, "engine": <object|null>, "version": <str>, "auth_required": <bool>}`. `version` (the package version) and `auth_required` (whether `server_auth_token` is set) are **additive** in this feature.
- Rationale: liveness probes and the client's reachability check must work regardless of auth; `/health` is also the only unauthenticated place a client or third-party implementation can learn the remote's contract and auth expectation (FR-019).

### `GET /metrics`

- **Auth**: never required.
- **Response `200`**: unchanged Prometheus exposition.
- Rationale: scraping stays functional when remote-serving auth is enabled.

### `POST /v1/systemone`

- **Auth**: required **iff** `server_auth_token` is configured; otherwise unchanged (no auth).
- **Request body**: unchanged (`AdviseRequest`); no new fields.
- **Request headers (when auth enabled)**: `Authorization: Bearer <token>`.
- **Success `200`**: unchanged SystemOne response.
- **Failure surface** (unchanged statuses plus one new):

| Status | Condition | Body |
|--------|-----------|------|
| `401` | auth enabled and header missing **or** token wrong | generic detail, e.g. `{"detail": "Not authenticated"}`, header `WWW-Authenticate: Bearer` |
| `413` | input exceeds per-request cap | unchanged |
| `422` | malformed questions/media/kwargs | unchanged |
| `503` | model not loaded yet, or admission queue full | unchanged |

## Auth semantics (precise)

1. `server_auth_token` unset ⇒ no `Authorization` handling; identical to current behavior.
2. `server_auth_token` set:
   - Parse the request's `Authorization` header (scheme must be `Bearer`).
   - Compare the presented token with the configured token using
     `secrets.compare_digest(received.encode(), expected.encode())`.
   - Missing header, wrong scheme, or wrong token ⇒ **one** generic `401` response with
     `WWW-Authenticate: Bearer`. Missing and invalid are deliberately indistinguishable
     (no oracle).
3. Comparison is constant-time; the token value is never logged.

## Async posture

- `POST /v1/systemone` remains a synchronous handler carrying
  `# async-first:exception - engine lock is synchronous` (Article XII §12.2); the engine lock
  is synchronous by design.
- The server auth dependency performs no I/O (config read + `secrets.compare_digest`) and is a
  pure synchronous function (no tag needed).
- The **client** advise path is `async def` with `httpx.AsyncClient`; blocking local autostart
  is offloaded with `anyio.to_thread` (Article XII §12.3). See [contracts/mcp-tool.md](./mcp-tool.md).

## Third-party implementation (extensibility)

A conforming remote server is any HTTP service that:

1. Implements `POST /v1/systemone` with the SystemOne request/response bodies (unchanged),
   returning `200` on success and `413`/`422`/`503` on the documented failures.
2. Implements `GET /health` returning at least `status` (`"ok"`/`"loading"`); `version` and
   `auth_required` are recommended so ember's client and status can reason about it.
3. Optionally enforces `Authorization: Bearer <token>` on `/v1/systemone` (and may rely on a
   proxy for TLS).

ember's client requires only (1) and `status` in (2); a missing `version`/`auth_required`
degrades to "unknown", never an error. The contract is intentionally implementable without
ember so other teams can host decision servers behind it. Contract changes are additive within
`v1`; a breaking change would introduce a new path or `version` signal.

## Non-goals in this contract

- No TLS termination server-side (operator proxy responsibility).
- No change to `/v1/systemone` request/response schema.
- No change to `/health` or `/metrics` auth posture.
- No multi-token/allow-list support (single token; YAGNI).
- **No custom-header validation server-side**: ember's server checks only
  `Authorization: Bearer`. A client configured with a custom header (e.g. `X-API-KEY`) must
  point at a proxy/gateway that accepts it and translates to the bearer header.

## Client-side counterpart (for reference)

The ember client (`ember/mcp/mcp_server.py`, `ember/cli.py`) targets these endpoints. The client
does **not** health-probe a **remote** endpoint before an advise call (only loopback endpoints
are probed, to autostart a local server); a remote advise call goes straight to
`POST /v1/systemone` and maps failures via the error taxonomy. `GET /health` is used only by
`status`/`doctor` and for the loopback readiness check, so a remote server's contract/auth can
be inspected without a credential.

## References

- Research decisions D4, D5, D6 ([research.md](../research.md)).
- Data model §3 ([data-model.md](../data-model.md)).
- Spec FR-007, FR-011, SC-006.
