# AGENTS.md — ember

**Last updated**: 2026-10-07 (`ember init` can bootstrap clients against a hosted/remote endpoint: `--server-url`/`--auth-header` on `ember init`, never writing the credential to disk)

## What this repo is

`ember` runs decision models (currently Cloudflare's Clef) locally on Apple Silicon (MPS) by
default, or against a single configured remote inference server
(`EMBER_SERVER_URL`/config `server_url`) when the user opts in, and exposes them to coding
agents as one advisory MCP tool, `advise` (opencode: `ember_advise`; Kilo Code:
`ember_advise`; Claude Code: `mcp__ember__advise`). An agent sends a `state` plus typed
questions and gets calibrated probabilities back — no prose. It ships as the `gut` uv tool
(commands `ember`, `gut`, `ember-mcp`), a local opencode plugin, and an **agent onboarding
kit** that teaches consumers' agents to use the tool well. Kilo Code is a first-class
supported harness alongside opencode.

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
| Agent-facing contract (tool schema, instructions, guide, skill, snippet) | `ember/mcp/mcp_server.py`, `ember/agent_kit/` |
| Model revisions | `REGISTRY` in `ember/models.py` |
| Dependency ranges | `pyproject.toml` + `uv.lock` |
| Lifecycle commands | `Makefile` (contributors), `ember` CLI (users) |
| User documentation | `README.md` |
| Dependency licenses | `THIRD_PARTY_NOTICES.md` |
| Tested versions and limits | `COMPATIBILITY.md` |
| Intended and excluded uses | `RESPONSIBLE_USE.md` |
| Development memory (decisions, discoveries, session logs) | `vault/` (hub `vault/ember.md`) |
| Verification | `tests/`, `.github/workflows/ci.yml` |
| Site build and deploy | `scripts/build_site_docs.py`, `site/_data/docs.json`, `.github/workflows/deploy-site.yml` |
| Benchmark runs (data the site renders) | `benchmark/<run-id>/`, written by `scripts/snapshot_evals.py` (via `evals/eval/snapshot_evals.py`) |

## Project structure

```
ember/
  cli.py              # `ember` / `gut` composition root: argparse wiring + main()
  commands/           # subcommand handlers: lifecycle, doctor, models, agents, eval, config
  models.py           # model registry + pull/list/rm
  serving/            # HTTP model server, MPS runtime, lifecycle, media
    server.py         #   FastAPI: POST /v1/systemone, GET /health (reports pid)
    runtime.py        #   MPS-safe loader (CPU load → .to("mps")) + Engine
    process.py        #   warm-server lifecycle (pidfile + HTTP health)
    media.py          #   base64 data-URI / {content_type,base64} → PIL decoder
  mcp/                # MCP stdio server and wire types
    mcp_server.py     #   MCP stdio server: advise tool, instructions, ember://guide
    mcp_types.py      #   Pydantic wire types: Question, AdviseInput
  cfg/                # configuration, endpoint, and platform paths
    config.py         #   config resolution (CLI flag > env > file > default)
    endpoint.py       #   client endpoint: loopback check, transport guard, auth headers
    paths.py          #   platform-aware app dirs (macOS Library, XDG)
  opencode/           # opencode integration
    opencode_config.py  # generates opencode.json
    opencode_plugin.py  # installs the npm plugin
  kilocode/           # Kilo Code integration
    kilocode_config.py  # generates kilo.json (mcp.ember entry; reuses opencode's entry builder)
  agent_kit/          # consumer onboarding kit (single source of truth)
    api.py            #   public API: instructions(), skill(), snippet(), install_skill()
    instructions.md   #   MCP initialize.instructions (≤ 2 KB)
    ember-advise/     #   installable skill + ember://guide content
    AGENTS.snippet.md #   block consumers paste into their AGENTS.md / CLAUDE.md
packages/opencode-plugin/   # npm-ready opencode plugin source
shared/               # Makefile domain modules (.mk files)
  helper.mk           #   auto-generated make help
  python.mk           #   lint, format, typecheck, security, pr-ready
  testing.mk          #   test, test-fast, test-strict, test-cov, smoke, mcp-check
  server.mk           #   serve, start, stop, restart, status, logs, mcp, doctor
   release.mk          #   download, init, bootstrap, check, ci, clean
   vault.mk            #   vault-audit
   site.mk             #   site, site-serve (Jekyll Pages)
scripts/              # make-only dev tools: MPS smoke, MCP e2e, site build, provenance/vault audits
tests/                # pytest suite (unit + model-backed, host-isolated)
site/                 # Jekyll GitHub Pages site (docs, brand assets, benchmark report generated at build)
benchmark/            # tracked benchmark runs (results, trace, dataset, model.json) the site renders
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
| `make setup` | Deps only (no model weights; use `make download` or `make bootstrap` for weights) |
| `make check` | Fast pre-commit gate: compile + unit tests, no model load |
| `make lint` | Run ruff lint checks |
| `make format` | Run ruff formatter |
| `make typecheck` | Run mypy in strict mode |
| `make security` | Run bandit security scan |
| `make pr-ready` | Format, lint, typecheck, security, compile, unit tests — run before every PR |
| `make test` | Full suite including model-backed tests (~30 s) |
| `make test-cov` | Unit suite (`-m "not model"`) with coverage report and the `fail_under` gate |
| `make test-strict` | Full suite; fails instead of skipping when weights are missing |
| `make start` / `stop` / `restart` / `status` / `logs` | Warm-server lifecycle |
| `make init` / `make opencode` | Regenerate `opencode.json` / install the local plugin and skill |
| `make smoke` / `make mcp-check` | Direct MPS inference / MCP protocol end-to-end |
| `make doctor` | Environment, model, and server readiness |
| `make vault-audit` | Audit `vault/` notes: frontmatter, tags, wikilinks, code-refs, orphans |
| `make eval-run` / `make eval-export` | Model benchmark (`evals/clef-flash.jsonl`) / reviewer report bundle |
| `make eval-snapshot` | Copy the latest run into `benchmark/` for the site to render |
| `make eval-agent` / `make eval-agent-smoke` | Agent-in-the-loop eval through opencode (opt-in; spends provider credit) |
| `make site` / `make site-serve` | Build the Pages site into `site/_site` / preview it at `:4000` (needs Docker) |
| `make release-dry` | Preview the next ember version bump without changes |
| `make release-ember` / `release-plugin` | Trigger a component release workflow on `main` (bump PR → GitHub Release) |
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
| `ember` | stdio (`ember-mcp`, or `python -m ember.mcp.mcp_server`) | `advise`; input wrapped in `input` | `initialize.instructions` + resource `ember://guide` | Starts the HTTP server lazily unless `EMBER_AUTOSTART=0` |

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
   Every commit touching a specific component MUST carry its scope:

   | Scope | Component | Versioned separately? |
   | --- | --- | --- |
   | `ember` | Python package / CLI / MCP server (`ember/`) | Yes — `v*` tag, PyPI wheel |
   | `plugin` | opencode npm plugin (`packages/opencode-plugin/`) | Yes — `plugin/v*` tag |
   | `evals` | benchmark harness (`evals/`) | No — root changelog only |
   | `site` | Jekyll Pages site (`site/`) | No — root changelog only |

   Cross-cutting changes (CI, tooling, root docs) may omit the scope.
   Examples: `feat(ember): …`, `fix(plugin): …`, `chore(evals): …`, `ci: …`
7. **Dogfood.** When `ember_advise` is available, consult it with the kit's recipes for
   this repo's own triage and risk checks.
8. **Use the vault.** Search `vault/` before non-trivial decisions, and write decisions
   and discoveries back as they happen (see the vault protocol below).
9. **TDD Always — Red-Green-Refactor** (Article XI). Every feature and bugfix MUST follow
   the TDD cycle. The test MUST be written (and confirmed failing) BEFORE any implementation
   code. A commit with implementation but no corresponding test is incomplete.

   **Red phase** — Write a failing test expressing the desired behaviour. Confirm it fails:
   ```bash
   python -m pytest tests/ -k test_<name> -x   # must FAIL
   ```
   **Green phase** — Write the *minimal* implementation to make the test pass. No speculative
   generality, no extra behaviour. If the test uncovers an edge case, write that test first
   (return to Red), then fix the code.

   **Refactor phase** — Clean up: remove duplication, improve naming, extract helpers.
   Keep all tests green:
   ```bash
   make test   # must PASS
   ```
   **Legacy code** — For existing code with no tests, write a characterization test capturing
   current behaviour *before* modifying it. Then change the test to express desired behaviour
   and fix the code.

   **Enforcement** — `make test` MUST pass before any task is marked complete. A single new
   failure outside pre-existing conditions reverts the work to Red phase. Run `make test-cov`
   after every session; `fail_under = 81` is the ratchet floor — never lower it.

10. **Simplest solution first** (Article XV). Before designing an implementation, identify the
    simplest viable approach. Document in the commit or vault if a more complex path was
    chosen and why.
11. **Async by default** (Article XII). New FastAPI route handlers are `async def`. New I/O
    outside the engine lock uses async libraries. Sync engine calls carry the
    `# async-first:exception` tag.
12. **Respect the layers** (Article XIII). MCP layer calls HTTP; HTTP layer owns the engine
    and metrics; engine has no network imports. Data crossing a layer is a Pydantic model or
    plain dict. Check the import graph before adding a cross-layer import.

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

## Testing

Test files live under `tests/`. The `conftest.py` fixture provides a warm-server
base URL and MCP stdio parameters for integration tests.

| Test file | What it covers |
|-----------|---------------|
| `tests/test_agent_kit.py` | Kit contract: instructions size, skill frontmatter, guide resource |
| `tests/test_cli.py` | CLI paths: onboarding, init, lifecycle on unused ports, doctor, uninstall |
| `tests/test_media.py` | Media decoding: data URIs, {content_type,base64} objects, rejection of URLs |
| `tests/test_metrics.py` | Prometheus endpoint: counter/gauge lifecycle, registry isolation |
| `tests/test_mcp_tool.py` | MCP protocol: tool discovery, advise over stdio, error handling, autostart |
| `tests/test_opencode_plugin.py` | Plugin install/uninstall, config merge/remove |
| `tests/test_runtime_unit.py` | Runtime helpers: device selection, model max length, mcp_server isolation |
| `tests/test_vault_audit.py` | Vault audit script: frontmatter, tags, wikilinks, code-refs, orphans |
| `tests/test_http_api.py` | HTTP API call paths: GET /health, POST /v1/systemone across all question types, request-validation errors |
| `tests/test_eval_benchmark.py` | Benchmark dataset integrity: schema, gold labels, split coverage |
| `tests/test_advise_evals.py` | Calibration evals (model-backed): recipe correctness end-to-end |
| `tests/test_agent_eval.py` | Agent-in-the-loop eval: judge scoring, sandbox lifecycle |
| `tests/test_eval_report.py` | Report generation: HTML structure, Markdown fidelity, chart output |
| `packages/opencode-plugin/index.test.js` | npm plugin config hook: env defaults and overrides (`node --test index.test.js`) |

**Writing new tests — unit pattern** (`tests/test_<module>.py`):
```python
"""Unit tests for <module>."""

from __future__ import annotations


def test_<behaviour>() -> None:
    result = <function>()
    assert result == <expected>
```

**Writing new tests — MCP / HTTP integration pattern**:
```python
"""Integration tests for <endpoint>."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_<endpoint>(base_url: str) -> None:
    # base_url fixture spins up a real server on a random free port
    import httpx
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{base_url}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
```

**Test naming**: `test_<behaviour>_<expected_outcome>` — e.g.
`test_empty_input_raises_value_error`, `test_health_returns_ok_when_loaded`.

**One logical assertion per test is preferred**; multiple are acceptable when they
test a single indivisible behaviour.

**Model-backed tests** are decorated `@pytest.mark.model` and skipped unless
weights are present. Run with `make test` (locally, with weights) or
`make test-strict` (fails instead of skipping).

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

## Python conventions

`ember/` follows the Python conventions in `.specify/memory/constitution.md` **Article X**.
Article VIII's tooling is the floor; these are the rules tooling does not fully enforce. The
highlights:

- **Package ownership via `__init__.py`** — every owned package level carries an
  `__init__.py`. Sub-package markers are bare and docstring-only (no imports, no
  re-exports). The package root `ember/__init__.py` is the **only** level permitted to
  re-export symbols (and MAY carry `__version__`). A sub-package that needs a public API
  (e.g. `ember/agent_kit/`) puts that code in a named module (`api.py`) and callers import
  from it explicitly — not through the sub-package `__init__.py`. Data-only directories
  have none.
- **One class per file**; modules are `snake_case.py`, named after their primary class.
- **Sizing** — ≤ 400 lines per module; split by responsibility rather than compress.
- **Imports at the top** — the only exceptions are a `TYPE_CHECKING` cycle guard tagged
  `# cycle:`, an optional-dependency `try/except ImportError`, the runtime `joint_schema_model`
  import, or a justified `# import-placement:allow`. Relative imports inside `ember/`; absolute
  `ember.` imports only from outside the package. Never import through an `__init__` re-export.
- **Typing** — `mypy --strict`; no bare `# type: ignore` (an error code and a comment are
  required), no `cast()`/`Any` used to silence the checker; `from __future__ import
  annotations` everywhere; PEP 604 unions.
- **Enums over magic strings** — any value drawn from a fixed known set uses `StrEnum` /
  `IntEnum`, never a bare string constant or dict mapping. `Literal[...]` is permitted only
  for published-schema fields (e.g. the `advise` question `type`). Define enums in the
  domain sub-package that owns them; standalone enum files are named `<thing>.py`. At
  external boundaries (API input, config), accept `str | MyEnum` and convert immediately:
  `if isinstance(x, str): x = MyEnum(x)`. Internal code stays strictly typed.
- **Pydantic `BaseModel` over `@dataclass`** for data that crosses a layer boundary (HTTP,
  MCP, config, on-disk). An internal value object that never crosses a boundary MAY be a
  `@dataclass(frozen=True)`.
- **Protocols over ABCs**; constructor injection; no service locators or dependency-plumbing
  module singletons — a private lazy cache for the engine or runtime module is allowed.
- **Forward references via PEP 563** — never use string-literal forward references
  (`"MyClass"`). Add `from __future__ import annotations` at the top of every module; this
  defers all annotation evaluation automatically. Use `TYPE_CHECKING`-guarded imports ONLY
  to break a genuine runtime circular import that cannot be resolved by restructuring. Each
  permitted guarded import MUST carry a `# cycle:` comment naming the specific cycle.
- **NumPy-style docstrings** on every module, class, and public function (enforced by ruff
  `D` on `ember/`). See the Docstring Convention section below.
- **Comments explain why**; section separators use solid `#` lines — never dashes. Every
  rule exception carries a machine-readable tag (`# cycle:`, `# import-placement:allow`,
  `# async-first:exception`).
- **Idempotent, atomic writes** — write a sibling `.tmp` then `os.replace()`.
- **No single God class** — each subsystem has one composition root (`Engine.advise`,
  `process.start`, `mcp_server.main`, `cli.main`); that split is the seam.

These apply to new and modified code. Existing violations are recorded as migration debt in
Article X §10.18 and MUST NOT grow — pay a file's debt down when you next touch it, and do not
reformat untouched files just to satisfy Article X.

## Architecture Rules

These are prescriptive, agent-actionable rules. Check these before writing any new code.

- **Layer discipline** — ember has exactly three layers; cross-layer imports are a bug:
  - `ember/mcp/` → calls HTTP layer; MUST NOT import torch, `Engine`, or FastAPI.
  - `ember/serving/` → owns the HTTP API and engine; MUST NOT import from `ember/mcp/`.
  - `ember/serving/runtime.py` → pure model I/O; MUST NOT import network or protocol libs.
  - Data crossing a layer is a Pydantic `BaseModel` or a plain `dict[str, Any]`. No
    torch tensors or processor objects may cross a layer boundary.
- **Relative imports only inside `ember/`** — never use `ember.X` absolute imports from
  within the package. Use `from .module import X`, `from ..parent.module import Y`. Absolute
  `ember.X` imports are valid only from `tests/` and `scripts/`.
- **No lazy imports** — all `import` / `from … import` statements MUST appear at the top of
  the file. Imports inside function bodies are forbidden with three exceptions: a
  `TYPE_CHECKING` block carrying `# cycle:`, a `try/except ImportError` for an optional
  dep, or a line tagged `# import-placement:allow`. Internal ember modules MUST NEVER be
  lazy-imported.
- **One class per file** — every `.py` file declares at most one primary class. A tightly-
  coupled exception class raised only by that primary class may share the file.
- **`py.typed` marker** — `ember/py.typed` ships with the package (PEP 561). Keep it; do
  not add `py.typed` to sub-packages — the root marker covers all sub-packages.
- **Enums are the single source of truth** — never duplicate enum values as string literals
  elsewhere. Import and use the enum member.
- **TDD gate** — every feature and bugfix begins with a failing test (Red phase). The test
  suite MUST pass before any task is considered complete. Enforcement: run `make test` at
  task completion; a single new failure outside pre-existing conditions reverts the work to
  Red phase.

## Docstring Convention

Every module, class, and public function MUST have a NumPy-style docstring (enforced by
ruff `D` on `ember/`; tests and scripts are exempt).

**Module**:
```python
"""Short description of what this module provides."""
```

**Class** (parameters in `__init__`, not class docstring):
```python
class Engine:
    """Load the Clef model once and serve advise requests.

    Parameters
    ----------
    model_dir : Path
        Path to the unpacked model snapshot directory.
    device : str, optional
        ``"mps"``, ``"cpu"``, or ``"auto"``.
    """
```

**Function / method**:
```python
def advise(self, state: Any, questions: dict[str, Any]) -> dict[str, Any]:
    """Run inference and return calibrated probabilities.

    Parameters
    ----------
    state : Any
        The situation to read: a string or JSON value.
    questions : dict[str, Any]
        Mapping of question ID to typed question schema.

    Returns
    -------
    dict[str, Any]
        SystemOne response body including ``answers`` and ``usage``.

    Raises
    ------
    ValueError
        If a question has an unsupported ``type``.
    """
```

| Entity | Required sections |
|--------|------------------|
| Module / package | Short description |
| Class | Short description; constructor params in `__init__` |
| Public method / function | Short description; `Parameters`, `Returns` (if not None), `Raises` (if applicable) |
| Property | Short description (no Parameters) |

One-line docstrings are acceptable ONLY for trivial properties or obvious getters.
Use ` ``backticks`` ` for parameter names and code references within prose.

## Design System

`DESIGN.md` governs all visual and brand decisions. Do not invent colors, fonts,
spacing values, or component styles outside the design system.

- `assets/brand/tokens.css` is the source of truth for all CSS custom property values. A
  systemic restyle MUST be a token edit — never hardcode raw values.
- Approved brand assets and usage rules are in `assets/brand/README.md`. Preserve the
  primary Ember mascot choice; Mellow and Float are alternate concepts.
- Record material origins, prompts, licensing evidence and URL checks in `provenance.json`.
  Run `python3 scripts/check_provenance.py` after changing brand assets.
- All UI, template, and CSS work MUST comply with `DESIGN.md`. Do not dilute its rules.

## What to watch out for

- **Never pass `device_map={"": "mps"}`** — it segfaults. `runtime.load_clef` loads on CPU and
  moves the module to MPS; keep it that way.
- **stdout is the MCP wire.** Log to stderr only in `mcp_server.py`; never `print`.
- **`opencode.json`, `.opencode/plugins/ember.js`, `.opencode/skills/ember-advise/`, and
  `.kilo/jetbrains.json` are per-machine** (absolute paths and the installer's `PATH`). They
  are gitignored; regenerate them, never commit them.
- **`.opencode/opencode.json` is shared and committed.** Put shared opencode settings (such
  as the `vault` MCP server) there; opencode merges it with the per-machine root file.
- **The `advise` input is wrapped in `input`.** mcp v2 does not flatten a single model parameter.
- **Raise `ToolError` for failures the agent should read.** mcp v2 reports any other exception
  as a bare "Error executing tool advise", hiding the actionable message.
- **`stop` signals only the recorded pid**, after confirming it is still an ember server.
  Never kill by port or process pattern (constitution Article IV).
- **torch and torchvision are pinned to the tested minor series** because MPS behavior is
  version-sensitive; widening the range is a constitution-governed change.
- **Media refs are `data:` URIs or `{content_type, base64}` objects only** (`ember/serving/media.py`);
  remote URLs and local paths are rejected so an agent cannot make the warm server read host
  files or fetch URLs. Video frames must be decoded to PIL before Clef's processor — string
  frames need `torchcodec`, which we do not ship.
- **`max_length` of `0` means "the model's maximum"** (`ember/cfg/config.py` → `Engine` →
  `runtime.model_max_length`). Do not reintroduce a hardcoded 16384 cap.
- **Metric names and labels are public API** (`ember/serving/server.py`): change
  `ember_advise_*` / `ember_model_info` together with the README and `tests/test_metrics.py`.
  They live in a dedicated `CollectorRegistry`, so only ember metrics are exposed — no
  `python_*`/`process_*` collectors.
- **Model-backed tests are local-only.** CI runs format/lint, typecheck, security,
  `make check` (unit), a build/install smoke, a SonarCloud scan (`SONAR_TOKEN` repository
  secret), and zizmor — no model-backed tests: the ~19 GB fp16 model fits neither hosted runners nor the org's 8 GiB self-hosted
  Apple Silicon VMs (the server OOMs on MPS). Run `make test` locally for model-affecting
  changes. See `vault/discoveries/2026-10-03-self-hosted-vms-cannot-hold-the-model.md`.
- **Pushing `.github/workflows/` changes over HTTPS** needs a gh token with the `workflow` scope.
- **Workflows run untrusted code.** A fork's pull request runs its own copy of the workflows,
  so: pin every `uses:` to a full commit SHA with a `# vX.Y.Z` comment (Dependabot bumps
  both); start from `permissions: {}` and grant per job; set `persist-credentials: false` on
  checkout; never use `pull_request_target`, `workflow_run`, or a self-hosted runner; never
  reference org secrets. The `zizmor` job in `ci` enforces this; run
  `uvx zizmor@1.30.1 .github/` before pushing workflow changes. See
  `vault/decisions/2026-10-03-harden-github-before-going-public.md`.
- **The release workflows open bump PRs.** `release-ember.yml` (paths `ember/**`,
  `evals/**`; tags `v*`) and `release-plugin.yml` (paths `packages/opencode-plugin/**`;
  tags `plugin/v*`) run from `main` only. Each computes the next version from
  conventional commits, commits it, pushes a `ci/bump-*` branch, opens a PR with
  auto-merge, waits for that PR to actually merge, and only then tags the merged
  commit and creates the GitHub Release — a blocked or closed PR leaves no tag
  behind. Reruns are safe: the branch is force-pushed, an open bump PR is reused,
  and a branch that falls behind main is updated while waiting. If the wait times
  out because check runs await maintainer approval (the public-repo contributor
  gate that applied to the bot's first PRs), approve the runs, let the bump PR
  merge, then dispatch the workflow (`make release-ember` / `make release-plugin`)
  — it detects the already-merged version on main and goes straight to tagging
  and publishing. The ember side releases on commitizen's rules; the
  plugin side releases only for `feat` (minor) and `fix`/`perf`/`refactor`/`revert`
  (patch) commits — `docs`/`chore`/`test`/`ci`/`style`/`build` changes accumulate
  until a release-worthy commit arrives. Two repo settings are load-bearing: the
  Actions token must be read-write and "Allow GitHub Actions to create and approve
  pull requests" must be on — the workflows create their PRs with `GITHUB_TOKEN`,
  never a stored personal token. Bump commit subjects (`release v…`,
  `release plugin/v…`) are filtered out of the commit scan, and only files under the
  component's own paths trigger the workflow, so a bump never triggers another bump.
  To cut a release by hand, run `make release-ember` / `make release-plugin`
  (workflow dispatch); `make release-dry` previews the next ember version.
- **The Pages site is generated at build.** `site/_docs/` and `site/assets/brand/` come from
  `scripts/build_site_docs.py` (manifest in `site/_data/docs.json`), so they are gitignored and
  must not be committed. To publish a page, add a manifest entry and run `make site`; never hand
  a file into `site/_docs/`. The site is a project page under `/ember/`; keep `baseurl` out of
  `_config.yml` and pass it in CI, and use `relative_url` for internal links.
  `.github/workflows/deploy-site.yml` is SHA-pinned and `ruby/setup-ruby` is on the Actions
  allow-list. See `vault/decisions/2026-10-03-publish-a-pages-site.md`.
- **The benchmark report is rendered by the site.** A run's data is snapshotted into the
  tracked `benchmark/<run-id>/` (results, trace, dataset, and the `analysis.build` model) by
  `scripts/snapshot_evals.py`; `scripts/build_site_benchmark.py` renders that model into native
  pages under `site/results/` (`/results/<section>/`), reusing `evals/report.css` as the site
  asset `benchmark.css`. The run produces data; the website renders the HTML. `site/results/`
  is generated and gitignored. `ember eval export` still writes a portable single-file HTML for
  external reviewers.
- **The agent eval is the only code that launches opencode.** `ember eval agent`
  (`evals/eval/run_agent_evals.py`, `evals/agent/`) runs `opencode run --pure` in a temporary
  sandbox with a private HOME and XDG dirs and no port (constitution Article IV). Keep it out of
  `tests/`; its unit tests (`tests/test_agent_eval.py`) use scripted transcripts. Benchmark
  gold labels and agent-scenario checks are frozen before runs; see
  `vault/decisions/2026-10-03-freeze-benchmark-labels-before-runs.md`.
- **Article X is prospective.** It binds new and modified code, not the existing tree; don't
  reformat untouched files to satisfy it. See the migration-debt list in Article X §10.18.
- **Article X docstrings are enforced.** ruff `D` with `convention = "numpy"` runs over
  `ember/` (tests and scripts are exempt) and `ember/py.typed` ships, so keep new public
  modules, classes, and functions documented or `make lint` fails.
- **Tests ship with the code that needs them** (Article XI). A commit that adds behaviour
  without a test is incomplete. Run `make test-cov` after; `fail_under = 81` is the ratchet
  floor — never lower it.
- **New FastAPI route handlers are `async def`** (Article XII §12.1). Sync handlers that
  call the engine carry `# async-first:exception - engine lock is synchronous`. Any new
  handler without one of these is a violation.
- **Layers must not leak** (Article XIII). Never import from `ember/mcp/` inside
  `ember/serving/`, and never import torch or `Engine` inside `ember/mcp/`. Data crossing a
  layer boundary must be a Pydantic `BaseModel` or a plain `dict`. Check the import graph
  (`python3 -c "import ember.mcp.mcp_server"` must not import torch) before landing a change.
- **Pit of success** (Article XIV). The server returns `503` when the model is not yet
  loaded — never a crash. CPU is the always-available fallback device. `ember start` on a
  machine with no weights must print an actionable error, not a traceback.
- **YAGNI** (Article XV). Before adding a new abstraction, parameter, or capability, ask
  "does the current requirement actually need this?" If not, don't add it. Document any
  complexity beyond the simplest viable solution in the commit or vault.

## Speckit integration

spec-kit 1.0.8 for opencode (`.specify/`, `.opencode/commands/speckit.*.md`). Drive features
with `/speckit.specify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement`; every plan
MUST pass the constitution check.

## Active Technologies

- Python 3.12, uv, torch 2.14 (MPS), transformers 5.18, FastAPI + uvicorn, mcp 2.3
  (`MCPServer`), huggingface-hub 1.33; ruff, mypy (strict), bandit, pytest-cov, commitizen;
  `ember`/`gut` CLI; JavaScript opencode plugin (V1 `config` hook).

## Recent Changes

- 2026-10-08: removed the `ANACONDA_S3` `REGISTRY`-entry subsystem (simplification): per
  direct maintainer pushback ("this is like shaving the yacht, do we actually need this
  level of complexity?"), `anaconda-flash`/`anaconda-clef` `REGISTRY` entries, the
  `ModelSource` `StrEnum`, `ModelSpec.source`/`s3_bucket`/`s3_prefix` fields, and the shared
  `anaconda_s3_bucket` config key are all removed — `EMBER_MODEL_S3_URI` (added the same day,
  see the entry below) already solves the hosted-deployment case completely on its own by
  bypassing `REGISTRY` entirely, making a parallel named-registry path for the identical
  weights unnecessary. `REGISTRY` reverted to Hugging-Face-sourced entries only
  (`flash`/`full`); `DEFAULT` reverted to `"flash"`. `ember/cfg/anaconda_s3.py` kept only its
  generic `s3_client()`/`download_prefix()` primitives (still used by
  `ember/serving/hosted.py`); its `ModelSpec`-specific `download()` wrapper is gone.
  `specs/002-anaconda-models-provider/` is marked superseded (not deleted) for an honest
  historical record. See
  `vault/decisions/2026-10-08-simplify-remove-anaconda-s3-registry-entries.md`.
- 2026-10-08: Article V redefined from "Reproducibility by Pinning" to "Model Loading"
  (constitution v3.0.0, MAJOR): per direct maintainer direction ("we do not need pinned
  models as we will support any that can run and will likely not be able to manage/pin
  them all"), the mandatory `REGISTRY` SHA-256 schema/head hash-verification requirement is
  removed — `ember/serving/integrity.py` deleted; `ModelSpec.schema_sha256`/`head_sha256`
  fields removed; `revision` made optional (`str | None`, a download-targeting convenience
  only, not a verified pin). `runtime.joint_module()`/`load_clef()`/`Engine.__init__()` no
  longer verify a model directory before importing `joint_schema_model.py` — `_classify_dir`
  and the `skip_integrity` parameter are removed entirely (nothing left to skip).
  `ember/serving/hosted.py`'s `EMBER_MODEL_S3_URI` path (added the same day for Outerbounds
  hosted deployments) no longer requires the `EMBER_MODEL_S3_UNVERIFIED=1` acknowledgment —
  unverified loading is now the normal behavior for every model source, not an exception.
  Dependency pinning (`uv.lock`, `uv sync --locked`) is unchanged. README/COMPATIBILITY
  updated; `tests/test_model_integrity.py` reduced to registry-structure and S3-download-
  dispatch coverage (the hash/classification test groups removed).
- 2026-10-08: Outerbounds hosted deployment support: `ember/serving/hosted.py` resolves
  `EMBER_MODEL_S3_URI` (an `s3://bucket/prefix` URI) once at process startup, independent of
  `REGISTRY`/`EMBER_MODEL`, reusing `ember/cfg/anaconda_s3.py`'s download primitive (split
  into a spec-independent `download_prefix()`). Wired into both `ember/serving/process.py`'s
  `start()` (parent-process fail-fast before spawning) and `ember/serving/server.py`'s
  `lifespan()` (direct `ember serve`/platform-launched startup). `ember doctor` reports the
  hosted location when configured. Originally gated behind constitution Article V's
  "Unverified hosted-deployment exception" (added then superseded the same day — see the
  entry above).
- 2026-10-07: `ember init` bootstraps clients against a hosted/remote endpoint:
  new `--server-url`/`--auth-header` flags on `ember init`; `opencode_config.build_entry`/
  `write` and `kilocode_config.write` accept `server_url`/`auth_header` and emit
  `EMBER_SERVER_URL`/`EMBER_AUTH_HEADER` for the remote case (`EMBER_AUTOSTART` forced
  to `0`); `opencode_plugin.render`/`install` gained the same `auth_header` parameter
  so `ember init --opencode --server-url ...` also bootstraps the generated plugin.
  The credential itself is **never** written to `kilo.json`/`opencode.json`/the plugin
  file — `EMBER_AUTH_TOKEN` must be exported in the shell that launches the agent.
  Consulted `ember_advise` on the design (`should_build_cli_support` P=0.60,
  `token_in_config_file_acceptable` P=0.02 — confirming never embed the token).
  README's Remote inference section documents the new flags.
- 2026-10-07: Kilo Code adopted as a first-class supported harness: `kilocode` added to
  `agent_kit.api._SKILL_ROOTS` (skill installs to `.kilo/skills/ember-advise/SKILL.md`
  project-local, `~/.config/kilo/skills/...` global); `ember/kilocode/kilocode_config.py`
  writes/removes the `mcp.ember` entry in `kilo.json` (same entry shape as opencode's,
  reusing `opencode_config.build_entry`); `ember init --kilocode` registers the server and
  installs the skill in one step; `ember uninstall` cleans up the global `kilo.json` entry;
  README and CLI help updated. No constitution change — purely additive to the existing
  agent onboarding kit pattern.
- 2026-10-06: remote inference servers: the client (MCP + eval harness) may target a configured
  remote `server_url` (any endpoint, opt-in), with bearer/custom-header credentials; the
  server gains optional, disableable bearer auth on `POST /v1/systemone` and `/health` advertises
  `version`/`auth_required`; `ember/cfg/endpoint.py` added; the MCP `advise` tool is async;
  loopback-only validation removed; Article I redefined to "Local-First by Default";
  constitution v2.0.0 (MAJOR). Feature `specs/001-remote-inference-servers/`.
- 2026-10-04: constitutional Articles XI–XV adopted; Testing section added; Architecture
  Rules + Docstring Convention + Design System sections added; behavioral principles 9–12
  expanded with full TDD workflow; Python conventions expanded with enums, forward refs,
  solid separators; `health()` and `metrics()` in `ember/serving/server.py` converted to
  `async def` (Article XII); `fail_under` ratcheted 60 → 71 (Article XI); 59 dashed
  comment separators converted to solid `#` (§10.11); constitution v1.4.0 (MINOR).
- 2026-10-02: full context window and vision inputs: `max_length` now defaults to the model's
  maximum (262144, derived from the pinned `config.json`; `0` means derive); `advise` accepts
  `images`/`videos`/`media_kwargs` as base64 `data:` URIs or `{content_type, base64}` objects,
  decoded to PIL in `ember/serving/media.py` (server-side only); MCP and HTTP schemas, the agent kit,
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
