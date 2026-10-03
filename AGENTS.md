# AGENTS.md — ember

**Last updated**: 2026-10-02 (project vault; product renamed to ember to match the mascot; table-stakes tooling; design doc; community docs; full context window and vision inputs; Prometheus metrics)

## What this repo is

`ember` runs Cloudflare's Clef decision models locally on Apple Silicon (MPS) and
exposes them to coding agents as one advisory MCP tool, `advise` (opencode: `ember_advise`; Claude
Code: `mcp__ember__advise`). An agent sends a `state` plus typed questions and gets calibrated
probabilities back — no prose. It ships as the `gut` uv tool (commands `ember`, `gut`,
`ember-mcp`), a local opencode plugin, and an **agent onboarding kit** that teaches consumers'
agents to use the tool well.

`.specify/memory/constitution.md` governs this repo. This file operationalizes it; where the
two conflict, the constitution wins and this file MUST be updated.

## Naming

The product is **ember**, named after the Ember mascot. Only the distribution differs: it is
`gut`, because `ember` is taken on PyPI. ember *advises*; the agent decides — keep that voice
in user-facing text.

"Gut feeling" is flavor text, not a name. Keep the tagline *Give your agent a gut feeling.*,
"a local gut feeling for coding agents", and the `gut` CLI alias as they are.

| Thing | Name |
| --- | --- |
| Distribution (PyPI, `uv tool`) | `gut` |
| Python package, app dir | `ember` |
| CLI | `ember` (alias `gut`); MCP command `ember-mcp` |
| MCP server / tool | `ember` / `advise` (opencode `ember_advise`, Claude Code `mcp__ember__advise`) |
| Skill / MCP resource | `ember-advise` / `ember://guide` |
| Environment variables | `EMBER_*` |
| GitHub repository | `shapeandshare/ember` |

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
| Agent-facing contract (tool schema, instructions, guide, skill, snippet) | `ember/mcp_server.py`, `ember/agent_kit/` |
| Model revisions | `REGISTRY` in `ember/models.py` |
| Dependency ranges | `pyproject.toml` + `uv.lock` |
| Lifecycle commands | `Makefile` (contributors), `ember` CLI (users) |
| User documentation | `README.md` |
| Development memory (decisions, discoveries, session logs) | `vault/` (hub `vault/ember.md`) |
| Verification | `tests/`, `.github/workflows/ci.yml` |

## Project structure

```
ember/
  runtime.py          # MPS-safe loader (CPU load → .to("mps")) + Engine
  server.py           # FastAPI: POST /v1/systemone, GET /health (reports pid)
  mcp_server.py       # MCP stdio server: advise tool, instructions, ember://guide resource
  agent_kit/          # consumer onboarding kit (single source of truth)
    instructions.md   #   MCP initialize.instructions (≤ 2 KB)
    ember-advise/     #   installable skill + ember://guide content
    AGENTS.snippet.md #   block consumers paste into their AGENTS.md / CLAUDE.md
  cli.py              # `ember` / `gut` command: lifecycle, models, doctor, init, agents
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
  vault.mk            #   vault-audit
scripts/              # MPS smoke test, MCP e2e check, provenance and vault audits
tests/                # pytest suite (unit + model-backed, host-isolated)
vault/                # project memory (Obsidian): decisions, discoveries, sessions
  ember.md            #   hub note; every note must be reachable from it
  _meta/              #   tags.md (controlled vocabulary) and templates/
.specify/             # spec-kit (constitution, templates, scripts)
.opencode/commands/   # spec-kit slash commands and /vault-health
.opencode/opencode.json   # shared opencode config: the vault MCP server
```

## Runtime environment

- macOS on Apple Silicon (arm64); Python 3.12 managed by uv (`.python-version`).
- torch MPS backend in fp16; CPU fallback in fp32 (`EMBER_DEVICE=cpu`).
- Weights: contributor clones use `.models/clef-flash` (`make download`, pinned); installed tools
  use the shared Hugging Face cache (`ember model pull`, pinned).
- Model server: `127.0.0.1:8765` by default; config and state live in
  `~/Library/Application Support/ember`.

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
| `make vault-audit` | Audit `vault/` notes: frontmatter, tags, wikilinks, code-refs, orphans |
| `.venv/bin/ember …` or `.venv/bin/gut …` | Primary CLI, built from this checkout |

## Architecture (call path)

```
agent ──tools/call advise──► ember-mcp (stdio, mcp_server.py)
                               │  initialize.instructions + resource ember://guide (agent_kit)
                               ▼  lazy autostart through process.start (pid-tracked)
                     HTTP POST /v1/systemone (server.py)
                               ▼
                     Engine.advise (runtime.py) → joint_schema_model.systemone
                               ▼
                     Qwen3.5 backbone + joint schema head on MPS (fp16)
```

- The MCP process never imports torch; startup stays instant.
- Every start path (`ember start`, `make start`, MCP autostart) goes through
  `process.start`: one model resolution, one pid file, one log.
- The model loads once per server process; a lock serializes MPS inference.
- `joint_schema_model.py` comes from the pinned Hugging Face snapshot and is imported from the
  model directory, never vendored.

## MCP server

| Server | Transport | Tool | Agent guidance | Notes |
| --- | --- | --- | --- | --- |
| `ember` | stdio (`ember-mcp`, or `python -m ember.mcp_server`) | `advise`; input wrapped in `input` | `initialize.instructions` + resource `ember://guide` | Starts the HTTP server lazily unless `EMBER_AUTOSTART=0` |

## Agent onboarding kit

`ember/agent_kit/` is the single source for everything a consumer's agent reads:

| File | Delivered as | Reaches |
| --- | --- | --- |
| `instructions.md` | MCP `initialize.instructions` | opencode and Claude Code, automatically |
| `ember-advise/SKILL.md` | MCP resource `ember://guide`; skill via `ember agents install` and `ember init --opencode` | opencode, Claude Code, Codex |
| `AGENTS.snippet.md` | `ember agents show snippet` | any agent that reads AGENTS.md or CLAUDE.md |

Rules for changing it:

- `instructions.md` MUST stay ≤ 2048 bytes (Claude Code truncates longer instructions).
- The skill name MUST stay `ember-advise` and match its directory.
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
7. **Dogfood.** When `ember_advise` is available, consult it with the kit's recipes for
   this repo's own triage and risk checks.
8. **Use the vault.** Search `vault/` before non-trivial decisions, and write decisions
   and discoveries back as they happen (see the vault protocol below).

## Vault protocol

`vault/` is this project's development memory (constitution Article IX): decisions,
discoveries, and session logs. Read it before deciding, and write to it when you learn
something durable, as it happens rather than at session end.

opencode reaches it through the `vault` MCP server (`@bitbonsai/mcpvault`, registered in
`.opencode/opencode.json`) as `vault_*` tools such as `vault_search_notes`,
`vault_read_note`, and `vault_write_note`. **Launch opencode from the repository root**:
the server resolves `vault` against the launch directory. Without the server, read and
edit the files directly.

### Searching (session start, and before any non-trivial decision)

1. Open the hub `vault/ember.md` and follow its wikilinks, or search with
   `vault_search_notes` or `grep -ril "<topic>" vault --include="*.md"`.
2. Read frontmatter and summaries first; open full notes only for the best matches.
3. Treat `status/draft` notes as unverified and `status/reviewed` ones as checked
   against the code.
4. If the vault has nothing, carry on: it speeds work up and never blocks it.
5. If a note turns out wrong or stale, fix it or tag it `status/stale` in the same change.

### Writing back

| Finding | Folder | Template |
| --- | --- | --- |
| A decision and its reasons | `vault/decisions/` | `vault/_meta/templates/decision.md` |
| A non-obvious constraint, gap, or conflict | `vault/discoveries/` | `vault/_meta/templates/discovery.md` |
| What a session did (append-only, never pruned) | `vault/sessions/` | `vault/_meta/templates/session-log.md` |

To add a note, copy its template, name it `YYYY-MM-DD-short-slug.md`, take tags from
`vault/_meta/tags.md`, link the hub with `[[ember]]`, and list the note under the right
heading in `vault/ember.md` so it stays reachable. Start at `status/draft`, and move to
`status/reviewed` only after checking the note against the code. Never set
`status/canonical`; that is a human decision.

Don't write notes for routine changes or for facts already in `README.md`, `AGENTS.md`,
`DESIGN.md`, or `PROVENANCE.md`; link to those instead. Run `make vault-audit` (or
`/vault-health`) before calling vault work done, and keep notes in the same change as
the work behind them.

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
- **`opencode.json`, `.opencode/plugins/ember.js`, and `.opencode/skills/ember-advise/` are per-machine** (absolute paths and the
  installer's `PATH`). They are gitignored; regenerate them, never commit them.
- **`.opencode/opencode.json` is shared and committed.** Put shared opencode settings (such
  as the `vault` MCP server) there; opencode merges it with the per-machine root file.
- **The `advise` input is wrapped in `input`.** mcp v2 does not flatten a single model parameter.
- **Raise `ToolError` for failures the agent should read.** mcp v2 reports any other exception
  as a bare "Error executing tool advise", hiding the actionable message.
- **`stop` signals only the recorded pid**, after confirming it is still an ember server.
  Never kill by port or process pattern (constitution Article IV).
- **torch and torchvision are pinned to the tested minor series** because MPS behavior is
  version-sensitive; widening the range is a constitution-governed change.
- **Media refs are `data:` URIs or `{content_type, base64}` objects only** (`ember/media.py`);
  remote URLs and local paths are rejected so an agent cannot make the warm server read host
  files or fetch URLs. Video frames must be decoded to PIL before Clef's processor — string
  frames need `torchcodec`, which we do not ship.
- **`max_length` of `0` means "the model's maximum"** (`ember/config.py` → `Engine` →
  `runtime.model_max_length`). Do not reintroduce a hardcoded 16384 cap.
- **Metric names and labels are public API** (`ember/server.py`): change
  `ember_advise_*` / `ember_model_info` together with the README and `tests/test_metrics.py`.
  They live in a dedicated `CollectorRegistry`, so only ember metrics are exposed — no
  `python_*`/`process_*` collectors.
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
  `ember`/`gut` CLI; JavaScript opencode plugin (V1 `config` hook).

## Recent Changes

- 2026-10-02: full context window and vision inputs: `max_length` now defaults to the model's
  maximum (262144, derived from the pinned `config.json`; `0` means derive); `advise` accepts
  `images`/`videos`/`media_kwargs` as base64 `data:` URIs or `{content_type, base64}` objects,
  decoded to PIL in `ember/media.py` (server-side only); MCP and HTTP schemas, the agent kit,
  README, and tests updated; vision verified end-to-end on MPS.
- 2026-10-02: Prometheus metrics: the model server exposes `GET /metrics` with
  `ember_advise_requests_total{status}`, `ember_advise_latency_seconds`,
  `ember_advise_input_tokens_total`, `ember_advise_output_tokens_total`, and
  `ember_model_info{model,device,dtype}`; `prometheus-client` is a pinned dependency.
- 2026-10-02: project vault on the wellspring pattern: `vault/` (hub `vault/ember.md`,
  tag vocabulary, templates), the `vault` MCP server (`@bitbonsai/mcpvault@0.12.4`) in
  `.opencode/opencode.json`, `make vault-audit` (`scripts/vault_audit.py`, also run by the
  unit suite), `/vault-health`, and the vault protocol; constitution v1.2.0 (Article IX).
- 2026-10-02: product renamed from gut-feeling to ember to match the mascot: package, CLI
  (`gut` alias kept), MCP server and tool (`ember_advise`), `ember-advise` skill,
  `ember://guide`, `EMBER_*`, app dir, and `--ember-*` CSS tokens; distribution `gut`
  (`ember` is taken on PyPI); repository renamed to `shapeandshare/ember`; npm plugin
  package `opencode-ember-advise` (`opencode-ember` is taken on npm); "gut feeling" flavor
  text unchanged; constitution v1.1.2.
- 2026-10-02: naming consolidated on gut-feeling (`advise` tool, `gut-feeling-advise` skill,
  `gut-feeling://guide`, `GUT_FEELING_*`, `gut` alias); MCP autostart now shares
  `process.start` (fixes model resolution for installed tools); actionable MCP errors; doctor
  and uninstall fixes; bash lifecycle scripts replaced by the CLI.
- 2026-10-02: table-stakes tooling (ruff, mypy-strict, bandit, commitizen, pytest-cov); shared/.mk Makefile domain split; DESIGN.md; community docs (CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md, SUPPORT.md); CI workflow stubs.
- 2026-10-02: agent onboarding kit (MCP instructions, `gut-feeling://guide`, `gut-feeling-advise` skill,
  AGENTS.md snippet, `gut-feeling agents`); constitution v1.0.0.
- 2026-10-02: initial `gut-feeling`: MPS runtime, HTTP and MCP servers, CLI, opencode plugin,
  pinned model and dependencies, CI.
