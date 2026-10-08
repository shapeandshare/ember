# Contract: Anaconda-Hosted Endpoint (Remote Inference)

**Feature**: `002-anaconda-models-provider`
**Scope**: The contract for reaching an Anaconda-hosted decision-model endpoint (spec User
Story 3; FR-006, FR-007; data-model.md "Entities inherited unchanged"). This contract adds
**no new fields and no new behavior** beyond
`specs/001-remote-inference-servers/contracts/` — it exists to make explicit that the
Anaconda-hosted case is fully covered by the already-shipped generic remote-endpoint contract
(research R5), not to define anything new.

## Contract

1. **No new configuration keys.** An Anaconda-hosted endpoint is configured with the existing
   `server_url`, `auth_token`, `auth_header`, `allow_insecure_transport`, and
   `request_timeout` keys (`ember/cfg/config.py` `DEFAULTS`, unchanged), through the existing
   flag > env > config-file > default precedence (`ember/cfg/config.py` `resolve()`,
   unchanged).
2. **No auto-detection.** ember MUST NOT inspect its runtime environment to infer it is
   running on Anaconda's platform and MUST NOT switch to any endpoint without the user (or
   the platform's own bootstrap step) explicitly setting `server_url`/credentials
   (spec Clarification 5, FR-007). Explicit configuration is the only activation path.
3. **Same transport-security rule, no exemption.** An Anaconda-hosted endpoint is classified
   as loopback or non-loopback by the existing `is_loopback_host()` (`ember/cfg/endpoint.py`),
   and if non-loopback, plaintext HTTP is refused unless `allow_insecure_transport` is
   explicitly set — identical to any other remote endpoint, with **no hostname-based or
   vendor-based exemption**.
4. **Same credential scheme.** An Anaconda-issued token is carried via `build_auth_headers()`
   (`ember/cfg/endpoint.py`, unchanged): `Authorization: Bearer <token>` when `auth_header` is
   `Authorization` (the default), or `<auth_header>: <token>` otherwise.
5. **Same failure taxonomy.** Unreachable, certificate, timeout, auth, not-ready, too-large,
   malformed-input, and incompatible-response failures against an Anaconda-hosted endpoint
   MUST map to the same distinct, actionable error classes already defined in
   `specs/001-remote-inference-servers/research.md` D5 — no Anaconda-specific error class.
6. **Same autostart suppression.** Because an Anaconda-hosted endpoint is non-loopback,
   `process.start` (local autostart) MUST NOT be attempted for it (existing behavior,
   `specs/001-remote-inference-servers/research.md` D7).
7. **Observability.** `ember doctor` / `/health` MUST report that a configured Anaconda-hosted
   endpoint is in use (reusing the existing endpoint-status reporting in
   `ember/commands/doctor.py` / `ember/commands/endpoint.py`, unchanged) so a user can always
   tell whether requests are local or remote (spec FR-005, SC-004).

## Out of scope for this contract

- Any Anaconda-specific authentication scheme beyond the existing bearer/custom-header
  mechanism.
- Any mechanism for ember to discover an Anaconda-hosted endpoint URL on its own.
- Any change to `ember/serving/server.py`'s server-side auth (that governs ember's *own*
  server when it hosts remotely; an Anaconda-hosted endpoint is a server ember does not run).
