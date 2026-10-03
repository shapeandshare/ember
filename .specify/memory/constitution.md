<!--
SYNC IMPACT REPORT — Ember Rename Amendment
Version change: 1.1.1 → 1.1.2 (PATCH: product renamed to match the mascot, no principle change)
Date: 2026-10-02
Modified principles:
  - Articles I, III, VIII — names updated (`ember-mcp`, `ember://guide` resource,
    `ember-advise` skill, `ember/` package)
Added sections: none (the naming bullet in Additional Constraints now marks "gut feeling"
  as flavor text and names the `gut` distribution)
Removed sections: none
Templates / docs propagated:
  - ✅ AGENTS.md (Naming section; names throughout)
  - ✅ README.md, CONTRIBUTING.md, DESIGN.md, SECURITY.md, SUPPORT.md (names, repository URLs)
  - ✅ ember/agent_kit/ (instructions, skill, snippet)
  - ✅ assets/brand/ (banner wordmark, titles, `--ember-*` tokens) and provenance.json
Follow-up TODOs: none (repository renamed to shapeandshare/ember; distribution is `gut`
  because `ember` is taken on PyPI)
-->
<!--
SYNC IMPACT REPORT — Naming Consolidation Amendment
Version change: 1.1.0 → 1.1.1 (PATCH: names and clarifications, no principle change)
Date: 2026-10-02
Modified principles:
  - Article III — artifact names updated (`advise` tool, `gut-feeling-advise` skill,
    `gut-feeling://guide` resource)
Added sections: none (one naming bullet added to Additional Constraints)
Removed sections: none
Templates / docs propagated:
  - ✅ AGENTS.md (Naming section; names throughout)
  - ✅ README.md, CONTRIBUTING.md, DESIGN.md, SECURITY.md, SUPPORT.md (names)
  - ✅ gut_feeling/agent_kit/ (instructions, skill, snippet reframed as an advisor)
Follow-up TODOs: none
-->
<!--
SYNC IMPACT REPORT — Tooling & Quality Gates Amendment
Version change: 1.0.0 → 1.1.0
Date: 2026-10-02
Modified principles: none
Added sections:
  - Article VIII — Tooling and Code Quality
Removed sections: none
Migration debt: none (tooling config already added to pyproject.toml)
Templates / docs propagated:
  - ✅ AGENTS.md (new "Tooling" section added; commands table updated)
  - ✅ CONTRIBUTING.md (code style table, pr-ready gate, commit conventions)
  - ✅ DESIGN.md (tooling stack section, config-location section)
  - ✅ pyproject.toml ([tool.ruff], [tool.mypy], [tool.bandit], [tool.commitizen], [tool.coverage.*])
  - ✅ shared/python.mk (lint, format, typecheck, security, pr-ready targets)
  - ✅ .github/workflows/ci-check.yml (stub: lint + typecheck + security jobs)
Follow-up TODOs:
  - Enable ci-check.yml auto-trigger once `make pr-ready` is confirmed green on main
  - Ratchet coverage floor (currently 60%) upward as test coverage grows
-->
<!--
SYNC IMPACT REPORT — Constitution Ratification
Version change: template → 1.0.0 (initial ratification)
Date: 2026-10-02
Modified principles: n/a (template placeholders replaced)
Added sections:
  - Article I — Local-First and Private
  - Article II — Typed Decisions, Not Text
  - Article III — Agent-Legible Contract
  - Article IV — Lazy, Non-Interfering Lifecycle
  - Article V — Reproducibility by Pinning
  - Article VI — Apple Silicon First
  - Article VII — Verification Over Assertion
  - Additional Constraints
  - Development Workflow & Quality Gates
  - Governance
Removed sections: none
Templates / docs propagated:
  - ✅ AGENTS.md (operationalizes this constitution; behavioral principles map to Articles)
  - ✅ CLAUDE.md (imports AGENTS.md)
  - ✅ README.md (agent onboarding section reflects Article III)
  - ⚠ .specify/templates/*.md (no change — the generic Constitution Check gate applies as-is)
Follow-up TODOs: none
-->
# ember Constitution

## Core Principles

### Article I — Local-First and Private

Inference MUST run on the user's machine. The decision path (`ember-mcp` → HTTP server →
model) MUST NOT send `state`, questions, or answers over the network; the only network access is
the explicit, user-initiated weight download (`ember model pull`, `make download`). Model
weights MUST stay in the Hugging Face cache or a user-chosen directory, and MUST NOT be
redistributed from this repository.

Rationale: agents pass sensitive context (code, diffs, logs, user messages) into `state`.
Keeping it local is the core value proposition.

### Article II — Typed Decisions, Not Text

The product surface is calibrated probabilities over options the caller defines (`noul`,
`choice`, `score`), returned in the Jev/SystemOne response shape. The tool MUST NOT generate
free-form text, and the server MUST reject malformed questions with explicit errors (HTTP 422,
MCP tool errors) rather than guessing. New question types or response fields are API changes
(see Governance).

Rationale: bounded, machine-readable outputs are what make the model safe to wire into agent
control flow.

### Article III — Agent-Legible Contract

For consumers' agents, the tool name, input schema, field descriptions, MCP
`initialize.instructions`, the `ember://guide` resource, the `ember-advise` skill, and the
AGENTS.md snippet are the entire manual. Therefore:

- §3.1 All agent-facing guidance MUST live in `ember/agent_kit/` and be delivered from
  there; no channel may carry a divergent copy.
- §3.2 `instructions.md` MUST stay within 2048 bytes; the skill MUST satisfy the Agent Skills
  frontmatter contract (`name` matching its directory, `description` ≤ 1024 characters).
- §3.3 Thresholds and observed numbers in the kit MUST come from real model output and MUST be
  re-measured when the model revision or a recipe schema changes.
- §3.4 Changes to any of these artifacts MUST be reviewed as public-API changes and land with
  matching README and test updates.

### Article IV — Lazy, Non-Interfering Lifecycle

The model server SHALL start on demand (lazy autostart) and stay warm; nothing may run at
login or boot unless the user opts in. Tooling MUST only start, signal, or stop processes it
launched itself (tracked by PID) and MUST NOT kill by port or by pattern. Tests MUST bind random
free ports, MUST NOT use the default port 8765, and MUST NOT invoke the opencode CLI or modify
global opencode configuration.

Rationale: users run several opencode instances and their own servers on the same host.

### Article V — Reproducibility by Pinning

Model weights MUST be pinned to Hugging Face commit SHAs in `REGISTRY`. Dependency ranges MUST
be anchored to tested versions, `uv.lock` MUST be committed, and CI MUST install with
`uv sync --locked`. Bumping a model revision or widening a dependency range MUST be accompanied
by green model-backed tests and re-measured agent-kit numbers (§3.3).

### Article VI — Apple Silicon First

The supported platform is macOS on Apple Silicon with the MPS backend in float16, falling back to
CPU in float32. Weights MUST be loaded on CPU and then moved to MPS; `device_map={"": "mps"}`
MUST NOT be used (it segfaults with the pinned stack). CUDA and other platforms are out of scope
until this Article is amended.

### Article VII — Verification Over Assertion

Work is done when the evidence says so: `make check` passes before every commit, `make test`
passes for changes to the runtime, servers, CLI, or agent kit, and CI is green. User-visible
behavior MUST be exercised for real (CLI runs, MCP protocol calls, and an opencode end-to-end
check where integration changes), not inferred from reading code.

### Article VIII — Tooling and Code Quality

**Applicability**: Effective 2026-10-02. Fully applies; no migration debt.

All Python source in `ember/` MUST pass the following gates before a commit reaches
`main`:

- **Formatting**: `ruff format` (line length 88, double quotes). Run via `make format`.
- **Linting**: `ruff check` with rule sets E, F, I, N, W, UP, B, S, PT, RUF.
  Run via `make lint`.
- **Type checking**: `mypy --strict` targeting `ember/`. Run via `make typecheck`.
- **Security**: `bandit -r ember/`. Run via `make security`.
- **Compile**: `python -m compileall -q ember scripts tests`. Run via `make compile`.
- **Unit tests**: `pytest -m "not model"`. Run via `make test-fast`.

The composite gate `make pr-ready` runs all of the above in order. It MUST pass before opening
a pull request. CI will enforce a subset of these gates automatically once
`.github/workflows/ci-check.yml` is enabled (currently stub — manual trigger only).

All tool configuration MUST live in `pyproject.toml`. Separate tool config files (`ruff.toml`,
`mypy.ini`, `.bandit`, `.coveragerc`) MUST NOT be created; they scatter configuration and
create reconciliation debt.

Commit messages MUST follow Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`,
`refactor:`, `test:`). Version bumps are managed by commitizen (`uv run cz bump`).

Coverage is tracked but not yet gated; the initial floor is 60% (`fail_under = 60` in
`[tool.coverage.report]`). The floor MUST only move upward as the test suite grows; it MUST NOT
be lowered to make a failing run pass.

## Additional Constraints

- The product name is **ember**, after the Ember mascot, in every artifact: package `ember`,
  MCP server `ember` with the `advise` tool, skill `ember-advise`, resource `ember://guide`,
  environment variables `EMBER_*`, and repository `shapeandshare/ember`. The one exception
  is the distribution, `gut`, because `ember` is taken on PyPI. "Gut feeling" phrasing, such
  as the tagline, is flavor text, not a name. "Clef" MUST refer only to Cloudflare's
  upstream model. ember advises; agents decide.
- Python 3.12 managed by uv (consumers install with `uv tool install --python 3.12`); console
  scripts `ember`, `gut`, and `ember-mcp` are the supported entry points.
- `stdout` of the MCP process is the JSON-RPC wire; diagnostics MUST go to stderr.
- Per-machine generated files (`opencode.json`, `.opencode/plugins/ember.js`,
  `.opencode/skills/ember-advise/`) MUST NOT be committed.
- Repository code is MIT-licensed; the upstream Clef weights and `joint_schema_model.py` remain
  Apache-2.0 and are downloaded at runtime, never vendored.

## Development Workflow & Quality Gates

1. Plan non-trivial features with spec-kit (`/speckit.specify` → `/speckit.plan` →
   `/speckit.tasks` → `/speckit.implement`); every plan MUST pass a Constitution Check.
2. Commit atomically with Conventional Commits subjects; tests land in the same commit as the
   code they cover.
3. Gate every commit on `make check`; gate PRs on `make pr-ready`; gate merges on CI plus
   `make test` (or `make test-strict` on a self-hosted Apple Silicon runner) for
   model-affecting changes.
4. Keep `AGENTS.md`, `README.md`, and the agent kit consistent with each other and with this
   constitution in the same change.

## Governance

- This constitution supersedes ad hoc practice for all work in this repository. `AGENTS.md`
  operationalizes it for agent sessions; where the two conflict, the constitution wins and
  `AGENTS.md` MUST be updated.
- Agents MUST NOT weaken a principle to make work pass; principle changes are human-approved
  amendments.
- Amendments land through a pull request that prepends a new Sync Impact Report block at the
  top of this file and bumps the version: MAJOR for removing or redefining a principle, MINOR
  for adding a principle or section, PATCH for clarifications.
- Reviews MUST check changes against the Articles, with special attention to Article III
  (agent contract) and Article V (pins).

**Version**: 1.1.2 | **Ratified**: 2026-10-02 | **Last Amended**: 2026-10-02
