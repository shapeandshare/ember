# Contract: MCP `advise` tool (remote-inference changes)

**Feature**: `001-remote-inference-servers`
**Date**: 2026-10-06
**Scope**: `ember/mcp/mcp_server.py` and `ember/mcp/mcp_types.py`. The tool **schema is
unchanged**; only transport behavior and error semantics change.

## Tool schema (UNCHANGED — public API)

`advise(input: AdviseInput)` remains wrapped in `input`. Fields `state`, `questions`, `model`,
`images`, `videos`, `media_kwargs` are unchanged. No new tool parameters. Rationale: remote
behavior is a function of configuration, not of the agent's call; changing the schema would
break the published agent contract (Article III).

## Behavior changes

| Aspect | Before | After |
|--------|--------|-------|
| Endpoint | `EMBER_SERVER_URL`, loopback-only enforced | `server_url` via `config.resolve`; loopback and remote allowed |
| Transport | loopback only | non-loopback requires `https` unless `allow_insecure_transport` |
| Credentials | none | optional bearer/custom header per `contracts/config.md` |
| Autostart | start local server if down | only when endpoint is loopback; remote never autostarts or health-probes first |
| Fallback | n/a | none — remote failure does not fall back to local |
| Model label | echoed | mismatch vs. requested label reported as a non-fatal warning |
| Async | sync `httpx.post` | `async def` handler + `httpx.AsyncClient`; blocking autostart via `anyio.to_thread` |

## Result shape

The success result is the SystemOne response unchanged, plus `latency_ms`. This feature adds an
**optional** `warning` string field when the endpoint's loaded model differs from the requested
label (FR-014). It is additive; consumers that ignore unknown fields are unaffected. The warning
is also logged to stderr.

## Error semantics (agent-visible `ToolError`)

Only `ToolError` messages reach the agent (existing convention). Distinct, actionable messages:

- **Insecure endpoint**: "refusing to send to non-local http endpoint `<url>`; use https or set
  `allow_insecure_transport`."
- **Unreachable**: "ember server not reachable at `<url>`" (no autostart attempt for remote).
- **Certificate**: "TLS certificate verification failed for `<url>`."
- **Timeout**: "ember server timed out after `<n>`s at `<url>`."
- **Authentication**: "ember server authentication failed (401) at `<url>`; check
  `auth_token`/`auth_header`."
- **Not ready** (`503`): surface the server's detail (model loading / queue full).
- **Too large** (`413`) / **malformed** (`422`): surface the server's detail.
- **Incompatible response**: "endpoint at `<url>` did not return a valid ember response."
- **Version compatibility**: a remote's `/health` `version` is read by `status`/`doctor`
  (`contract_version`), not on the advise hot path (remote advise does not health-probe first);
  an unknown/older version degrades to "unknown", never a failed call (extensibility, D12).

## Unchanged guarantees

- The MCP process never imports torch or loads a model (Article XIII §13.1).
- `ember://guide`, `initialize.instructions`, and the `ember-advise` skill keep working; remote
  guidance is added within the `instructions.md` 2048-byte cap (Article III §3.2).
- stdout remains the JSON-RPC wire; diagnostics go to stderr.

## References

- Research D3, D4, D5, D7, D8, D9 ([research.md](../research.md)).
- Spec FR-004, FR-005, FR-008, FR-009, FR-010, FR-014.
