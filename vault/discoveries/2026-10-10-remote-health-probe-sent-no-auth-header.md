---
title: "ember status/doctor's remote health probe sent no auth header"
type: discovery
tags:
  - type/discovery
  - domain/cli
  - status/draft
created: "2026-10-10"
updated: "2026-10-10"
code-refs:
  - ember/commands/endpoint.py
  - tests/test_cli.py
---

# ember status/doctor's remote health probe sent no auth header

Part of [[ember]]. `ember status`/`ember doctor` always reported a gateway-authenticated
remote endpoint (e.g. the Outerbounds deployment fixed in
[[2026-10-10-remove-t004-non-loopback-auth-check]]) as `reachable: false`, even when the
deployment was fully healthy and reachable with `curl` plus the correct credential header.

## What was tested

Ran `ember status` against the live Outerbounds endpoint (`EMBER_SERVER_URL`,
`EMBER_AUTH_HEADER=x-api-key`, `EMBER_AUTH_TOKEN` exported) and got
`"reachable": false, "ready": null`. A direct `curl -H "x-api-key: $TOKEN" .../health`
against the same URL returned `200 {"status":"ok", ...}` — the deployment was genuinely
healthy; only the CLI's own probe disagreed.

Traced `ember/commands/endpoint.py::remote_health()`: it calls `httpx.get(f"{endpoint.url}/health",
timeout=...)` with no `headers` argument at all. `ember/mcp/mcp_server.py`'s real `advise`
call path (line 261) already calls `build_auth_headers()` and sends it, but
`remote_health()` never did — these are two independent HTTP call sites that diverged.

## Finding

Any remote deployment that gates `/health` behind the same auth as `/v1/systemone` (ember's
own `EMBER_SERVER_AUTH_TOKEN`, or — as here — a platform gateway like Outerbounds'
`auth.type: API` that authenticates every request before it reaches the pod, including
`/health`) will always be reported unreachable by `ember status`/`ember doctor`, regardless
of actual health. This is purely a client-side reporting bug: inference itself
(`/v1/systemone` through the real MCP path) was never affected, since `mcp_server.py`
already sends the credential correctly.

## Relevance

Fixed by calling `build_auth_headers()` in `remote_health()` (same function the real advise
path uses), so the status/doctor probe and the real inference call now authenticate
identically. `ember doctor`'s "limits: unknown; remote endpoint unreachable" line
(`ember/commands/doctor.py:215`) and the reachability checks a user runs before trusting a
remote endpoint were silently wrong for any gateway-authenticated deployment until now.
Regression test: `tests/test_cli.py::test_remote_health_sends_configured_auth_header`.

## References

- `ember/commands/endpoint.py::remote_health` — the fix.
- `ember/cfg/endpoint.py::build_auth_headers` — the shared helper, already correctly used by
  `ember/mcp/mcp_server.py`.
- [[2026-10-10-remove-t004-non-loopback-auth-check]] — the deployment this was discovered
  against.
