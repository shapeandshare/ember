---
description: "Task list for Remote Inference Servers implementation"
---

# Tasks: Remote Inference Servers

**Input**: Design documents from `/specs/001-remote-inference-servers/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: INCLUDED — the project constitution (Article XI) mandates TDD. Write each test
first, confirm it FAILS (Red), then implement (Green), then refactor. Tests land in the same
commit as the code they cover.

**Organization**: Tasks are grouped by user story to enable independent implementation and
testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Every task names an exact file path

## Path Conventions

Single Python package at repository root: `ember/` (source), `tests/` (pytest),
`packages/opencode-plugin/` (npm plugin), `.specify/memory/constitution.md`, `vault/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Governance prerequisite and configuration surface.

- [x] T001 Amend Article I in `.specify/memory/constitution.md` to "Local-First by Default": prepend a Sync Impact Report, change the principle text (local default; one explicitly configured remote endpoint allowed), bump the version MAJOR (1.4.0 → 2.0.0), and update `AGENTS.md`. **DONE in this change** — resolves analysis finding C1. No implementation code has been written.
- [x] T002 Add remote keys to `DEFAULTS` in `ember/cfg/config.py`: `server_url` (default `"http://127.0.0.1:8765"`), `auth_token` (unset/`None`), `auth_header` (default `"Authorization"`), `allow_insecure_transport` (default `False`), `request_timeout` (default `300`), `server_auth_token` (unset/`None`) — per [contracts/config.md](./contracts/config.md).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared endpoint helper and the additive health contract every story reads.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 [P] Write failing unit tests in `tests/test_endpoint.py` for the endpoint helper: loopback classification (`localhost`, `127.0.0.1`, `::1`, `::ffff:127.0.0.1` → local; `192.0.2.1`, `0.0.0.0`, and a non-`localhost` hostname → remote); the insecure-transport guard (`http` + non-local raises `InsecureEndpointError` unless `allow_insecure_transport` is true); credential header construction (`Authorization` → `Bearer <token>`; other name → raw `<token>`); `request_timeout` resolution (default `300`, env override); and config precedence (env beats config file beats default). These supersede the removed `validate_server_url` tests (D13). Confirm collection fails.
- [x] T004 Implement `ember/cfg/endpoint.py`: the `Endpoint` model (`url`, `host`, `scheme`, `is_local`, `allow_insecure_transport`, `request_timeout`) with validation rules from [data-model.md](./data-model.md) §1; `is_loopback_host(host)`; `resolve_endpoint()` reading `config.resolve`; `build_auth_headers()` (returns `{}` when no token); `InsecureEndpointError` and `InvalidEndpointError`. Make T003 pass. `from __future__ import annotations`, NumPy-style docstrings, no lazy imports (Article X).
- [x] T005 [P] Write a failing contract test in `tests/test_http_api.py`, then extend `GET /health` in `ember/serving/server.py` with additive `version` (package version) and `auth_required` (bool) fields (FR-019, D12); assert `status`/`pid`/`engine` are unchanged and `/health`/`/metrics` need no credential.

**Checkpoint**: Endpoint helper + health contract tested and green.

---

## Phase 3: User Story 1 - Send advice requests to a remote endpoint (Priority: P1) 🎯 MVP

**Goal**: The agent sends advise requests to the configured endpoint, remote or local, local
default, no local model on the client.

**Independent Test**: Point the client at a model server on a random port with
`EMBER_AUTOSTART=0`; call `advise`; assert a valid answer of the same shape as local and no
local server spawned.

### Tests for User Story 1 ⚠️ (write first, must FAIL)

- [x] T006 [P] [US1] Write failing integration tests in `tests/test_mcp_tool.py`: `test_advise_uses_configured_remote_endpoint` (model server on a random port, never 8765; `EMBER_AUTOSTART=0`; assert a valid answer), `test_remote_answer_shape_matches_local` (assert response field structure — per-question `answers` keys, `usage`, `model`, `latency_ms`; M4), and `test_remote_endpoint_does_not_autostart` (unreachable remote must not call `process.start`).
- [x] T007 [P] [US1] Write failing tests in `tests/test_cli.py`: `test_status_reports_remote_endpoint` (`kind=local` for reachable loopback; `kind=remote` for a non-loopback URL), `test_status_accepts_server_url_on_status_and_doctor` (enumerate `status`, `doctor`; L1), and `test_local_to_remote_is_single_reversible_change` (M3/SC-001).

### Implementation for User Story 1

- [x] T008 [US1] Update `ember/mcp/mcp_server.py`: make `advise` an **`async def`** using `httpx.AsyncClient` (FR-018); resolve the endpoint via `resolve_endpoint()` (replacing the module-level `os.environ.get("EMBER_SERVER_URL", ...)`); use `request_timeout`; gate `_ensure_server()` autostart to **loopback only**, and only there health-probe (remote calls go straight to the POST); run blocking autostart via `anyio.to_thread.run_sync` with `# async-first:exception - runs in a worker thread; subprocess + sync health probe`; remove `validate_server_url` and its call in `main()`; keep stdout clean (stderr logging). Delete the 8 `validate_server_url` tests and the S-001 block in `tests/test_runtime_unit.py` (D13), keeping the CLI `0.0.0.0`→loopback normalisation test. Makes T006 pass.
- [x] T009 [US1] Update `ember/cli.py`: add `--server-url` to `status` and `doctor`; make `config show` display the resolved `server_url` (secrets masked); update `cmd_status`/`cmd_doctor` to report `kind`, `url`, `reachable`, `contract_version`, `remote_auth_required`, `auth_configured`, and the local-server fields per [data-model.md](./data-model.md) §4 (no secret values). Makes T007 pass.
- [x] T010 [P] [US1] Write failing test `test_remote_advise_forwards_media` in `tests/test_mcp_tool.py`: a remote request carrying `images` reaches the configured endpoint with `images`/`videos`/`media_kwargs` intact (M1/FR-013).
- [x] T011 [P] [US1] Write failing tests in `tests/test_mcp_tool.py`: `test_request_sent_only_to_configured_endpoint` (stub records the request; exactly one destination; M2/SC-002) and `test_client_works_with_no_local_weights` (canned stub endpoint, no model directory; M5/SC-007).

**Checkpoint**: US1 works end-to-end against a configured endpoint with no local model on the client.

---

## Phase 4: User Story 2 - Authenticate to the remote endpoint (Priority: P2)

**Goal**: The client sends credentials as a bearer token or a custom header (env/config, env
precedence), never leaks them, and opencode users reach the MCP with those settings.

**Independent Test**: Point the client at a stub endpoint that asserts the auth header; confirm
bearer and custom header are sent, `401` maps to an actionable error, no token leaks, and the
plugin forwards the vars.

### Tests for User Story 2 ⚠️ (write first, must FAIL)

- [x] T012 [P] [US2] Write failing tests in `tests/test_mcp_tool.py` against a stub HTTP server on a random port: `test_client_sends_bearer_token`, `test_client_sends_custom_header` (`X-API-KEY`), and `test_auth_failure_is_actionable` (`401` → distinct ToolError, no token in the message).
- [x] T013 [P] [US2] Write failing test `test_config_show_masks_secrets` in `tests/test_cli.py`: with `EMBER_AUTH_TOKEN`/`EMBER_SERVER_AUTH_TOKEN` set, `ember config show` renders them `"***"` and never the raw value.
- [x] T014 [P] [US2] Write failing tests in `packages/opencode-plugin/index.test.js`: the plugin's child `environment` includes `EMBER_AUTH_TOKEN`, `EMBER_AUTH_HEADER`, `EMBER_ALLOW_INSECURE_TRANSPORT`, and `EMBER_REQUEST_TIMEOUT` when set, and omits them when unset (FR-020).

### Implementation for User Story 2

- [x] T015 [US2] Update `ember/mcp/mcp_server.py` to attach `build_auth_headers()` and map HTTP `401`/`403` to a distinct actionable `ToolError` (per [contracts/mcp-tool.md](./contracts/mcp-tool.md)); guarantee the token never enters the message, the `warning`, or logs. Makes T012 pass.
- [x] T016 [US2] Update `cmd_config_show` in `ember/cli.py` to mask `auth_token` and `server_auth_token` (set → `"***"`, unset → `null`). Makes T013 pass.
- [x] T017 [US2] Update `packages/opencode-plugin/index.js` to forward the client env vars into `config.mcp.ember.environment` (omit unset). Makes T014 pass.

**Checkpoint**: US1 and US2 work independently; credentials are sent correctly, never exposed, and reach the MCP under opencode.

---

## Phase 5: User Story 3 - Operate an ember server for remote clients (Priority: P3)

**Goal**: The server can require an optional bearer token on `POST /v1/systemone`; auth can be
disabled so hosters delegate; defaults and `/health`/`/metrics` stay as today.

**Independent Test**: auth-enabled server → valid `200`, missing/wrong `401` +
`WWW-Authenticate`; `/health`+`/metrics` open; auth-disabled unchanged.

### Tests for User Story 3 ⚠️ (write first, must FAIL)

- [x] T018 [P] [US3] Write failing tests in `tests/test_http_api.py` against a server on a **random port** with `EMBER_SERVER_AUTH_TOKEN` set: valid bearer → `200`; missing → `401` with `WWW-Authenticate: Bearer`; wrong → `401` with the same generic detail as missing; `/health` and `/metrics` → `200` without a token; and without the token → unauthenticated request succeeds.

### Implementation for User Story 3

- [x] T019 [US3] Implement optional server auth in `ember/serving/server.py`: a FastAPI dependency using `HTTPBearer(auto_error=False)` that is a no-op when `config.resolve("server_auth_token")` is unset, else compares the bearer token with `secrets.compare_digest(received.encode(), expected.encode())`, raising `HTTPException(401, headers={"WWW-Authenticate": "Bearer"})` for both missing and wrong tokens; apply only to `POST /v1/systemone`; leave `/health`/`/metrics` untouched. Makes T018 pass.
- [x] T020 [US3] Update `cmd_doctor`/`cmd_status` in `ember/cli.py` to report `server_remote_enabled` (host non-loopback) and `server_auth_required` (`server_auth_token` set) per [data-model.md](./data-model.md) §4, without printing any token.

**Checkpoint**: US1–US3 work independently; a remote client can authenticate to an enforcing server.

---

## Phase 6: User Story 4 - Fail clearly and safely (Priority: P4)

**Goal**: Unreachable, timeout, certificate, incompatible-response, and insecure-transport
failures each yield a distinct, actionable message; no silent local fallback; model/version
mismatches are reported, not fatal.

**Independent Test**: Exercise each failure class; assert distinct messages and no fallback;
attach a mismatched `model` and assert a warning.

### Tests for User Story 4 ⚠️ (write first, must FAIL)

- [x] T021 [P] [US4] Write failing tests (in `tests/test_endpoint.py` and `tests/test_mcp_tool.py`) for the failure taxonomy from [research.md](./research.md) D5: unreachable (`ConnectError` without an `ssl` cause), certificate (`ConnectError` whose `__cause__` is `ssl.SSLCertVerificationError`/`ssl.SSLError`), timeout (`httpx.TimeoutException`, `EMBER_REQUEST_TIMEOUT` low, message names the value), insecure transport (pre-flight), and incompatible response (`json.JSONDecodeError`/`UnicodeDecodeError`); assert each maps to a distinct message and no local server is started; add `test_model_mismatch_is_reported` (FR-014) and `test_unknown_remote_version_warns_not_fails` (D12).

### Implementation for User Story 4

- [x] T022 [US4] Implement the distinct error mapping and the non-fatal warnings in `ember/mcp/mcp_server.py`: classify on the `ssl` type **before** any generic `ValueError` branch (`ssl.SSLCertVerificationError` is a `ValueError` by MRO); add an additive `warning` field + stderr line when the response `model` differs from the requested label, and when the remote `/health` `version` is unknown (FR-014, FR-019). Makes T021 pass.

**Checkpoint**: All user stories independently functional and failing gracefully.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, governance bookkeeping, and final gates.

- [x] T023 [P] Update `README.md`: remote config keys and precedence (incl. `request_timeout`), a remote usage example (bearer + custom header), the local-default/revert story, and correct the local-only framing.
- [x] T024 [P] Update `SECURITY.md` (remote trust model: loopback default, allowed remote endpoints, optional server bearer auth, TLS via operator proxy) and `RESPONSIBLE_USE.md` (remove/adjust "inference runs on your machine / never leaves your machine" and "does not send state over the network") per FR-015.
- [x] T025 [P] Update the agent kit: `ember/agent_kit/instructions.md` (≤ 2048 bytes), `ember/agent_kit/ember-advise/SKILL.md`, `ember/agent_kit/AGENTS.snippet.md` to mention remote mode; adjust `tests/test_agent_kit.py` if the byte budget or content changes.
- [x] T026 [P] Write `vault/decisions/2026-10-06-remote-inference-servers.md` (remote-vs-local decision, Article I amendment rationale, any-endpoint policy, disableable-auth/proxy-TLS, `request_timeout`), link it from `vault/ember.md`, and run `make vault-audit`.
- [x] T027 Run the verification gates: `python3 -c "import ember.mcp.mcp_server"` must not import torch (Article XIII); `node --test packages/opencode-plugin/`; `make pr-ready`; `make check`; then `make test` and `make test-cov` (confirm `fail_under = 71` is not lowered). Fix diagnostics on touched files.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 is DONE (amendment landed); T002 feeds Phase 2.
- **Foundational (Phase 2)**: depends on T001+T002; **blocks all user stories**.
- **User Stories (Phase 3+)**: each depends on Foundational; P1 → P2 → P3 → P4 or parallel where files differ.
- **Polish (Phase 7)**: depends on all targeted user stories.

### User Story Dependencies

- **US1 (P1)**: depends on Foundational (T004 endpoint helper, T005 /health).
- **US2 (P2)**: depends on Foundational; shares `mcp_server.py` with US1 → follow US1.
- **US3 (P3)**: depends on Foundational; touches `server.py`; independent of US1.
- **US4 (P4)**: depends on US1 (same client file).

### Within Each User Story

- Tests first and FAILING before implementation (Article XI).
- Helpers before wiring; wiring before integration.
- Story complete and independently testable before moving on.

### Parallel Opportunities

- `[P]` test tasks per distinct file can be written in parallel.
- After Phase 2: **US3** (`server.py`, `test_http_api.py`) runs independently of **US1** (`mcp_server.py`).
- Polish docs T023–T026 touch different files (parallel).

---

## Parallel Example: User Story 1

```bash
Task: "T006 [US1] remote advise + shape parity in tests/test_mcp_tool.py"
Task: "T007 [US1] status/reversibility in tests/test_cli.py"
Task: "T010 [US1] media parity in tests/test_mcp_tool.py"
Task: "T011 [US1] single-destination + no-weights in tests/test_mcp_tool.py"
# then
Task: "T008 [US1] async endpoint wiring in ember/mcp/mcp_server.py"
Task: "T009 [US1] --server-url/status in ember/cli.py"
```

## Parallel Example: User Story 3 (independent of US1/US2)

```bash
Task: "T018 [US3] server-auth tests in tests/test_http_api.py"
Task: "T019 [US3] optional auth in ember/serving/server.py"
Task: "T020 [US3] doctor/status server fields in ember/cli.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (T001 done) and Phase 2.
2. Complete Phase 3 (US1).
3. **STOP and VALIDATE**: run T006/T007; confirm a configured endpoint serves advise with no local model on the client.

### Incremental Delivery

1. Setup + Foundational → helper + health contract.
2. US1 → remote advise (MVP).
3. US2 → credentials + plugin forwarding.
4. US3 → server-side auth.
5. US4 → failure taxonomy + warnings.
6. Polish → docs, vault, gates.

---

## Notes

- `[P]` = different files, no dependencies.
- Never bind port `8765` in tests; never kill by port/pattern (Article IV).
- No new runtime dependencies (research D; Article XV). `anyio` already ships via FastAPI/MCP.
- MCP **input** schema stays unchanged; the tool result gains only an additive optional `warning`.
- Keep `fail_under = 71`; ratchet only upward (Article XI §11.2).
- Commit atomically with scopes: `feat(ember): …`, `feat(plugin): …`, `test(ember): …`, `docs: …`.

## Phase 8: Convergence

- [x] T028 Add `test_remote_answer_shape_matches_local` in `tests/test_mcp_tool.py` comparing a remote response's field structure (`answers` keys per question, `usage`, `model`, `latency_ms`) against the local answer shape per US1/AC2 (SC-005) (partial)
- [x] T029 Resolve the endpoint and credentials in the eval harness (`evals/eval/run_evals.py` and `evals/eval/run_agent_evals.py`) through `ember.cfg.endpoint.Endpoint` + `build_auth_headers()` so benchmark runs honor config-file precedence and work against an auth-enabled remote per FR-008/FR-005 (partial)
- [x] T030 Add a CLI status test in `tests/test_cli.py` asserting a reachable remote endpoint surfaces `contract_version` and `remote_auth_required` from `/health` per FR-012 (partial)
- [x] T031 Make `cmd_config_show` in `ember/cli.py` display the env-resolved `server_url` (via `config.resolve`) per T009/FR-002 (partial)
