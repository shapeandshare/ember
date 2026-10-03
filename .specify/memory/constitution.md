<!--
SYNC IMPACT REPORT — Public Repository Clarification
Version change: 1.3.1 → 1.3.2 (PATCH: clarification, no principle change)
Date: 2026-10-03
Modified principles:
  - Development Workflow & Quality Gates — gate 3 names a maintainer's Apple Silicon machine
    for the model-backed suite; the repository is public and never uses a self-hosted runner.
    No requirement changes.
Added sections: none
Removed sections: none
Templates / docs propagated:
  - ✅ README.md (public install note; `test-strict` no longer "for CI")
  - ✅ vault/decisions/2026-10-03-harden-github-before-going-public.md
Follow-up TODOs: none
-->
<!--
SYNC IMPACT REPORT — Agent Evaluation Clarification
Version change: 1.3.0 → 1.3.1 (PATCH: clarification, no principle change)
Date: 2026-10-03
Modified principles:
  - Article IV — clarifies that the opt-in agent evaluation (`ember eval agent`) may launch the
    opencode CLI inside an isolated sandbox; tests still MUST NOT. Approved by the maintainer.
Added sections: none
Removed sections: none
Templates / docs propagated:
  - ✅ AGENTS.md (commands, watch-outs), README.md (Benchmark section)
  - ✅ vault/decisions/2026-10-03-measure-ember-through-the-agent.md
Follow-up TODOs: none
-->
<!--
SYNC IMPACT REPORT — Python Conventions Amendment
Version change: 1.2.0 → 1.3.0 (MINOR: new Article X)
Date: 2026-10-03
Modified principles:
  - Article VIII — unchanged; Article X refines it and defers to it where silent
Added sections:
  - Article X — Python Conventions
Removed sections: none
Migration debt:
  - Recorded inline as Article X §10.18; existing violations MUST NOT grow. One-class-per-file,
    no-loose-functions, and the 400-line ceiling remain prospective and tracked. NumPy
    docstrings (ruff `D`) and `ember/py.typed` are wired in this change and now enforced for
    `ember/`.
Templates / docs propagated:
  - ✅ AGENTS.md (new "Python conventions" section; watch-outs; truth table unchanged)
  - ✅ CONTRIBUTING.md (Code style section expanded with the same rules)
  - ✅ pyproject.toml ([tool.ruff.lint] selects `D`, `[tool.ruff.lint.pydocstyle]` numpy;
    tests/scripts exempt), ember/py.typed (zero-byte PEP 561 marker)
  - ✅ ember/ docstrings brought to NumPy compliance (66 → 0)
  - ✅ vault/decisions/2026-10-03-adopt-peer-python-conventions.md, vault/ember.md (hub link)
Follow-up TODOs:
  - Split `ember/cli.py` (788 lines) by responsibility to meet the Article X ceiling
  - Pay down one-class-per-file / no-loose-functions debt as files are next touched
-->
<!--
SYNC IMPACT REPORT — Project Memory Vault Amendment
Version change: 1.1.2 → 1.2.0 (MINOR: new Article IX)
Date: 2026-10-02
Modified principles: none
Added sections:
  - Article IX — Project Memory Vault
Removed sections: none
Templates / docs propagated:
  - ✅ AGENTS.md (vault protocol; structure, commands, and watch-outs)
  - ✅ README.md (layout and make targets)
  - ✅ vault/ (hub, tag vocabulary, templates, first notes)
  - ✅ scripts/vault_audit.py, tests/test_vault_audit.py, shared/vault.mk
  - ✅ .opencode/opencode.json (vault MCP server), .opencode/commands/vault-health.md
  - ✅ provenance.json, PROVENANCE.md (wellspring-adapted scaffolding, mcpvault)
Follow-up TODOs: none
-->
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
global opencode configuration. The opt-in agent evaluation (`ember eval agent`) is not a test:
it MAY launch the opencode CLI only inside a temporary sandbox with a private HOME and XDG
directories and no TCP port, MUST stop only the processes it launched, and MUST NOT run as part
of `make check`, `make test`, or CI.

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

### Article IX — Project Memory Vault

The vault at `vault/` is the governed memory of this project's own development: decisions,
discoveries, and session logs. It complements `README.md`, `AGENTS.md`, `DESIGN.md`, and
`PROVENANCE.md`, and never duplicates or overrides them.

- §9.1 Every note outside `vault/_meta/` MUST carry frontmatter (`title`, `type`, `tags`,
  `created`, `updated`) and use only tags listed in `vault/_meta/tags.md`: exactly one
  `type/*` matching `type`, at least one `domain/*`, and at most one `status/*`. A new tag
  is added to that file before it is used.
- §9.2 Significant decisions and non-obvious discoveries MUST be written back as they occur,
  in the same change as the work behind them. Session logs are append-only. Routine changes
  and facts documented elsewhere MUST NOT get notes.
- §9.3 Every note MUST be reachable by wikilinks from the hub `vault/ember.md`, and every
  wikilink and `code-refs` path MUST resolve.
- §9.4 Agent-written notes start at `status/draft` and MAY move to `status/reviewed` after
  verification against the code. Only a human sets `status/canonical`.
- §9.5 `make vault-audit` MUST pass before vault changes are complete; the unit suite runs
  the same audit over the real vault.

Rationale: without a vault, decisions and hard-won constraints live only in commit messages
and chat sessions. The sibling repositories (anvil, darkharbour, wellspring) keep the same
kind of vault, and agents read it through the `vault` MCP server.

### Article X — Python Conventions

**Applicability**: Effective 2026-10-03. Applies to new and modified code under `ember/`.
Existing violations are enumerated under §10.18 and MUST NOT increase. These rules refine
Article VIII; where they are silent, Article VIII governs. They are adapted from the peer
repositories' constitutions (anvil, wellspring, sonarqube-standalone, darkfactory,
infrastructure, k8s.platform) harvested on 2026-10-03.

- §10.1 **Package ownership.** Every fully-owned package level carries an `__init__.py`.
  Package markers are bare and docstring-only: no imports, and no re-exports of symbols
  defined in sibling modules. Two exceptions: the package root `ember/__init__.py` MAY carry
  the module docstring and `__version__`; and a sub-package whose entire purpose is a small
  public API (`ember/agent_kit/`) MAY define that API directly in its `__init__.py`. Data-only
  directories MUST NOT contain an `__init__.py`.
- §10.2 **One class per file.** A source file declares at most one primary class. A tightly
  coupled exception class raised only by that primary class MAY share its file.
- §10.3 **Sizing.** A module SHOULD NOT exceed 400 physical lines; reaching the ceiling is a
  design signal to split by responsibility — never delete docstrings, compress code, or
  suppress a check to comply. Evaluate decomposition when a package level reaches six peer
  modules, and keep nesting to at most two levels below the package root.
- §10.4 **Naming.** Modules are `snake_case.py`, named after their primary class when one
  exists. Classes are `PascalCase` with a subsystem suffix (`…Server`, `…Engine`, `…Client`,
  `…Error`). Constants are `UPPER_CASE`; private names start with `_`.
- §10.5 **Imports.** All imports live at the top of the file. Four exceptions only: a
  `TYPE_CHECKING` import that breaks a genuine runtime cycle, carrying a `# cycle:` comment; a
  `try`/`except ImportError` guard for an optional dependency, naming `ImportError`
  explicitly; an import of a module that ships outside this package and is loadable only after
  adjusting `sys.path` (the model snapshot's `joint_schema_model`), carrying an
  `# import-placement:allow` comment; and a last-resort `# import-placement:allow` with a
  justification. Internal `ember` modules MUST NOT be lazy-imported. Inside `ember/`, use
  relative imports; absolute `ember.` imports are valid only from outside the package
  (`tests/`, `scripts/`). Never import a symbol through an `__init__` re-export — import the
  defining module.
- §10.6 **Typing.** Article VIII's `mypy --strict` is the floor. A type suppression MUST carry
  a specific error code and a comment explaining why (`# type: ignore[arg-type]  - reason`);
  bare `# type: ignore`, `cast()` used to silence the checker, and `Any` used as an escape
  hatch are prohibited. Every module starts with `from __future__ import annotations`; never
  write string-literal forward references; prefer PEP 604 unions (`str | None`) over
  `typing.Optional`/`Dict`/`List`.
- §10.7 **Enums over magic strings.** A value drawn from a fixed, known set is an `Enum`
  (`StrEnum`/`IntEnum`), not a bare string constant or ad-hoc dict mapping. A Pydantic
  `Literal[...]` is permitted when the field is part of a published schema (for example the
  `advise` question `type`).
- §10.8 **Data models.** Structured data that crosses a boundary (HTTP, MCP, config, on-disk)
  uses a Pydantic v2 `BaseModel`; an internal value object that never crosses one MAY be a
  `@dataclass(frozen=True)` (for example the model registry's `ModelSpec`).
- §10.9 **Interfaces and dependencies.** Interfaces are `typing.Protocol`, never `abc.ABC`.
  Dependencies are constructor-injected. Service locators, and module-level singletons or
  mutable state used as general dependency plumbing, are prohibited. A private, module-owned
  lazy cache for a process-wide resource — the loaded engine (`server._ENGINE`) or the runtime
  module (`runtime._JOINT_MODULE`) — is permitted and is not public API. A test double replaces
  a boundary you own, never the unit under test.
- §10.10 **Docstrings.** Every module, class, and public function carries a NumPy-style
  docstring; a class documents its constructor parameters in `__init__`. One-line docstrings
  are acceptable only for trivial properties. Enforced by ruff `D` with
  `convention = "numpy"` over `ember/`; tests and scripts are exempt.
- §10.11 **Comments.** Comments explain why, not what. Section separators use solid `#` lines,
  never dashed rules. Every rule exception carries a machine-readable tag (`# cycle:`,
  `# import-placement:allow`).
- §10.12 **Error handling.** Raise typed exceptions; bare `except:` and swallowed errors are
  prohibited. Outbound network calls set an explicit timeout.
- §10.13 **Logging.** Library code logs through `logging.getLogger(__name__)` and never calls
  `print`; entry points render user output. In `mcp_server.py`, stdout remains the JSON-RPC
  wire (Additional Constraints).
- §10.14 **Concurrency.** Model inference is synchronous behind the engine lock and MUST NOT
  be made async. Async is used only at I/O boundaries and MUST use structured concurrency;
  fire-and-forget tasks are prohibited.
- §10.15 **Entry points, not a God class.** Each subsystem exposes one composition root
  (`Engine.advise`, `process.start`, `mcp_server.main`, `cli.main`). ember deliberately does
  not adopt a single application-wide façade (God Class): the MCP / HTTP / CLI split is the
  seam, and each root wires only its own subsystem.
- §10.16 **Client SDKs.** Any typed Python client for the model server follows a
  transport → sub-client → facade layering with one shared transport and lazy sub-clients; the
  server's request/response schema (`ember/server.py`) remains the source of truth.
- §10.17 **Idempotent, atomic operations.** State-writing commands are safe to re-run and
  existence-guarded; a file write that could clobber another writes a sibling `.tmp` first and
  installs it with `os.replace()`.
- §10.18 **Migration debt.** Known existing violations, tracked here and never increased:
  `ember/cli.py` is 788 lines, over the 400-line ceiling, and defers its `server`/`mcp_server`
  imports into commands to keep startup light (an unsanctioned exception to §10.5);
  `ember/mcp_server.py` declares two classes; and most modules are function-oriented rather
  than one-class-per-file. NumPy docstrings (ruff `D`) and the `py.typed` marker are now
  enforced. Each remaining item is paid down as its file is next touched — splitting
  `ember/cli.py` is the priority.

Rationale: ember's sibling repositories converge on these conventions, and adopting them keeps
agent-written changes consistent across the family. Where ember's runtime differs — synchronous
MPS inference, an MCP / HTTP / CLI seam, and deliberately function-oriented modules — the rule
is scoped or the divergence recorded, so this constitution stays truthful about what the code
actually does.

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
   `make test` for model-affecting changes, run on a maintainer's Apple Silicon machine
   (`make test-strict` fails instead of skipping when weights are missing).
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

**Version**: 1.3.2 | **Ratified**: 2026-10-02 | **Last Amended**: 2026-10-03
