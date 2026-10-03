# AGENTS.md — gut-feeling (clef-local)

**Last updated**: 2026-10-02 (agent onboarding kit; constitution v1.0.0 ratified)

## What this repo is

`clef-local` runs Cloudflare's Clef decision models locally on Apple Silicon (MPS) and
exposes them to coding agents as one MCP tool, `decide` (opencode: `clef_decide`; Claude
Code: `mcp__clef__decide`). An agent sends a `state` plus typed questions and gets calibrated
probabilities back — no prose. It ships as a uv tool (`clef`, `clef-mcp`), a local opencode
plugin, and an **agent onboarding kit** that teaches consumers' agents to use the tool well.

`.specify/memory/constitution.md` governs this repo. This file operationalizes it; where the
two conflict, the constitution wins and this file MUST be updated.

## Where truth lives

| Topic | Source of truth |
| --- | --- |
| Principles and gates | `.specify/memory/constitution.md` |
| Agent-facing contract (tool schema, instructions, guide, skill, snippet) | `clef_local/mcp_server.py`, `clef_local/agent_kit/` |
| Model revisions | `REGISTRY` in `clef_local/models.py` |
| Dependency ranges | `pyproject.toml` + `uv.lock` |
| Lifecycle commands | `Makefile` (contributors), `clef` CLI (users) |
| User documentation | `README.md` |
| Verification | `tests/`, `.github/workflows/ci.yml` |

## Project structure

```
clef_local/
  runtime.py          # MPS-safe loader (CPU load → .to("mps")) + ClefEngine
  server.py           # FastAPI: POST /v1/systemone, GET /health (reports pid)
  mcp_server.py       # MCP stdio server: decide tool, instructions, clef://guide resource
  agent_kit/          # consumer onboarding kit (single source of truth)
    instructions.md   #   MCP initialize.instructions (≤ 2 KB)
    clef-decide/      #   installable skill + clef://guide content
    AGENTS.snippet.md #   block consumers paste into their AGENTS.md / CLAUDE.md
  cli.py              # `clef` command: lifecycle, models, doctor, init, agents
  process.py          # warm-server lifecycle (pidfile + HTTP health)
  models.py           # pinned model registry + pull/list/rm
  paths.py config.py  # platform dirs, config precedence
  opencode_config.py opencode_plugin.py   # opencode integration
packages/opencode-plugin/   # npm-ready opencode plugin source
scripts/              # dev server script, doctor, MPS smoke test, MCP e2e check
tests/                # pytest suite (unit + model-backed, host-isolated)
.specify/             # spec-kit (constitution, templates, scripts)
.opencode/commands/   # spec-kit slash commands
```

## Runtime environment

- macOS on Apple Silicon (arm64); Python 3.12 managed by uv (`.python-version`).
- torch MPS backend in fp16; CPU fallback in fp32 (`CLEF_DEVICE=cpu`).
- Weights: contributor clones use `.models/clef-flash` (`make download`, pinned); installed tools
  use the shared Hugging Face cache (`clef model pull`, pinned).
- Model server: `127.0.0.1:8765` by default; config and state live in
  `~/Library/Application Support/clef-local`.

## Commands

| Command | Purpose |
| --- | --- |
| `make bootstrap` | Deps + pinned weights + `opencode.json` + readiness check |
| `make check` | Compile + unit tests, no model — run before every commit |
| `make test` | Full suite including model-backed tests (~30 s) |
| `make test-strict` | Full suite; fails instead of skipping when weights are missing |
| `make start` / `stop` / `restart` / `status` / `logs` | Warm-server lifecycle |
| `make init` / `make opencode` | Regenerate `opencode.json` / install the local plugin and skill |
| `make smoke` / `make mcp-check` | Direct MPS inference / MCP protocol end-to-end |
| `make doctor` | Environment, model, and server readiness |
| `.venv/bin/clef …` | The user-facing CLI, built from this checkout |

## Architecture (call path)

```
agent ──tools/call decide──► clef-mcp (stdio, mcp_server.py)
                               │  initialize.instructions + resource clef://guide (agent_kit)
                               ▼  lazy autostart of a PID-tracked child
                     HTTP POST /v1/systemone (server.py)
                               ▼
                     ClefEngine.decide (runtime.py) → joint_schema_model.systemone
                               ▼
                     Qwen3.5 backbone + joint schema head on MPS (fp16)
```

- The MCP process never imports torch; startup stays instant.
- The model loads once per server process; a lock serializes MPS inference.
- `joint_schema_model.py` comes from the pinned Hugging Face snapshot and is imported from the
  model directory, never vendored.

## MCP server

| Server | Transport | Tool | Agent guidance | Notes |
| --- | --- | --- | --- | --- |
| `clef` | stdio (`clef-mcp`, or `python -m clef_local.mcp_server`) | `decide`; input wrapped in `input` | `initialize.instructions` + resource `clef://guide` | Starts the HTTP server lazily unless `CLEF_AUTOSTART=0` |

## Agent onboarding kit

`clef_local/agent_kit/` is the single source for everything a consumer's agent reads:

| File | Delivered as | Reaches |
| --- | --- | --- |
| `instructions.md` | MCP `initialize.instructions` | opencode and Claude Code, automatically |
| `clef-decide/SKILL.md` | MCP resource `clef://guide`; skill via `clef agents install` and `clef init --opencode` | opencode, Claude Code, Codex |
| `AGENTS.snippet.md` | `clef agents show snippet` | any agent that reads AGENTS.md or CLAUDE.md |

Rules for changing it:

- `instructions.md` MUST stay ≤ 2048 bytes (Claude Code truncates longer instructions).
- The skill name MUST stay `clef-decide` and match its directory.
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
7. **Dogfood decisions.** When `clef_decide` is available, use the kit's recipes for this repo's
   own triage and risk gates.

## What to watch out for

- **Never pass `device_map={"": "mps"}`** — it segfaults. `runtime.load_clef` loads on CPU and
  moves the module to MPS; keep it that way.
- **stdout is the MCP wire.** Log to stderr only in `mcp_server.py`; never `print`.
- **`opencode.json` and `.opencode/plugins/clef.js` are per-machine** (absolute paths and the
  installer's `PATH`). They are gitignored; regenerate them, never commit them.
- **The `decide` input is wrapped in `input`.** mcp v2 does not flatten a single model parameter.
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
  (`MCPServer`), huggingface-hub 1.33; JavaScript opencode plugin (V1 `config` hook).

## Recent Changes

- 2026-10-02: agent onboarding kit (MCP instructions, `clef://guide`, `clef-decide` skill,
  AGENTS.md snippet, `clef agents`); constitution v1.0.0.
- 2026-10-02: initial `clef-local`: MPS runtime, HTTP and MCP servers, CLI, opencode plugin,
  pinned model and dependencies, CI.
