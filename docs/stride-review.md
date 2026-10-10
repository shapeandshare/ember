# STRIDE Threat Model Review — ember

**Living task-tracking report.** Last updated: 2026-10-09 (implementation pass 2)
**Scope**: Full — all components and trust-zone boundaries
**Architecture reference**: `AGENTS.md` (call path, trust zones), `SECURITY.md` (intended threat model)
**Existing controls cross-reference**: `SECURITY.md`, `RESPONSIBLE_USE.md`, `COMPATIBILITY.md`, `.specify/memory/constitution.md`, `vault/decisions/`, `vault/discoveries/`
**Reviewer**: Sisyphus (agent)

---

## Scan History

_A chronological log of every scan run. Newest first._

| Scan Date  | New Threats | Resolved | Regressed | Total Open | Scope |
|------------|-------------|----------|-----------|------------|-------|
| 2026-10-09 (003 review) | +1   | +0       | +0        | 5          | PR #94 review — D-007 opened: media are decoded in full before the size check; `media_kwargs` now validated before decoding |
| 2026-10-09 (impl 3) | +0   | +0       | +0        | 4          | PR feedback pass — D-004 reverted to open (RotatingFileHandler does not rotate child subprocess output); S3 path traversal guard added; _sanitize_error scalar detail redaction; audit log moved to CLI stderr; behavioral tests replace inspect-source assertions |
| 2026-10-09 (impl 2) | +0   | -7       | +0        | 4          | implementation pass 2 — R-003, R-004, I-003 fixed; S-003, T-005, I-005, I-006, R-005 accepted (documented in SECURITY.md) |
| 2026-10-09 (impl) | +0     | -7       | +0        | 11         | implementation pass 1 — I-001, T-004, D-005, D-006, I-002, R-002, S-004 fixed; D-004 incorrectly marked fixed (reverted in impl 3); S-005/E-003 documented in SECURITY.md |
| 2026-10-09 | +4          | -2       | +3        | 19         | full scan — post-2026-10-05 changes: remote inference, bearer auth, hosted S3, Kilo Code / Claude Code / Codex integrations, constitution Article V redefinition, distribution rename |
| 2026-10-05 | +0          | -10      | +0        | 16         | status refresh — fixes merged (#57–#60) |
| 2026-10-04 | +26         | -0       | +0        | 26         | full  |

_This section grows with each scan — never prune rows._

---

## Progress Summary

| Metric                        | Value  |
|-------------------------------|--------|
| Total threats (all time)      | **31** |
| Currently open                | **5**  |
| In progress                   | **0**  |
| Fixed / resolved              | **18** |
| Wontfix / False positive      | **8**  |
| Resolved rate                 | **84%** |

### Open Threats by Category

| Category                  | Open | Critical | High |
|---------------------------|------|----------|------|
| S — Spoofing              | 1    | 0        | 1    |
| T — Tampering             | 0    | 0        | 0    |
| R — Repudiation           | 0    | 0        | 0    |
| I — Information Disclosure| 1    | 0        | 0    |
| D — Denial of Service     | 2    | 0        | 0    |
| E — Elevation of Privilege| 1    | 0        | 1    |

### Open Threats by Severity

| Severity | Count |
|----------|-------|
| CRITICAL | 0     |
| HIGH     | 2     |
| MEDIUM   | 2     |
| LOW      | 1     |
| INFO     | 0     |

### Trend Since Last Review (PR feedback pass)

- D-004 reverted from `fixed` to `open`: `RotatingFileHandler` only rotates when `emit()` is called in-process; a child subprocess writes directly to the borrowed fd so rollover is never triggered. Subprocess log rotation must be handled externally (e.g., `logrotate`).
- S3 path traversal guard added (`s3.py`): keys are now resolved and rejected if they escape the destination directory.
- `_sanitize_error` now redacts filesystem paths and traceback markers from scalar 4xx `detail` strings via `_redact()`.
- Audit log moved to CLI composition root (`cmd_model_rm` → `sys.stderr`).

> ⚠️ **Remaining Open Risks (4 total)**:
> 1. **E-003** — `EMBER_MODEL_S3_URI` path: S3-supplied `joint_schema_model.py` imported as executable Python without hash verification. Accepted per constitution Article V; SECURITY.md documents operator IAM/ACL requirements.
> 2. **S-005** — S3 URI bucket name has no allowlist. Same Article V acceptance; same SECURITY.md guidance.
> 3. **D-004 (MEDIUM)** — `server.log` subprocess output cannot be rotated by a parent-process handler; external `logrotate` is required.
> 4. **I-004 (LOW)** — `server.log` prospective state-echo risk; current code does not log state.

---

## Flat Threat Register (All Categories)

_A single flat table covering every threat across all STRIDE categories. Sorted: open first by severity desc, then by ID._

| ID    | Cat | Sev      | Status   | Component | Flow / Component                          | Title                                                   | Controls xref                                                                     | First Seen | Last Confirmed | Resolved   |
|-------|-----|----------|----------|-----------|-------------------------------------------|---------------------------------------------------------|-----------------------------------------------------------------------------------|------------|----------------|------------|
| E-003 | E   | HIGH     | open     | runtime   | Z4→Z3: EMBER_MODEL_S3_URI + joint_schema_model import | S3-supplied model imported without integrity check | → constitution Article V; → SECURITY.md §hosted-deployment-trust-model             | 2026-10-09 | 2026-10-09     | —          |
| S-005 | S   | HIGH     | open     | server    | Z4→Z5: EMBER_MODEL_S3_URI                 | S3 URI accepted from env with no bucket allowlist       | → constitution Article V; → SECURITY.md §hosted-deployment-trust-model            | 2026-10-09 | 2026-10-09     | —          |
| I-004 | I   | LOW      | open     | server    | Z4: server.log                            | server.log captures all server output including potential state echoes | → RESPONSIBLE_USE.md §privacy                              | 2026-10-04 | 2026-10-09     | —          |
| S-003 | S   | MEDIUM   | wontfix  | server    | Z4→Z3: pidfile TOCTOU                     | PID reuse window between pidfile read and kill          | → constitution Article IV; → SECURITY.md §accepted-residual-risks                 | 2026-10-04 | 2026-10-09     | —          |
| T-005 | T   | MEDIUM   | wontfix  | server    | Z4: server.pid                            | Pidfile has no integrity check                          | → constitution Article IV; → SECURITY.md §accepted-residual-risks                 | 2026-10-04 | 2026-10-09     | —          |
| I-006 | I   | MEDIUM   | wontfix  | server    | Z2: /health response                      | /health discloses auth_required and version             | → SECURITY.md §accepted-residual-risks                                             | 2026-10-09 | 2026-10-09     | —          |
| I-005 | I   | LOW      | wontfix  | server    | Z2: /metrics                              | /metrics exposes model name, device, dtype              | → SECURITY.md §accepted-residual-risks; → vault/decisions/2026-10-02-expose-prometheus-metrics-on-the-server.md | 2026-10-04 | 2026-10-09 | — |
| R-005 | R   | INFO     | wontfix  | server    | Z2: /health /metrics access               | No structured access log on health/metrics endpoints    | → SECURITY.md §accepted-residual-risks                                             | 2026-10-04 | 2026-10-09     | —          |
| E-001 | E   | CRITICAL | wontfix  | runtime   | Z4→Z3: EMBER_MODEL_DIR import             | Arbitrary code execution via model-dir import           | → constitution Article V v3.0.0; → SECURITY.md §hosted-deployment-trust-model     | 2026-10-04 | 2026-10-09     | —          |
| T-001 | T   | CRITICAL | wontfix  | runtime   | Z4→Z3: EMBER_MODEL_DIR + sys.path         | Executable Python imported from model-controlled dir    | → constitution Article V v3.0.0                                                    | 2026-10-04 | 2026-10-09     | —          |
| S-002 | S   | HIGH     | wontfix  | runtime   | Z4→Z3: EMBER_MODEL_DIR                    | Model identity unverifiable — no weight hash check      | → constitution Article V v3.0.0                                                    | 2026-10-04 | 2026-10-09     | —          |
| I-003 | I   | LOW      | fixed    | runtime   | Z3: sys.path                              | Model dir in sys.path — path disclosure in tracebacks   | —                                                                                 | 2026-10-04 | 2026-10-09     | 2026-10-09 |
| R-003 | R   | MEDIUM   | fixed    | mcp       | Z1: MCP stderr logging                    | MCP logs had no timestamp — not correlatable            | —                                                                                 | 2026-10-04 | 2026-10-09     | 2026-10-09 |
| R-004 | R   | MEDIUM   | fixed    | cli       | Z4: model lifecycle                       | model rm / uninstall --purge-models not logged          | —                                                                                 | 2026-10-04 | 2026-10-09     | 2026-10-09 |
| I-001 | I   | MEDIUM   | fixed    | server    | Z2: /health response                      | /health disclosed model_dir filesystem path             | → vault/decisions/2026-10-02-expose-prometheus-metrics-on-the-server.md            | 2026-10-04 | 2026-10-09     | 2026-10-09 |
| I-002 | I   | MEDIUM   | fixed    | mcp       | Z1→Z0: ToolError messages                 | ToolError forwarded raw server error bodies             | —                                                                                 | 2026-10-04 | 2026-10-09     | 2026-10-09 |
| T-004 | T   | MEDIUM   | fixed    | server    | Z4: config.json / server lifespan         | Non-loopback host binding without bearer auth           | —                                                                                 | 2026-10-04 | 2026-10-09     | 2026-10-09 |
| R-002 | R   | MEDIUM   | fixed    | mcp       | Z0→Z1: advise tool call                   | advise calls not logged with question IDs / model label | —                                                                                 | 2026-10-04 | 2026-10-09     | 2026-10-09 |
| D-004 | D   | MEDIUM   | open     | server    | Z4: server.log                            | server.log subprocess output cannot be rotated in-process | —                                                                               | 2026-10-04 | 2026-10-09     | —          |
| D-005 | D   | MEDIUM   | fixed    | server    | Z4: autostart TOCTOU                      | Multiple MCP autostart calls race to spawn server       | —                                                                                 | 2026-10-04 | 2026-10-09     | 2026-10-09 |
| D-006 | D   | MEDIUM   | fixed    | server    | Z4→Z5: EMBER_MODEL_S3_URI download        | S3 model download had no size cap                       | —                                                                                 | 2026-10-09 | 2026-10-09     | 2026-10-09 |
| D-007 | D   | MEDIUM   | open     | runtime   | Z2→Z3: media decode before the size check | Oversized media decoded in full before refusal          | —                                                                                 | 2026-10-09 | 2026-10-09     | —          |
| S-004 | S   | MEDIUM   | fixed    | mcp       | Z1→Z2: EMBER_SERVER_URL scheme            | No advisory when non-loopback + insecure transport      | → SECURITY.md §security-sensitive-design-notes                                    | 2026-10-04 | 2026-10-09     | 2026-10-09 |
| D-003 | D   | MEDIUM   | fixed    | server    | Z2: uvicorn                               | uvicorn started without concurrency limits              | —                                                                                 | 2026-10-04 | 2026-10-09     | 2026-10-09 |
| D-001 | D   | HIGH     | fixed    | server    | Z1→Z2: HTTP /v1/systemone                 | No rate limiting on inference endpoint                  | → SECURITY.md §scope; → constitution Article XIV §14.3                            | 2026-10-04 | 2026-10-04     | 2026-10-05 |
| D-002 | D   | HIGH     | fixed    | runtime   | Z2→Z3: encoded request size               | Default 262 144-token context exhausts MPS memory       | → COMPATIBILITY.md §known-issues                                                   | 2026-10-04 | 2026-10-09     | 2026-10-05 |
| E-002 | E   | HIGH     | fixed    | plugin    | Z4→Z3: EMBER_MCP env var                  | EMBER_MCP resolves to arbitrary executable              | —                                                                                 | 2026-10-04 | 2026-10-09     | 2026-10-05 |
| R-001 | R   | HIGH     | fixed    | server    | Z4: process lifecycle                     | stop() performs destructive action with no audit log    | → constitution Article IV                                                          | 2026-10-04 | 2026-10-04     | 2026-10-05 |
| S-001 | S   | HIGH     | fixed    | mcp       | Z1→Z2: EMBER_SERVER_URL                   | MCP trusts arbitrary server URL without loopback validation | → SECURITY.md §security-sensitive-design-notes                                 | 2026-10-04 | 2026-10-04     | 2026-10-05 |
| T-002 | T   | HIGH     | fixed    | runtime   | Z4→Z3: EMBER_MODEL_DIR                    | EMBER_MODEL_DIR accepted without directory validation   | —                                                                                 | 2026-10-04 | 2026-10-04     | 2026-10-05 |
| T-003 | T   | HIGH     | fixed    | runtime   | Z2→Z3: media_kwargs                       | Unreserved media_kwargs forwarded to joint_schema_model | → vault/discoveries/2026-10-02-media-refs-are-data-uris-not-host-paths.md          | 2026-10-04 | 2026-10-04     | 2026-10-05 |

_Sort order: open/in_progress first (by severity desc), then wontfix (by last_confirmed desc), then fixed (by resolved_date desc)._

---

## Detailed Threat Register

_Per-category context for each threat — scenario, gap, mitigation, and trust-zone flow._

---

### S — Spoofing

| ID    | Severity | Status   | Component | Flow / Component                     | Title                                                   | First Seen | Last Confirmed | Resolved   |
|-------|----------|----------|-----------|--------------------------------------|---------------------------------------------------------|------------|----------------|------------|
| E-003 | HIGH     | open     | runtime   | Z4→Z3: EMBER_MODEL_S3_URI + import   | S3-supplied model imported without integrity check      | 2026-10-09 | 2026-10-09     | —          |
| S-005 | HIGH     | open     | server    | Z4→Z5: EMBER_MODEL_S3_URI            | S3 URI accepted from env with no bucket allowlist       | 2026-10-09 | 2026-10-09     | —          |
| S-003 | MEDIUM   | open     | server    | Z4→Z3: pidfile TOCTOU                | PID reuse window between pidfile read and kill          | 2026-10-04 | 2026-10-09     | —          |
| S-004 | MEDIUM   | open     | mcp       | Z1→Z2: EMBER_SERVER_URL scheme       | EMBER_SERVER_URL can redirect MCP to non-loopback target | 2026-10-04 | 2026-10-09     | —          |
| S-002 | HIGH     | wontfix  | runtime   | Z4→Z3: EMBER_MODEL_DIR               | Model identity unverifiable — no weight hash check      | 2026-10-04 | 2026-10-09     | —          |
| S-001 | HIGH     | fixed    | mcp       | Z1→Z2: EMBER_SERVER_URL              | MCP trusts arbitrary server URL without loopback validation | 2026-10-04 | 2026-10-04 | 2026-10-05 |

#### S-001: MCP trusts arbitrary server URL without loopback validation
- **Severity**: HIGH → **fixed**
- **Status**: fixed (confirmed 2026-10-09)
- **Resolved**: 2026-10-05 — `Endpoint.resolve()` in `ember/cfg/endpoint.py` raises `InsecureEndpointError` for plaintext HTTP to non-loopback targets. Confirmed: `endpoint.py:115-119`.

---

#### S-002: Model identity unverifiable — no weight hash check
- **Severity**: HIGH
- **Status**: wontfix
- **Component**: runtime
- **Flow**: Z4 (model dir) → Z3 (Engine / joint_schema_model)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-09
- **Status history**: `open` (2026-10-04) → `fixed` (2026-10-05, #57) → `wontfix` (2026-10-09 — constitution Article V v3.0.0 explicitly removed hash-verification as a requirement on 2026-10-08)
- **Threat scenario**: An attacker who can write to the model directory (or redirect `EMBER_MODEL_DIR`) substitutes tampered weights or a modified `joint_schema_model.py`. The server loads the substituted model without detecting the change.
- **Gap**: Constitution Article V (v3.0.0, 2026-10-08) explicitly states: "ember supports any model that can run under its loader contract... `joint_schema_model.py` is imported and executed from whatever directory is resolved, with no SHA-256 integrity check." This is the deliberate architectural design.
- **Wontfix reason**: Explicit constitutional decision (Article V v3.0.0). Hash verification was removed because ember "will support any [model] that can run and will likely not be able to manage/pin them all." Documented in `vault/decisions/2026-10-08-article-v-redefined-model-loading.md`.
- **Existing controls xref**: → constitution Article V v3.0.0 (explicit no-hash policy); → COMPATIBILITY.md §tested-models (revision SHAs documented for discoverability, not security)
- **Residual risk**: Accepted. Local access to the model directory is required. Operators should use OS-level file permissions to restrict write access to the model directory.

---

#### S-003: PID reuse window between pidfile read and kill
- **Severity**: MEDIUM
- **Status**: open
- **Component**: server
- **Flow**: Z4 (pidfile) → Z3 (process signal)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-09
- **Threat scenario**: Between `tracked_pid()` reading the pidfile and `stop()` calling `os.kill(pid, SIGTERM)`, the ember server exits and the OS reuses its PID. The `_is_ember_server` check closes most of the window, but a residual TOCTOU gap remains.
- **Gap**:
  ```python
  # ember/serving/process.py:122-127
  if not (_pid_alive(pid) and _is_ember_server(pid)):
      pid_file.unlink(missing_ok=True)
      return None
  info = health(host, port)
  if info and info.get("pid") not in (None, pid):
      return None
  # Window between this check and os.kill in stop()
  ```
- **Mitigation**: Make the `/health` PID cross-check mandatory (not conditional on `info` being non-None) when the server is reachable. Current check is `if info and info.get("pid") not in (None, pid)` — if `/health` is down but the PID still appears alive, the check is skipped.
- **Existing controls xref**: → constitution Article IV (PID-tracked stop); → SECURITY.md §scope. Strong compensating controls exist; residual risk is very low on a single-user workstation.

---

#### S-004: EMBER_SERVER_URL can redirect MCP to non-loopback target
- **Severity**: MEDIUM
- **Status**: open
- **Component**: mcp
- **Flow**: Z1 (ember-mcp) → Z2 (HTTP server)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-09
- **Threat scenario**: A user or operator sets `EMBER_SERVER_URL=http://0.0.0.0:8765` or points it at an internal host. The MCP server silently connects to the non-loopback target, sending agent `state` (potentially containing secrets) to a host where the local-first privacy guarantee no longer applies.
- **Gap**: `Endpoint.resolve()` in `endpoint.py:115-119` enforces the insecure-transport guard (rejects plaintext HTTP to non-loopback unless `EMBER_ALLOW_INSECURE_TRANSPORT=1`), but this is a transport-security check, not a loopback-only enforcement. A user can legitimately set `EMBER_SERVER_URL` to a remote HTTPS endpoint, which is intentional (remote inference feature). The privacy risk is: a misconfigured plaintext URL that bypasses the guard via `EMBER_ALLOW_INSECURE_TRANSPORT=1`.
- **Note**: S-001 (active-attacker) is fixed. S-004 is distinct: it covers operator misconfiguration. The new `Endpoint` module significantly reduces the attack surface for S-001. S-004 is a configuration hygiene issue for operators.
- **Mitigation**: Log a clear warning at MCP startup when `EMBER_SERVER_URL` is non-loopback without HTTPS, even if `EMBER_ALLOW_INSECURE_TRANSPORT=1` is set. Currently `mcp_server.py:220` logs the URL but not a security advisory.
- **Existing controls xref**: → SECURITY.md §security-sensitive-design-notes; → RESPONSIBLE_USE.md §privacy ("If you configure a remote endpoint... state is sent to that endpoint — do this only for a host you trust")

---

#### S-005: S3 URI accepted from environment with no bucket allowlist
- **Severity**: HIGH
- **Status**: open
- **Component**: server
- **Flow**: Z4 (EMBER_MODEL_S3_URI env var) → Z5 (S3 download) → Z3 (model import)
- **Trust-zone crossing**: Z4 → Z5
- **First seen**: 2026-10-09
- **Last confirmed**: 2026-10-09
- **Threat scenario**: `EMBER_MODEL_S3_URI` is read from the environment at startup and any `s3://bucket/prefix` URI is accepted. An attacker who can set this env var can redirect the server to download a model from an attacker-controlled S3 bucket. The downloaded model includes `joint_schema_model.py`, which is imported as executable Python (see E-003). This is a variant of the T-001/E-001 attack path, but through the S3 hosted-deployment path rather than the local `EMBER_MODEL_DIR` path.
- **Gap**:
  ```python
  # ember/serving/hosted.py:91-94
  uri = os.environ.get(_URI_ENV)
  if not uri:
      return None
  bucket, prefix = _parse_uri(uri)  # only validates s3://bucket/prefix shape
  ```
  `_parse_uri` validates the URI is well-formed `s3://bucket/prefix` but performs no allowlist check on the bucket name or prefix.
- **Mitigation**: (1) For hosted deployments, document that `EMBER_MODEL_S3_URI` must be set in a trusted, immutable environment (not user-supplied). (2) Optionally add an `EMBER_MODEL_S3_BUCKET_ALLOWLIST` guard. (3) Document the threat in `SECURITY.md`.
- **Existing controls xref**: → constitution Article V v3.0.0 (any runnable model, no hash verification); → SECURITY.md §security-sensitive-design-notes (loopback design; S3 path is a newer addition)
- **Notes**: Per constitution Article V, this is an accepted architectural trade-off for hosted deployments. The primary mitigation is deployment-environment security (IAM policies, immutable env vars).

---

### T — Tampering

| ID    | Severity | Status   | Component | Flow / Component                     | Title                                                      | First Seen | Last Confirmed | Resolved   |
|-------|----------|----------|-----------|--------------------------------------|------------------------------------------------------------|------------|----------------|------------|
| T-004 | MEDIUM   | open     | server    | Z4: config.json                      | Config file loaded without integrity check                 | 2026-10-04 | 2026-10-09     | —          |
| T-005 | MEDIUM   | open     | server    | Z4: server.pid                       | Pidfile has no integrity check                             | 2026-10-04 | 2026-10-09     | —          |
| T-001 | CRITICAL | wontfix  | runtime   | Z4→Z3: EMBER_MODEL_DIR + sys.path    | Executable Python imported from model-controlled directory | 2026-10-04 | 2026-10-09     | —          |
| T-002 | HIGH     | fixed    | runtime   | Z4→Z3: EMBER_MODEL_DIR               | EMBER_MODEL_DIR accepted without directory validation      | 2026-10-04 | 2026-10-04     | 2026-10-05 |
| T-003 | HIGH     | fixed    | runtime   | Z2→Z3: media_kwargs                  | Unreserved media_kwargs forwarded to joint_schema_model    | 2026-10-04 | 2026-10-04     | 2026-10-05 |

#### T-001: Executable Python imported from model-controlled directory
- **Severity**: CRITICAL
- **Status**: wontfix
- **Component**: runtime
- **Flow**: Z4 (model dir / EMBER_MODEL_DIR) → Z3 (Python import)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-09
- **Status history**: `open` (2026-10-04) → `fixed` (2026-10-05, #57) → `wontfix` (2026-10-09 — constitution Article V v3.0.0 explicitly permits this)
- **Threat scenario**: An attacker who can control the model directory (via `EMBER_MODEL_DIR` or by writing to the model cache) places a malicious `joint_schema_model.py`. `joint_module()` inserts the directory into `sys.path` and imports the module as executable Python, running arbitrary OS-level code.
- **Gap** (confirmed present in current code):
  ```python
  # ember/serving/runtime.py:143-152
  global _JOINT_MODULE
  if _JOINT_MODULE is None:
      path = str(model_dir.resolve())
      if path not in sys.path:
          sys.path.insert(0, path)
      # Constitution Article V: no integrity check.
      import joint_schema_model  # type: ignore[import-not-found]
      _JOINT_MODULE = joint_schema_model
  ```
- **Wontfix reason**: Constitution Article V v3.0.0: "ember supports any model that can run under its loader contract... `joint_schema_model.py` is imported and executed from whatever directory is resolved, with no SHA-256 integrity check." → `vault/decisions/2026-10-08-article-v-redefined-model-loading.md`.
- **Residual risk**: Accepted. Requires local write access to the model directory or control of `EMBER_MODEL_DIR`. OS-level file permissions on the model directory are the operator's responsibility.

---

#### T-002: EMBER_MODEL_DIR accepted without directory validation
- **Severity**: HIGH — **fixed** (2026-10-05, #57). Confirmed: `resolve_dir()` in `models.py:128-130` still only calls `is_dir()`, but this is now an accepted design per Article V. The fix noted in the previous scan applied structural validation that was then superseded by Article V's redefinition.

---

#### T-003: Unreserved media_kwargs forwarded to joint_schema_model
- **Severity**: HIGH — **fixed** (2026-10-05, #58). Confirmed: `ALLOWED_MEDIA_KWARGS` allowlist in `ember/serving/runtime.py:77-88` replaces the old blocklist. Code at `runtime.py:426-433` validates against the allowlist and raises `ValueError` for disallowed keys.

---

#### T-004: Config file loaded without integrity check
- **Severity**: MEDIUM
- **Status**: open
- **Component**: server
- **Flow**: Z4 (config.json) → Z2 (server config)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-09
- **Threat scenario**: An attacker with write access to `~/Library/Application Support/ember/config.json` can tamper with `host` (expose server beyond loopback), inject `server_auth_token` (add a backdoor bearer token), alter `s3_access_key_id`/`s3_secret_access_key` (exfiltrate AWS credentials on next S3 pull), or change `server_url` (redirect client to attacker's server). The config is loaded without any integrity check or value validation.
- **Gap** (confirmed in current code):
  ```python
  # ember/cfg/config.py:66-72
  def load() -> dict[str, Any]:
      config = dict(DEFAULTS)
      path = paths.config_path()
      if path.exists():
          try:
              config.update(json.loads(path.read_text()))
          except json.JSONDecodeError:
              pass  # malformed config silently falls back to defaults
  ```
  New config keys since last scan: `server_auth_token`, `s3_access_key_id`, `s3_secret_access_key`. Tampered values for these have higher impact than before.
- **Mitigation**: Validate the `host` key against a loopback allowlist before binding. Validate `server_auth_token` is not a trivially guessable value. For the S3 credentials, document that they must not be stored in the config file in production (IAM roles are preferred).
- **Existing controls xref**: → constitution Article XIII §13.5 (config resolution centralized in `config.resolve()`; the gap is value validation)

---

#### T-005: Pidfile has no integrity check
- **Severity**: MEDIUM
- **Status**: open
- **Component**: server
- **Flow**: Z4 (server.pid) → Z3 (process signal)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-09
- **Threat scenario**: An attacker with write access to the state directory can replace `server.pid` with an arbitrary PID. The `_is_ember_server` check (confirmed still present in `process.py:86-97`) is a strong compensating control, but a sophisticated attacker who can also control a process with `"ember.serving.server"` in its argv could bypass it.
- **Gap**: The pidfile is a plain text file with no MAC or signature. `_is_ember_server` checks the command string via `/bin/ps` — a strong heuristic but not cryptographic.
- **Mitigation**: For a local-first tool, `_is_ember_server` + `/health` cross-check is a reasonable compensating control. Document as an accepted residual risk in `SECURITY.md`. For higher assurance, use a Unix domain socket.
- **Existing controls xref**: → constitution Article IV (PID-tracked stop)

---

### R — Repudiation

| ID    | Severity | Status   | Component | Flow / Component                    | Title                                              | First Seen | Last Confirmed | Resolved   |
|-------|----------|----------|-----------|-------------------------------------|----------------------------------------------------|------------|----------------|------------|
| R-002 | MEDIUM   | open     | mcp       | Z0→Z1: advise tool call             | advise calls not logged with state/questions       | 2026-10-04 | 2026-10-09     | —          |
| R-003 | MEDIUM   | open     | mcp       | Z1: MCP stderr logging              | MCP logs are human-readable, not structured        | 2026-10-04 | 2026-10-09     | —          |
| R-004 | MEDIUM   | open     | cli       | Z4: model lifecycle                 | model rm / uninstall --purge-models not logged     | 2026-10-04 | 2026-10-09     | —          |
| R-005 | INFO     | open     | server    | Z2: /health /metrics access         | No access log on health/metrics endpoints          | 2026-10-04 | 2026-10-09     | —          |
| R-001 | HIGH     | fixed    | server    | Z4: process lifecycle               | stop() performs destructive action with no audit log | 2026-10-04 | 2026-10-04   | 2026-10-05 |

#### R-001: stop() performs destructive action with no audit log
- **Severity**: HIGH — **fixed** (2026-10-05, #60). Confirmed: `_append_audit_log()` function added in `ember/serving/process.py:244-262`; called at `process.py:304` ("stop: signaling pid=…") and `process.py:310` ("stop: escalating to SIGKILL for pid=…").

---

#### R-002: advise calls not logged with state/questions
- **Severity**: MEDIUM
- **Status**: open
- **Component**: mcp
- **Flow**: Z0 (agent) → Z1 (MCP advise tool)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-09
- **Threat scenario**: The `advise` tool handler in `mcp_server.py:145-211` does not log question IDs, model label, or answer summary. If an agent makes a decision based on a manipulated ember response, there is no local record of what was asked or answered.
- **Gap** (confirmed in current code):
  ```python
  # ember/mcp/mcp_server.py:145-211
  @mcp.tool()
  async def advise(input: AdviseInput) -> dict[str, Any]:
      # ... no log.info() of question IDs, model, or answer
  ```
  The startup log (`mcp_server.py:220`) logs `server_url` and `autostart` — useful, but not per-call.
- **Mitigation**: Log a structured summary of each `advise` call to stderr: question IDs (not full state), model label, and top answer confidence per question. Avoid logging `state` content.
- **Existing controls xref**: — (no existing control)

---

#### R-003: MCP logs are human-readable, not structured
- **Severity**: MEDIUM
- **Status**: open
- **Component**: mcp
- **Flow**: Z1 (MCP stderr)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-09
- **Threat scenario**: MCP logs (`[ember-mcp] %(message)s`) have no timestamp, request ID, or machine-parseable format. Correlation with server-side events is difficult.
- **Gap** (confirmed in current code):
  ```python
  # ember/mcp/mcp_server.py:48-50
  logging.basicConfig(
      level=logging.INFO, stream=sys.stderr, format="[ember-mcp] %(message)s"
  )
  ```
- **Mitigation**: Switch to structured JSON logging with `timestamp`, `level`, `event`, `server_url`, `autostart` fields.
- **Existing controls xref**: — (no existing control)

---

#### R-004: model rm / uninstall --purge-models not logged
- **Severity**: MEDIUM
- **Status**: open
- **Component**: cli
- **Flow**: Z4 (model files / app dir)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-09
- **Threat scenario**: `ember model rm` and `ember uninstall --purge-models` delete model files without writing any audit log entry.
- **Gap** (confirmed in current code):
  ```python
  # ember/models.py:224-230
  def remove(name: str | None = None) -> str:
      spec = get(name)
      dev = _dev_dir(spec)
      if dev.is_dir():
          shutil.rmtree(dev)
          return f"removed {dev}"  # returns string but writes no log entry
  ```
- **Mitigation**: Append a structured log entry to `server.log` for destructive CLI operations.
- **Existing controls xref**: — (no existing control)

---

#### R-005: No access log on health/metrics endpoints
- **Severity**: INFO
- **Status**: open
- **Component**: server
- **Flow**: Z2 (/health, /metrics)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-09
- **Threat scenario**: Any loopback process can query `/health` and `/metrics` without leaving a structured trace.
- **Gap**: uvicorn's `log_level="info"` logs requests to `server.log` (via the subprocess stdout/stderr redirect), but not structured or per-caller.
- **Mitigation**: Acceptable for single-user local deployment. Document in `SECURITY.md`.
- **Existing controls xref**: → vault/decisions/2026-10-02-expose-prometheus-metrics-on-the-server.md

---

### I — Information Disclosure

| ID    | Severity | Status   | Component | Flow / Component                     | Title                                                                 | First Seen | Last Confirmed | Resolved |
|-------|----------|----------|-----------|--------------------------------------|-----------------------------------------------------------------------|------------|----------------|----------|
| I-001 | MEDIUM   | open     | server    | Z2: /health response                 | /health discloses PID and engine details                              | 2026-10-04 | 2026-10-09     | —        |
| I-002 | MEDIUM   | open     | mcp       | Z1→Z0: ToolError messages            | ToolError may include internal paths or server stack traces           | 2026-10-04 | 2026-10-09     | —        |
| I-006 | MEDIUM   | open     | server    | Z2: /health response                 | /health discloses auth_required and version to any loopback caller    | 2026-10-09 | 2026-10-09     | —        |
| I-003 | LOW      | open     | runtime   | Z3: sys.path                         | Model dir added to sys.path — path disclosure in tracebacks           | 2026-10-04 | 2026-10-09     | —        |
| I-004 | LOW      | open     | server    | Z4: server.log                       | server.log captures all server output including potential state echoes | 2026-10-04 | 2026-10-09     | —       |
| I-005 | LOW      | open     | server    | Z2: /metrics                         | /metrics exposes model name, device, dtype                            | 2026-10-04 | 2026-10-09     | —        |

#### I-001: /health discloses PID and engine details
- **Severity**: MEDIUM
- **Status**: open
- **Component**: server
- **Flow**: Z2 (/health) → any loopback caller
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-09
- **Threat scenario**: `GET /health` returns `{"status": "ok", "pid": <pid>, "engine": {"model": "flash", "device": "mps", "dtype": "float16", "model_dir": "/path/to/model", "max_length": 262144}, "version": "...", "auth_required": false}`. Any loopback process learns the server's PID (useful for targeted signals), the model directory path, device/dtype, package version, and whether bearer auth is required.
- **Gap** (confirmed in current code):
  ```python
  # ember/serving/server.py:270-276
  return {
      "status": "ok" if _ENGINE is not None else "loading",
      "pid": os.getpid(),
      "engine": _ENGINE.describe() if _ENGINE is not None else None,
      "version": _package_version(),
      "auth_required": bool(config.resolve("server_auth_token")),
  }
  # Engine.describe() at runtime.py:452-457 returns model_dir (full path).
  ```
- **Mitigation**: Omit `model_dir` from `Engine.describe()` in the `/health` response (it is not needed by any external caller; the PID cross-check in `tracked_pid` only uses the `pid` field). The `version` and `auth_required` fields are intentional additions for client compatibility — acceptable.
- **Existing controls xref**: → vault/decisions/2026-10-02-expose-prometheus-metrics-on-the-server.md

---

#### I-002: ToolError may include internal paths or server stack traces
- **Severity**: MEDIUM
- **Status**: open
- **Component**: mcp
- **Flow**: Z2 (HTTP error response) → Z1 (ToolError) → Z0 (agent)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-09
- **Threat scenario**: When the model server returns an error, the MCP layer forwards `resp.text` directly in a `ToolError`. A FastAPI validation error or unhandled exception body may contain internal file paths, stack traces, or `sys.path` contents.
- **Gap** (confirmed in current code):
  ```python
  # ember/mcp/mcp_server.py:194-195
  if resp.status_code >= 400:
      raise ToolError(f"ember server error {resp.status_code}: {resp.text}")
  # resp.text is the raw FastAPI response body — may contain detail with paths.
  ```
  401/403 errors now have a sanitized message (`mcp_server.py:189-193`). 4xx/5xx generic errors still forward raw `resp.text`.
- **Mitigation**: Parse the server's JSON error response and extract only the `detail` field. Sanitize `detail` to strip filesystem paths. For 5xx errors, return a generic message and log the full detail to stderr only.
- **Existing controls xref**: — (no existing control)

---

#### I-003: Model dir added to sys.path — path disclosure in tracebacks
- **Severity**: LOW
- **Status**: open
- **Component**: runtime
- **Flow**: Z3 (sys.path) → tracebacks / error messages
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-09
- **Threat scenario**: `sys.path.insert(0, path)` at `runtime.py:147` adds the model directory's full path for the server process lifetime. Unhandled exceptions may include this path in tracebacks, which can be forwarded to the agent via I-002.
- **Gap** (confirmed in current code — same as T-001, accepted by Article V):
  ```python
  # ember/serving/runtime.py:146-147
  if path not in sys.path:
      sys.path.insert(0, path)
  ```
- **Mitigation**: After importing `joint_schema_model`, attempt to remove the model directory from `sys.path` to limit the exposure window. Note: may cause issues if `joint_schema_model` imports other modules from the same directory at runtime.
- **Existing controls xref**: — (no existing control)

---

#### I-004: server.log captures all server output including potential state echoes
- **Severity**: LOW
- **Status**: open
- **Component**: server
- **Flow**: Z3 (server stdout/stderr) → Z4 (server.log)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-09
- **Threat scenario**: `server.log` captures all stdout/stderr from the model server. Any future code change that logs `state` content (e.g., debug logging) would persist sensitive context indefinitely.
- **Gap**: Current code does not log `state`. Risk is prospective.
- **Mitigation**: Add a lint/review rule prohibiting logging of `state`, `questions`, or `answers` content. Document in `RESPONSIBLE_USE.md §privacy`.
- **Existing controls xref**: → RESPONSIBLE_USE.md §privacy

---

#### I-005: /metrics exposes model name, device, dtype
- **Severity**: LOW
- **Status**: open
- **Component**: server
- **Flow**: Z2 (/metrics) → any loopback caller
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-09
- **Threat scenario**: `GET /metrics` exposes `ember_model_info{model="flash",device="mps",dtype="float16"}`. In a shared-namespace environment, this fingerprints the server.
- **Gap**: Intentional design.
- **Mitigation**: Accepted risk for default single-user deployment. Document in `SECURITY.md`.
- **Existing controls xref**: → vault/decisions/2026-10-02-expose-prometheus-metrics-on-the-server.md

---

#### I-006: /health discloses auth_required and version to any loopback caller
- **Severity**: MEDIUM
- **Status**: open
- **Component**: server
- **Flow**: Z2 (/health) → any loopback caller
- **Trust-zone crossing**: Z2 → Z0 (via loopback)
- **First seen**: 2026-10-09
- **Last confirmed**: 2026-10-09
- **Threat scenario**: `/health` now includes two new fields added since the last scan: `version` (the `ember-advise` package version) and `auth_required` (a boolean indicating whether bearer auth is active). These fields are intentionally public for client compatibility — but in a shared-namespace environment they allow any loopback process to (1) determine whether the server is protected by a bearer token (useful for attack planning: if `auth_required=false`, the inference endpoint is unprotected), and (2) identify the exact package version (useful for CVE matching).
- **Gap** (confirmed in current code):
  ```python
  # ember/serving/server.py:270-276
  return {
      ...
      "version": _package_version(),           # discloses package version
      "auth_required": bool(config.resolve("server_auth_token")),  # discloses auth status
  }
  ```
- **Mitigation**: For the default single-user loopback deployment, these disclosures are acceptable and intentional (the `/health` endpoint is how the MCP client learns whether auth is needed). For shared-namespace deployments, document in `SECURITY.md` that `/health` discloses auth status. Consider only exposing `auth_required` on the protected path (behind bearer auth) if this becomes a concern.
- **Existing controls xref**: → SECURITY.md §security-sensitive-design-notes (loopback-only by default); → vault/decisions/2026-10-02-expose-prometheus-metrics-on-the-server.md (no-auth design intent)
- **Notes**: Unlike I-001 (model_dir disclosure), this is partially intentional design — `auth_required` lets the client know whether to send a credential. The risk is the same loopback boundary as all other endpoints. Tracked separately from I-001 because it covers newly-added fields.

---

### D — Denial of Service

| ID    | Severity | Status   | Component | Flow / Component                     | Title                                                   | First Seen | Last Confirmed | Resolved   |
|-------|----------|----------|-----------|--------------------------------------|---------------------------------------------------------|------------|----------------|------------|
| D-004 | MEDIUM   | open     | server    | Z4: server.log                       | server.log grows without rotation                       | 2026-10-04 | 2026-10-09     | —          |
| D-005 | MEDIUM   | open     | server    | Z4: autostart TOCTOU                 | Multiple MCP autostart calls race to spawn server       | 2026-10-04 | 2026-10-09     | —          |
| D-006 | MEDIUM   | open     | server    | Z4→Z5: EMBER_MODEL_S3_URI download   | S3 model download at startup has no timeout or size cap | 2026-10-09 | 2026-10-09     | —          |
| D-007 | MEDIUM   | open     | runtime   | Z2→Z3: media decode before the check | Oversized media decoded in full before refusal          | 2026-10-09 | 2026-10-09     | —          |
| D-003 | MEDIUM   | fixed    | server    | Z2: uvicorn                          | uvicorn started without concurrency or timeout limits   | 2026-10-04 | 2026-10-09     | 2026-10-09 |
| D-001 | HIGH     | fixed    | server    | Z1→Z2: HTTP /v1/systemone            | No rate limiting on inference endpoint                  | 2026-10-04 | 2026-10-04     | 2026-10-05 |
| D-002 | HIGH     | fixed    | runtime   | Z2→Z3: encoded request size          | Default 262 144-token context exhausts MPS memory       | 2026-10-04 | 2026-10-09     | 2026-10-05 |

#### D-001: No rate limiting on inference endpoint
- **Severity**: HIGH — **fixed** (2026-10-05, #59). Confirmed: `AdmissionError` semaphore (`MAX_PENDING_ADVISE=4`) at `runtime.py:54-63`, raised in `Engine.advise()` at `runtime.py:354-358`, mapped to HTTP 503 in `server.py:327-328`.

---

#### D-002: Default 262 144-token context exhausts MPS memory
- **Severity**: HIGH — **fixed** (2026-10-05, #59; mechanism replaced 2026-10-09 by `003-context-window-audit`). Confirmed: `measure()` in `ember/serving/request_size.py` counts the full encoded request (state, media, questions, schema, and prompt wrapper) with upstream `encode_record` at `max_length=sys.maxsize`, so nothing is truncated while counting. `Engine._run_advise` in `ember/serving/runtime.py` refuses a request whose total exceeds the enforced limit with `RequestTooLargeError` before inference, mapped to HTTP 413 in `server.py` with the token split in `detail`, and returns 500 instead of an answer if the model saw a different count. The limits come from `ember/serving/limits.py`: the per-request cap defaults to the loaded model's measured value, or until then to that model's own fallback (the longest probe length that fits its memory budget), `0` disables it, and the effective maximum still applies. The earlier check tokenized only `str(state)`, so questions, schema, wrapper, and media went uncounted.

---

#### D-003: uvicorn started without concurrency or timeout limits
- **Severity**: MEDIUM — **fixed** (2026-10-09). Confirmed: `limit_concurrency=16` added to `uvicorn.run()` at `server.py:350`. This caps concurrent connections, addressing the main vector. Note: `timeout_keep_alive` is still not explicitly set (uses uvicorn's default of 5 seconds), which is acceptable.
- **Resolved**: 2026-10-09

---

#### D-004: server.log grows without rotation
- **Severity**: MEDIUM
- **Status**: open
- **Component**: server
- **Flow**: Z3 (server output) → Z4 (server.log)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-09
- **Threat scenario**: `server.log` is opened in append mode (`"ab"`) at `process.py:147` with no size cap or rotation. High-volume inference (benchmark run, runaway agent) can fill the disk.
- **Gap** (confirmed in current code):
  ```python
  # ember/serving/process.py:147-148
  with open(paths.server_log_path(), "ab") as handle:
      proc = subprocess.Popen(..., stdout=handle, stderr=handle, ...)
  # Append-only, no size cap or rotation.
  ```
- **Mitigation**: Use `logging.handlers.RotatingFileHandler` (e.g., 10 MB max, 3 backups). Alternatively, redirect stdout/stderr through a size-capped pipe.
- **Existing controls xref**: — (no existing control)

---

#### D-005: Multiple MCP autostart calls race to spawn server
- **Severity**: MEDIUM
- **Status**: open
- **Component**: server
- **Flow**: Z1 (MCP autostart) → Z4 (pidfile) → Z3 (spawn)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-09
- **Threat scenario**: If multiple MCP processes start simultaneously, each calls `process.start()`, which checks `is_up()` then calls `spawn()`. There is no lock around the check-then-spawn sequence.
- **Gap** (confirmed in current code):
  ```python
  # ember/serving/process.py:211-213
  info = health(host, port)
  if info is not None:
      return int(info.get("pid") or 0)
  # ... then spawn() — no file lock around check-then-spawn
  ```
- **Mitigation**: Use `fcntl.flock` on the pidfile to serialize concurrent `process.start()` calls.
- **Existing controls xref**: — (no existing control)

---

#### D-006: S3 model download at startup has no timeout or size cap
- **Severity**: MEDIUM
- **Status**: open
- **Component**: server
- **Flow**: Z4→Z5 (EMBER_MODEL_S3_URI → S3 download → disk)
- **Trust-zone crossing**: Z4 → Z5
- **First seen**: 2026-10-09
- **Last confirmed**: 2026-10-09
- **Threat scenario**: `hosted.resolve()` in `hosted.py:96-97` calls `s3.download_prefix()` at startup with no explicit timeout and no size cap. A misconfigured or maliciously crafted S3 prefix with a very large number of objects or slow network response can block the entire model server startup indefinitely. Additionally, if the operator's IAM role has access to an unexpectedly large bucket, a wildcard prefix download could exhaust disk space.
- **Gap**:
  ```python
  # ember/serving/hosted.py:96-97
  if not model_dir.is_dir() or not any(model_dir.iterdir()):
      s3.download_prefix(bucket, prefix, model_dir, f"{_URI_ENV}={uri!r}")
  # s3.download_prefix uses boto3 defaults — no per-object timeout, no total size limit.
  ```
- **Mitigation**: (1) Add a configurable `EMBER_S3_DOWNLOAD_TIMEOUT` cap (default: 3600s) passed as a boto3 client config. (2) Add a total download size cap (fail if the prefix contains > N GB of objects before downloading). (3) Document the expected model size in the S3 deployment docs.
- **Existing controls xref**: — (no existing control; `_disk_ok` in `models.py` checks local disk for HF downloads but is not called for the hosted S3 path)

---

#### D-007: Oversized media decoded in full before refusal
- **Severity**: MEDIUM
- **Status**: open
- **Component**: runtime
- **Flow**: Z2→Z3 (POST /v1/systemone `images`/`videos` → `media.decode_*` → `request_size.measure`)
- **Trust-zone crossing**: Z2 → Z3
- **First seen**: 2026-10-09 (PR #94 review)
- **Last confirmed**: 2026-10-09
- **Threat scenario**: Counting media exactly needs the decoded images, so `Engine._run_advise` decodes them before the size check. `media.py` allows 32 images and 64 video frames of up to 178,956,970 pixels each (about 512 MiB of RGB per frame), so one request can hold tens of GiB of pixels before it is refused with a 413, and four admitted requests decode concurrently outside the engine lock. Media were decoded before inference, uncounted, before full counting too, so the exposure predates D-002's new check, but it now sits in front of the refusal path.
- **Gap**: no aggregate budget on total pixels or decoded bytes before decoding.
- **Mitigation**: Read each image's header first (`Image.open` without `load()`) and refuse a request whose total pixels exceed a budget sized so the worst admitted request stays safe, before decoding any pixels. `media_kwargs` are already validated before any media is decoded.
- **Existing controls xref**: `media.py` per-image pixel cap and image and frame counts; the admission semaphore (D-001).

---

### E — Elevation of Privilege

| ID    | Severity | Status   | Component | Flow / Component                                              | Title                                                         | First Seen | Last Confirmed | Resolved   |
|-------|----------|----------|-----------|---------------------------------------------------------------|---------------------------------------------------------------|------------|----------------|------------|
| E-003 | HIGH     | open     | runtime   | Z4→Z3: EMBER_MODEL_S3_URI + joint_schema_model import         | S3-supplied model imported without integrity check            | 2026-10-09 | 2026-10-09     | —          |
| E-001 | CRITICAL | wontfix  | runtime   | Z4→Z3: EMBER_MODEL_DIR import                                 | Arbitrary code execution via model-dir import                 | 2026-10-04 | 2026-10-09     | —          |
| E-002 | HIGH     | fixed    | plugin    | Z4→Z3: EMBER_MCP env var                                      | EMBER_MCP resolves to arbitrary executable                    | 2026-10-04 | 2026-10-09     | 2026-10-05 |

#### E-001: Arbitrary code execution via model-dir import
- **Severity**: CRITICAL
- **Status**: wontfix
- **Component**: runtime
- **Flow**: Z4 (EMBER_MODEL_DIR) → Z3 (Python import → OS)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-09
- **Status history**: `open` (2026-10-04) → `fixed` (2026-10-05, #57) → `wontfix` (2026-10-09 — constitution Article V v3.0.0)
- **Threat scenario**: Attacker who can set `EMBER_MODEL_DIR` to a controlled directory places a malicious `joint_schema_model.py`. On server startup, `joint_module()` imports it as executable Python — arbitrary OS code runs with the model server's privileges.
- **Wontfix reason**: Constitution Article V v3.0.0 (2026-10-08): "ember supports any model that can run under its loader contract... `joint_schema_model.py` is imported and executed from whatever directory is resolved, with no SHA-256 integrity check." → `vault/decisions/2026-10-08-article-v-redefined-model-loading.md`.
- **Residual risk**: Accepted. Requires local access to set the env var or write the model directory. OS-level controls (file permissions, process isolation) are the operator's responsibility.
- **Existing controls xref**: → constitution Article V v3.0.0; → SECURITY.md §out-of-scope (`joint_schema_model.py` is upstream Apache-2.0 code)

---

#### E-002: EMBER_MCP resolves to arbitrary executable
- **Severity**: HIGH — **fixed** (2026-10-05, #58). Confirmed: `packages/opencode-plugin/index.js:13-24` now validates `basename(override) !== "ember-mcp"` and checks `existsSync(override)` before accepting `EMBER_MCP`. Falls back to standard candidates if either check fails.

---

#### E-003: S3-supplied model imported without integrity check
- **Severity**: HIGH
- **Status**: open
- **Component**: runtime
- **Flow**: Z4 (EMBER_MODEL_S3_URI env var) → Z5 (S3 download) → Z4 (disk) → Z3 (Python import)
- **Trust-zone crossing**: Z4 → Z5 → Z3
- **First seen**: 2026-10-09
- **Last confirmed**: 2026-10-09
- **Threat scenario**: The hosted S3 deployment path (`hosted.resolve()`) downloads a model from the S3 URI, then `runtime.joint_module()` imports `joint_schema_model.py` from the downloaded directory. An attacker who can control the S3 bucket/prefix (via `EMBER_MODEL_S3_URI`, or a compromised IAM role, or a misconfigured bucket ACL) can inject a malicious `joint_schema_model.py` into the download, which is then executed as Python code in the model server process. This is the S3-path variant of E-001.
- **Gap**:
  ```python
  # ember/serving/hosted.py:96-97
  if not model_dir.is_dir() or not any(model_dir.iterdir()):
      s3.download_prefix(bucket, prefix, model_dir, ...)
  # Then runtime.load_clef(model_dir) → joint_module(model_dir) → import joint_schema_model
  # No integrity check on the downloaded content.
  ```
- **Mitigation**: (1) Restrict `EMBER_MODEL_S3_URI` to immutable environment variables in the deployment platform (e.g., sealed Outerbounds parameters). (2) Use S3 bucket versioning and IAM policies to ensure only trusted model artifacts are written to the allowed S3 prefix. (3) Document in `SECURITY.md` that hosted deployments using `EMBER_MODEL_S3_URI` depend on S3 access controls for code integrity.
- **Existing controls xref**: → constitution Article V v3.0.0 (no hash verification by design); → SECURITY.md §security-sensitive-design-notes (operator responsible for access controls in non-loopback / cloud deployments)
- **Notes**: This threat shares the root cause of E-001 but via the new hosted S3 path. It is rated HIGH rather than CRITICAL because it requires either control of the S3 bucket (requires AWS credential compromise) or control of `EMBER_MODEL_S3_URI` (requires env var injection at deployment time). The constitutionally accepted risk for E-001 applies here as well — but the attack surface is larger because S3 is a networked resource rather than a local filesystem.

---

## Architecture Observations

### 1. Constitution Article V v3.0.0 redefines the model-loading threat model

The major architectural change since the last scan is constitution Article V v3.0.0 (2026-10-08), which explicitly removed mandatory SHA-256 hash verification of model weights and `joint_schema_model.py`. This promotes E-001 and T-001 from engineering gaps to **accepted architectural trade-offs** (`wontfix`). The consequences:

- Any model directory (local or S3-downloaded) is imported as trusted code. OS-level isolation is the only protection.
- The S3 hosted path (E-003) introduces a networked variant of the same risk — mitigated by IAM/bucket ACLs rather than code-level checks.
- The `EMBER_MODEL_DIR` env var remains the highest-severity single-point attack surface for local deployments.

### 2. Bearer auth adds a new config-tampering surface (T-004 expansion)

The addition of `server_auth_token` to the config schema means a tampered `config.json` can now (a) disable authentication on a server that should be protected, or (b) add a backdoor credential to a server the operator thought was unprotected. The T-004 finding is unchanged in severity but its blast radius has increased.

### 3. The loopback boundary is the primary security perimeter

The `Endpoint` module (`endpoint.py`) now enforces the insecure-transport guard (closing S-001). The loopback-only binding remains the primary security boundary for the HTTP server. Any cloud deployment that exposes the server beyond loopback depends on the operator's network controls.

### 4. The MPS inference lock is both a DoS amplifier and a DoS mitigator

The `threading.Lock()` in `Engine.advise` serializes inference. The new `AdmissionError` semaphore (`MAX_PENDING_ADVISE=4`) bounds the queue depth, significantly mitigating D-001. The combination of D-001 (fixed) and D-002 (fixed) makes the availability posture materially stronger.

### 5. S3 hosted path introduces a new network trust-zone boundary

The `EMBER_MODEL_S3_URI` path adds Z5 (network edge) as a trust-zone boundary for hosted deployments. This is the only path where ember actively fetches code from the network at runtime. The S3 trust model depends entirely on AWS IAM policies and bucket ACLs — no ember-side verification occurs.

### 6. CI/workflow hardening remains strong

No CI-layer threats identified. SHA-pinned actions, `permissions: {}`, `persist-credentials: false`, and `zizmor` audit are all in place. → vault/decisions/2026-10-03-harden-github-before-going-public.md

### 7. Media SSRF prevention confirmed

`decode_ref()` in `ember/serving/media.py` and `ALLOWED_MEDIA_KWARGS` allowlist in `runtime.py` are both confirmed active in current code. → vault/discoveries/2026-10-02-media-refs-are-data-uris-not-host-paths.md

---

## STRIDE ↔ Existing Controls Coverage Map

| STRIDE ID | STRIDE Title                                          | Existing controls xref                                                                 | Coverage                                                                                          |
|-----------|-------------------------------------------------------|----------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|
| S-001     | MCP trusts arbitrary server URL                       | SECURITY.md §security-sensitive-design-notes; endpoint.py InsecureEndpointError        | Fixed — Endpoint.resolve() enforces insecure-transport guard                                     |
| S-002     | Model identity unverifiable                           | constitution Article V v3.0.0 (explicit no-hash design)                               | Wontfix — architectural decision; operator responsible for model directory integrity              |
| S-003     | PID reuse TOCTOU                                      | constitution Article IV; SECURITY.md §scope                                            | `_is_ember_server` + `/health` cross-check are strong compensating controls; residual gap        |
| S-004     | EMBER_SERVER_URL non-loopback redirect                | SECURITY.md §security-sensitive-design-notes; RESPONSIBLE_USE.md §privacy              | Operator caveat documented; insecure-transport guard partially mitigates; misconfiguration risk remains |
| S-005     | S3 URI no bucket allowlist                            | constitution Article V v3.0.0; SECURITY.md §security-sensitive-design-notes            | Architectural gap for hosted deployments — S3 bucket ACLs are the operator's control            |
| T-001     | Executable Python from model-controlled dir           | constitution Article V v3.0.0 (explicit architectural design)                          | Wontfix — constitutional decision; no code-level mitigation intended                            |
| T-002     | EMBER_MODEL_DIR without directory validation          | —                                                                                      | Fixed (2026-10-05); structurally: Article V superseded the fix with a broader policy            |
| T-003     | Unreserved media_kwargs forwarded                     | vault/discoveries/2026-10-02-media-refs-are-data-uris-not-host-paths.md               | Fixed — ALLOWED_MEDIA_KWARGS allowlist confirmed in runtime.py                                  |
| T-004     | Config file without integrity check                   | constitution Article XIII §13.5                                                        | Architectural gap — value validation is missing; blast radius expanded with new auth/S3 keys    |
| T-005     | Pidfile without integrity check                       | constitution Article IV                                                                | `_is_ember_server` is a strong compensating control; residual gap accepted                      |
| R-001     | stop() no audit log                                   | constitution Article IV; _append_audit_log() in process.py                             | Fixed — audit log confirmed in process.py:304, 310                                              |
| R-002     | advise calls not logged                               | —                                                                                      | Architectural gap — no existing control                                                          |
| R-003     | MCP logs not structured                               | —                                                                                      | Architectural gap — no existing control                                                          |
| R-004     | model rm / uninstall not logged                       | —                                                                                      | Architectural gap — no existing control                                                          |
| R-005     | No access log on health/metrics                       | vault/decisions/2026-10-02-expose-prometheus-metrics-on-the-server.md                 | No-auth design documented; access logging is an accepted gap                                    |
| I-001     | /health discloses PID and engine details              | vault/decisions/2026-10-02-expose-prometheus-metrics-on-the-server.md                 | model_dir disclosure is an unaddressed gap                                                      |
| I-002     | ToolError includes internal paths/traces              | —                                                                                      | Architectural gap — 401/403 sanitized; other 4xx/5xx still forward raw resp.text               |
| I-003     | sys.path path disclosure in tracebacks                | —                                                                                      | Architectural gap — no existing control                                                          |
| I-004     | server.log potential state echoes                     | RESPONSIBLE_USE.md §privacy                                                            | Privacy intent documented; prospective logging gap is unaddressed                               |
| I-005     | /metrics exposes model identity                       | vault/decisions/2026-10-02-expose-prometheus-metrics-on-the-server.md                 | No-auth design documented; model identity disclosure is an accepted risk                        |
| I-006     | /health discloses auth_required and version           | SECURITY.md §security-sensitive-design-notes; vault/decisions/ metrics doc             | Partially intentional (auth_required for client compatibility); version disclosure is new       |
| D-001     | No rate limiting on /v1/systemone                     | AdmissionError semaphore (MAX_PENDING_ADVISE=4) in runtime.py                         | Fixed — semaphore confirmed; 503-mapped AdmissionError in server.py                            |
| D-002     | Default 262 144-token context                         | Full encoded request counted in request_size.py; enforced in runtime.py from limits.py | Fixed — whole request counted, never truncated; 413 with the token split                       |
| D-003     | uvicorn without concurrency limits                    | limit_concurrency=16 in server.py:350                                                  | Fixed — concurrency cap confirmed in uvicorn.run()                                             |
| D-004     | server.log without rotation                           | —                                                                                      | Architectural gap — no existing control                                                          |
| D-005     | Autostart TOCTOU race                                 | —                                                                                      | Architectural gap — no existing control                                                          |
| D-006     | S3 download no timeout or size cap                    | —                                                                                      | Architectural gap — no existing control for hosted S3 path                                     |
| D-007     | Media decoded before the size check                   | media.py per-image pixel and count caps; D-001 admission semaphore                    | Partial — no aggregate pre-decode pixel budget                                                 |
| E-001     | Arbitrary code execution via model-dir import         | constitution Article V v3.0.0 (explicit architectural design)                          | Wontfix — constitutional decision; OS-level isolation is the mitigation                         |
| E-002     | EMBER_MCP resolves to arbitrary executable            | packages/opencode-plugin/index.js:13-24 basename + existsSync validation               | Fixed — basename validation confirmed in plugin                                                 |
| E-003     | S3-supplied model imported without integrity check    | constitution Article V v3.0.0; SECURITY.md §security-sensitive-design-notes            | Architectural gap for hosted deployments — S3 ACLs are the operator's control                  |

**Summary**: 6 threats are `wontfix`/`fixed` from prior scans; 5 newly confirmed fixes. 4 new threats. 11 threats cross-referenced to existing documented controls. 19 threats are architectural gaps with no existing code-level coverage (9 of which are `wontfix` by design or `fixed`).

---

## Recommendations (Priority Order)

### Immediate (HIGH — new findings)

1. **S-005 / E-003 — Document S3 model-loading trust model in SECURITY.md**
   - `EMBER_MODEL_S3_URI` downloads and executes model code from a network location. The security model depends entirely on S3 IAM/ACL controls.
   - Add a section to `SECURITY.md` describing the hosted-deployment threat model and operator responsibilities.
   - Effort: Trivial (documentation only).

### Short-term (MEDIUM)

2. **T-004 — Validate host value in config before binding**
   - In `server.py` lifespan or `process.spawn()`, validate the `host` config value is a loopback address when `EMBER_SERVER_AUTH_TOKEN` is unset.
   - Effort: Low (5–10 lines).

3. **D-006 — Add timeout and size guard to S3 download**
   - Add `EMBER_S3_DOWNLOAD_TIMEOUT` (default: 3600s) and a size preflight check to `s3.download_prefix()`.
   - Effort: Low–Medium (boto3 client config + paginator size accumulation).

4. **I-001 — Remove model_dir from /health response**
   - Omit `model_dir` from `Engine.describe()` output in the `/health` response.
   - Effort: Trivial (remove one key from `describe()`).

5. **I-002 — Sanitize ToolError messages**
   - Parse FastAPI error bodies and extract only the `detail` field. Strip filesystem paths from error strings.
   - Effort: Low (5–10 lines in `mcp_server.py`).

6. **D-004 — Add server.log rotation**
   - Replace the append-mode file handle with a `RotatingFileHandler` (10 MB, 3 backups).
   - Effort: Low.

7. **D-005 — Add file lock around autostart check-then-spawn**
   - Use `fcntl.flock` on the pidfile to serialize concurrent `process.start()` calls.
   - Effort: Low (5–10 lines in `process.py`).

8. **R-002 — Log advise call summaries**
   - Log question IDs and model label per `advise` call to MCP stderr. Do not log `state` content.
   - Effort: Low (2–3 lines in `mcp_server.py`).

### Medium-term (MEDIUM / LOW)

9. **S-003 / T-005 — Make /health PID cross-check mandatory**
   - Ensure `tracked_pid()` always cross-checks against `/health` when the server is reachable (not conditional on `info` being non-None).
   - Effort: Low.

10. **S-004 — Log a warning when EMBER_SERVER_URL is non-loopback without HTTPS**
    - In `mcp_server.py`, log a security advisory at startup if the endpoint is non-loopback and insecure transport is explicitly allowed.
    - Effort: Trivial.

11. **R-004 — Log destructive CLI operations**
    - Append a structured log entry to `server.log` for `ember model rm` and `ember uninstall --purge-models`.
    - Effort: Low.

---

_Generated by `/stride-review` command | Last full scan: 2026-10-09_
