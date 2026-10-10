# Contract: ember configuration (remote-inference additions)

**Feature**: `001-remote-inference-servers`
**Date**: 2026-10-06
**Scope**: New keys in `ember/cfg/config.py` `DEFAULTS` and their precedence. This is a public
contract: keys, env names, and defaults are documented in README and must change together
with tests.

## Precedence

Unchanged and applied to every key:
**command-line flag > environment variable (`EMBER_*`) > config file JSON > default.**

## New keys

| Key | Env var | Type | Default | Consumer | Secret |
|-----|---------|------|---------|----------|--------|
| `server_url` | `EMBER_SERVER_URL` | str (URL) | `http://127.0.0.1:8765` | client (MCP, CLI) | no |
| `auth_token` | `EMBER_AUTH_TOKEN` | str | unset (`None`) | client | **yes** |
| `auth_header` | `EMBER_AUTH_HEADER` | str | `Authorization` | client | no |
| `allow_insecure_transport` | `EMBER_ALLOW_INSECURE_TRANSPORT` | bool | `false` | client | no |
| `request_timeout` | `EMBER_REQUEST_TIMEOUT` | int (seconds) | `900` | client | no |
| `server_auth_token` | `EMBER_SERVER_AUTH_TOKEN` | str | unset (`None`) | server (HTTP) | **yes** |

Existing keys (`model`, `host`, `port`, `device`, `max_length`, `max_request_length`) are
unchanged. `host`/`port` continue to configure the **local** server bind; `server_url`
configures where the **client** sends requests. They may point at the same local server
(default) or a different remote one.

## Behavior rules

- `server_url` host is classified local/remote (loopback check). A non-loopback `http://` URL
  is rejected at client startup unless `allow_insecure_transport` is true (FR-007).
- `auth_token` + `auth_header` produce exactly one credential header per request:
  - `auth_header` == `Authorization` (case-insensitive) ⇒ `Authorization: Bearer <token>`.
  - otherwise ⇒ `<auth_header>: <token>`. A custom header is intended for an endpoint or proxy
    that accepts it; ember's built-in server auth validates only `Authorization: Bearer`
    (see [contracts/http-api.md](./http-api.md)), so a custom header normally pairs with an
    operator-managed proxy/gateway.
- `request_timeout` bounds each advise request; exceeding it yields the timeout failure class
  (research D5) naming the configured value. Default `900`; it was `300` until 2026-10-10,
  when it rose so that a request at full's 65,536-token default can finish.
- Environment variable wins over the config file for the same key (Clarification 4).
- `server_auth_token` unset ⇒ server auth disabled (delegate to proxy); set ⇒ server requires
  `Authorization: Bearer <token>` on `POST /v1/systemone` only.

## Secret handling (public contract)

- `ember config show` MUST mask `auth_token` and `server_auth_token` (render set values as
  `"***"`, keep unset as `null`). The config file may still contain them in cleartext, but no
  command prints them.
- Status/doctor output MUST NOT print token values.
- Server logs MUST NOT include tokens or the `Authorization` header value.

## Consumers

The opencode plugin (`packages/opencode-plugin/`) builds an **explicit** child environment and
so MUST forward `EMBER_SERVER_URL`, `EMBER_AUTH_TOKEN`, `EMBER_AUTH_HEADER`,
`EMBER_ALLOW_INSECURE_TRANSPORT`, and `EMBER_REQUEST_TIMEOUT` (omitting keys that are unset).
Without forwarding, remote/auth settings in the user's shell never reach `ember-mcp` (FR-020).
Direct `ember mcp` invocations inherit the shell environment and need no change.

## Glossary

- **endpoint** / **`server_url`**: where the client sends advise requests (default loopback).
- **local / remote**: loopback vs. non-loopback endpoint host.
- **server auth** / **`server_auth_token`**: optional bearer token ember's own server requires.
- **client credential** / **`auth_token`**: token the client presents to an endpoint.

## Back-compat

- An existing install with no remote keys set resolves `server_url` to the loopback default and
  behaves exactly as today.
- `EMBER_SERVER_URL` semantics are unchanged in name; the value is now validated for transport
  security rather than rejected purely for being non-loopback.
- Reverting to local-only is a single change: unset/omit the remote keys.

## References

- Research D2, D3, D4, D10 ([research.md](../research.md)).
- Data model §2, §3 ([data-model.md](../data-model.md)).
- Spec FR-002, FR-005, FR-006, FR-007, FR-016; Clarifications 1–4.
