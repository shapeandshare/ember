# Phase 0 Research: Remote Inference Servers

**Feature**: `001-remote-inference-servers`
**Date**: 2026-10-06
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

This file resolves the unknowns identified in the plan's Technical Context and records the
decisions, rationale, and alternatives for the remote-inference design.

## D1 — Constitution amendment (Article I, prerequisite)

**Decision**: Amend Article I ("Local-First and Private") from "inference MUST run on the
user's machine; the decision path MUST NOT send state over the network" to a
**local-first-by-default** principle: local inference remains the default and the only
behavior when no remote endpoint is configured; a user MAY explicitly configure a remote
endpoint, in which case state, questions, and answers are sent to that endpoint. The
amendment lands as a human-approved change with a Sync Impact Report block and a MAJOR
version bump (it redefines a principle).

**Rationale**: The feature's whole purpose is remote inference; the current Article I text
forbids it and the existing documentation ("never leaves your machine") is a false claim once
this ships. Governance requires principle changes to be explicit amendments, not silent
drift.

**Alternatives considered**:
- *Keep Article I and treat remote as an undocumented escape hatch* — rejected: contradicts a
  ratified principle and leaves false privacy claims in `RESPONSIBLE_USE.md`.
- *Add remote without touching the constitution* — rejected by Governance ("Agents MUST NOT
  weaken a principle to make work pass").

## D2 — Endpoint configuration shape and precedence

**Decision**: Represent the client's inference endpoint as a single configurable value,
`server_url`, resolved through the existing precedence
(`flag > env EMBER_SERVER_URL > config file > default http://127.0.0.1:8765`). Add default
keys to `ember/cfg/config.py`:

| Key | Env | Default | Meaning |
|-----|-----|---------|---------|
| `server_url` | `EMBER_SERVER_URL` | `http://127.0.0.1:8765` | Where the client sends advise requests |
| `auth_token` | `EMBER_AUTH_TOKEN` | unset (`None`) | Client credential (secret) |
| `auth_header` | `EMBER_AUTH_HEADER` | `Authorization` | Header carrying the credential |
| `allow_insecure_transport` | `EMBER_ALLOW_INSECURE_TRANSPORT` | `false` | Explicit override for plaintext to a non-local host |
| `server_auth_token` | `EMBER_SERVER_AUTH_TOKEN` | unset (`None`) | Optional token the server requires |

`server_url`/`auth_*` are read by the client (MCP + CLI); `server_auth_token` is read by the
HTTP layer.

**Rationale**: Matches the project's existing "flag > env > config > default" mechanism
(Article XIII §13.5 requires all layers to use `config.resolve`). Reuses one endpoint — no
profiles (FR-016, Clarification 3).

**Alternatives considered**: named endpoint profiles (rejected, Clarification 3, YAGNI);
separate host/port config for the remote client (rejected — a URL is the natural unit for a
possibly-TLS remote and mirrors `EMBER_SERVER_URL` already in use).

## D3 — Client credential header scheme

**Decision**: A single credential + header name. When `auth_header` is `Authorization`
(case-insensitive), send `Authorization: Bearer <token>`. Otherwise send `<auth_header>:
<token>` verbatim (e.g. `X-API-KEY: <token>`). Implement as header construction (not a custom
`httpx.Auth` subclass) because there is exactly one scheme at a time and no challenge/retry
flow.

**Rationale**: Directly satisfies Clarification 2. httpx accepts an arbitrary `dict[str, str]`
of headers, so both schemes are the same mechanism (encode/httpx docs). Header *name*
configurability mirrors the `auth_header_name` pattern used by `agno-agi/agno`.

**Alternatives considered**: `httpx.Auth` subclass (rejected — more machinery for a static
header, YAGNI); a boolean `use_bearer` flag (rejected — a header name is more expressive and
covers arbitrary gateways).

## D4 — Transport security for non-local endpoints

**Decision**: Classify the endpoint host as loopback or not. If non-loopback **and** scheme
is `http` (not `https`), refuse to send unless `allow_insecure_transport` is explicitly
true. Loopback hosts are always allowed over `http`. `is_loopback_host` returns true for
`localhost`, any address where `ipaddress.ip_address(host).is_loopback` is true, and
IPv4-mapped IPv6 loopback (`::ffff:127.0.0.1`).

**Rationale**: Satisfies FR-007 without breaking the default local `http://127.0.0.1:8765`.
The loopback algorithm matches the most complete OSS reference
(`headroomlabs-ai/headroom`, `vllm`/`fastapi` conventions).

**Known trade-off (documented, not silently resolved)**: `ipaddress` classifies **literals**
only. A DNS hostname other than `localhost` (e.g. `myhost.local` resolving to `127.0.0.1`) is
treated as non-loopback. We deliberately do **not** resolve DNS in the guard (TOCTOU /
DNS-rebinding risk; matches production practice), and we document it in the contract.

**Alternatives considered**: DNS resolution before classification (rejected — adds a
rebinding window and network I/O in a security check); allow `http` to any host (rejected —
violates FR-007).

## D5 — Client failure taxonomy

**Decision**: Distinguish failure classes using the httpx/stdlib exception surface, mapping
each to a distinct, actionable `ToolError` (and a distinct CLI message):

| Failure | Detected via | Message intent |
|---------|--------------|----------------|
| Unreachable | `httpx.ConnectError` whose `__cause__` is **not** an `ssl.SSLError`/`ssl.SSLCertVerificationError` | name endpoint; "unreachable" |
| Certificate | `httpx.ConnectError` whose `__cause__` **is** `ssl.SSLCertVerificationError`/`ssl.SSLError` | "TLS certificate verification failed" |
| Timeout | `httpx.TimeoutException` (incl. `ConnectTimeout`/`ReadTimeout`/`WriteTimeout`/`PoolTimeout`) | "timed out after Ns" |
| Auth | HTTP `401`/`403` response | "authentication failed" |
| Not ready / busy | HTTP `503` | surface server detail (model loading / queue full) |
| Too large | HTTP `413` | surface server detail |
| Malformed input | HTTP `422` | surface server detail |
| Incompatible response | `json.JSONDecodeError`, `UnicodeDecodeError` (and optionally a non-JSON content type) | "endpoint did not return a valid ember response" |
| Insecure transport | our `InsecureEndpointError` (pre-flight, D4) | "refusing plaintext to non-local host; set allow_insecure_transport" |

**Rationale**: httpx deliberately does **not** expose a distinct `SSLError`; a certificate
failure is the *same* class (`ConnectError`) as a refused connection, and the original
`ssl.SSLError` is preserved on `__cause__` (httpx docs + `map_httpcore_exceptions`). Caution:
`ssl.SSLCertVerificationError` is also a `ValueError` via MRO, so classify on the explicit
`ssl` type **before** any generic `ValueError` branch. Timeouts are siblings of
`NetworkError`, not subclasses.

**Alternatives considered**: string-matching the top-level httpx message (rejected — brittle;
research shows httpx changed hint strings across versions); treating all `ConnectError` as
"unreachable" (rejected — breaks FR-010's "distinct certificate failure").

## D6 — Server-side optional authentication

**Decision**: Protect only `POST /v1/systemone` with a FastAPI dependency built on
`HTTPBearer(auto_error=False)`. The dependency is a **no-op when `server_auth_token` is
unset** (behavior identical to today, honoring "auth can be disabled so hosters supply their
own layer"). When set, require a bearer token compared with `secrets.compare_digest`; return
`401` with `WWW-Authenticate: Bearer` for **both** a missing and a wrong token (same generic
detail, no oracle). `GET /health` and `GET /metrics` stay unauthenticated (matching vLLM's
documented security posture) so liveness/scraping keep working. The server does not terminate
TLS (FR-011); operators front it with a proxy.

**Rationale**: FastChat's `check_api_key` and vLLM's middleware both prove the
"config-absent = no-op" dependency shape; FastAPI's own docs teach `secrets.compare_digest`
for timing safety; every surveyed project returns `401` for both missing and invalid
credentials. Per-route `Depends` (vs prefix middleware) fits a single sensitive route and
keeps the protected surface visible at the route (Article XIII layering).

**Alternatives considered**: ASGI prefix middleware (rejected — more machinery than one
route needs, YAGNI); guarding `/health` too (rejected — breaks liveness probes and the
client's reachability check); distinct 403 for "present but wrong" (rejected — information
oracle, and all references use 401).

## D7 — Autostart and fallback behavior

**Decision**: Autostart (`process.start`) applies **only** when the endpoint is loopback.
For a remote endpoint the client never spawns a local server. If a remote endpoint is
unreachable, the client returns an actionable error and does **not** fall back to local
inference (FR-009, FR-010, edge case "autostart when endpoint remote").

**Rationale**: There is nothing local to start for a remote endpoint, and a silent fallback
would send state to an inference location the user did not choose. Satisfies FR-009/FR-010.

**Alternatives considered**: fall back to local on remote failure (rejected — surprising and
privacy-relevant); autostart a local server pointed at the same port for remote (nonsensical).

## D8 — Async-first posture for the touched code

**Decision**: Convert the MCP `advise` tool handler to `async def` and use
`httpx.AsyncClient` for the request (Article XII §12.3). The blocking local autostart
(`process.start`: subprocess + synchronous health polling) runs via
`anyio.to_thread.run_sync(_ensure_server)` so it never blocks the event loop, and is attempted
only for loopback endpoints. `_ensure_server` and `process.health` remain synchronous
(subprocess / worker-thread I/O) and carry an
`# async-first:exception - runs in a worker thread; subprocess + sync health probe` tag. The
new server-side auth dependency performs no I/O (config read + `secrets.compare_digest`), so
it is a pure synchronous function. The `POST /v1/systemone` route stays sync with its existing
`# async-first:exception - engine lock is synchronous` tag.

**Verified**: the pinned `mcp` `MCPServer.tool()` decorator supports `async def` handlers
(documented examples in its docstring).

**Rationale**: The MCP advise path is the agent hot path; async-first is the constitution's
default (Article XII) and was explicitly requested. Offloading autostart keeps the one
genuinely blocking operation off the loop without rewriting the subprocess lifecycle.

**Alternatives considered**: keep the client sync with a tag (rejected — request requires
async-first and `MCPServer` supports async tools); rewrite `process.py` to fully async
(rejected — larger blast radius; the subprocess lifecycle is inherently synchronous and
`to_thread` is the idiomatic bridge).

## D9 — Model mismatch reporting

**Decision**: After a successful response, compare the response `model` field with the
requested `model` label; when they differ, attach a non-fatal warning to the result the agent
sees (or to CLI output) rather than rewriting the label (FR-014).

**Rationale**: The server echoes the model it loaded; the client must not present a different
model as the requested one. Non-fatal because the answer is still valid advice.

**Alternatives considered**: hard error on mismatch (rejected — the remote's model may be an
acceptable sibling revision); silently echoing (rejected — violates FR-014).

## D10 — Secret hygiene in CLI output

**Decision**: `ember config show` masks `auth_token` and `server_auth_token` (e.g. render the
value as `"***"` when set, omit or null when unset). Credentials are never logged by the MCP
server, the HTTP server, or lifecycle code (FR-006, SC-003).

**Rationale**: `ember config show` prints the effective config today; once secrets live there,
printing them raw would leak them into terminals and agent transcripts.

**Alternatives considered**: print secrets (rejected — SC-003); separate secret file (rejected
— Clarification 4 permits config file + env).

## D11 — Request timeout configuration

**Decision**: Add `request_timeout` (env `EMBER_REQUEST_TIMEOUT`, default `300` seconds, int)
to the config defaults and use it as the httpx timeout for advise requests. A request that
exceeds it maps to the timeout failure class (D5) with the configured value named in the
message.

**Rationale**: FR-010/SC-004 require a bounded wait, but the earlier draft left it undefined.
The current MCP client hardcodes `timeout=300.0`; making it a config key preserves the default
while making the bound explicit and testable (FR-017).

**Alternatives considered**: leave the hardcoded 300 s (rejected — "bounded wait" untestable and
not user-tunable); a float timeout (avoided — `config.resolve` coerces int/bool defaults, not
float, so an int avoids changing the resolver's type logic).

## D12 — Health advertises contract version and auth requirement (extensibility)

**Decision**: Extend `GET /health` additively with `"version"` (ember's package version) and
`"auth_required"` (bool). The client and `status`/`doctor` read `auth_required` to report
whether a remote expects a credential, and report client-side `auth_configured` separately.
The client treats a missing/unknown `version` as "unknown", never an error.

**Rationale**: `/health` is unauthenticated by design, so it is the only place a client or a
third-party implementation can learn the remote's contract/auth expectations without a
credential. This closes the "caller version newer/older than remote contract" edge case and
makes the contract implementable by others.

**Alternatives considered**: a separate authenticated `/version` endpoint (rejected — extra
RTT and a route for one boolean); not advertising auth (rejected — status could not report a
remote's auth requirement truthfully).

## D13 — Remove loopback-only validation; forward client env through the plugin

**Decision**: Delete `validate_server_url` (and its `mcp_server.main()` startup call) plus its
8 tests in `tests/test_runtime_unit.py`; loopback classification moves to `is_loopback_host` in
`ember/cfg/endpoint.py`, and its tests in `tests/test_endpoint.py` supersede them. Update
`packages/opencode-plugin/index.js` to forward `EMBER_AUTH_TOKEN`, `EMBER_AUTH_HEADER`,
`EMBER_ALLOW_INSECURE_TRANSPORT`, and `EMBER_REQUEST_TIMEOUT` into the MCP child environment
(omit when unset), with matching assertions in `packages/opencode-plugin/index.test.js`.

**Rationale**: The loopback prohibition is the behavior being removed; leaving the helper and
its tests would make the suite contradict the feature. The plugin constructs an explicit child
`environment` map, so without forwarding the new vars an auth token set in the user's shell
would never reach `ember-mcp` — silently breaking remote auth for opencode users.

**Alternatives considered**: keep `validate_server_url` as a deprecated alias (rejected — dead
code, Article XV); rely on opencode passing the parent env (rejected — the plugin's own test
suite proves it builds an explicit map).

## Resolved unknowns from Technical Context

All Technical Context entries are now concrete; no `NEEDS CLARIFICATION` remains. New
dependencies: none (httpx, FastAPI, pydantic, prometheus-client already pinned).
