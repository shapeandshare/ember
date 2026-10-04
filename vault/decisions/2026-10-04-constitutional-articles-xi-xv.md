---
title: "Add constitutional Articles XI–XV: TDD, async-first, layered architecture, pit of success, simplicity"
type: decision
tags:
  - type/decision
  - domain/governance
  - domain/tooling
  - status/reviewed
created: "2026-10-04"
updated: "2026-10-04"
code-refs:
  - .specify/memory/constitution.md
  - AGENTS.md
  - CONTRIBUTING.md
  - ember/serving/server.py
  - pyproject.toml
---

# Add constitutional Articles XI–XV

Part of [[ember]]. Five new constitutional articles adopted from the anvil peer
repo's constitution, adapted for ember's single-purpose inference tool context.
Constitution bumped to v1.4.0 (MINOR — new articles added).

## Context

The user requested adoption of several constitutional principles from the anvil
peer repo's constitution, scoped to what is applicable for ember's growth:

- TDD and coverage ratcheting — universally applicable
- Async-first — applicable; server routes were sync (health, metrics)
- Layered architecture — applicable; ember's MCP→HTTP→Engine seam formalized
- Pit of success — applicable; ember already practiced this, now mandated
- DDD — already covered at 6-module threshold; broadened for agent decisions
- Simplicity First / YAGNI — universally applicable; not previously in ember's constitution

Articles V (Async-First), VII (Layered Architecture), IX (Pit of Success) from
anvil were not imported verbatim — they were adapted to ember's context (no DB,
no UI, no God Class).

## Decision

**Article XI — Test-Driven Development and Coverage Ratchet**
- Tests MUST ship in the same commit as implementation
- Coverage floor ratcheted from 60% → 71% (current measured level)
- `fail_under` bumped in `pyproject.toml`

**Article XII — Async-First**
- New FastAPI route handlers MUST be `async def`
- Sync engine calls carry `# async-first:exception` tag
- `health()` and `metrics()` converted to `async def`
- `systemone_endpoint()` stays `def` (engine lock is synchronous) with tag

**Article XIII — Layered Architecture**
- Formalizes the MCP→HTTP→Engine three-layer stack
- Cross-layer data MUST be Pydantic or plain dict
- No primitives (torch, Engine) may cross layer boundaries

**Article XIV — Pit of Success**
- Server returns 503 when model not loaded — never crashes
- CPU is always the fallback device
- Setup commands are idempotent

**Article XV — Simplicity First and YAGNI**
- Simplest viable solution; boring over novel
- No speculative generality
- Document complexity beyond the obvious minimum

## Consequences

- `health()` and `metrics()` are now `async def`; tests updated if needed
- `fail_under = 71` — coverage may not regress below this
- Agents now have explicit guidance for each principle in AGENTS.md behavioral
  principles (items 9–12) and "watch out for" bullets
- CONTRIBUTING.md convention table extended with new rows
- `make pr-ready` passes: ruff, mypy (19 files), bandit, compile, 127 tests
