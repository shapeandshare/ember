---
title: "Decision models are the category; Clef is the current one"
type: decision
tags:
  - type/decision
  - domain/models
  - domain/governance
  - status/draft
created: "2026-10-05"
updated: "2026-10-05"
code-refs:
  - ember/models.py
  - ember/cli.py
  - ember/mcp/mcp_server.py
  - ember/agent_kit/instructions.md
  - ember/agent_kit/ember-advise/SKILL.md
---

# Decision models are the category; Clef is the current one

Part of [[ember]]. ember is framed and structured as a runner of **decision models**
as a category; Cloudflare's Clef (flash, full) is the current model, not the product
definition. New decision models can be added to the registry as they arrive.

## Context

The product pitch read as if ember *is* the Clef tool ("ember runs Cloudflare's
Clef-Flash model"), which ties the product to a single upstream model. More decision
models are expected, and Clef's `flash` and `full` revisions are already two registry
entries. The registry in `ember/models.py` was structurally a list of pinned repos but
was named and documented only as Clef models.

## Decision

- Record the category on the registry entry: `ModelSpec.kind` defaults to `"decision"`,
  and `list_models()` exposes it per row.
- Frame the product as running decision models, with Clef as the current instance, in
  README, RESPONSIBLE_USE, DESIGN, CONTRIBUTING, AGENTS.md, the site, and the agent kit.
- Keep model-specific facts where they are facts: pinned revisions, integrity hashes,
  the measured thresholds, and the eval report stay tied to Clef.
- Do not rename internal symbols (`load_clef`, `ClefModel`). `ClefModel` comes from
  upstream `joint_schema_model.py`; renaming our loader is churn with no user benefit.

## Consequences

- Adding a future decision model is a registry entry plus a `kind`, not a product rewrite.
- `ember model list` reports each model's `kind`.
- `ember/agent_kit/instructions.md` stays within its 2048-byte cap.
- `tests/test_model_integrity.py` covers the registry category.
- The category is a seed, not a framework: no filtering CLI or plugin system until a
  second category actually exists.
