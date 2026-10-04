---
title: "Restructure ember/ and evals/ into domain-aligned sub-packages"
type: decision
tags:
  - type/decision
  - domain/governance
  - domain/tooling
  - status/reviewed
created: "2026-10-04"
updated: "2026-10-04"
code-refs:
  - ember/serving/server.py
  - ember/serving/runtime.py
  - ember/serving/process.py
  - ember/serving/media.py
  - ember/mcp/mcp_server.py
  - ember/mcp/mcp_types.py
  - ember/cfg/config.py
  - ember/cfg/paths.py
  - ember/opencode/opencode_config.py
  - ember/opencode/opencode_plugin.py
  - evals/render/render_html.py
  - evals/render/render_markdown.py
  - evals/render/markup.py
  - evals/render/blocks.py
  - evals/sections/sections_front.py
  - evals/sections/sections_results.py
  - evals/sections/sections_review.py
  - evals/sections/sections_agent.py
  - evals/charts/charts.py
  - evals/charts/charts_calibration.py
  - evals/charts/charts_agent.py
  - evals/charts/svg.py
  - .specify/memory/constitution.md
---

# Restructure ember/ and evals/ into domain-aligned sub-packages

Part of [[ember]]. Both `ember/` (13 flat modules) and `evals/` (19 flat modules)
exceeded constitution §10.3's 6-module decomposition threshold. Both packages were
reorganised into domain-aligned sub-packages in a zero-behavioral-delta structural commit.

## Context

Constitution §10.3 (adopted from wellspring's scaled-down threshold): "Evaluate
decomposition when a package level reaches six peer modules." Peer survey confirmed:

- `ember/` had 13 peer `.py` modules at root — more than double the threshold.
- `evals/` had 19 peer `.py` modules at root — more than triple the threshold.

Natural domain boundaries were clear from the existing import graph.

## Decision

**`ember/` split into 4 new sub-packages (zero behavioral delta):**

| Sub-package | Modules moved | Domain |
|---|---|---|
| `ember/serving/` | `server.py`, `runtime.py`, `process.py`, `media.py` | HTTP model server, MPS runtime, lifecycle, media decoding |
| `ember/mcp/` | `mcp_server.py`, `mcp_types.py` | MCP stdio server and wire types |
| `ember/cfg/` | `config.py`, `paths.py` | Configuration resolution and platform paths |
| `ember/opencode/` | `opencode_config.py`, `opencode_plugin.py` | opencode integration |

Stays at root: `cli.py` (entry point), `models.py` (cross-cutting), `agent_kit/` (already a sub-package).

**`evals/` split into 3 new sub-packages (zero behavioral delta):**

| Sub-package | Modules moved | Domain |
|---|---|---|
| `evals/render/` | `render_html.py`, `render_markdown.py`, `markup.py`, `blocks.py`, `report.css` | Report rendering: HTML/Markdown writers, inline markup, block DSL, stylesheet |
| `evals/sections/` | `sections_front.py`, `sections_results.py`, `sections_review.py`, `sections_agent.py` | Report section builders |
| `evals/charts/` | `charts.py`, `charts_calibration.py`, `charts_agent.py`, `svg.py` | Chart generation and SVG primitives |

Stays at root: `analysis.py`, `metrics.py`, `document.py`, `export.py`, `brand.py`, `report_text.py` (cross-cutting or entry-point style); `agent/` (already a sub-package).

## Consequences

- `pyproject.toml` entry point updated: `ember-mcp = "ember.mcp.mcp_server:main"`.
- All internal relative imports updated throughout `ember/` and `evals/`.
- All external absolute imports updated in `tests/`, `scripts/`, `evals/`.
- Vault code-refs updated in 4 affected notes.
- `make pr-ready` passes: ruff, mypy (19 files), bandit, compile, 127 tests.
- `make vault-audit` passes: clean.
- AGENTS.md and README.md project structure trees updated.
- Constitution §10.3 compliance restored for both packages.
