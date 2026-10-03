# Contributing to gut-feeling

gut-feeling is a local MCP server that exposes Cloudflare's Clef decision model to coding
agents. It runs on Apple Silicon (MPS), ships as a uv tool, and integrates with opencode and
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
git clone https://github.com/shapeandshare/gut-feeling
cd gut-feeling
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
  call `.to("mps")`. See `gut_feeling/runtime.py` for the canonical pattern.
- **`opencode.json` and `.opencode/plugins/gut.js` are per-machine.** They are gitignored.
  Never commit them.

---

## Commit messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/).

**Format:**

```
<type>: <subject>

[optional body]

[optional footer]
```

**Types:** `feat`, `fix`, `docs`, `chore`, `test`, `refactor`, `perf`, `ci`

**Subject rules:** imperative mood, 72 characters or fewer, no trailing period.

**Body rules:** wrap at 72 characters; explain *why*, not just *what*.

**Examples:**

```
feat: add score question type to CLI output

fix: handle missing pidfile in stop command

docs: update agent onboarding kit README

chore: bump ruff to 0.9.1

test: add model-backed noul boundary test
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
  weights are absent. They run locally and on the self-hosted Apple Silicon CI runner.

### Test layout

```
tests/
  test_runtime.py        # Engine, MPS loader
  test_server.py         # FastAPI endpoint, request validation
  test_mcp_tool.py       # MCP tool schema, advise handler
  test_cli.py            # CLI commands
  test_agent_kit.py      # kit file sizes, schema consistency
  test_process.py        # warm-server lifecycle
```

---

## Agent contract changes

The following are **public API** (Article III of the constitution). Changes to any of them
require matching README and test updates in the same PR.

| Artifact | Location | Constraint |
| --- | --- | --- |
| Tool name | `gut_feeling/mcp_server.py` | Must stay `gut-feeling_advise` (opencode) / `advise` (MCP) |
| Input schema | `gut_feeling/mcp_server.py` | Input wrapped in `input`; do not flatten |
| MCP instructions | `gut_feeling/agent_kit/instructions.md` | Must stay ≤ 2048 bytes |
| Guide resource | `gut_feeling/agent_kit/gut-feeling-advise/SKILL.md` | Delivered as `gut-feeling://guide` |
| Skill name | `gut_feeling/agent_kit/gut-feeling-advise/` | Must stay `gut-feeling-advise` |
| AGENTS.md snippet | `gut_feeling/agent_kit/AGENTS.snippet.md` | Shown by `gut agents show snippet` |

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
- The agent must use `gut-feeling_advise` (via the local MCP server) for triage and risk-gate
  decisions, following the recipes in `gut_feeling/agent_kit/gut-feeling-advise/SKILL.md`.
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

For questions and usage help, use [GitHub Discussions](https://github.com/shapeandshare/gut-feeling/discussions)
rather than Issues.

For security vulnerabilities, see [SECURITY.md](SECURITY.md). Do not open a public issue.
