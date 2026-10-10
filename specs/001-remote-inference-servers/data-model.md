# Phase 1 Data Model: Remote Inference Servers

**Feature**: `001-remote-inference-servers`
**Date**: 2026-10-06

Entities are expressed at the level the feature spec uses (inference endpoint, credentials,
remote-serving configuration, endpoint status). Implementation types are noted where they
cross a layer boundary; per Article X, cross-layer data is a Pydantic `BaseModel` or a plain
`dict`.

## 1. Inference endpoint

Represents where advise requests are sent.

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `url` | `str` | `config.resolve("server_url")` | Full base URL, e.g. `http://127.0.0.1:8765` |
| `host` | `str` | parsed from `url` | Hostname or IP literal |
| `scheme` | `str` | parsed from `url` | `http` or `https` |
| `is_local` | `bool` | computed via `is_loopback_host(host)` | Loopback ⇒ local |
| `allow_insecure_transport` | `bool` | `config.resolve("allow_insecure_transport")` | Explicit override |
| `request_timeout` | `int` (seconds) | `config.resolve("request_timeout")` | Default `900` (`300` until 2026-10-10); bounds each advise request, local or remote |

**Validation rules**

- `url` MUST be a well-formed absolute URL with an `http`/`https` scheme (else
  `InvalidEndpointError`).
- If `not is_local and scheme == "http" and not allow_insecure_transport` →
  `InsecureEndpointError` (FR-007), raised **before** any request is constructed.
- `is_loopback_host` is true for `localhost`, `ipaddress.ip_address(host).is_loopback`, and
  IPv4-mapped IPv6 loopback (`::ffff:127.0.0.1`). DNS hostnames other than `localhost` are
  treated as non-local (documented trade-off; no DNS resolution).

**Lifecycle / state transitions**

`resolved → (validated) → in use`. Invalid endpoints never reach "in use".

## 2. Endpoint credentials

Represents the client credential presented to the endpoint.

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `token` | `str \| None` | `config.resolve("auth_token")` | Secret; never logged/serialized |
| `header` | `str` | `config.resolve("auth_header")`, default `Authorization` | Header name |
| `scheme` | `"bearer" \| "raw"` | derived | `bearer` iff `header.lower() == "authorization"`, else `raw` |
| `source` | `"env" \| "config" \| "none"` | derived from resolution | For status/reporting only (never the value) |

**Validation rules**

- `token is None` ⇒ no credential is attached (unauthenticated request).
- Rendered header value: `Bearer <token>` when `scheme == "bearer"`, else `<token>` verbatim
  (Clarification 2, FR-005).
- Environment variable takes precedence over the config file (Clarification 4) — achieved via
  `config.resolve` (`EMBER_AUTH_TOKEN` wins).
- The token value MUST NOT appear in logs, error messages, `ember config show`, status output,
  or MCP tool output (FR-006, SC-003, D10).

## 3. Remote-serving configuration (server side)

Represents the operator-side settings of a running ember server.

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `host` | `str` | `config.resolve("host")` | Loopback by default; non-loopback ⇒ remote-serving |
| `port` | `int` | `config.resolve("port")` | |
| `auth_token` | `str \| None` | `config.resolve("server_auth_token")` | `None` ⇒ auth disabled (delegate) |
| `remote_enabled` | `bool` | derived: `not is_loopback_host(host)` | Reported by status/doctor |

**Validation / behavior rules**

- `auth_token is None` ⇒ `POST /v1/systemone` unauthenticated (behavior identical to today)
  (FR-011, Clarification 2).
- `auth_token` set ⇒ require `Authorization: Bearer <token>`; compare with
  `secrets.compare_digest`; on missing **or** wrong token return `401` +
  `WWW-Authenticate: Bearer` with a single generic detail (D6).
- `GET /health` and `GET /metrics` are always unauthenticated (D6).
- The server never terminates TLS; `host` on a non-loopback interface is expected to sit behind
  an operator proxy (FR-011, Assumption).
- Default `host` is `127.0.0.1` ⇒ remote-serving off by default (FR-011).

## 4. Endpoint status

Reported health surfaced by `ember status` / `ember doctor`.

| Field | Type | Notes |
|-------|------|-------|
| `kind` | `"local" \| "remote"` | From endpoint classification |
| `url` | `str` | Configured endpoint (no secrets) |
| `reachable` | `bool` | `/health` responded |
| `ready` | `"ok" \| "loading"` | Server `/health` `status` field |
| `contract_version` | `str \| None` | Server `/health` `version` (None if absent/unreachable) |
| `remote_auth_required` | `bool \| None` | Server `/health` `auth_required` (None if unreachable) |
| `auth_configured` | `bool` | Client has `auth_token` set for the endpoint |
| `server_remote_enabled` | `bool` | For the local server: binds non-loopback |
| `server_auth_required` | `bool` | For the local server: `server_auth_token` is set |

**Validation rules**

- Status output MUST NOT include the token value (FR-006).
- Status MUST NOT claim to have verified credentials against a remote; `/health` is
  unauthenticated, so only "the remote advertises auth required" (`remote_auth_required`) and
  "the client has a credential configured" (`auth_configured`) are knowable (FR-012).
- When the endpoint is remote, `server_remote_enabled`/`server_auth_required` describe the
  local server (if any), clearly labelled, not the remote.

## Cross-layer data contracts

- The MCP `AdviseInput` schema is **unchanged** (no new tool fields). Remote behavior is a
  function of configuration, not of tool input, so the published agent contract stays stable
  (FR-008).
- The HTTP request/response bodies (`AdviseRequest`, SystemOne response) are **unchanged**;
  only an optional `Authorization` header is added on the request side and a `401` is added to
  the response surface.
- No torch tensors, processor objects, or internal runtime state cross any boundary.

## Entities vs. requirements traceability

| Entity | Requirements |
|--------|--------------|
| Inference endpoint | FR-001, FR-002, FR-003, FR-004, FR-007, FR-016 |
| Endpoint credentials | FR-005, FR-006, SC-003 |
| Remote-serving configuration | FR-011, FR-012, SC-006 |
| Endpoint status | FR-012, FR-014 |
