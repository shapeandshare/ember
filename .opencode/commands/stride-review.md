---
description: Review the ember architecture and codebase against STRIDE threat categories (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege) using ember's trust-zone model, and maintain a living task-tracking report.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

The argument is an optional target path or component scope (e.g., `ember/mcp/`, `ember/serving/`, `mcp`, `server`, `runtime`, `cli`). If omitted, default to the full ember surface — all components and trust-zone boundaries.

## Goal

Apply the STRIDE threat-modeling methodology against the ember architecture — grounded in the trust-zone model, call path, and boundary-crossing inventory described below — and maintain a **living task-tracking report** in TWO formats:

1. **Living markdown report** at `docs/stride-review.md` — human-readable, with Scan History, Progress Summary, and Flat Threat Register.
2. **Running CSV tracker** at `docs/stride-tracker.csv` — machine-parseable, for import into Sheets/Excel/scripts, tracking each threat's lifecycle across all runs.

If the report already exists, read it, re-check each threat against the current codebase and architecture, merge in new threats, update statuses, and write back both files.

STRIDE complements the existing security documentation (`SECURITY.md`, `RESPONSIBLE_USE.md`, `COMPATIBILITY.md`): those documents record the intended threat model and accepted design decisions; STRIDE identifies architectural threat categories and gaps. Where a threat maps to a documented design decision or accepted risk, cross-reference it rather than re-litigate it.

## STRIDE vs Existing Controls — Scope Clarification

| STRIDE Category | Primary Existing Control | What STRIDE adds |
|---|---|---|
| Spoofing | Loopback-only binding; no auth by design (SECURITY.md) | Identity trust at every trust-zone crossing, not just the HTTP boundary |
| Tampering | Pinned model revisions (Article V); data-URI-only media (SECURITY.md) | Integrity of data in flight and at rest across all DFD flows |
| Repudiation | stderr-only logging in mcp_server; server.log in app dir | Accountability and non-repudiation guarantees per actor and operation |
| Information Disclosure | Local-only inference (Article I); loopback binding | Data classification and confidentiality at every boundary |
| Denial of Service | MPS inference lock; Article XIV 503 on unloaded model | Availability attacks at each layer and flow |
| Elevation of Privilege | PID-tracked stop (Article IV); no shell=True | Privilege escalation paths across trust-zone boundaries |

## Operating Constraints

1. **Architecture-first**: Start from the trust zones and call path below. Threats are identified per data flow and trust-zone boundary, not just per code pattern.
2. **Read-only on source**: Do not modify any source files. Findings only.
3. **Evidence-based**: Every threat must cite the specific data flow, trust-zone crossing, or `file:line` where the gap exists. No vague claims.
4. **Severity rating**: Every threat gets a severity — `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, or `INFO`.
5. **Existing-controls cross-reference**: If a threat is already addressed by a documented design decision, reference it (e.g., `→ SECURITY.md §security-sensitive-design-notes`, `→ constitution Article IV`, `→ vault/decisions/2026-10-03-harden-github-before-going-public.md`) instead of re-documenting the same evidence. Add the architectural context that the existing doc missed.
6. **Component-aware**: Scope each finding with the relevant component(s): `mcp`, `server`, `runtime`, `cli`, `plugin`, `kit`, or `ci`.
7. **Living doc discipline**: The report is the authoritative task list. Every update must preserve: threat IDs, history (`first_seen`, `last_confirmed`, `resolved_date`), and status transitions. Never silently drop a threat — if it is no longer present in the report, it must be explicitly marked `fixed` or `wontfix`.
8. **Tracker sync discipline**: The CSV tracker at `docs/stride-tracker.csv` mirrors the Flat Threat Register. Both must be written in the same run with identical data. Never write one without the other.
9. **Pre-seeded context**: Load architecture docs before scanning. Note trust-zone implications, known accepted risks, and cross-references to existing controls.

## ember Trust-Zone Model

ember is a local-first, single-user tool. There is no multi-tenancy, no cloud data store, and no authentication layer by design. The trust zones are:

| Zone | Name | What it contains |
|------|------|-----------------|
| Z0 | Calling agent | The coding agent (opencode, Claude Code, Codex) that calls the `advise` tool over MCP stdio. Untrusted input source. |
| Z1 | MCP stdio process | `ember/mcp/mcp_server.py` — the JSON-RPC stdio server. stdout is the MCP wire; stderr is the only safe log channel. Validates `AdviseInput` via Pydantic before forwarding. |
| Z2 | HTTP model server | `ember/serving/server.py` — FastAPI on loopback `127.0.0.1:8765` (default). No authentication. Accepts `POST /v1/systemone`, `GET /health`, `GET /metrics`. |
| Z3 | Model runtime | `ember/serving/runtime.py` — torch/MPS engine. Imports `joint_schema_model.py` from the model directory at runtime. Serializes inference behind a threading lock. |
| Z4 | Host storage | App dir (`~/Library/Application Support/ember`): pidfile, logs, config. `.models/clef-flash` or HF cache: pinned weights. |
| Z5 | Network edge | Hugging Face Hub (weight download only, explicit user action). Deployment: any host that runs the server beyond loopback. |

**Call path** (from `AGENTS.md`):
```
Z0: agent ──tools/call advise──► Z1: ember-mcp (stdio, mcp_server.py)
                                    │  lazy autostart via process.start
                                    ▼
                          Z2: HTTP POST /v1/systemone (server.py)
                                    ▼
                          Z3: Engine.advise (runtime.py) → joint_schema_model.systemone
                                    ▼
                          Z3: Qwen3.5 backbone + joint schema head on MPS (fp16)
```

**Key boundary crossings**:
- Z0 → Z1: MCP stdio (JSON-RPC). Input: `AdviseInput` (state, questions, images, videos). No authentication.
- Z1 → Z2: HTTP POST to loopback. Input: JSON payload. No authentication (loopback is the boundary).
- Z2 → Z3: In-process function call. Input: Python dicts. Engine lock serializes.
- Z3 → Z4: Model weight files read at startup. `joint_schema_model.py` imported from model dir.
- Z1 → Z4: Pidfile read/write for autostart. Config file read.
- Z4 → Z5: `ember model pull` downloads weights from HF Hub (explicit, user-initiated).

## Threat Lifecycle Model

Every threat in the report has these fields:

```
<threat-id> | <category> | <severity> | <status> | <component> | <flow/component> | <title> | <first_seen> | <last_confirmed> | <resolved_date>
```

**Threat IDs**: Prefixed by STRIDE letter — `S-001` (Spoofing), `T-001` (Tampering), `R-001` (Repudiation), `I-001` (Information Disclosure), `D-001` (Denial of Service), `E-001` (Elevation of Privilege).

**Component**: `mcp`, `server`, `runtime`, `cli`, `plugin`, `kit`, or `ci`.

**Statuses** (task-tracked):
| Status | Meaning |
|--------|---------|
| `open` | Identified, not yet addressed |
| `in_progress` | Work underway (set when someone starts mitigating it) |
| `fixed` | Confirmed mitigated in codebase or architecture |
| `wontfix` | Accepted risk — will not fix (with reason) |
| `false_positive` | Initial threat assessment was incorrect |

**Status transitions allowed**:
- `open` ↔ `in_progress` ↔ `fixed`
- `fixed` → `open` (regression — mitigation removed)
- `open` → `wontfix` | `false_positive`
- `wontfix` → `open` (re-opened after risk re-evaluation)

**Merge rules** (when report already exists):
1. For each threat in the **existing report**:
   - Re-check the cited flow/component against current architecture and codebase
   - If the gap still exists → update `last_confirmed` to today; keep status
   - If the gap is closed → mark `fixed`, set `resolved_date`
2. For each **new threat** discovered in this scan:
   - Check if it already exists (same flow + same category)
   - If truly new → add with `status: open`, `first_seen: today`, `last_confirmed: today`
3. **Scan History**: Append a new row for this scan. Never prune or edit historical rows.
4. Never delete entries. Never change existing threat IDs.

## Execution Steps

### Phase 0: Architecture and Security Context Load

1. **Read the ember architecture reference documents** — in this order:
   - `AGENTS.md` — "Architecture (call path)", "Architecture Rules", "What to watch out for", and "MCP server" sections
   - `SECURITY.md` — "Scope" (in-scope components) and "Security-sensitive design notes" (loopback-only, no auth, intended threat model)
   - `RESPONSIBLE_USE.md` — privacy section (local inference, server logs)
   - `COMPATIBILITY.md` — "Running in the cloud" (loopback exposure caveat), "Known issues"
   - `.specify/memory/constitution.md` — Article I (local-first), Article IV (lazy lifecycle, PID discipline), Article XIII (layered architecture), Article XIV (pit of success)

2. **Build the threat surface inventory** from the trust-zone model above. For each boundary crossing, note:
   - Source zone and destination zone
   - Data carried (agent state/questions/media, JSON payloads, pidfile, config, model weights)
   - Existing controls (loopback binding, Pydantic validation, data-URI-only media, PID-tracked stop, pinned revisions)
   - Flows to scrutinize: Z0→Z1 (MCP stdio input), Z1→Z2 (HTTP loopback), Z2→Z3 (engine call), Z3→Z4 (model dir import), Z1→Z4 (pidfile/config), Z4→Z5 (HF download)

3. **Load the existing controls cross-reference index** — read the following and note which threats they already address:
   - `SECURITY.md §security-sensitive-design-notes` — loopback-only, no auth, shared-namespace caveat
   - `vault/decisions/2026-10-03-harden-github-before-going-public.md` — CI/workflow hardening
   - `vault/discoveries/2026-10-02-media-refs-are-data-uris-not-host-paths.md` — media SSRF prevention
   - `vault/decisions/2026-10-02-expose-prometheus-metrics-on-the-server.md` — metrics endpoint design
   - Constitution Article IV — PID-tracked stop, no kill-by-port
   - Constitution Article V — pinned model revisions

4. If `$ARGUMENTS` contains a path or component keyword (`mcp`, `server`, `runtime`, `cli`, `plugin`, `kit`, `ci`), scope the review to that component's trust-zone crossings.

### Phase 0.5: Load Existing Report

1. Check if `docs/stride-review.md` exists.
2. If it does, read it in full and parse the threat register into a structured index keyed by `<threat-id>`.
3. Note the current status of each threat.
4. If it does not exist, start from a clean slate. The `docs/` directory will be created on first write.

### Phase 1: Per-Category Analysis

For each of the 6 STRIDE categories below, evaluate threats per data flow and trust-zone boundary. Fire parallel background exploration agents (`subagent_type="explore"`) for bulk code-pattern searches across independent categories — S and T can run in parallel, then R and I, then D and E.

For each threat, capture:
- **Threat ID**: Generated if new (e.g., `S-001`). Preserved if re-checking an existing one.
- **Category**: STRIDE letter (S/T/R/I/D/E) and full name
- **Severity**: CRITICAL / HIGH / MEDIUM / LOW / INFO
- **Component**: `mcp | server | runtime | cli | plugin | kit | ci`
- **Flow/Component**: The specific trust-zone crossing or component where the threat applies (e.g., `Z0→Z1: MCP stdio AdviseInput`)
- **Title**: Short, actionable description
- **Threat scenario**: What an attacker or misbehaving agent could do, using the trust-zone model
- **Gap**: The missing control or architectural weakness
- **Mitigation**: Specific architectural or code fix
- **Existing controls xref**: Corresponding existing control reference if already documented (e.g., `→ SECURITY.md §security-sensitive-design-notes`)
- **First seen**: Today's date if new
- **Last confirmed**: Today's date

---

#### S — Spoofing

**Question**: Can an attacker impersonate a legitimate entity (agent, process, service) at any trust-zone crossing?

**Trust-zone crossings to evaluate:**

| Crossing | What could be spoofed | Controls to verify |
|---|---|---|
| Z0 → Z1 (agent → MCP stdio) | Agent identity — any process that can write to stdin is "the agent" | No authentication on MCP stdio; trust is OS-level process isolation |
| Z1 → Z2 (MCP → HTTP loopback) | HTTP caller identity — any loopback process can call the server | Loopback binding is the only boundary; no token or mTLS |
| Z1 → Z2 (`EMBER_SERVER_URL`) | Server URL — env var can redirect MCP to an arbitrary target | `EMBER_SERVER_URL` trusted without validation |
| Z4 → Z3 (pidfile → process) | Server identity — pidfile records a PID, but PID reuse is possible | `_is_ember_server` checks `/bin/ps` command string |
| Z2 → Z2 (`/health` pid) | Server identity — `/health` reports `os.getpid()` | PID cross-check in `tracked_pid` |
| Z4 → Z3 (model dir → runtime) | Model identity — `EMBER_MODEL_DIR` can point to an arbitrary directory | No cryptographic verification of model weights |

**Code patterns to search:**

```python
# HIGH: EMBER_SERVER_URL trusted without scheme/host validation
SERVER_URL = os.environ.get("EMBER_SERVER_URL", "http://127.0.0.1:8765").rstrip("/")
# ember/mcp/mcp_server.py — any URL accepted, including non-loopback targets

# MEDIUM: PID reuse window in tracked_pid
pid = int(pid_file.read_text().strip())
if not (_pid_alive(pid) and _is_ember_server(pid)):
# ember/serving/process.py — TOCTOU between read and kill

# MEDIUM: No model weight integrity check
backbone = Qwen3_5ForConditionalGeneration.from_pretrained(str(model_dir), ...)
# ember/serving/runtime.py — loads whatever is in model_dir without hash verification

# INFO: MCP stdio has no caller authentication
mcp = MCPServer("ember", instructions=agent_kit.instructions())
# ember/mcp/mcp_server.py — any process that can exec ember-mcp becomes "the agent"
```

Search scope: `ember/mcp/mcp_server.py`, `ember/serving/process.py`, `ember/serving/runtime.py`, `ember/cfg/config.py`

---

#### T — Tampering

**Question**: Can an attacker modify data — in transit, at rest, or in processing — without detection?

**Data flows to evaluate:**

| Flow | Data at risk | Controls to verify |
|---|---|---|
| Z0 → Z1: MCP stdio | `state`, `questions`, `images`, `videos` | Pydantic `AdviseInput` validates types; no content sanitization |
| Z1 → Z2: HTTP loopback | JSON payload forwarded from MCP | Pydantic `AdviseRequest` validates on server side |
| Z4 → Z3: model weights | `joint_head.safetensors`, backbone weights | Pinned revision SHA in `REGISTRY`; no runtime hash check |
| Z4 → Z3: `joint_schema_model.py` | Executable Python imported from model dir | `EMBER_MODEL_DIR` can point to attacker-controlled dir |
| Z4: config file | `config.json` in app dir | JSON file; no integrity check; world-readable by default |
| Z4: pidfile | `server.pid` in app dir | Plain text; no integrity check |
| Z1 → Z2: media payload | base64 image/video data | `decode_ref` validates content type and pixel count; no MIME sniffing |
| Z3: `media_kwargs` | Processor arguments | `RESERVED_MEDIA_KWARGS` blocks key overrides; arbitrary kwargs pass through |

**Code patterns to search:**

```python
# HIGH: joint_schema_model.py imported from EMBER_MODEL_DIR without hash check
if path not in sys.path:
    sys.path.insert(0, path)
import joint_schema_model
# ember/serving/runtime.py — arbitrary code execution if model dir is attacker-controlled

# HIGH: EMBER_MODEL_DIR accepted without validation
env_dir = os.environ.get("EMBER_MODEL_DIR")
if override and env_dir:
    path = Path(env_dir)
    return path if path.is_dir() else None
# ember/models.py — any directory accepted as model dir

# MEDIUM: media_kwargs passes arbitrary kwargs to the processor
if media_kwargs:
    reserved = RESERVED_MEDIA_KWARGS.intersection(media_kwargs)
    ...
    request["media_kwargs"] = media_kwargs
# ember/serving/runtime.py — non-reserved kwargs forwarded to joint_schema_model

# MEDIUM: config.json loaded without integrity check
config.update(json.loads(path.read_text()))
# ember/cfg/config.py — malformed or tampered config silently falls back to defaults

# LOW: safetensors loaded with strict=True but no hash verification
head.load_state_dict(load_file(model_dir / "joint_head.safetensors"), strict=True)
# ember/serving/runtime.py — strict shape check, no cryptographic integrity
```

Search scope: `ember/serving/runtime.py`, `ember/models.py`, `ember/serving/media.py`, `ember/cfg/config.py`, `ember/serving/process.py`

---

#### R — Repudiation

**Question**: Can an actor (agent, user, attacker) deny having performed an action, because the audit trail is incomplete or forgeable?

**Actions that require non-repudiation:**

| Action | Required evidence | Controls to verify |
|---|---|---|
| `advise` tool call | Who called, what state/questions, when | MCP server logs to stderr; no structured audit log |
| Model server start | Who started, what model, when | `server.log` in app dir; process spawned with `start_new_session=True` |
| Model server stop | Who stopped, what PID, when | `stop()` logs nothing; pidfile deleted silently |
| `ember model pull` | Who downloaded, what revision, when | No download audit log; HF cache records revision |
| `ember model rm` | Who deleted, what model, when | `remove()` returns a string but logs nothing |
| CLI destructive ops (`uninstall --purge-models`) | Who ran, what was deleted | No structured audit log |
| `/health` and `/metrics` access | Who queried, when | No access log on health/metrics endpoints |
| Config file changes | Who changed, what values | No change log; config overwritten atomically |

**Code patterns to search:**

```python
# HIGH: stop() performs a destructive action with no audit log
os.kill(pid, signal.SIGTERM)
paths.pid_path().unlink(missing_ok=True)
# ember/serving/process.py — no log entry for who stopped what

# MEDIUM: MCP server logs to stderr but not structured
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="[ember-mcp] %(message)s")
log.info("ember server not running; starting it on %s:%s", host, port)
# ember/mcp/mcp_server.py — human-readable, not machine-parseable; no caller identity

# MEDIUM: advise tool call not logged with state/questions
def advise(input: AdviseInput) -> dict[str, Any]:
    _ensure_server()
    payload = {...}
    resp = httpx.post(...)
# ember/mcp/mcp_server.py — no log of what was asked or answered

# LOW: model remove() returns a string but does not log
return f"removed {dev}"
# ember/models.py — no structured log entry for model deletion

# INFO: server.log captures stdout+stderr of the server process
with open(paths.server_log_path(), "ab") as handle:
    proc = subprocess.Popen(..., stdout=handle, stderr=handle, ...)
# ember/serving/process.py — server output captured, but not structured
```

Search scope: `ember/mcp/mcp_server.py`, `ember/serving/process.py`, `ember/models.py`, `ember/cli.py`, `ember/serving/server.py`

---

#### I — Information Disclosure

**Question**: Can an attacker gain access to data they should not see — in transit, at rest, in errors, or through side channels?

**Data flows and stores to evaluate:**

| Asset | Confidentiality requirement | Controls to verify |
|---|---|---|
| Agent `state` (code, diffs, logs, user messages) | Must not leave the host (Article I) | Local inference; no network call in advise path |
| `state` in server logs | Must not persist sensitive agent context | `server.log` captures all server output; state is not logged by default |
| `state` in MCP stderr | Must not leak to agent's log aggregator | MCP logs to stderr; state not logged in `advise()` |
| `/health` response | Reports `os.getpid()` | PID disclosure to any loopback caller |
| `/metrics` response | Prometheus counters and model info | Token counts, model name, device, dtype exposed to any loopback caller |
| Error messages from `ToolError` | Must not reveal internal paths | `ToolError(str(exc))` may include file paths or stack details |
| `EMBER_*` env vars | Must not be returned by any endpoint | No env-dump endpoint; config endpoint not present |
| Config file (`config.json`) | Contains host/port/device/model settings | World-readable in app dir; no encryption |
| Model weights in `.models/` or HF cache | Proprietary upstream weights | Local files; no network exposure by ember |
| `joint_schema_model.py` import path in `sys.path` | Internal path disclosure | `sys.path.insert(0, path)` adds model dir to Python path |
| Prometheus `ember_model_info` labels | Reveals model name, device, dtype | Exposed on `/metrics` to any loopback caller |

**Code patterns to search:**

```python
# MEDIUM: /health discloses PID to any loopback caller
return {
    "status": "ok" if _ENGINE is not None else "loading",
    "pid": os.getpid(),
    "engine": _ENGINE.describe() if _ENGINE is not None else None,
}
# ember/serving/server.py — pid + model dir + device + dtype exposed

# MEDIUM: ToolError may include internal path or exception detail
raise ToolError(f"ember server request failed: {exc}") from exc
raise ToolError(f"ember server error {resp.status_code}: {resp.text}")
# ember/mcp/mcp_server.py — resp.text may contain server-side stack traces

# LOW: sys.path modified with model dir (path disclosure in tracebacks)
sys.path.insert(0, path)
# ember/serving/runtime.py — model dir path appears in import tracebacks

# LOW: server.log captures all server output including potential state echoes
with open(paths.server_log_path(), "ab") as handle:
    proc = subprocess.Popen(..., stdout=handle, stderr=handle, ...)
# ember/serving/process.py — if server ever logs state, it persists in app dir

# INFO: /metrics exposes model name, device, dtype
MODEL_INFO.labels(model=name, device=_ENGINE.device, dtype=...).set(1)
# ember/serving/server.py — model identity visible to any loopback process
```

Search scope: `ember/serving/server.py`, `ember/mcp/mcp_server.py`, `ember/serving/runtime.py`, `ember/serving/process.py`, `ember/cfg/paths.py`

---

#### D — Denial of Service

**Question**: Can an attacker (or runaway agent) exhaust resources and make the system unavailable?

**Attack vectors to evaluate per layer:**

| Layer / Flow | DoS vector | Controls to verify |
|---|---|---|
| Z0 → Z1: MCP stdio | Flooding `advise` calls | MCP server serializes via HTTP; engine lock queues requests |
| Z1 → Z2: HTTP loopback | Any loopback process can flood `/v1/systemone` | No rate limiting; no request queue depth limit |
| Z2 → Z3: engine lock | Huge `max_length` (262144 tokens) exhausts MPS memory | `max_length` defaults to model maximum; no per-request cap |
| Z2 → Z3: media payload | 32 images × 178 MP each = ~5.7 billion pixels | `MAX_IMAGES=32`, `MAX_IMAGE_PIXELS=178_956_970` per image; total memory unbounded |
| Z3: MPS memory | ~19 GB model + activations; OOM kills the server | No memory guard; OOM is a hard crash |
| Z4: pidfile race | Multiple MCP autostart calls race to spawn the server | `process.start` checks `is_up` first but has a TOCTOU window |
| Z4: server.log | Unbounded log growth from high-volume inference | No log rotation; `server.log` grows indefinitely |
| Z2: uvicorn | No `limit_concurrency` or `timeout_keep_alive` override | `uvicorn.run(app, host=..., port=..., log_level="info")` — defaults only |
| Z1: `START_TIMEOUT` | 300-second wait blocks the MCP process | `START_TIMEOUT=300` default; agent hangs if server never starts |
| Z4: HF cache | `ember model pull` downloads ~18 GB; disk exhaustion | `_disk_ok` checks free space with 1.15× headroom |

**Code patterns to search:**

```python
# HIGH: No rate limiting on /v1/systemone
@app.post("/v1/systemone")
def systemone_endpoint(req: AdviseRequest) -> dict[str, Any]:
# ember/serving/server.py — any loopback caller can flood inference requests

# HIGH: max_length defaults to 262144 — huge context exhausts MPS memory
self.max_length = (
    max_length if max_length is not None else model_max_length(self.model_dir)
)
# ember/serving/runtime.py — no per-request cap; model_max_length returns 262144

# MEDIUM: media total memory not bounded (32 images × up to 178 MP each)
MAX_IMAGES = 32
MAX_IMAGE_PIXELS = 178_956_970  # per image
# ember/serving/media.py — total pixel budget = 32 × 178M = ~5.7B pixels

# MEDIUM: TOCTOU in autostart — multiple callers can race to spawn
info = health(host, port)
if info is not None:
    return int(info.get("pid") or 0)
# ... then spawn() — window between is_up check and spawn
# ember/serving/process.py — no lock around the check-then-spawn sequence

# MEDIUM: uvicorn started without concurrency or timeout limits
uvicorn.run(app, host=config.resolve("host"), port=int(config.resolve("port")), log_level="info")
# ember/serving/server.py — no limit_concurrency, timeout_keep_alive, or backlog

# LOW: server.log grows without rotation
with open(paths.server_log_path(), "ab") as handle:
# ember/serving/process.py — append-only, no size cap or rotation
```

Search scope: `ember/serving/server.py`, `ember/serving/runtime.py`, `ember/serving/media.py`, `ember/serving/process.py`, `ember/mcp/mcp_server.py`

---

#### E — Elevation of Privilege

**Question**: Can an attacker (or misbehaving agent) gain capabilities beyond their intended authorization level — by exploiting trust assumptions, boundary gaps, or privilege escalation paths?

**Privilege boundaries to evaluate:**

| Boundary | EoP vector | Controls to verify |
|---|---|---|
| Z0 → Z3: agent → model runtime | Arbitrary code via `EMBER_MODEL_DIR` + `joint_schema_model.py` import | `EMBER_MODEL_DIR` accepted without validation; imported as executable Python |
| Z0 → Z4: agent → host filesystem | SSRF via media refs (remote URLs, local paths) | `decode_ref` rejects non-`data:` refs; enforced in `ember/serving/media.py` |
| Z0 → Z4: agent → host filesystem | `state` field could encode path traversal if server ever writes it | Server never writes `state` to disk; no path construction from `state` |
| Z1 → Z4: MCP → pidfile | Pidfile TOCTOU — attacker replaces pidfile between read and kill | `_is_ember_server` checks process command; `tracked_pid` cross-checks `/health` |
| Z4 → Z3: plugin → PATH | `ember-mcp` resolved from `EMBER_MCP` or PATH — PATH injection | `resolveEmberMcp()` in plugin checks `existsSync`; falls back to `ember-mcp` in PATH |
| Z2 → Z3: HTTP → OS | No `subprocess` with user-controlled args in server path | Server never calls subprocess; CLI uses fixed argv |
| Z4 → Z3: model dir → Python | `sys.path.insert(0, model_dir)` — any `.py` in model dir is importable | Only `joint_schema_model` is explicitly imported; but model dir is on `sys.path` |
| Z2: `/metrics` | Prometheus endpoint accessible to any loopback process | No auth on `/metrics`; same loopback boundary as `/v1/systemone` |
| CI: workflow permissions | Fork PRs run attacker-controlled workflow code | SHA-pinned actions; `permissions: {}`; `zizmor` audit in CI |

**Code patterns to search:**

```python
# CRITICAL: joint_schema_model.py imported from EMBER_MODEL_DIR — arbitrary code execution
sys.path.insert(0, path)
import joint_schema_model
# ember/serving/runtime.py — if EMBER_MODEL_DIR points to attacker-controlled dir,
# any .py file in that dir is importable; joint_schema_model itself executes on import

# HIGH: EMBER_MODEL_DIR accepted from environment without validation
env_dir = os.environ.get("EMBER_MODEL_DIR")
if override and env_dir:
    path = Path(env_dir)
    return path if path.is_dir() else None
# ember/models.py — no check that the dir is a legitimate model snapshot

# HIGH: ember-mcp resolved from EMBER_MCP env var without validation
const candidates = [
    process.env.EMBER_MCP,
    ...
].filter(Boolean);
for (const candidate of candidates) {
    if (existsSync(candidate)) return [candidate];
}
# packages/opencode-plugin/index.js — EMBER_MCP can point to arbitrary executable

# MEDIUM: sys.path pollution — model dir added to Python path permanently
if path not in sys.path:
    sys.path.insert(0, path)
# ember/serving/runtime.py — any .py in model dir becomes importable for the process lifetime

# MEDIUM: EMBER_SERVER_URL can redirect MCP to a non-loopback target
SERVER_URL = os.environ.get("EMBER_SERVER_URL", "http://127.0.0.1:8765").rstrip("/")
# ember/mcp/mcp_server.py — MCP will POST to any URL, including external hosts

# INFO: /metrics and /health have no auth — same loopback boundary as inference
@app.get("/health")
async def health() -> dict[str, Any]:
@app.get("/metrics")
async def metrics() -> Response:
# ember/serving/server.py — intentional design; loopback is the boundary
```

Search scope: `ember/serving/runtime.py`, `ember/models.py`, `ember/mcp/mcp_server.py`, `packages/opencode-plugin/index.js`, `ember/serving/server.py`, `.github/workflows/`

---

### Phase 2: Deep-Dive for Critical and High Threats

For threats rated `CRITICAL` or `HIGH`:
1. Read the surrounding 20 lines of context to confirm the threat is real (not a false positive)
2. Check for compensating controls (e.g., loopback binding compensating for no HTTP auth; `_is_ember_server` check compensating for PID reuse)
3. Confirm or downgrade the severity
4. Check if an existing control already captures the evidence — if so, reference it and add only the architectural context it missed

### Phase 3: Merge & Reconcile

After completing the scan:

1. **Build the new-threats index**: keyed by `(flow_or_component, category)` for deduplication
2. **Process existing threats** (if report existed):
   - Re-check cited flow/component against current architecture and codebase
   - Apply status transitions per the merge rules above
   - Carry forward all old threats (even resolved ones) into the new report
3. **Merge new threats**: check for duplicates; assign new IDs if truly new (sequential within category: e.g., highest existing `S-N` + 1)
4. **Preserve history**: Never drop resolved/fixed entries.

### Phase 4: Report Generation

Write the merged report to `docs/stride-review.md` with the following structure:

```markdown
# STRIDE Threat Model Review — ember

**Living task-tracking report.** Last updated: <YYYY-MM-DD>
**Scope**: <full / component-scoped — path if scoped>
**Architecture reference**: `AGENTS.md` (call path, trust zones), `SECURITY.md` (intended threat model)
**Existing controls cross-reference**: `SECURITY.md`, `RESPONSIBLE_USE.md`, `COMPATIBILITY.md`, `.specify/memory/constitution.md`, `vault/decisions/`, `vault/discoveries/`
**Reviewer**: Sisyphus (agent)

---

## Scan History

_A chronological log of every scan run. Newest first._

| Scan Date | New Threats | Resolved | Regressed | Total Open | Scope |
|-----------|-------------|----------|-----------|------------|-------|
| <YYYY-MM-DD> | +N | -N | +N | N | <scope> |

_This section grows with each scan — never prune rows._

---

## Progress Summary

| Metric | Value |
|--------|-------|
| Total threats (all time) | **N** |
| Currently open | **X** |
| In progress | **Y** |
| Fixed / resolved | **Z** |
| Wontfix / False positive | **W** |
| Resolved rate | **P%** |

### Open Threats by Category

| Category | Open | Critical | High |
|----------|------|----------|------|
| S — Spoofing | N | N | N |
| T — Tampering | N | N | N |
| R — Repudiation | N | N | N |
| I — Information Disclosure | N | N | N |
| D — Denial of Service | N | N | N |
| E — Elevation of Privilege | N | N | N |

### Open Threats by Severity

| Severity | Count |
|----------|-------|
| CRITICAL | N |
| HIGH | N |
| MEDIUM | N |
| LOW | N |
| INFO | N |

### Trend Since Last Review

- New threats added: +N
- Threats resolved: −N
- Threats regressed: +N

> ⚠️ **Top 3 Risks**:
> 1. ...

---

## Flat Threat Register (All Categories)

_A single flat table covering every threat across all STRIDE categories. Sortable by status (open first), severity, or date._

| ID | Cat | Sev | Status | Component | Flow / Component | Title | Controls xref | First Seen | Last Confirmed | Resolved |
|----|-----|-----|--------|-----------|-----------------|-------|---------------|------------|----------------|----------|
| S-001 | S | HIGH | open | mcp | Z1→Z2: EMBER_SERVER_URL | MCP trusts arbitrary server URL | — | 2026-10-04 | 2026-10-04 | — |
| T-001 | T | CRITICAL | open | runtime | Z4→Z3: EMBER_MODEL_DIR import | joint_schema_model.py imported without hash check | → SECURITY.md §out-of-scope | 2026-10-04 | 2026-10-04 | — |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

_Sort order: open/in_progress first (by severity desc), then fixed/wontfix (by resolved_date desc)._

---

## Detailed Threat Register

_Per-category context for each threat — scenario, gap, mitigation, and trust-zone flow._

### S — Spoofing

| ID | Severity | Status | Component | Flow / Component | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|-----------|-----------------|-------|------------|----------------|----------|
| S-001 | HIGH | open | mcp | Z1→Z2: EMBER_SERVER_URL | MCP trusts arbitrary server URL | 2026-10-04 | 2026-10-04 | — |

#### S-001: [Title]
- **Severity**: HIGH
- **Status**: open
- **Component**: mcp
- **Flow**: Z1 (ember-mcp) → Z2 (HTTP server via EMBER_SERVER_URL)
- **Trust-zone crossing**: Z1 → Z2
- **First seen**: 2026-10-04
- **Last confirmed**: 2026-10-04
- **Threat scenario**: An attacker who can set `EMBER_SERVER_URL` in the MCP process environment redirects all `advise` calls to an attacker-controlled server. The MCP layer trusts the URL without validating that it resolves to loopback.
- **Gap**:
  ```python
  # ember/mcp/mcp_server.py
  SERVER_URL = os.environ.get("EMBER_SERVER_URL", "http://127.0.0.1:8765").rstrip("/")
  # No validation that SERVER_URL is a loopback address
  ```
- **Mitigation**: Validate that `SERVER_URL` resolves to a loopback address (`127.0.0.1` or `::1`) before use; reject non-loopback targets with a clear error.
- **Existing controls xref**: → SECURITY.md §security-sensitive-design-notes (loopback-only design intent)
- **Notes**: The default is safe; the risk is in operator misconfiguration or environment injection.

[Repeat for each threat in this category]

### T — Tampering
...

### R — Repudiation
...

### I — Information Disclosure
...

### D — Denial of Service
...

### E — Elevation of Privilege
...

---

## Architecture Observations

Observations about structural gaps in the trust model that span multiple STRIDE categories or require architectural changes (not just code fixes).

_Key observations to consider:_
- The loopback-only binding is the primary security boundary for Z1→Z2. Any deployment that exposes the server beyond loopback (cloud, container with shared network namespace) removes this boundary entirely — document this as a deployment-time risk.
- `EMBER_MODEL_DIR` + `joint_schema_model.py` import is the highest-severity cross-cutting concern: it spans Tampering (code injection), Elevation of Privilege (arbitrary code execution), and Spoofing (model identity). A single env var controls all three.
- The MPS inference lock serializes all requests, which is both a DoS amplifier (one slow request blocks all others) and a DoS mitigator (prevents parallel resource exhaustion).
- The absence of authentication is a documented design decision (SECURITY.md), not a gap — but it means the entire security model depends on OS-level process isolation and the loopback interface.

---

## STRIDE ↔ Existing Controls Coverage Map

_Cross-reference showing which STRIDE threats map to existing documented controls, and which are architectural gaps with no existing coverage._

| STRIDE ID | STRIDE Title | Existing controls xref | Coverage |
|-----------|-------------|----------------------|---------|
| S-001 | ... | SECURITY.md §design-notes | Existing doc covers intent; STRIDE adds Z1→Z2 crossing detail |
| T-001 | ... | — | Architectural gap — no existing control |
| E-001 | ... | constitution Article IV | Article IV covers PID discipline; STRIDE adds model-dir import vector |

---

## Recommendations (Priority Order)

1. **Immediate** (CRITICAL): ...
2. **Short-term** (HIGH): ...
3. **Medium-term** (MEDIUM): ...

---

_Generated by `/stride-review` command | Last full scan: <YYYY-MM-DD>_
```

### Phase 4.5: Write Running Tracker CSV

After the markdown report is written, generate or update `docs/stride-tracker.csv` with ALL threats (all statuses) in CSV format:

```
threat_id,category,severity,status,component,flow_component,title,controls_xref,first_seen,last_confirmed,resolved_date,notes
S-001,S,HIGH,open,mcp,"Z1→Z2: EMBER_SERVER_URL","MCP trusts arbitrary server URL","SECURITY.md §design-notes",2026-10-04,2026-10-04,,"Validate SERVER_URL is loopback before use"
T-001,T,CRITICAL,open,runtime,"Z4→Z3: EMBER_MODEL_DIR import","joint_schema_model.py imported without hash check","",2026-10-04,2026-10-04,,"EMBER_MODEL_DIR can point to attacker-controlled dir"
```

**CSV formatting rules:**
- No spaces after commas in the header row
- Fields containing commas MUST be double-quoted
- Quoted fields escape internal double quotes as `""`
- Date format: `YYYY-MM-DD`
- Empty cells: leave blank (no space between commas)
- Sorting: open/in_progress first (sorted by severity CRITICAL→HIGH→MEDIUM→LOW→INFO, then by threat_id), then fixed/wontfix/false_positive (sorted by resolved_date descending, then threat_id)

### Phase 5: Summary

After writing the report and CSV, print a brief summary to the user:
- **Threats delta**: X new, Y resolved, Z regressed since last scan
- **Open burden**: N open (X critical, Y high) across N STRIDE categories
- **Existing controls overlap**: N threats already addressed by documented controls; N are architectural gaps with no existing coverage
- **Outputs**: `docs/stride-review.md` (markdown) and `docs/stride-tracker.csv` (CSV)
- **Top 3 things to fix first** (by severity × exploitability × architectural blast radius)

## Context

$ARGUMENTS
