---
title: "Remote inference servers: opt-in, any endpoint, disableable server auth"
type: decision
tags:
  - type/decision
  - domain/mcp
  - domain/server
  - domain/governance
  - status/draft
created: "2026-10-06"
updated: "2026-10-06"
code-refs:
  - ember/cfg/endpoint.py
  - ember/cfg/config.py
  - ember/mcp/mcp_server.py
  - ember/serving/server.py
  - ember/cli.py
  - packages/opencode-plugin/index.js
  - .specify/memory/constitution.md
---

# Remote inference servers: opt-in, any endpoint, disableable server auth

Part of [[ember]]. ember's client may send advise requests to a single configured remote
endpoint; local stays the default, the server gains optional bearer auth that can be disabled,
and Article I was amended to "Local-First by Default" (constitution v2.0.0).

## Context

The model needs more unified memory/disk than many hosts have (the org's 8 GiB CI VMs cannot
hold it), so users needed to point the agent at a decision model running elsewhere. The prior
design hard-enforced loopback (`validate_server_url`) and both the constitution (Article I) and
`RESPONSIBLE_USE.md` promised state never left the machine. The feature
`specs/001-remote-inference-servers/` was specified and planned before implementation.

## Decision

- **Any endpoint, no approval gate.** The client sends to whatever `server_url` the operator
  configures; the loopback-only helper and its tests were removed. Prose claiming state "never
  leaves your machine" was corrected.
- **Transport guard.** Plaintext `http` to a non-loopback host is refused unless
  `EMBER_ALLOW_INSECURE_TRANSPORT` is set. `is_loopback_host` (localhost, 127.0.0.0/8, ::1,
  IPv4-mapped IPv6) lives in `ember/cfg/endpoint.py`.
- **Client credentials.** `auth_token` + `auth_header`; `Authorization` sends
  `Bearer <token>`, any other header sends the token verbatim. Env beats config; secrets are
  masked in `ember config show` and never logged.
- **Server auth is optional and disableable.** `server_auth_token` unset means no auth
  (delegate to a proxy). When set, only `POST /v1/systemone` requires a bearer token, compared
  with `secrets.compare_digest`; `/health` and `/metrics` stay open, and `/health` advertises
  `version` + `auth_required`. Ember does not terminate TLS.
- **Async-first client.** The MCP `advise` tool is `async def` with `httpx.AsyncClient`;
  blocking local autostart runs via `anyio.to_thread`.
- **Autostart is loopback-only**, remote failures never fall back to local, and `request_timeout`
  (default 300 s) bounds a request.
- **Plugin forwarding.** The opencode plugin builds an explicit child environment, so it now
  forwards the remote/auth env vars.

## Consequences

- An unconfigured install is byte-for-byte the old local-only behavior; reverting is unsetting
  the remote keys.
- Remote operators must supply TLS (proxy) and, if they disable ember auth, their own access
  control.
- The remote HTTP contract is documented for third-party implementations in
  `specs/001-remote-inference-servers/contracts/http-api.md`.
- The MCP tool input schema is unchanged; the result gains only an optional `warning`.
