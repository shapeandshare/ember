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
# gut-feeling (clef-local) Constitution

## Core Principles

### Article I — Local-First and Private

Inference MUST run on the user's machine. The decision path (`clef-mcp` → HTTP server → model)
MUST NOT send `state`, questions, or answers over the network; the only network access is the
explicit, user-initiated weight download (`clef model pull`, `make download`). Model weights
MUST stay in the Hugging Face cache or a user-chosen directory, and MUST NOT be redistributed
from this repository.

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
`initialize.instructions`, the `clef://guide` resource, the `clef-decide` skill, and the
AGENTS.md snippet are the entire manual. Therefore:

- §3.1 All agent-facing guidance MUST live in `clef_local/agent_kit/` and be delivered from
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

## Additional Constraints

- Python 3.12 managed by uv; console scripts `clef` and `clef-mcp` are the supported entry points.
- `stdout` of the MCP process is the JSON-RPC wire; diagnostics MUST go to stderr.
- Per-machine generated files (`opencode.json`, `.opencode/plugins/clef.js`) MUST NOT be
  committed.
- Repository code is MIT-licensed; the upstream Clef weights and `joint_schema_model.py` remain
  Apache-2.0 and are downloaded at runtime, never vendored.

## Development Workflow & Quality Gates

1. Plan non-trivial features with spec-kit (`/speckit.specify` → `/speckit.plan` →
   `/speckit.tasks` → `/speckit.implement`); every plan MUST pass a Constitution Check.
2. Commit atomically with plain, imperative English subjects; tests land in the same commit
   as the code they cover.
3. Gate every commit on `make check`; gate merges on CI plus `make test` (or `make test-strict`
   on a self-hosted Apple Silicon runner) for model-affecting changes.
4. Keep `AGENTS.md`, `README.md`, and the agent kit consistent with each other and with this
   constitution in the same change.

## Governance

- This constitution supersedes ad hoc practice for all work in this repository. `AGENTS.md`
  operationalizes it for agent sessions; where the two conflict, the constitution wins and
  `AGENTS.md` MUST be updated.
- Agents MUST NOT weaken a principle to make work pass; principle changes are human-approved
  amendments.
- Amendments land through a pull request that updates the Sync Impact Report at the top of this
  file and bumps the version: MAJOR for removing or redefining a principle, MINOR for adding a
  principle or section, PATCH for clarifications.
- Reviews MUST check changes against the Articles, with special attention to Article III
  (agent contract) and Article V (pins).

**Version**: 1.0.0 | **Ratified**: 2026-10-02 | **Last Amended**: 2026-10-02
