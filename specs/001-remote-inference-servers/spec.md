# Feature Specification: Remote Inference Servers

**Feature Branch**: `001-remote-inference-servers`

**Created**: 2026-10-06

**Status**: Draft

**Input**: User description: "we must support remote inference servers for our decision models"

## Clarifications

### Session 2026-10-06

- Q: How should a remote endpoint become "approved" before ember will send state, questions, or media to it? → A: Allow any endpoint — no allow-list or approval gate; remove documentation prose claiming state "never leaves your machine."
- Q: Should ember's own server provide authentication and encryption for remote-serving mode? → A: Optional bearer-token authentication in the server, disableable so hosters can supply their own auth layer; TLS terminated by an operator-managed proxy; the client supports either a bearer token or a custom header such as `X-API-KEY`.
- Q: Should remote support be a single configurable endpoint, or named endpoint profiles with a selected default and per-invocation choice? → A: A single configurable endpoint, generalizing the current server URL; local remains the default.
- Q: Where should a remote endpoint's credential be supplied from? → A: Either an environment variable or the configuration file, with the environment variable taking precedence.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Send advice requests to a remote inference endpoint (Priority: P1)

A person who cannot run the decision model on their own machine — because it needs more
unified memory or disk than they have, or because they are on a CI host — points ember at an
inference server running elsewhere (another machine they own, a shared team host, or a private
cloud host). Their agent calls the `advise` tool exactly as before and receives the same
calibrated probabilities, with no local model loaded.

**Why this priority**: This is the feature. Every other story only shapes how the remote path
is secured, operated, or surfaced. Without it there is nothing to secure or operate.

**Independent Test**: Configure an endpoint that is not the local model server, call `advise`
through the agent tool and through the CLI, and confirm answers are returned in the same shape
as local answers while no model is loaded on the client machine.

**Acceptance Scenarios**:

1. **Given** no local model is present and a reachable inference endpoint is configured,
   **When** an agent calls the `advise` tool, **Then** a valid answer is returned from the
   remote endpoint.
2. **Given** the same configured endpoint, **When** an ember client sends the same advise
   request through it, **Then** the result matches the shape and semantics returned locally
   (leading option, confidence, full probabilities / expected score / P(true)).
3. **Given** the remote endpoint is configured, **When** ember starts,
   **Then** ember does not attempt to load or start a local model server.

---

### User Story 2 - Authenticate to the remote endpoint (Priority: P2)

A person directing ember at a remote endpoint supplies credentials so the remote can verify
the caller — either as a bearer token or as a custom request header (for example `X-API-KEY`).
Requests are sent to whatever endpoint is configured, and credentials never leak into logs,
errors, or agent-visible output.

**Why this priority**: A remote endpoint may require proof of identity, and mishandling a
credential is a real risk. This must ship with the capability, not after it.

**Independent Test**: Configure a remote endpoint that requires credentials, confirm requests
succeed with valid credentials and fail with a distinct, actionable authentication error
without them, and confirm credentials never appear in any log, error, or tool output.

**Acceptance Scenarios**:

1. **Given** a remote endpoint requiring credentials, **When** a request is made without
   valid credentials, **Then** the failure is reported as an actionable authentication
   error, not a generic failure.
2. **Given** valid credentials, **When** requests are made, **Then** the credentials are
   never written to logs, error messages, or agent-visible output.
3. **Given** an endpoint configured to expect a custom header such as `X-API-KEY`, **When** a
   request is made, **Then** the credential is sent in that header.
4. **Given** an unencrypted remote endpoint, **When** it is configured, **Then** ember
   rejects it unless the operator makes an explicit, recorded insecure override.

---

### User Story 3 - Operate an ember server for remote clients (Priority: P3)

A team wants one powerful machine to host the decision model and let other machines connect to
it. The operator runs an ember server that accepts remote clients safely — off by default, with
optional bearer-token authentication that can be turned off when the operator supplies its own
auth layer — and can confirm who can reach it.

**Why this priority**: Remote consumption is useless without a server willing to serve remote
clients. It ranks below the client path because the client path is the user-visible value and
because a reverse proxy can satisfy some deployments in the interim.

**Independent Test**: Start an ember server in a remote-serving configuration, send a request
from a second machine with valid credentials (succeeds) and without them (rejected), and
confirm the default startup remains narrowly bound and unauthenticated for local use.

**Acceptance Scenarios**:

1. **Given** the server is configured for remote clients with authentication enabled,
   **When** a client presents valid credentials, **Then** the request is served.
2. **Given** the same configuration, **When** a client presents no or invalid credentials,
   **Then** the request is rejected with a clear authentication error.
3. **Given** the default configuration, **When** the server starts, **Then** it remains
   bound narrowly and requires no credentials, unchanged from today.
4. **Given** an operator wants to confirm reachability, **When** they run the status/doctor
   path, **Then** it reports whether remote clients are enabled and whether authentication
   is required or delegated to an operator-managed layer.

---

### User Story 4 - Fail clearly and safely (Priority: P4)

A person misconfigures an endpoint, loses network access, or hits an incompatible remote. They
get a precise, actionable message rather than a stack trace, a hang, or a silent fallback to
inference they did not intend.

**Why this priority**: Robustness is what makes the remote path trustworthy in day-to-day use,
but it refines the core stories rather than delivering new value on its own.

**Independent Test**: Exercise unreachable, unauthenticated, TLS-invalid, and
response-incompatible endpoints and confirm each yields a distinct, actionable message within
a bounded time and that no local fallback occurs implicitly.

**Acceptance Scenarios**:

1. **Given** a configured remote endpoint that is unreachable, **When** an advise request is
   made, **Then** the caller receives an actionable error naming the endpoint within a bounded
   wait, and ember does not silently fall back to local inference.
2. **Given** a remote endpoint presenting an invalid certificate, **When** a request is made,
   **Then** the failure is reported distinctly from an unreachable endpoint.
3. **Given** a remote endpoint returning an incompatible response, **When** a request is made,
   **Then** ember reports the incompatibility instead of surfacing malformed data as a valid
   answer.
4. **Given** media is attached to a request, **When** the endpoint is remote, **Then** the
   media is sent to the configured endpoint on the same terms as other state.

---

### Edge Cases

- What happens when the remote endpoint is reachable but the model there is still loading
  (not yet ready)?
- How does ember behave when the remote reports a different loaded model than the caller
  expected?
- What happens when credentials expire or are revoked mid-session?
- How are self-signed or otherwise untrusted certificates handled, and how does the operator
  opt in to trusting one?
- What happens when the operator disables ember's authentication and relies on a proxy's own
  scheme?
- What happens when autostart is enabled but the endpoint is remote (there is nothing local
  to start)?
- How are latency or admission-limit errors from a busy remote surfaced to the caller?
- What happens when the caller's version of ember is newer or older than the remote's
  contract?
- Does an existing loopback configuration continue to behave exactly as before, and can a
  user revert to local-only cleanly?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to direct advise requests to an inference endpoint other than
  the local model server.
- **FR-002**: The endpoint location MUST be configurable with the same precedence the project
  already uses for settings (command-line flag > environment variable > configuration file >
  default), without editing code.
- **FR-003**: Local inference MUST remain the default; remote inference MUST be opt-in and is
  selected by configuring an endpoint (see FR-016).
- **FR-004**: Ember MUST send advise requests to any endpoint the user configures, local or
  remote, without requiring an allow-list or other approval gate. (This does not make remote
  the default; see FR-003.)
- **FR-005**: The client MUST support supplying a credential as either a bearer token or a
  custom request header (for example `X-API-KEY`), configurable for the endpoint. The
  credential MUST be resolvable from an environment variable or the configuration file, with
  the environment variable taking precedence.
- **FR-006**: Credentials MUST never appear in logs, error messages, or agent-visible output.
- **FR-007**: Communication with a non-local endpoint MUST be encrypted by default; plaintext
  to a non-local host MUST be rejected unless the operator makes an explicit, recorded
  insecure override.
- **FR-008**: The agent tool MUST exhibit the same advise behavior (input fields, answer shape,
  error semantics) against a remote endpoint as against a local server. Any ember client that
  sends advise requests (MCP server, eval harness) MUST target the same configured endpoint;
  the CLI provides lifecycle and status reporting, not an advise command.
- **FR-009**: When the configured endpoint is remote, ember MUST NOT attempt to start or load
  a local model server.
- **FR-010**: Remote failures (unreachable, authentication, certificate, timeout, incompatible
  response, endpoint busy) MUST each produce a distinct, actionable message within the
  configured request timeout (`request_timeout`, default 300 s), and MUST NOT silently fall
  back to local inference.
- **FR-011**: An ember server MUST be able to accept remote clients with optional
  bearer-token authentication that can be disabled, so operators can delegate authentication
  to their own layer (proxy, gateway, or private network). Remote-serving mode MUST be off by
  default and MUST NOT change the safe default behavior for local use. Ember does not
  terminate TLS for remote-serving mode; encryption is provided by an operator-managed proxy.
- **FR-012**: The status/doctor path MUST report, for the configured endpoint: local/remote
  classification, URL, reachability, the remote's advertised `auth_required` (from `/health`),
  and whether the client has a credential configured (`auth_configured`). For the local server
  it MUST also report whether remote clients are enabled (`server_remote_enabled`) and whether
  server auth is required (`server_auth_required`). It MUST NOT claim to have verified
  credentials against a remote — that cannot be known from the unauthenticated `/health`.
- **FR-013**: Media payloads (`images`, `videos`, `media_kwargs`) MUST be sent to the
  configured endpoint on the same terms as other state, with no separate approval gate.
- **FR-014**: Ember MUST report when the model loaded by the endpoint differs from the model
  the caller expected, rather than presenting it as the requested model. The report MUST be
  non-fatal and visible to the caller (an additive `warning` field in the tool result plus a
  stderr log line); the `model` label MUST NOT be rewritten.
- **FR-015**: SECURITY.md, RESPONSIBLE_USE.md (privacy), README configuration, and the agent
  kit MUST be updated to describe the remote trust model, credentials, and defaults. Prose
  claiming state "never leaves your machine" (and equivalent privacy guarantees) MUST be
  removed or corrected to say that state is sent to whatever endpoint the user configures.
- **FR-016**: Remote endpoint settings MUST be representable in the configuration file as a
  single configurable endpoint and resolvable through the existing configuration mechanism;
  local remains the default.
- **FR-017**: The remote request timeout MUST be configurable (`request_timeout`, env
  `EMBER_REQUEST_TIMEOUT`, default 300 s) using the existing precedence, and MUST bound a
  remote request before it is reported as a timeout failure.
- **FR-018**: The MCP advise path MUST be async-first: the tool handler MUST be `async def` and
  use an async HTTP client, with any blocking local autostart offloaded to a worker thread
  (Article XII).
- **FR-019**: `GET /health` MUST advertise, additively, a contract `version` value and an
  `auth_required` boolean, so clients, status reporting, and third-party implementations can
  determine the remote contract and auth expectation without a credential.
- **FR-020**: The opencode plugin MUST forward the client's remote/auth environment variables
  (server URL, auth token, auth header, insecure override, request timeout) into the MCP child
  process, so remote configuration set in the user's environment reaches `ember-mcp`.

### Key Entities *(include if feature involves data)*

- **Inference endpoint**: A place advise requests are sent. Attributes: location, whether it
  is local or remote, and its reachability state.
- **Endpoint credentials**: A secret presented to a remote endpoint to authenticate the
  caller. Attributes: the secret itself (never exposed), the endpoint it belongs to, the auth
  scheme (bearer token or custom header name), and its source (environment variable or
  configuration file).
- **Remote-serving configuration**: The operator-side settings that determine whether an ember
  server accepts remote clients, whether authentication is required, and how it is protected.
- **Endpoint status**: The reported health of an endpoint — local/remote, reachable,
  authenticated, ready — surfaced by status/doctor.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can switch from local to remote inference with a single configuration
  change and no code changes, the change is reversible in a single step, and status reflects
  the switch, verified by test.
- **SC-002**: 100% of advise requests are sent to the endpoint the user configured and to no
  other destination, verified by test.
- **SC-003**: Credentials appear in zero logs, error messages, or agent-visible output across
  a full request cycle, including failure paths, verified by test.
- **SC-004**: Unreachable, unauthenticated, certificate-invalid, timed-out, and
  response-incompatible endpoints each produce a distinct, actionable message within the
  configured `request_timeout`, and none triggers an implicit local fallback, verified by test.
- **SC-005**: Answers returned from a remote endpoint match the local answer shape and
  semantics field-for-field for the same inputs, verified by test comparing an identical
  request against a local and a remote server.
- **SC-006**: An ember server can serve an authenticated remote client and rejects an
  unauthenticated one when authentication is enabled; with authentication disabled it serves
  without ember-side verification, verified by test, while default startup behavior is
  unchanged.
- **SC-007**: A client machine with no local model weights can obtain advice through the agent
  tool pointed at a remote endpoint, verified by a client-side test that loads no weights.

## Assumptions

- The remote endpoint speaks the same request/response contract as the local model server, so
  no new answer schema is introduced.
- Any reachable endpoint the user configures is acceptable, including third-party hosting;
  the user is responsible for choosing endpoints and for the trust they place in them.
- The client establishes encryption for remote transport (TLS); ember's server does not
  terminate TLS, so remote-serving deployments rely on an operator-managed proxy for
  encryption and may delegate authentication to that proxy as well.
- A custom credential header (e.g. `X-API-KEY`) is for endpoints or proxies that accept it;
  ember's built-in server authentication validates only `Authorization: Bearer`, so a custom
  header is expected to be translated by an operator-managed proxy/gateway in front of an
  ember server.
- The client side of ember (the agent tool) remains free of model-loading dependencies; model
  weights and inference stay on the endpoint.
- The existing configuration precedence and lifecycle commands continue to apply, with remote
  behavior layered onto them rather than replacing them.
- Local loopback behavior, including the existing no-authentication default, is preserved when
  no remote endpoint is configured.
- The model label reported by the endpoint is authoritative for that endpoint; ember reports
  mismatches rather than rewriting them.
