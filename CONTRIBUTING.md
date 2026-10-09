# Contributing to ember

ember is an MCP server that exposes a decision model (currently Cloudflare's Clef) to coding
agents, running locally on Apple Silicon (MPS) by default or against a configured remote
inference server. It ships as a uv tool and integrates with opencode, Kilo Code, Codex CLI, and
Claude Code via a single `advise` tool. Contributions are welcome.

The governing document for this project is `.specify/memory/constitution.md`. This file
operationalizes it. Where the two conflict, the constitution wins.

---

## Table of contents

- [Getting started](#getting-started)
- [Development workflow](#development-workflow)
- [Quality gates](#quality-gates)
- [Code style](#code-style)
- [Commit messages](#commit-messages)
- [Tests](#tests)
- [Agent contract changes](#agent-contract-changes)
- [Dependency and model pins](#dependency-and-model-pins)
- [Agentic development](#agentic-development)
- [Pull requests](#pull-requests)
- [Issues](#issues)

---

## Getting started

You'll need macOS on Apple Silicon, Python 3.12 (managed by uv), and Git.

```bash
git clone https://github.com/shapeandshare/ember
cd ember
make bootstrap    # deps + model weights + opencode.json + readiness check
make check        # fast gate: compile + unit tests, no model load
```

`make bootstrap` installs dependencies via `uv sync --locked`, pulls the pinned model weights,
regenerates `opencode.json`, and runs `make doctor` to confirm the environment is ready.

`make check` is the fast feedback loop. It runs formatting, linting, type checking, security
scanning, and unit tests without loading the model. Run it before every commit.

---

## Development workflow

Feature work follows the spec-kit flow:

1. `/speckit.specify` — write or update the feature spec
2. `/speckit.plan` — produce a design plan; every plan must pass a Constitution Check
3. `/speckit.tasks` — break the plan into atomic tasks
4. `/speckit.implement` — execute the tasks

The Constitution Check is not optional. If a plan conflicts with `.specify/memory/constitution.md`,
revise the plan before proceeding.

### Branch naming

| Type | Pattern | Example |
| --- | --- | --- |
| Feature | `feat/<slug>` | `feat/score-question-type` |
| Bug fix | `fix/<slug>` | `fix/missing-pidfile-stop` |
| Documentation | `docs/<slug>` | `docs/agent-kit-readme` |
| Chore / maintenance | `chore/<slug>` | `chore/bump-ruff` |

One logical change per PR. Stacked PRs are fine; mark them as draft until the base merges.

---

## Quality gates

All of these must pass before a PR is ready for review.

```bash
make pr-ready     # format, lint, typecheck, security, compile, test-fast — no model load
make test         # full suite including model-backed tests (requires weights, ~30s)
```

`make pr-ready` is the minimum bar. `make test` is required for any change that touches the
runtime, servers, CLI, or agent kit.

The individual targets are also available:

```bash
make format       # ruff format
make lint         # ruff check
make typecheck    # mypy --strict
make security     # bandit
make compile      # py_compile on all source files
make test-fast    # pytest, no model load (~11s)
```

---

## Code style

All configuration lives in `pyproject.toml`. There are no separate config files.

| Concern | Tool | Config section |
| --- | --- | --- |
| Formatting | ruff format | `[tool.ruff.format]` |
| Linting | ruff check | `[tool.ruff.lint]` |
| Type checking | mypy --strict | `[tool.mypy]` |
| Security scanning | bandit | `[tool.bandit]` |
| Tests | pytest | `[tool.pytest.ini_options]` |

A few non-negotiable rules that tooling doesn't fully enforce:

- **stdout is the MCP wire.** In `mcp_server.py`, log to stderr only. Never `print` to stdout.
- **Never pass `device_map={"": "mps"}`** to a model loader. It segfaults. Load on CPU, then
  call `.to("mps")`. See `ember/serving/runtime.py` for the canonical pattern.
- **`opencode.json` and `.opencode/plugins/ember.js` are per-machine.** They are gitignored.
  Never commit them.

Beyond the tooling, `ember/` follows the Python conventions in
`.specify/memory/constitution.md` **Articles X–XV** (adapted from the sibling repositories). They
apply to new and modified code; existing violations are tracked as migration debt in Article X
§10.18 and must not grow.

| Concern | Convention |
| --- | --- |
| Package ownership | Every owned package level has a bare, docstring-only `__init__.py` (no imports, no re-exports); the package root `ember/__init__.py` is the only level that MAY re-export symbols; sub-packages with a public API (e.g. `agent_kit`) put that code in a named module (`api.py`) — callers import from it explicitly, not through `__init__.py`; data-only dirs have none |
| File shape | One primary class per file; modules `snake_case.py` named after their class |
| Sizing | ≤ 400 lines/module; evaluate splitting at six peer modules; ≤ 2 levels of nesting |
| Imports | Top of file only; exceptions: `TYPE_CHECKING` (`# cycle:`), optional-dep `try/except ImportError`, the runtime model import, `# import-placement:allow`; relative inside the package |
| Typing | `mypy --strict`; coded + commented suppressions only; no `cast()`/`Any` escape hatches; `from __future__ import annotations`; PEP 604 unions |
| Enums | `Enum`/`StrEnum`/`IntEnum` for fixed value sets — never magic strings or dict mappings; `Literal[...]` only for published-schema fields |
| Data models | Pydantic v2 `BaseModel` for boundary data; internal frozen dataclasses allowed |
| Interfaces & DI | `typing.Protocol` over `abc.ABC`; constructor injection; no service locators or dependency-plumbing singletons (private lazy caches allowed) |
| Docstrings | NumPy-style on modules, classes, and public functions (enforced by ruff `D` on `ember/`) |
| Comments | Explain why; solid `#` separators; tag every rule exception |
| Errors | Typed exceptions; no bare `except:` or swallowed errors; explicit timeouts on network calls |
| Logging | `logging.getLogger(__name__)` in library code; never `print` (stdout is the MCP wire) |
| Concurrency | Sync inference behind the engine lock; async only at I/O boundaries with structured concurrency |
| Entry points | One composition root per subsystem; ember deliberately has no application-wide God class |
| Writes | Idempotent and guarded; `.tmp` + `os.replace()` for files that could clobber |
| Tests (Article XI) | Tests ship in the same commit as the code they cover; `fail_under = 81` is the ratchet floor — never lower it; run `make test-cov` to verify |
| Async-first (Article XII) | New FastAPI route handlers are `async def`; sync engine calls carry `# async-first:exception - engine lock is synchronous` |
| Layered architecture (Article XIII) | MCP layer → HTTP layer → Engine layer; no primitives cross layer boundaries; cross-layer data is Pydantic or plain dict |
| Pit of success (Article XIV) | Server returns 503 when model not loaded (never crashes); CPU is always the fallback device; setup is idempotent |
| Simplicity / YAGNI (Article XV) | Choose the simplest viable solution; no speculative generality; document complexity beyond the obvious minimum in commit or vault |

---

## Commit messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/).

**Format:**

```
<type>: <subject>

[optional body]

[optional footer]
```

**Types:** `feat`, `fix`, `docs`, `chore`, `test`, `refactor`, `perf`, `ci`, `build`,
`style`, `revert` (commitizen `cz_conventional_commits`)

**Scopes:** every commit touching a specific component MUST carry its scope in
parentheses. The valid scopes are:

| Scope | Component | Versioned separately? |
| --- | --- | --- |
| `ember` | Python package / CLI / MCP server (`ember/`) | Yes — `v*` tag, GitHub Release, PyPI `ember-advise` |
| `plugin` | opencode plugin source (`packages/opencode-plugin/`) | No — releases stopped after `plugin/v0.4.0`; appears in the root changelog |
| `evals` | benchmark harness (`evals/`) | No — appears in the root changelog |
| `site` | Jekyll Pages site (`site/`) | No — appears in the root changelog |

A commit that touches more than one component should use the scope of the
**primary** component changed; note secondary components in the body.
Cross-cutting changes (CI, tooling, root docs) may omit the scope.

**Subject rules:** imperative mood, 72 characters or fewer, no trailing period.

**Body rules:** wrap at 72 characters; explain *why*, not just *what*.

**Examples:**

```
feat(ember): add score question type to CLI output

fix(ember): handle missing pidfile in stop command

docs(ember): update agent onboarding kit README

chore: bump ruff to 0.9.1

test(ember): add model-backed noul boundary test

feat(plugin): resolve ember-mcp from EMBER_MCP env var

fix(evals): include model label in trace records

chore(site): add CHANGELOG link to navigation
```

Breaking changes go in the footer:

```
feat!: rename advise input field from query to state

BREAKING CHANGE: the `query` field in the MCP tool input is now `state`.
Update all callers before upgrading.
```

---

## Tests

### Running tests

```bash
make test-fast    # unit tests only, no model load (~11s)
make test         # full suite including model-backed tests (~30s)
make test-strict  # full suite; fails instead of skipping when weights are missing
```

### Writing tests

- New behavior ships with tests in the same commit. No exceptions.
- Tests that start a server must bind a **random free port** — never hardcode 8765.
- Tests must stop only the processes they started.
- Tests must never invoke the opencode CLI.
- Model-backed tests are marked with `@pytest.mark.model` and skipped automatically when
  weights are absent. They run locally, not in CI — the model does not fit the available runners.

### Test layout

```
tests/
  test_runtime_unit.py     # device selection, model max length, MCP isolation
  test_http_api.py         # /health and /v1/systemone across question types
  test_mcp_tool.py         # MCP tool schema, advise handler, autostart
  test_cli.py              # CLI commands and lifecycle on unused ports
  test_media.py            # data-URI and media decoding
  test_metrics.py          # Prometheus endpoint
  test_agent_kit.py        # kit file sizes and schema consistency
  test_opencode_config.py  # opencode config generation
  test_opencode_plugin.py  # plugin install and uninstall
  test_vault_audit.py      # vault checks
  test_model_integrity.py  # pinned model artifacts
```

Model-backed tests (`@pytest.mark.model`) additionally cover the calibration evals
(`test_advise_evals.py`), the agent-in-the-loop eval (`test_agent_eval.py`), and the
benchmark dataset and report (`test_eval_benchmark.py`, `test_eval_report.py`).

---

## Agent contract changes

The following are **public API** (Article III of the constitution). Changes to any of them
require matching README and test updates in the same PR.

| Artifact | Location | Constraint |
| --- | --- | --- |
| Tool name | `ember/mcp/mcp_server.py` | Must stay `ember_advise` (opencode) / `advise` (MCP) |
| Input schema | `ember/mcp/mcp_server.py` | Input wrapped in `input`; do not flatten |
| MCP instructions | `ember/agent_kit/instructions.md` | Must stay ≤ 2048 bytes |
| Guide resource | `ember/agent_kit/ember-advise/SKILL.md` | Delivered as `ember://guide` |
| Skill name | `ember/agent_kit/ember-advise/` | Must stay `ember-advise` |
| AGENTS.md snippet | `ember/agent_kit/AGENTS.snippet.md` | Shown by `ember agents show snippet` |

**Observed thresholds** in the kit (e.g., calibration numbers, example probabilities) must come
from real model output. Re-measure them whenever the model revision or a recipe schema changes.
Questions are scored jointly, so a schema change can shift all thresholds.

---

## Dependency and model pins

This project pins aggressively because MPS behavior is version-sensitive (Article V).

- `uv.lock` is committed. Always install with `uv sync --locked`.
- `torch` and `torchvision` are pinned to a tested minor series. Widening the range requires
  green model-backed tests on the new version.
- Model revision bumps require green model-backed tests **and** re-measured kit numbers.
- Dependency range widening follows the same bar.

Do not widen pins speculatively. Open an issue first if you believe a range needs updating.

---

## Agentic development

### Human using AI tools

You are welcome to use AI coding assistants. You remain the author and are responsible for the
quality, correctness, and constitution-compliance of everything you submit. Review the diff
before opening a PR.

### Fully autonomous agents

Agents may open PRs against this repository under these conditions:

- The PR description must identify the agent system that generated it.
- The agent must have run `make pr-ready` and `make test` before opening the PR.
- The agent must use `ember_advise` (via the MCP server; local by default) for triage and
  risk-gate decisions, following the recipes in `ember/agent_kit/ember-advise/SKILL.md`.
- The PR must not be bulk-generated, untested, or in conflict with the constitution.

PRs that violate these conditions will be closed without review.

Agents filing issues must follow the etiquette described in [SUPPORT.md](SUPPORT.md).

---

## Pull requests

A PR template lives at `.github/PULL_REQUEST_TEMPLATE.md`. Fill it out completely.

Before marking a PR ready for review:

1. `make pr-ready` passes cleanly.
2. `make test` passes (or model-backed tests are explicitly skipped with justification).
3. The branch is rebased on `main` with no merge commits.
4. The PR description explains *why* the change is needed, not just what it does.
5. Agent contract changes include README and test updates.
6. Model or dependency pin bumps include re-measured numbers.

---

## Issues

Issue templates live at `.github/ISSUE_TEMPLATE/`. Use the appropriate template for bug
reports, feature requests, and agent contract proposals.

For questions and usage help, use [GitHub Discussions](https://github.com/shapeandshare/ember/discussions)
rather than Issues.

For security vulnerabilities, see [SECURITY.md](SECURITY.md). Do not open a public issue.

## Material provenance

For new artwork, copied text, templates, or dependencies, document the source and
license evidence in [provenance.json](provenance.json) and follow
[PROVENANCE.md](PROVENANCE.md). Disclose AI generation and keep actual prompts
when available. Never substitute an assumed license for missing evidence.
Run `python3 scripts/check_provenance.py` after changing brand assets.
