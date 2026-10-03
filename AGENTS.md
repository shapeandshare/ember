# AGENTS.md — gut-feeling

**Last updated**: 2026-10-02 (table-stakes tooling; design doc; community docs; naming consolidated on gut-feeling)

## What this repo is

`gut-feeling` runs Cloudflare's Clef decision models locally on Apple Silicon (MPS) and
exposes them to coding agents as one advisory MCP tool, `advise` (opencode: `gut-feeling_advise`; Claude
Code: `mcp__gut-feeling__advise`). An agent sends a `state` plus typed questions and gets calibrated
probabilities back — no prose. It ships as a uv tool (`gut-feeling`, `gut-feeling-mcp`), a
local opencode plugin, and an **agent onboarding kit** that teaches consumers' agents to use
the tool well.

`.specify/memory/constitution.md` governs this repo. This file operationalizes it; where the
two conflict, the constitution wins and this file MUST be updated.

## Naming

The product is **gut-feeling**, everywhere. gut-feeling *advises*; the agent decides — keep
that voice in user-facing text.

| Thing | Name |
| --- | --- |
| Distribution, repository, app dir | `gut-feeling` |
| Python package | `gut_feeling` |
| CLI | `gut-feeling` (alias `gut`); MCP command `gut-feeling-mcp` |
| MCP server / tool | `gut-feeling` / `advise` (opencode `gut-feeling_advise`, Claude Code `mcp__gut-feeling__advise`) |
| Skill / MCP resource | `gut-feeling-advise` / `gut-feeling://guide` |
| Environment variables | `GUT_FEELING_*` |

"Clef" refers only to Cloudflare's upstream model and its artifacts (`Cloudflare/clef-flash`,
`.models/clef-flash`, `joint_schema_model.py`, `load_clef`). Never use it for this product.

## Visual identity

Ember is the primary mascot. Use `assets/brand/README.md` for approved assets and
`assets/brand/tokens.css` for light/dark palette tokens. Preserve the primary
mascot choice; Mellow and Float are alternate concepts. `DESIGN.md` governs usage.
Record material origins, prompts, licensing evidence and URL checks in
`provenance.json`; see `PROVENANCE.md`. Run `python3 scripts/check_provenance.py`
after changing brand assets. Do not invent missing provenance or license facts.

## Where truth lives

| Topic | Source of truth |
| --- | --- |
| Principles and gates | `.specify/memory/constitution.md` |
| Agent-facing contract (tool schema, instructions, guide, skill, snippet) | `gut_feeling/mcp_server.py`, `gut_feeling/agent_kit/` |
| Model revisions | `REGISTRY` in `gut_feeling/models.py` |
| Dependency ranges | `pyproject.toml` + `uv.lock` |
| Lifecycle commands | `Makefile` (contributors), `gut-feeling` CLI (users) |
| User documentation | `README.md` |
| Verification | `tests/`, `.github/workflows/ci.yml` |

## Project structure

```
gut_feeling/
  runtime.py          # MPS-safe loader (CPU load → .to("mps")) + Engine
  server.py           # FastAPI: POST /v1/systemone, GET /health (reports pid)
  mcp_server.py       # MCP stdio server: advise tool, instructions, gut-feeling://guide resource
  agent_kit/          # consumer onboarding kit (single source of truth)
    instructions.md   #   MCP initialize.instructions (≤ 2 KB)
    gut-feeling-advise/      #   installable skill + gut-feeling://guide content
    AGENTS.snippet.md #   block consumers paste into their AGENTS.md / CLAUDE.md
  cli.py              # `gut-feeling` / `gut` command: lifecycle, models, doctor, init, agents
  process.py          # warm-server lifecycle (pidfile + HTTP health)
  models.py           # pinned model registry + pull/list/rm
  paths.py config.py  # platform dirs, config precedence
  opencode_config.py opencode_plugin.py   # opencode integration
packages/opencode-plugin/   # npm-ready opencode plugin source
shared/               # Makefile domain modules (.mk files)
  helper.mk           #   auto-generated make help
  python.mk           #   lint, format, typecheck, security, pr-ready
  testing.mk          #   test, test-fast, test-strict, test-cov, smoke, mcp-check
  server.mk           #   serve, start, stop, restart, status, logs, mcp, doctor
  release.mk          #   download, init, bootstrap, check, ci, clean
scripts/              # MPS smoke test, MCP e2e check
tests/                # pytest suite (unit + model-backed, host-isolated)
.specify/             # spec-kit (constitution, templates, scripts)
.opencode/commands/   # spec-kit slash commands
```

## Runtime environment

- macOS on Apple Silicon (arm64); Python 3.12 managed by uv (`.python-version`).
- torch MPS backend in fp16; CPU fallback in fp32 (`GUT_FEELING_DEVICE=cpu`).
- Weights: contributor clones use `.models/clef-flash` (`make download`, pinned); installed tools
  use the shared Hugging Face cache (`gut-feeling model pull`, pinned).
- Model server: `127.0.0.1:8765` by default; config and state live in
  `~/Library/Application Support/gut-feeling`.

## Commands

| Command | Purpose |
| --- | --- |
| `make bootstrap` | Deps + pinned weights + `opencode.json` + readiness check |
| `make check` | Fast pre-commit gate: compile + unit tests, no model load |
| `make lint` | Run ruff lint checks |
| `make format` | Run ruff formatter |
| `make typecheck` | Run mypy in strict mode |
| `make security` | Run bandit security scan |
| `make pr-ready` | Format, lint, typecheck, security, compile, unit tests — run before every PR |
| `make test` | Full suite including model-backed tests (~30 s) |
| `make test-cov` | Full suite with coverage report |
| `make test-strict` | Full suite; fails instead of skipping when weights are missing |
| `make start` / `stop` / `restart` / `status` / `logs` | Warm-server lifecycle |
| `make init` / `make opencode` | Regenerate `opencode.json` / install the local plugin and skill |
| `make smoke` / `make mcp-check` | Direct MPS inference / MCP protocol end-to-end |
| `make doctor` | Environment, model, and server readiness |
| `.venv/bin/gut-feeling …` or `.venv/bin/gut …` | Primary CLI, built from this checkout |

## Architecture (call path)

```
agent ──tools/call advise──► gut-feeling-mcp (stdio, mcp_server.py)
                               │  initialize.instructions + resource gut-feeling://guide (agent_kit)
                               ▼  lazy autostart through process.start (pid-tracked)
                     HTTP POST /v1/systemone (server.py)
                               ▼
                     Engine.advise (runtime.py) → joint_schema_model.systemone
                               ▼
                     Qwen3.5 backbone + joint schema head on MPS (fp16)
```

- The MCP process never imports torch; startup stays instant.
- Every start path (`gut-feeling start`, `make start`, MCP autostart) goes through
  `process.start`: one model resolution, one pid file, one log.
- The model loads once per server process; a lock serializes MPS inference.
- `joint_schema_model.py` comes from the pinned Hugging Face snapshot and is imported from the
  model directory, never vendored.

## MCP server

| Server | Transport | Tool | Agent guidance | Notes |
| --- | --- | --- | --- | --- |
| `gut-feeling` | stdio (`gut-feeling-mcp`, or `python -m gut_feeling.mcp_server`) | `advise`; input wrapped in `input` | `initialize.instructions` + resource `gut-feeling://guide` | Starts the HTTP server lazily unless `GUT_FEELING_AUTOSTART=0` |

## Agent onboarding kit

`gut_feeling/agent_kit/` is the single source for everything a consumer's agent reads:

| File | Delivered as | Reaches |
| --- | --- | --- |
| `instructions.md` | MCP `initialize.instructions` | opencode and Claude Code, automatically |
| `gut-feeling-advise/SKILL.md` | MCP resource `gut-feeling://guide`; skill via `gut-feeling agents install` and `gut-feeling init --opencode` | opencode, Claude Code, Codex |
| `AGENTS.snippet.md` | `gut-feeling agents show snippet` | any agent that reads AGENTS.md or CLAUDE.md |

Rules for changing it:

- `instructions.md` MUST stay ≤ 2048 bytes (Claude Code truncates longer instructions).
- The skill name MUST stay `gut-feeling-advise` and match its directory.
- Thresholds and "Observed" numbers MUST come from real model output. Re-measure them when the
  model revision or a recipe schema changes — questions are scored jointly.
- The tool name, input schema, and kit text are public API: change them together with the
  README and tests (`tests/test_agent_kit.py`, `tests/test_mcp_tool.py`, `tests/test_cli.py`).

## Agent behavioral principles

1. **Constitution first.** Read `.specify/memory/constitution.md` before changing behavior.
2. **Verify, don't assert.** Run `make check` before every commit and `make test` for changes
   to the runtime, servers, CLI, or kit; exercise the CLI and MCP paths for real.
3. **Never interfere with the host.** Tests use random ports (never 8765), stop only processes
   they started, and never invoke the opencode CLI.
4. **Treat the agent contract as public API** (see the kit rules above).
5. **Keep pins honest.** Bump model revisions or dependency ranges only with model-backed tests
   and re-measured kit numbers.
6. **Smallest correct change.** Atomic commits with plain, imperative English subjects.
7. **Dogfood.** When `gut-feeling_advise` is available, consult it with the kit's recipes for
   this repo's own triage and risk checks.

## Tooling

| Tool | Purpose | Config |
| --- | --- | --- |
| ruff | Format + lint | `[tool.ruff]` in `pyproject.toml` |
| mypy | Type checking (strict mode) | `[tool.mypy]` in `pyproject.toml` |
| bandit | Security static analysis | `[tool.bandit]` in `pyproject.toml` |
| pytest + pytest-cov | Tests + coverage | `[tool.pytest.ini_options]` + `[tool.coverage.*]` |
| commitizen | Conventional commits + version bump | `[tool.commitizen]` in `pyproject.toml` |
| uv | Dependency management + venv | `pyproject.toml` + `uv.lock` |

All tool configuration lives in `pyproject.toml` — no separate config files.

Run `make pr-ready` before every PR: formats, lints, type-checks, security-scans, compiles, and runs unit tests.

## What to watch out for

- **Never pass `device_map={"": "mps"}`** — it segfaults. `runtime.load_clef` loads on CPU and
  moves the module to MPS; keep it that way.
- **stdout is the MCP wire.** Log to stderr only in `mcp_server.py`; never `print`.
- **`opencode.json`, `.opencode/plugins/gut-feeling.js`, and `.opencode/skills/gut-feeling-advise/` are per-machine** (absolute paths and the
  installer's `PATH`). They are gitignored; regenerate them, never commit them.
- **The `advise` input is wrapped in `input`.** mcp v2 does not flatten a single model parameter.
- **Raise `ToolError` for failures the agent should read.** mcp v2 reports any other exception
  as a bare "Error executing tool advise", hiding the actionable message.
- **`stop` signals only the recorded pid**, after confirming it is still a gut-feeling server.
  Never kill by port or process pattern (constitution Article IV).
- **torch and torchvision are pinned to the tested minor series** because MPS behavior is
  version-sensitive; widening the range is a constitution-governed change.
- **Hosted CI cannot hold the model.** Model-backed tests run locally or on a self-hosted
  Apple Silicon runner via `workflow_dispatch`.
- **Pushing `.github/workflows/` changes over HTTPS** needs a gh token with the `workflow` scope.

## Speckit integration

spec-kit 1.0.8 for opencode (`.specify/`, `.opencode/commands/speckit.*.md`). Drive features
with `/speckit.specify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement`; every plan
MUST pass the constitution check.

## Active Technologies

- Python 3.12, uv, torch 2.14 (MPS), transformers 5.18, FastAPI + uvicorn, mcp 2.3
  (`MCPServer`), huggingface-hub 1.33; ruff, mypy (strict), bandit, pytest-cov, commitizen;
  `gut-feeling`/`gut` CLI; JavaScript opencode plugin (V1 `config` hook).

## Recent Changes

- 2026-10-02: naming consolidated on gut-feeling (`advise` tool, `gut-feeling-advise` skill,
  `gut-feeling://guide`, `GUT_FEELING_*`, `gut` alias); MCP autostart now shares
  `process.start` (fixes model resolution for installed tools); actionable MCP errors; doctor
  and uninstall fixes; bash lifecycle scripts replaced by the CLI.
- 2026-10-02: table-stakes tooling (ruff, mypy-strict, bandit, commitizen, pytest-cov); shared/.mk Makefile domain split; DESIGN.md; community docs (CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md, SUPPORT.md); CI workflow stubs.
- 2026-10-02: agent onboarding kit (MCP instructions, `gut-feeling://guide`, `gut-feeling-advise` skill,
  AGENTS.md snippet, `gut-feeling agents`); constitution v1.0.0.
- 2026-10-02: initial `gut-feeling`: MPS runtime, HTTP and MCP servers, CLI, opencode plugin,
  pinned model and dependencies, CI.
