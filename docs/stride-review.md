# STRIDE Threat Model Review — ember

**Living task-tracking report.** Last updated: 2026-10-04
**Scope**: Full — all components and trust-zone boundaries
**Architecture reference**: `AGENTS.md` (call path, trust zones), `SECURITY.md` (intended threat model)
**Existing controls cross-reference**: `SECURITY.md`, `RESPONSIBLE_USE.md`, `COMPATIBILITY.md`, `.specify/memory/constitution.md`, `vault/decisions/`, `vault/discoveries/`
**Reviewer**: Sisyphus (agent)

---

## Scan History

_A chronological log of every scan run. Newest first._

| Scan Date  | New Threats | Resolved | Regressed | Total Open | Scope |
|------------|-------------|----------|-----------|------------|-------|
| 2026-10-04 | +26         | -0       | +0        | 26         | full  |

_This section grows with each scan — never prune rows._

---

## Progress Summary

| Metric                        | Value  |
|-------------------------------|--------|
| Total threats (all time)      | **26** |
| Currently open                | **26** |
| In progress                   | **0**  |
| Fixed / resolved              | **0**  |
| Wontfix / False positive      | **0**  |
| Resolved rate                 | **0%** |

### Open Threats by Category

| Category                  | Open | Critical | High |
|---------------------------|------|----------|------|
| S — Spoofing              | 4    | 0        | 2    |
| T — Tampering             | 5    | 1        | 2    |
| R — Repudiation           | 5    | 0        | 1    |
| I — Information Disclosure| 5    | 0        | 0    |
| D — Denial of Service     | 5    | 0        | 2    |
| E — Elevation of Privilege| 2    | 1        | 1    |

### Open Threats by Severity

| Severity | Count |
|----------|-------|
| CRITICAL | 2     |
| HIGH     | 8     |
| MEDIUM   | 12    |
| LOW      | 3     |
| INFO     | 1     |

### Trend Since Last Review

- New threats added: +26
- Threats resolved: −0
- Threats regressed: +0

> ⚠️ **Top 3 Risks**:
> 1. **E-001 / T-001** — `EMBER_MODEL_DIR` + `joint_schema_model.py` import: a single env-var controls arbitrary code execution at model-server startup. Spans Tampering (code injection), Elevation of Privilege (ACE), and Spoofing (model identity). CRITICAL severity; no compensating runtime control.
> 2. **E-002** — `EMBER_MCP` env var in the opencode plugin resolves to an arbitrary executable without validation. Any process that can set `EMBER_MCP` in the opencode environment can substitute a malicious binary for `ember-mcp`. HIGH severity.
> 3. **D-001 / D-002** — No rate limiting on `/v1/systemone` combined with a 262 144-token default `max_length`: a runaway agent or any loopback process can exhaust MPS memory and crash the server. HIGH severity; no queue depth or per-request token cap.

---

## Flat Threat Register (All Categories)

_A single flat table covering every threat across all STRIDE categories. Sorted: open first by severity desc, then by ID._

| ID    | Cat | Sev      | Status | Component | Flow / Component                          | Title                                              | Controls xref                                                                 | First Seen | Last Confirmed | Resolved |
|-------|-----|----------|--------|-----------|-------------------------------------------|----------------------------------------------------|-------------------------------------------------------------------------------|------------|----------------|----------|
| E-001 | E   | CRITICAL | open   | runtime   | Z4→Z3: EMBER_MODEL_DIR import             | Arbitrary code execution via model-dir import      | → SECURITY.md §out-of-scope (joint_schema_model.py is upstream code)          | 2026-10-04 | 2026-10-04     | —        |
| T-001 | T   | CRITICAL | open   | runtime   | Z4→Z3: EMBER_MODEL_DIR + sys.path         | Executable Python imported from attacker-controlled dir | → vault/discoveries/2026-10-02-media-refs-are-data-uris-not-host-paths.md (parallel SSRF fix) | 2026-10-04 | 2026-10-04     | —        |
| S-001 | S   | HIGH     | open   | mcp       | Z1→Z2: EMBER_SERVER_URL                   | MCP trusts arbitrary server URL without loopback validation | → SECURITY.md §security-sensitive-design-notes                          | 2026-10-04 | 2026-10-04     | —        |
| S-002 | S   | HIGH     | open   | runtime   | Z4→Z3: EMBER_MODEL_DIR                    | Model identity unverifiable — no weight hash check | → constitution Article V (pinned revisions); → COMPATIBILITY.md §tested-models | 2026-10-04 | 2026-10-04     | —        |
| T-002 | T   | HIGH     | open   | runtime   | Z4→Z3: EMBER_MODEL_DIR                    | EMBER_MODEL_DIR accepted without directory validation | —                                                                            | 2026-10-04 | 2026-10-04     | —        |
| T-003 | T   | HIGH     | open   | runtime   | Z2→Z3: media_kwargs                       | Unreserved media_kwargs forwarded to joint_schema_model | → vault/discoveries/2026-10-02-media-refs-are-data-uris-not-host-paths.md  | 2026-10-04 | 2026-10-04     | —        |
| E-002 | E   | HIGH     | open   | plugin    | Z4→Z3: EMBER_MCP env var                  | EMBER_MCP resolves to arbitrary executable         | —                                                                             | 2026-10-04 | 2026-10-04     | —        |
| D-001 | D   | HIGH     | open   | server    | Z1→Z2: HTTP /v1/systemone                 | No rate limiting on inference endpoint             | → SECURITY.md §scope (DoS in scope)                                           | 2026-10-04 | 2026-10-04     | —        |
| D-002 | D   | HIGH     | open   | runtime   | Z2→Z3: max_length                         | Default 262 144-token context exhausts MPS memory  | → COMPATIBILITY.md §known-issues (context length note)                        | 2026-10-04 | 2026-10-04     | —        |
| R-001 | R   | HIGH     | open   | server    | Z4: process lifecycle                     | stop() performs destructive action with no audit log | → constitution Article IV (PID-tracked stop)                                | 2026-10-04 | 2026-10-04     | —        |
| S-003 | S   | MEDIUM   | open   | server    | Z4→Z3: pidfile TOCTOU                     | PID reuse window between pidfile read and kill     | → constitution Article IV; → SECURITY.md §scope (process.py in scope)        | 2026-10-04 | 2026-10-04     | —        |
| S-004 | S   | MEDIUM   | open   | mcp       | Z1→Z2: EMBER_SERVER_URL scheme            | EMBER_SERVER_URL can redirect MCP to non-loopback  | → SECURITY.md §security-sensitive-design-notes                                | 2026-10-04 | 2026-10-04     | —        |
| T-004 | T   | MEDIUM   | open   | server    | Z4: config.json                           | Config file loaded without integrity check         | —                                                                             | 2026-10-04 | 2026-10-04     | —        |
| T-005 | T   | MEDIUM   | open   | server    | Z4: server.pid                            | Pidfile has no integrity check                     | → constitution Article IV                                                     | 2026-10-04 | 2026-10-04     | —        |
| R-002 | R   | MEDIUM   | open   | mcp       | Z0→Z1: advise tool call                   | advise calls not logged with state/questions       | —                                                                             | 2026-10-04 | 2026-10-04     | —        |
| R-003 | R   | MEDIUM   | open   | mcp       | Z1: MCP stderr logging                    | MCP logs are human-readable, not structured        | —                                                                             | 2026-10-04 | 2026-10-04     | —        |
| R-004 | R   | MEDIUM   | open   | cli       | Z4: model lifecycle                       | model rm / uninstall --purge-models not logged     | —                                                                             | 2026-10-04 | 2026-10-04     | —        |
| I-001 | I   | MEDIUM   | open   | server    | Z2: /health response                      | /health discloses PID and engine details           | → vault/decisions/2026-10-02-expose-prometheus-metrics-on-the-server.md       | 2026-10-04 | 2026-10-04     | —        |
| I-002 | I   | MEDIUM   | open   | mcp       | Z1→Z0: ToolError messages                 | ToolError may include internal paths or server stack traces | —                                                                     | 2026-10-04 | 2026-10-04     | —        |
| D-003 | D   | MEDIUM   | open   | server    | Z2: uvicorn                               | uvicorn started without concurrency or timeout limits | —                                                                           | 2026-10-04 | 2026-10-04     | —        |
| D-004 | D   | MEDIUM   | open   | server    | Z4: server.log                            | server.log grows without rotation                  | —                                                                             | 2026-10-04 | 2026-10-04     | —        |
| D-005 | D   | MEDIUM   | open   | server    | Z4: autostart TOCTOU                      | Multiple MCP autostart calls race to spawn server  | —                                                                             | 2026-10-04 | 2026-10-04     | —        |
| I-003 | I   | LOW      | open   | runtime   | Z3: sys.path                              | Model dir added to sys.path — path disclosure in tracebacks | —                                                                     | 2026-10-04 | 2026-10-04     | —        |
| I-004 | I   | LOW      | open   | server    | Z4: server.log                            | server.log captures all server output including potential state echoes | → RESPONSIBLE_USE.md §privacy                                  | 2026-10-04 | 2026-10-04     | —        |
| I-005 | I   | LOW      | open   | server    | Z2: /metrics                              | /metrics exposes model name, device, dtype         | → vault/decisions/2026-10-02-expose-prometheus-metrics-on-the-server.md       | 2026-10-04 | 2026-10-04     | —        |
| R-005 | R   | INFO     | open   | server    | Z2: /health /metrics access               | No access log on health/metrics endpoints          | → vault/decisions/2026-10-02-expose-prometheus-metrics-on-the-server.md       | 2026-10-04 | 2026-10-04     | —        |

_Sort order: open/in_progress first (by severity desc), then fixed/wontfix (by resolved_date desc)._

---

## Detailed Threat Register

_Per-category context for each threat — scenario, gap, mitigation, and trust-zone flow._

---

### S — Spoofing

| ID    | Severity | Status | Component | Flow / Component                    | Title                                              | First Seen | Last Confirmed | Resolved |
|-------|----------|--------|-----------|-------------------------------------|----------------------------------------------------|------------|----------------|----------|
| S-001 | HIGH     | open   | mcp       | Z1→Z2: EMBER_SERVER_URL             | MCP trusts arbitrary server URL without loopback validation | 2026-10-04 | 2026-10-04 | — |
| S-002 | HIGH     | open   | runtime   | Z4→Z3: EMBER_MODEL_DIR              | Model identity unverifiable — no weight hash check | 2026-10-04 | 2026-10-04     | —        |
| S-003 | MEDIUM   | open   | server    | Z4→Z3: pidfile TOCTOU               | PID reuse window between pidfile read and kill     | 2026-10-04 | 2026-10-04     | —        |
| S-004 | MEDIUM   | open   | mcp       | Z1→Z2: EMBER_SERVER_URL scheme      | EMBER_SERVER_URL can redirect MCP to non-loopback  | 2026-10-04 | 2026-10-04     | —        |

#### S-001: MCP trusts arbitrary server URL without loopback validation

- **Severity**: HIGH
- **Status**: open
- **Component**: mcp
- **Flow**: Z1 (ember-mcp) → Z2 (HTTP server via EMBER_SERVER_URL)
- **Trust-zone crossing**: Z1 → Z2
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: An attacker who can set `EMBER_SERVER_URL` in the MCP process environment (e.g., via a compromised opencode plugin config, a malicious `.env`, or environment injection through the agent) redirects all `advise` calls to an attacker-controlled server. The attacker's server can return crafted probabilities to manipulate agent decisions, or log the full `state` payload (which may contain code, diffs, or secrets).
- **Gap**:
  ```python
  # ember/mcp/mcp_server.py:40
  SERVER_URL = os.environ.get("EMBER_SERVER_URL", "http://127.0.0.1:8765").rstrip("/")
  # No validation that SERVER_URL resolves to a loopback address.
  # _host_port() parses it but does not reject non-loopback hosts.
  ```
- **Mitigation**: At startup, validate that `SERVER_URL`'s hostname resolves to `127.0.0.1` or `::1`; reject non-loopback targets with a clear error. Alternatively, warn loudly when a non-loopback URL is configured.
- **Existing controls xref**: → SECURITY.md §security-sensitive-design-notes (loopback-only design intent documented; the gap is that the MCP layer does not enforce it)
- **Notes**: The default is safe. Risk is operator misconfiguration or environment injection. The opencode plugin also passes `EMBER_SERVER_URL` from `process.env`, so a compromised plugin config is a realistic injection vector.

---

#### S-002: Model identity unverifiable — no weight hash check

- **Severity**: HIGH
- **Status**: open
- **Component**: runtime
- **Flow**: Z4 (model dir) → Z3 (Engine / joint_schema_model)
- **Trust-zone crossing**: Z4 → Z3
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: An attacker who can write to the model directory (or redirect `EMBER_MODEL_DIR` to a directory they control) substitutes tampered weights or a modified `joint_schema_model.py`. The server loads the substituted model without detecting the change. The tampered model returns adversarially crafted probabilities to manipulate agent decisions.
- **Gap**:
  ```python
  # ember/serving/runtime.py:158-163
  backbone = Qwen3_5ForConditionalGeneration.from_pretrained(
      str(model_dir), dtype=dtype, device_map={"": "cpu"}, local_files_only=True
  )
  # ember/serving/runtime.py:170
  head.load_state_dict(load_file(model_dir / "joint_head.safetensors"), strict=True)
  # strict=True checks tensor shapes but not cryptographic integrity.
  # No SHA-256 or HF revision hash verification at load time.
  ```
- **Mitigation**: At `Engine.__init__`, verify the SHA-256 of `joint_head.safetensors` and `joint_schema_model.py` against values pinned in `REGISTRY`. Alternatively, verify the HF snapshot hash via `huggingface_hub.snapshot_info`.
- **Existing controls xref**: → constitution Article V (pinned revisions in `REGISTRY`); → COMPATIBILITY.md §tested-models (revision SHAs documented). The gap is that the pinned SHA is used only at download time, not at load time.

---

#### S-003: PID reuse window between pidfile read and kill

- **Severity**: MEDIUM
- **Status**: open
- **Component**: server
- **Flow**: Z4 (pidfile) → Z3 (process signal)
- **Trust-zone crossing**: Z4 → Z3
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: Between `tracked_pid()` reading the pidfile and `stop()` calling `os.kill(pid, SIGTERM)`, the ember server process exits and the OS reuses its PID for an unrelated process. The `_is_ember_server` check uses `/bin/ps` to confirm the command string, which closes most of the window, but there is a residual TOCTOU gap between the `ps` check and the `kill` call.
- **Gap**:
  ```python
  # ember/serving/process.py:116-122
  if not (_pid_alive(pid) and _is_ember_server(pid)):
      pid_file.unlink(missing_ok=True)
      return None
  info = health(host, port)
  # ... then stop() calls os.kill(pid, signal.SIGTERM)
  # Window between _is_ember_server check and os.kill
  ```
- **Mitigation**: After `_is_ember_server` confirms the PID, cross-check the `/health` endpoint's reported `pid` field against the pidfile value before signaling. This is already partially done in `tracked_pid` but the cross-check is conditional (`if info and info.get("pid") not in (None, pid)`). Make the cross-check mandatory when a server is reachable.
- **Existing controls xref**: → constitution Article IV (PID-tracked stop, no kill-by-port); → SECURITY.md §scope (process.py in scope). The `_is_ember_server` check and `/health` cross-check are strong compensating controls; this is a residual low-probability gap.

---

#### S-004: EMBER_SERVER_URL can redirect MCP to non-loopback target

- **Severity**: MEDIUM
- **Status**: open
- **Component**: mcp
- **Flow**: Z1 (ember-mcp) → Z2 (HTTP server)
- **Trust-zone crossing**: Z1 → Z2
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: A user or operator sets `EMBER_SERVER_URL=http://0.0.0.0:8765` or `http://remote-host:8765` in the environment. The MCP server silently connects to the non-loopback target, sending agent `state` (potentially containing secrets) to a remote host. This is a misconfiguration vector, not an active exploit, but it violates the local-first privacy guarantee.
- **Gap**: Same as S-001 — `SERVER_URL` is accepted without scheme/host validation. S-001 covers the active-attacker scenario; S-004 covers the misconfiguration scenario.
- **Mitigation**: Same as S-001 — validate hostname at startup. Log a warning if the URL is non-loopback even if validation is not enforced.
- **Existing controls xref**: → SECURITY.md §security-sensitive-design-notes; → COMPATIBILITY.md §running-in-the-cloud (caveat documented for operators)
- **Notes**: S-001 and S-004 share the same root cause. They are tracked separately because S-001 is an active-attacker scenario and S-004 is an operator-misconfiguration scenario with different mitigations (hard reject vs. warn).

---

### T — Tampering

| ID    | Severity | Status | Component | Flow / Component                    | Title                                                   | First Seen | Last Confirmed | Resolved |
|-------|----------|--------|-----------|-------------------------------------|---------------------------------------------------------|------------|----------------|----------|
| T-001 | CRITICAL | open   | runtime   | Z4→Z3: EMBER_MODEL_DIR + sys.path   | Executable Python imported from attacker-controlled dir | 2026-10-04 | 2026-10-04     | —        |
| T-002 | HIGH     | open   | runtime   | Z4→Z3: EMBER_MODEL_DIR              | EMBER_MODEL_DIR accepted without directory validation   | 2026-10-04 | 2026-10-04     | —        |
| T-003 | HIGH     | open   | runtime   | Z2→Z3: media_kwargs                 | Unreserved media_kwargs forwarded to joint_schema_model | 2026-10-04 | 2026-10-04     | —        |
| T-004 | MEDIUM   | open   | server    | Z4: config.json                     | Config file loaded without integrity check              | 2026-10-04 | 2026-10-04     | —        |
| T-005 | MEDIUM   | open   | server    | Z4: server.pid                      | Pidfile has no integrity check                          | 2026-10-04 | 2026-10-04     | —        |

#### T-001: Executable Python imported from attacker-controlled directory

- **Severity**: CRITICAL
- **Status**: open
- **Component**: runtime
- **Flow**: Z4 (model dir / EMBER_MODEL_DIR) → Z3 (Python import)
- **Trust-zone crossing**: Z4 → Z3
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: An attacker who can set `EMBER_MODEL_DIR` to a directory they control places a malicious `joint_schema_model.py` in that directory. When the model server starts, `joint_module()` inserts the directory into `sys.path` and imports `joint_schema_model` as executable Python. The malicious module runs arbitrary code in the model server process at startup — with the same OS privileges as the user running `ember start`.
- **Gap**:
  ```python
  # ember/serving/runtime.py:84-95
  def joint_module(model_dir: Path) -> Any:
      global _JOINT_MODULE
      if _JOINT_MODULE is None:
          path = str(model_dir.resolve())
          if path not in sys.path:
              sys.path.insert(0, path)
          # import-placement:allow - joint_schema_model ships in the model snapshot.
          import joint_schema_model  # type: ignore[import-not-found]
          _JOINT_MODULE = joint_schema_model
      return _JOINT_MODULE
  # EMBER_MODEL_DIR is accepted without validation in models.resolve_dir():
  # ember/models.py:107-110
  env_dir = os.environ.get("EMBER_MODEL_DIR")
  if override and env_dir:
      path = Path(env_dir)
      return path if path.is_dir() else None  # only checks is_dir(), not content
  ```
- **Mitigation**: (1) Before importing `joint_schema_model`, verify its SHA-256 against a value pinned in `REGISTRY`. (2) Validate that `EMBER_MODEL_DIR` contains the expected model files (e.g., `joint_head_config.json`, `joint_head.safetensors`) before accepting it. (3) Consider importing `joint_schema_model` from a fixed, trusted path rather than from an env-var-controlled directory.
- **Existing controls xref**: → SECURITY.md §out-of-scope (`joint_schema_model.py` is upstream Apache-2.0 code; weight-level issues are out of scope). The gap is that `EMBER_MODEL_DIR` is an env-var attack surface that the out-of-scope declaration does not address.
- **Notes**: This is the highest-severity finding. It is a local privilege escalation, not a remote one — an attacker must be able to set env vars in the model server's process environment. On a single-user workstation this requires local access; in a shared environment (container, multi-user server) it is more accessible.

---

#### T-002: EMBER_MODEL_DIR accepted without directory validation

- **Severity**: HIGH
- **Status**: open
- **Component**: runtime
- **Flow**: Z4 (EMBER_MODEL_DIR env var) → Z3 (Engine)
- **Trust-zone crossing**: Z4 → Z3
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: `EMBER_MODEL_DIR` is accepted as the model directory if it `is_dir()`. No check is made that the directory contains a legitimate model snapshot (expected files, correct structure). An attacker can point it at any directory containing a `joint_schema_model.py` (see T-001) or at a directory with tampered weights.
- **Gap**:
  ```python
  # ember/models.py:107-110
  env_dir = os.environ.get("EMBER_MODEL_DIR")
  if override and env_dir:
      path = Path(env_dir)
      return path if path.is_dir() else None
  # Only checks is_dir(); no validation of expected model files.
  ```
- **Mitigation**: Add a `_validate_model_dir(path)` function that checks for the presence of required files (`joint_head_config.json`, `joint_head.safetensors`, `joint_schema_model.py`, `config.json`) before accepting the directory. Raise a clear error if validation fails.
- **Existing controls xref**: — (no existing control addresses this gap)

---

#### T-003: Unreserved media_kwargs forwarded to joint_schema_model

- **Severity**: HIGH
- **Status**: open
- **Component**: runtime
- **Flow**: Z2 (HTTP /v1/systemone) → Z3 (joint_schema_model.systemone)
- **Trust-zone crossing**: Z2 → Z3
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: The `media_kwargs` field in `AdviseRequest` allows the caller to pass arbitrary keyword arguments to `joint_schema_model.systemone` (via the processor). Only the keys in `RESERVED_MEDIA_KWARGS` (`text`, `images`, `videos`, `return_tensors`) are blocked. Any other key passes through unchecked. A malicious or misbehaving agent could use this to tamper with processor behavior, override internal parameters, or trigger unexpected code paths in `joint_schema_model`.
- **Gap**:
  ```python
  # ember/serving/runtime.py:229-236
  if media_kwargs:
      reserved = RESERVED_MEDIA_KWARGS.intersection(media_kwargs)
      if reserved:
          raise ValueError(
              "media_kwargs may not set reserved keys: " + ", ".join(sorted(reserved))
          )
      request["media_kwargs"] = media_kwargs  # all non-reserved keys pass through
  ```
- **Mitigation**: Switch from a blocklist (`RESERVED_MEDIA_KWARGS`) to an allowlist of explicitly permitted `media_kwargs` keys. Document the permitted keys in the API schema. Reject any key not on the allowlist.
- **Existing controls xref**: → vault/discoveries/2026-10-02-media-refs-are-data-uris-not-host-paths.md (parallel SSRF fix for media refs; `media_kwargs` was not in scope of that discovery)

---

#### T-004: Config file loaded without integrity check

- **Severity**: MEDIUM
- **Status**: open
- **Component**: server
- **Flow**: Z4 (config.json) → Z2 (server config)
- **Trust-zone crossing**: Z4 → Z2
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: An attacker with write access to `~/Library/Application Support/ember/config.json` can tamper with the config to change `host` (exposing the server beyond loopback), `port` (DoS via port conflict), `device` (forcing CPU for performance degradation), or `model` (pointing to a different model). The config is loaded without any integrity check.
- **Gap**:
  ```python
  # ember/cfg/config.py:37-40
  try:
      config.update(json.loads(path.read_text()))
  except json.JSONDecodeError:
      pass  # malformed config silently falls back to defaults; tampered config accepted
  ```
- **Mitigation**: For the `host` key specifically, validate that the resolved value is a loopback address before binding. For other keys, add range/type validation. Consider documenting that the config file is a trust boundary.
- **Existing controls xref**: → constitution Article XIII §13.5 (all layers read config through `config.resolve()`; the gap is that `resolve()` does not validate values)

---

#### T-005: Pidfile has no integrity check

- **Severity**: MEDIUM
- **Status**: open
- **Component**: server
- **Flow**: Z4 (server.pid) → Z3 (process signal)
- **Trust-zone crossing**: Z4 → Z3
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: An attacker with write access to the state directory can replace `server.pid` with an arbitrary PID. The `_is_ember_server` check mitigates this by verifying the process command string, but a sophisticated attacker who can also control a process with the right command string in its argv could bypass this check.
- **Gap**: The pidfile is a plain text file with no MAC or signature. The `_is_ember_server` check is a strong compensating control but not cryptographic.
- **Mitigation**: The `_is_ember_server` + `/health` cross-check is a reasonable compensating control for a local-first tool. Document this as an accepted residual risk in `SECURITY.md`. For higher assurance, use a Unix domain socket or a shared secret written to the pidfile at spawn time.
- **Existing controls xref**: → constitution Article IV (PID-tracked stop; `_is_ember_server` check documented)

---

### R — Repudiation

| ID    | Severity | Status | Component | Flow / Component                    | Title                                              | First Seen | Last Confirmed | Resolved |
|-------|----------|--------|-----------|-------------------------------------|----------------------------------------------------|------------|----------------|----------|
| R-001 | HIGH     | open   | server    | Z4: process lifecycle               | stop() performs destructive action with no audit log | 2026-10-04 | 2026-10-04   | —        |
| R-002 | MEDIUM   | open   | mcp       | Z0→Z1: advise tool call             | advise calls not logged with state/questions       | 2026-10-04 | 2026-10-04     | —        |
| R-003 | MEDIUM   | open   | mcp       | Z1: MCP stderr logging              | MCP logs are human-readable, not structured        | 2026-10-04 | 2026-10-04     | —        |
| R-004 | MEDIUM   | open   | cli       | Z4: model lifecycle                 | model rm / uninstall --purge-models not logged     | 2026-10-04 | 2026-10-04     | —        |
| R-005 | INFO     | open   | server    | Z2: /health /metrics access         | No access log on health/metrics endpoints          | 2026-10-04 | 2026-10-04     | —        |

#### R-001: stop() performs destructive action with no audit log

- **Severity**: HIGH
- **Status**: open
- **Component**: server
- **Flow**: Z4 (pidfile) → Z3 (SIGTERM/SIGKILL)
- **Trust-zone crossing**: Z4 → Z3
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: `process.stop()` sends SIGTERM (and SIGKILL on timeout) to the tracked server PID and deletes the pidfile. No log entry records who stopped the server, what PID was signaled, or when. If the server is stopped unexpectedly (e.g., by a misbehaving agent calling `ember stop` via a shell tool), there is no audit trail to diagnose the event.
- **Gap**:
  ```python
  # ember/serving/process.py:259-265
  os.kill(pid, signal.SIGTERM)
  deadline = time.time() + timeout
  while time.time() < deadline and _pid_alive(pid):
      time.sleep(0.2)
  if _pid_alive(pid):
      os.kill(pid, signal.SIGKILL)
  paths.pid_path().unlink(missing_ok=True)
  # No log.info() call recording the stop action.
  ```
- **Mitigation**: Add a `log.info("stopping ember server pid=%d", pid)` call before `os.kill`. Append a timestamped stop entry to `server.log`. This is a low-effort, high-value change.
- **Existing controls xref**: → constitution Article IV (PID-tracked stop is documented; the gap is the missing audit log entry)

---

#### R-002: advise calls not logged with state/questions

- **Severity**: MEDIUM
- **Status**: open
- **Component**: mcp
- **Flow**: Z0 (agent) → Z1 (MCP advise tool)
- **Trust-zone crossing**: Z0 → Z1
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: The `advise` tool handler in `mcp_server.py` does not log the `state`, `questions`, or the returned answer. If an agent makes a decision based on a manipulated ember response (e.g., due to S-001 or T-001), there is no local record of what was asked or answered to support post-incident analysis.
- **Gap**:
  ```python
  # ember/mcp/mcp_server.py:93-131
  @mcp.tool()
  def advise(input: AdviseInput) -> dict[str, Any]:
      _ensure_server()
      payload = {...}
      resp = httpx.post(f"{SERVER_URL}/v1/systemone", json=payload, timeout=300.0)
      # No log.info() of what was asked or answered.
  ```
- **Mitigation**: Log a structured summary of each `advise` call to stderr: question IDs (not full state, to avoid logging sensitive content), the model label, and the top answer per question. Avoid logging `state` content to prevent sensitive data persistence.
- **Existing controls xref**: — (no existing control; `RESPONSIBLE_USE.md §privacy` notes that the server keeps local logs but does not address MCP-layer logging)

---

#### R-003: MCP logs are human-readable, not structured

- **Severity**: MEDIUM
- **Status**: open
- **Component**: mcp
- **Flow**: Z1 (MCP stderr)
- **Trust-zone crossing**: within Z1
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: The MCP server logs to stderr in a human-readable format (`[ember-mcp] %(message)s`). There is no caller identity, no request ID, and no machine-parseable structure. This makes it difficult to correlate MCP events with server-side events or to feed logs into a SIEM.
- **Gap**:
  ```python
  # ember/mcp/mcp_server.py:35-37
  logging.basicConfig(
      level=logging.INFO, stream=sys.stderr, format="[ember-mcp] %(message)s"
  )
  ```
- **Mitigation**: Switch to structured JSON logging (e.g., `python-json-logger`) with fields for `timestamp`, `level`, `event`, `server_url`, and `autostart`. This is a low-priority quality-of-life improvement for a local-first tool.
- **Existing controls xref**: — (no existing control)

---

#### R-004: model rm / uninstall --purge-models not logged

- **Severity**: MEDIUM
- **Status**: open
- **Component**: cli
- **Flow**: Z4 (model files / app dir)
- **Trust-zone crossing**: within Z4
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: `ember model rm` and `ember uninstall --purge-models` delete model files and app state without writing any audit log entry. If a misbehaving agent or script runs these commands, there is no record of what was deleted or when.
- **Gap**:
  ```python
  # ember/models.py:203-209
  def remove(name: str | None = None) -> str:
      spec = get(name)
      dev = _dev_dir(spec)
      if dev.is_dir():
          shutil.rmtree(dev)
          return f"removed {dev}"  # returns a string but does not log
  ```
- **Mitigation**: Add a structured log entry (to `server.log` or a separate audit log) for destructive CLI operations. For `ember uninstall --purge-models`, log the list of paths deleted.
- **Existing controls xref**: — (no existing control)

---

#### R-005: No access log on health/metrics endpoints

- **Severity**: INFO
- **Status**: open
- **Component**: server
- **Flow**: Z2 (/health, /metrics)
- **Trust-zone crossing**: within Z2
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: Any loopback process can query `/health` and `/metrics` without leaving a trace. In a shared-namespace environment (container, multi-user server), this means an attacker can enumerate the server's state and model identity without detection.
- **Gap**: uvicorn's default `log_level="info"` logs HTTP requests to stdout/stderr, but the server redirects both to `server.log`. Access logging is present but not structured or queryable.
- **Mitigation**: For a local-first single-user tool, this is acceptable. Document in `SECURITY.md` that access logging is unstructured. For shared environments, recommend a reverse proxy with access logging.
- **Existing controls xref**: → vault/decisions/2026-10-02-expose-prometheus-metrics-on-the-server.md (no-auth design decision documented)

---

### I — Information Disclosure

| ID    | Severity | Status | Component | Flow / Component                    | Title                                                          | First Seen | Last Confirmed | Resolved |
|-------|----------|--------|-----------|-------------------------------------|----------------------------------------------------------------|------------|----------------|----------|
| I-001 | MEDIUM   | open   | server    | Z2: /health response                | /health discloses PID and engine details                       | 2026-10-04 | 2026-10-04     | —        |
| I-002 | MEDIUM   | open   | mcp       | Z1→Z0: ToolError messages           | ToolError may include internal paths or server stack traces    | 2026-10-04 | 2026-10-04     | —        |
| I-003 | LOW      | open   | runtime   | Z3: sys.path                        | Model dir added to sys.path — path disclosure in tracebacks    | 2026-10-04 | 2026-10-04     | —        |
| I-004 | LOW      | open   | server    | Z4: server.log                      | server.log captures all server output including potential state echoes | 2026-10-04 | 2026-10-04 | —   |
| I-005 | LOW      | open   | server    | Z2: /metrics                        | /metrics exposes model name, device, dtype                     | 2026-10-04 | 2026-10-04     | —        |

#### I-001: /health discloses PID and engine details

- **Severity**: MEDIUM
- **Status**: open
- **Component**: server
- **Flow**: Z2 (/health) → any loopback caller
- **Trust-zone crossing**: Z2 → Z0 (via loopback)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: `GET /health` returns `{"status": "ok", "pid": <pid>, "engine": {"model": "flash", "device": "mps", "dtype": "float16", "model_dir": "/path/to/model", "max_length": 262144}}`. Any loopback process can query this endpoint and learn the server's PID (useful for targeted signals), the model directory path (useful for T-001/T-002 attacks), and the device/dtype (useful for fingerprinting). In a shared-namespace environment, this is a meaningful information leak.
- **Gap**:
  ```python
  # ember/serving/server.py:189-193
  return {
      "status": "ok" if _ENGINE is not None else "loading",
      "pid": os.getpid(),
      "engine": _ENGINE.describe() if _ENGINE is not None else None,
  }
  # Engine.describe() returns model_dir (full path), device, dtype, max_length.
  ```
- **Mitigation**: For the default single-user loopback deployment, this is acceptable (the PID cross-check in `tracked_pid` depends on it). Consider omitting `model_dir` from the `/health` response, as it is not needed by any caller and discloses a filesystem path. Document the disclosure in `SECURITY.md`.
- **Existing controls xref**: → vault/decisions/2026-10-02-expose-prometheus-metrics-on-the-server.md (no-auth design decision; `/health` disclosure is a parallel concern)

---

#### I-002: ToolError may include internal paths or server stack traces

- **Severity**: MEDIUM
- **Status**: open
- **Component**: mcp
- **Flow**: Z2 (HTTP error response) → Z1 (ToolError) → Z0 (agent)
- **Trust-zone crossing**: Z2 → Z1 → Z0
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: When the model server returns an error, the MCP layer wraps `resp.text` directly in a `ToolError`. If the server returns a FastAPI validation error or an unhandled exception, `resp.text` may contain internal file paths, stack traces, or other implementation details that should not be visible to the calling agent (which may be untrusted or compromised).
- **Gap**:
  ```python
  # ember/mcp/mcp_server.py:127-129
  except httpx.HTTPError as exc:
      raise ToolError(f"ember server request failed: {exc}") from exc
  if resp.status_code >= 400:
      raise ToolError(f"ember server error {resp.status_code}: {resp.text}")
  # resp.text may contain FastAPI's full error body including internal details.
  ```
- **Mitigation**: Parse the server's error response and extract only the `detail` field from FastAPI's error body. Sanitize the detail string to remove file paths before forwarding to the agent. For 5xx errors, return a generic message and log the full detail to stderr.
- **Existing controls xref**: — (no existing control)

---

#### I-003: Model dir added to sys.path — path disclosure in tracebacks

- **Severity**: LOW
- **Status**: open
- **Component**: runtime
- **Flow**: Z3 (sys.path) → tracebacks / error messages
- **Trust-zone crossing**: within Z3
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: `sys.path.insert(0, path)` adds the model directory's full path to Python's module search path for the lifetime of the server process. If an unhandled exception occurs anywhere in the server, the traceback will include the model directory path. This path may be forwarded to the agent via I-002.
- **Gap**:
  ```python
  # ember/serving/runtime.py:89-90
  if path not in sys.path:
      sys.path.insert(0, path)
  ```
- **Mitigation**: After importing `joint_schema_model`, remove the model directory from `sys.path` to limit the exposure window. Note: this may cause issues if `joint_schema_model` imports other modules from the same directory at runtime.
- **Existing controls xref**: — (no existing control; the `import-placement:allow` tag documents the necessity of the import but not the path-disclosure side effect)

---

#### I-004: server.log captures all server output including potential state echoes

- **Severity**: LOW
- **Status**: open
- **Component**: server
- **Flow**: Z3 (server stdout/stderr) → Z4 (server.log)
- **Trust-zone crossing**: Z3 → Z4
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: `server.log` captures all stdout and stderr from the model server process. If any future code change causes `state` content to be logged (e.g., a debug log statement), sensitive agent context (code, diffs, secrets) would persist on disk indefinitely. The current code does not log `state`, but the log file is an unbounded append-only sink.
- **Gap**: The current code does not log `state`. The risk is prospective — a future change could inadvertently add state logging. The log file has no rotation or size cap (see D-004).
- **Mitigation**: Add a lint rule or code review checklist item prohibiting logging of `state`, `questions`, or `answers` content. Document in `RESPONSIBLE_USE.md §privacy` that `server.log` must not contain inference inputs.
- **Existing controls xref**: → RESPONSIBLE_USE.md §privacy ("the server keeps local logs, so avoid passing secrets you would not keep locally")

---

#### I-005: /metrics exposes model name, device, dtype

- **Severity**: LOW
- **Status**: open
- **Component**: server
- **Flow**: Z2 (/metrics) → any loopback caller
- **Trust-zone crossing**: Z2 → Z0 (via loopback)
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: `GET /metrics` exposes `ember_model_info{model="flash",device="mps",dtype="float16"}`. Any loopback process can learn the model name and device. In a shared-namespace environment, this fingerprints the server for targeted attacks.
- **Gap**: Intentional design — the metrics endpoint is unauthenticated by design (same loopback boundary as the inference endpoint).
- **Mitigation**: For the default single-user loopback deployment, this is an accepted risk. Document in `SECURITY.md` that `/metrics` discloses model identity. For shared environments, recommend binding to a Unix domain socket or adding a reverse proxy with authentication.
- **Existing controls xref**: → vault/decisions/2026-10-02-expose-prometheus-metrics-on-the-server.md ("No authentication: `/metrics` is reachable wherever the server is bound")

---

### D — Denial of Service

| ID    | Severity | Status | Component | Flow / Component                    | Title                                              | First Seen | Last Confirmed | Resolved |
|-------|----------|--------|-----------|-------------------------------------|----------------------------------------------------|------------|----------------|----------|
| D-001 | HIGH     | open   | server    | Z1→Z2: HTTP /v1/systemone           | No rate limiting on inference endpoint             | 2026-10-04 | 2026-10-04     | —        |
| D-002 | HIGH     | open   | runtime   | Z2→Z3: max_length                   | Default 262 144-token context exhausts MPS memory  | 2026-10-04 | 2026-10-04     | —        |
| D-003 | MEDIUM   | open   | server    | Z2: uvicorn                         | uvicorn started without concurrency or timeout limits | 2026-10-04 | 2026-10-04   | —        |
| D-004 | MEDIUM   | open   | server    | Z4: server.log                      | server.log grows without rotation                  | 2026-10-04 | 2026-10-04     | —        |
| D-005 | MEDIUM   | open   | server    | Z4: autostart TOCTOU                | Multiple MCP autostart calls race to spawn server  | 2026-10-04 | 2026-10-04     | —        |

#### D-001: No rate limiting on inference endpoint

- **Severity**: HIGH
- **Status**: open
- **Component**: server
- **Flow**: Z1 (MCP) → Z2 (HTTP /v1/systemone) → Z3 (Engine)
- **Trust-zone crossing**: Z1 → Z2 → Z3
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: Any loopback process (not just the MCP server) can flood `POST /v1/systemone` with inference requests. The engine lock serializes requests, so each request blocks the next, but the queue is unbounded. A runaway agent or a malicious loopback process can keep the server busy indefinitely, preventing legitimate use. Combined with D-002 (large `max_length`), each request can be very expensive.
- **Gap**:
  ```python
  # ember/serving/server.py:202-205
  @app.post("/v1/systemone")
  def systemone_endpoint(req: AdviseRequest) -> dict[str, Any]:
  # No rate limiting, no queue depth limit, no per-client throttle.
  ```
- **Mitigation**: Add a `slowapi` or `fastapi-limiter` rate limiter on `/v1/systemone`. For a local-first tool, a simple token bucket (e.g., 10 requests/minute) is sufficient. Alternatively, add a `limit_concurrency` parameter to `uvicorn.run()` to cap the number of concurrent connections.
- **Existing controls xref**: → SECURITY.md §scope (DoS via malformed payloads is in scope); → constitution Article XIV §14.3 (503 on unloaded model is a partial mitigation)

---

#### D-002: Default 262 144-token context exhausts MPS memory

- **Severity**: HIGH
- **Status**: open
- **Component**: runtime
- **Flow**: Z2 (HTTP request) → Z3 (Engine.advise)
- **Trust-zone crossing**: Z2 → Z3
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: `max_length` defaults to 262 144 tokens (the model's maximum, derived from `config.json`). A caller that sends a request with a very large `state` (e.g., a full codebase dump) can cause the model to allocate a very large KV cache, potentially exhausting MPS unified memory and crashing the server process with an OOM error. There is no per-request token cap.
- **Gap**:
  ```python
  # ember/serving/runtime.py:203-205
  self.max_length = (
      max_length if max_length is not None else model_max_length(self.model_dir)
  )
  # model_max_length returns 262144; no per-request cap.
  ```
- **Mitigation**: Add a configurable `EMBER_MAX_REQUEST_LENGTH` cap (e.g., default 32 768 tokens) that is enforced per request, independent of the model's maximum. The server-level `max_length` can remain at the model maximum for flexibility, but individual requests should be capped.
- **Existing controls xref**: → COMPATIBILITY.md §known-issues ("Context length. `max_length` defaults to the model maximum (262144)"); → constitution Article XIV §14.3 (503 on unloaded model; OOM crash is not covered)

---

#### D-003: uvicorn started without concurrency or timeout limits

- **Severity**: MEDIUM
- **Status**: open
- **Component**: server
- **Flow**: Z2 (uvicorn)
- **Trust-zone crossing**: within Z2
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: `uvicorn.run()` is called with only `host`, `port`, and `log_level`. No `limit_concurrency`, `timeout_keep_alive`, or `backlog` parameters are set. Under a flood of connections, uvicorn will accept and queue them all, consuming file descriptors and memory. The engine lock serializes inference, but the HTTP layer has no protection against connection exhaustion.
- **Gap**:
  ```python
  # ember/serving/server.py:249-254
  uvicorn.run(
      app,
      host=config.resolve("host"),
      port=int(config.resolve("port")),
      log_level="info",
  )
  # No limit_concurrency, timeout_keep_alive, or backlog.
  ```
- **Mitigation**: Add `limit_concurrency=10` (or a configurable value) and `timeout_keep_alive=5` to `uvicorn.run()`. For a local-first tool, these defaults are conservative and safe.
- **Existing controls xref**: — (no existing control)

---

#### D-004: server.log grows without rotation

- **Severity**: MEDIUM
- **Status**: open
- **Component**: server
- **Flow**: Z3 (server output) → Z4 (server.log)
- **Trust-zone crossing**: Z3 → Z4
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: `server.log` is opened in append mode (`"ab"`) with no size cap or rotation. Under high-volume inference (e.g., a benchmark run or a runaway agent), the log file can grow to fill the disk, causing the server to crash or the host to become unresponsive.
- **Gap**:
  ```python
  # ember/serving/process.py:141-142
  with open(paths.server_log_path(), "ab") as handle:
      proc = subprocess.Popen(..., stdout=handle, stderr=handle, ...)
  # Append-only, no size cap or rotation.
  ```
- **Mitigation**: Use Python's `logging.handlers.RotatingFileHandler` (e.g., 10 MB max, 3 backups) for the server log. Alternatively, add a `logrotate` configuration for the log file.
- **Existing controls xref**: — (no existing control)

---

#### D-005: Multiple MCP autostart calls race to spawn server

- **Severity**: MEDIUM
- **Status**: open
- **Component**: server
- **Flow**: Z1 (MCP autostart) → Z4 (pidfile) → Z3 (spawn)
- **Trust-zone crossing**: Z1 → Z4 → Z3
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: If multiple MCP processes start simultaneously (e.g., two opencode instances launching `ember-mcp` at the same time), each calls `process.start()`, which checks `is_up()` and then calls `spawn()`. Between the `is_up()` check and the `spawn()` call, another process may have already spawned the server. Both processes then spawn a server, and the second one fails to bind the port, leaving a zombie process and a stale pidfile.
- **Gap**:
  ```python
  # ember/serving/process.py:200-211
  info = health(host, port)
  if info is not None:
      return int(info.get("pid") or 0)
  # ... then spawn() — no lock around the check-then-spawn sequence
  proc = spawn(model_dir, host, port, device)
  ```
- **Mitigation**: Use a file lock (e.g., `fcntl.flock` on the pidfile) around the check-then-spawn sequence to serialize concurrent autostart attempts. The second process would wait for the lock, then find the server already running and return its PID.
- **Existing controls xref**: — (no existing control; constitution Article IV documents PID tracking but not the race condition)

---

### E — Elevation of Privilege

| ID    | Severity | Status | Component | Flow / Component                    | Title                                              | First Seen | Last Confirmed | Resolved |
|-------|----------|--------|-----------|-------------------------------------|----------------------------------------------------|------------|----------------|----------|
| E-001 | CRITICAL | open   | runtime   | Z4→Z3: EMBER_MODEL_DIR import       | Arbitrary code execution via model-dir import      | 2026-10-04 | 2026-10-04     | —        |
| E-002 | HIGH     | open   | plugin    | Z4→Z3: EMBER_MCP env var            | EMBER_MCP resolves to arbitrary executable         | 2026-10-04 | 2026-10-04     | —        |

#### E-001: Arbitrary code execution via model-dir import

- **Severity**: CRITICAL
- **Status**: open
- **Component**: runtime
- **Flow**: Z4 (EMBER_MODEL_DIR) → Z3 (Python import → OS)
- **Trust-zone crossing**: Z4 → Z3
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: An attacker who can set `EMBER_MODEL_DIR` to a directory they control places a malicious `joint_schema_model.py` in that directory. When the model server starts, `joint_module()` imports it as executable Python. The malicious module runs arbitrary OS-level code in the model server process — reading files, spawning processes, exfiltrating data, or establishing persistence. This is a local privilege escalation: the attacker gains the capabilities of the user running the model server.
- **Gap**: Same root cause as T-001. The EoP angle is that the import executes arbitrary Python code, not just loads data.
  ```python
  # ember/serving/runtime.py:84-95
  def joint_module(model_dir: Path) -> Any:
      global _JOINT_MODULE
      if _JOINT_MODULE is None:
          path = str(model_dir.resolve())
          if path not in sys.path:
              sys.path.insert(0, path)
          import joint_schema_model  # executes on import
          _JOINT_MODULE = joint_schema_model
      return _JOINT_MODULE
  ```
- **Mitigation**: (1) Verify `joint_schema_model.py`'s SHA-256 against a value pinned in `REGISTRY` before importing. (2) Validate `EMBER_MODEL_DIR` against expected model files before accepting it. (3) Consider using `importlib.util.spec_from_file_location` with a restricted loader that prevents side effects, though this is complex for a third-party module.
- **Existing controls xref**: → SECURITY.md §out-of-scope (`joint_schema_model.py` is upstream code; weight-level issues are out of scope). The gap is that `EMBER_MODEL_DIR` is an env-var attack surface that the out-of-scope declaration does not address. → constitution Article IV (no kill-by-port; the analogous principle for model loading would be "no import from unvalidated paths").

---

#### E-002: EMBER_MCP resolves to arbitrary executable

- **Severity**: HIGH
- **Status**: open
- **Component**: plugin
- **Flow**: Z4 (EMBER_MCP env var) → Z3 (opencode spawns the MCP process)
- **Trust-zone crossing**: Z4 → Z3
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: The opencode plugin resolves the `ember-mcp` command from `process.env.EMBER_MCP` first, before checking the standard install locations. If an attacker can set `EMBER_MCP` in the opencode process environment (e.g., via a malicious `.env` file, a compromised shell profile, or environment injection), they can substitute an arbitrary executable for `ember-mcp`. opencode will spawn this executable as the MCP server, giving it access to the MCP stdio channel and the ability to return crafted tool responses to the agent.
- **Gap**:
  ```javascript
  // packages/opencode-plugin/index.js:11-22
  function resolveEmberMcp() {
    const candidates = [
      process.env.EMBER_MCP,  // trusted without validation
      join(homedir(), ".local", "bin", "ember-mcp"),
      "/opt/homebrew/bin/ember-mcp",
      "/usr/local/bin/ember-mcp",
    ].filter(Boolean);
    for (const candidate of candidates) {
      if (existsSync(candidate)) return [candidate];
    }
    return ["ember-mcp"];
  }
  // existsSync checks existence but not that the file is the legitimate ember-mcp.
  ```
- **Mitigation**: (1) Validate that the resolved `EMBER_MCP` path ends with `ember-mcp` (or `ember-mcp.exe` on Windows). (2) Optionally, verify the binary's SHA-256 against a known-good value. (3) Document in the plugin README that `EMBER_MCP` is a trusted configuration value and should not be set from untrusted sources.
- **Existing controls xref**: — (no existing control)

---

## Architecture Observations

### 1. EMBER_MODEL_DIR is the highest-severity cross-cutting concern

`EMBER_MODEL_DIR` + `joint_schema_model.py` import spans three STRIDE categories:
- **Tampering** (T-001, T-002): tampered weights or code injected via the env var
- **Elevation of Privilege** (E-001): arbitrary code execution at model-server startup
- **Spoofing** (S-002): model identity cannot be verified without a hash check

A single env var controls all three. The fix is the same for all three: validate `EMBER_MODEL_DIR` against expected model files and verify `joint_schema_model.py`'s SHA-256 before importing. This is the highest-priority architectural change.

### 2. The loopback boundary is the primary security perimeter

The entire security model depends on OS-level process isolation and the loopback interface. This is a documented design decision (SECURITY.md), not a gap. However:
- Any deployment that exposes the server beyond loopback (cloud, container with shared network namespace) removes this boundary entirely.
- `EMBER_SERVER_URL` (S-001, S-004) and `EMBER_HOST` (T-004) can both bypass the loopback boundary through misconfiguration.
- The loopback boundary is not enforced in code — it is enforced by the default configuration. A validation check at startup would make it structural rather than conventional.

### 3. The MPS inference lock is both a DoS amplifier and a DoS mitigator

The `threading.Lock()` in `Engine.advise` serializes all inference requests. This prevents parallel resource exhaustion (a DoS mitigator) but also means one slow request (e.g., a 262 144-token context) blocks all subsequent requests (a DoS amplifier). The combination of D-001 (no rate limiting) and D-002 (large default `max_length`) makes this a meaningful availability risk.

### 4. No authentication is a documented design decision, not a gap

The absence of authentication on the HTTP and MCP layers is documented in `SECURITY.md` and `RESPONSIBLE_USE.md`. STRIDE does not re-litigate this decision. The threats in this report (S-001, S-004, D-001, I-001, I-005) are consequences of the no-auth design that are not fully addressed by the existing documentation — they require either code-level mitigations or explicit acceptance in `SECURITY.md`.

### 5. CI/workflow hardening is well-executed

The CI workflows are SHA-pinned, start from `permissions: {}`, use `persist-credentials: false`, and are audited by `zizmor` on every PR. No CI-layer threats were identified. → vault/decisions/2026-10-03-harden-github-before-going-public.md

### 6. Media SSRF prevention is well-executed

`decode_ref()` in `ember/serving/media.py` enforces a strict allowlist of content types and rejects non-`data:` refs with a clear error. The per-image pixel cap and total image/frame count caps bound memory usage. → vault/discoveries/2026-10-02-media-refs-are-data-uris-not-host-paths.md

---

## STRIDE ↔ Existing Controls Coverage Map

| STRIDE ID | STRIDE Title                                          | Existing controls xref                                                                 | Coverage                                                                                 |
|-----------|-------------------------------------------------------|----------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------|
| S-001     | MCP trusts arbitrary server URL                       | SECURITY.md §security-sensitive-design-notes                                           | Existing doc covers loopback intent; STRIDE adds Z1→Z2 crossing enforcement gap          |
| S-002     | Model identity unverifiable                           | constitution Article V; COMPATIBILITY.md §tested-models                                | Pinning is at download time only; STRIDE adds load-time verification gap                 |
| S-003     | PID reuse TOCTOU                                      | constitution Article IV; SECURITY.md §scope                                            | `_is_ember_server` + `/health` cross-check are strong compensating controls; residual gap |
| S-004     | EMBER_SERVER_URL non-loopback redirect                | SECURITY.md §security-sensitive-design-notes; COMPATIBILITY.md §running-in-the-cloud   | Operator caveat documented; STRIDE adds misconfiguration enforcement gap                 |
| T-001     | Executable Python from attacker-controlled dir        | SECURITY.md §out-of-scope (upstream code)                                              | Architectural gap — out-of-scope declaration does not address env-var attack surface     |
| T-002     | EMBER_MODEL_DIR without directory validation          | —                                                                                      | Architectural gap — no existing control                                                  |
| T-003     | Unreserved media_kwargs forwarded                     | vault/discoveries/2026-10-02-media-refs-are-data-uris-not-host-paths.md               | Media ref SSRF fixed; media_kwargs blocklist is a parallel gap                           |
| T-004     | Config file without integrity check                   | constitution Article XIII §13.5                                                        | Config resolution is centralized; value validation is the gap                            |
| T-005     | Pidfile without integrity check                       | constitution Article IV                                                                | PID tracking documented; `_is_ember_server` is a strong compensating control            |
| R-001     | stop() no audit log                                   | constitution Article IV (PID-tracked stop)                                             | Stop mechanism documented; audit logging is the gap                                      |
| R-002     | advise calls not logged                               | —                                                                                      | Architectural gap — no existing control                                                  |
| R-003     | MCP logs not structured                               | —                                                                                      | Architectural gap — no existing control                                                  |
| R-004     | model rm / uninstall not logged                       | —                                                                                      | Architectural gap — no existing control                                                  |
| R-005     | No access log on health/metrics                       | vault/decisions/2026-10-02-expose-prometheus-metrics-on-the-server.md                 | No-auth design documented; access logging is an accepted gap                             |
| I-001     | /health discloses PID and engine details              | vault/decisions/2026-10-02-expose-prometheus-metrics-on-the-server.md                 | No-auth design documented; model_dir disclosure is an unaddressed gap                   |
| I-002     | ToolError includes internal paths/traces              | —                                                                                      | Architectural gap — no existing control                                                  |
| I-003     | sys.path path disclosure in tracebacks                | —                                                                                      | Architectural gap — no existing control                                                  |
| I-004     | server.log potential state echoes                     | RESPONSIBLE_USE.md §privacy                                                            | Privacy note covers intent; prospective logging gap is unaddressed                       |
| I-005     | /metrics exposes model identity                       | vault/decisions/2026-10-02-expose-prometheus-metrics-on-the-server.md                 | No-auth design documented; model identity disclosure is an accepted risk                 |
| D-001     | No rate limiting on /v1/systemone                     | SECURITY.md §scope (DoS in scope); constitution Article XIV §14.3                     | DoS is in scope; rate limiting is an unaddressed gap                                     |
| D-002     | Default 262 144-token context                         | COMPATIBILITY.md §known-issues                                                         | Context length documented; per-request cap is the gap                                   |
| D-003     | uvicorn without concurrency limits                    | —                                                                                      | Architectural gap — no existing control                                                  |
| D-004     | server.log without rotation                           | —                                                                                      | Architectural gap — no existing control                                                  |
| D-005     | Autostart TOCTOU race                                 | —                                                                                      | Architectural gap — no existing control                                                  |
| E-001     | Arbitrary code execution via model-dir import         | SECURITY.md §out-of-scope; constitution Article IV                                     | Upstream code out-of-scope; env-var attack surface is an unaddressed gap                |
| E-002     | EMBER_MCP resolves to arbitrary executable            | —                                                                                      | Architectural gap — no existing control                                                  |

**Summary**: 10 threats are cross-referenced to existing documented controls (with STRIDE adding architectural context the existing docs missed). 16 threats are architectural gaps with no existing coverage.

---

## Recommendations (Priority Order)

### Immediate (CRITICAL)

1. **E-001 / T-001 — Validate EMBER_MODEL_DIR and verify joint_schema_model.py before import**
   - Add a `_validate_model_dir(path)` function that checks for required model files.
   - Compute and verify the SHA-256 of `joint_schema_model.py` against a value pinned in `REGISTRY` before importing.
   - This single change closes E-001, T-001, T-002, and S-002 simultaneously.
   - Effort: Medium (requires adding SHA pins to `REGISTRY` and a pre-import check in `joint_module()`).

### Short-term (HIGH)

2. **S-001 / S-004 — Validate EMBER_SERVER_URL is a loopback address**
   - In `mcp_server.py`, at module load time, validate that `SERVER_URL`'s hostname is `127.0.0.1` or `::1`.
   - Reject non-loopback URLs with a clear error message.
   - Effort: Low (5–10 lines in `mcp_server.py`).

3. **E-002 — Validate EMBER_MCP path in the opencode plugin**
   - In `resolveEmberMcp()`, validate that the resolved path ends with `ember-mcp` (or the platform-appropriate binary name).
   - Effort: Low (2–3 lines in `index.js`).

4. **D-001 — Add rate limiting on /v1/systemone**
   - Add a `slowapi` or `fastapi-limiter` rate limiter (e.g., 10 requests/minute per client IP).
   - Alternatively, add `limit_concurrency=10` to `uvicorn.run()`.
   - Effort: Low–Medium (add dependency + 5–10 lines in `server.py`).

5. **D-002 — Add a per-request token cap**
   - Add `EMBER_MAX_REQUEST_LENGTH` (default: 32 768) enforced in `systemone_endpoint` before calling `Engine.advise`.
   - Effort: Low (5–10 lines in `server.py` + config key).

6. **T-003 — Switch media_kwargs from blocklist to allowlist**
   - Define an explicit allowlist of permitted `media_kwargs` keys.
   - Reject any key not on the allowlist.
   - Effort: Low (update `RESERVED_MEDIA_KWARGS` logic in `runtime.py`).

7. **R-001 — Add audit log entry to stop()**
   - Add `log.info("stopping ember server pid=%d", pid)` before `os.kill` in `process.stop()`.
   - Effort: Trivial (1 line).

### Medium-term (MEDIUM)

8. **D-003 — Add uvicorn concurrency and timeout limits**
   - Add `limit_concurrency=10` and `timeout_keep_alive=5` to `uvicorn.run()`.
   - Effort: Trivial (2 parameters).

9. **D-004 — Add server.log rotation**
   - Replace the append-mode file handle with a `RotatingFileHandler` (10 MB, 3 backups).
   - Effort: Low (refactor `spawn()` in `process.py`).

10. **D-005 — Add file lock around autostart check-then-spawn**
    - Use `fcntl.flock` on the pidfile to serialize concurrent `process.start()` calls.
    - Effort: Low (5–10 lines in `process.py`).

11. **I-001 — Remove model_dir from /health response**
    - Omit `model_dir` from `Engine.describe()` in the `/health` response.
    - Effort: Trivial (remove one key from `describe()`).

12. **I-002 — Sanitize ToolError messages**
    - Parse FastAPI error bodies and extract only the `detail` field.
    - Strip file paths from error strings before forwarding to the agent.
    - Effort: Low (5–10 lines in `mcp_server.py`).

13. **T-004 — Validate host value in config**
    - In `config.resolve("host")`, validate that the returned value is a loopback address before it is used to bind the server.
    - Effort: Low (add validation in `server.py` lifespan or `process.spawn()`).

14. **R-002 — Log advise call summaries (question IDs only)**
    - Log question IDs and model label per `advise` call to MCP stderr.
    - Do not log `state` content.
    - Effort: Low (2–3 lines in `mcp_server.py`).

---

_Generated by `/stride-review` command | Last full scan: 2026-10-04_
