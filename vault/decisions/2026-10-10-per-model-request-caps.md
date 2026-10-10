---
title: "give each model its own memory-checked fallback request cap"
type: decision
tags:
  - type/decision
  - domain/models
  - domain/server
  - domain/agent-kit
  - status/draft
created: "2026-10-10"
updated: "2026-10-10"
code-refs:
  - ember/models.py
  - ember/serving/limits.py
  - ember/cfg/endpoint.py
  - ember/codex/codex_config.py
  - evals/context/items.py
  - evals/context/run_context.py
  - evals/clef-flash.jsonl
---

# give each model its own memory-checked fallback request cap

Part of [[ember]]. Until the long-context probe measures a model's cap, each registry model
falls back to the longest probe length whose peak memory leaves 4 GiB of its own budget
free, instead of a shared 32,768. full's documented minimum rises to 96 GB so that its
fallback can be 65,536, and the client waits up to 900 s for a request. The benchmark grows
so that the probe can resolve its accuracy tolerance.

## Context

- The pilot could not resolve the 2-point accuracy tolerance with 232 text items
  ([[2026-10-10-probe-items-cannot-resolve-the-tolerance]]).
- A memory check found that 32,768 tokens peak at 32.35 GiB on flash, over its 32 GiB
  budget ([[2026-10-10-memory-checks-bound-each-models-cap]]).
- Asked whether to lower the shared fallback, the maintainer answered that more models are
  coming, each with its own memory requirements, so no single value fits them all.
- Copilot's review of #96 flagged that full at 16,384 tokens peaks at 63.54 GiB, leaving
  0.46 GiB of its 64 GiB budget for macOS and everything else. The maintainer chose to keep
  4 GiB of every budget free, which put full at 8,192.
- The maintainer then preferred allowing 16K and up and requiring more memory for full,
  and chose a 96 GB minimum. full at 65,536 tokens takes about 740 s on an M4 Max, so they
  also chose a 900 s default request timeout.

## Decision

- **No shared fallback.** `ModelSpec` declares `memory_budget_bytes`, moved from the probe's
  `MEMORY_BUDGETS`, and `fallback_request_length`: the longest probe length whose peak
  leaves at least 4 GiB of that budget free for the OS. `default_request_cap` returns the
  measured cap when there is one and otherwise the model's own fallback, reported as
  `fallback`. A model outside the registry gets the lowest registry cap, measured or
  fallback, because nothing is known about its memory. `FALLBACK_REQUEST_CAP` is gone.
- **flash** keeps its 32 GiB budget and falls back to 24,576 (27.83 GiB, 4.17 GiB free).
  **full** now requires 96 GB and falls back to 65,536, the longest probe length (90.80
  GiB, 5.20 GiB free).
- **Wait 900 s.** `EMBER_REQUEST_TIMEOUT` defaults to 900 s instead of 300 s, so a request
  at full's default can finish. The generated Codex `tool_timeout_sec` is 1,260 s, enough
  for a 300 s autostart, the 900 s request, and a minute of margin.
- **Grow the benchmark; keep the tolerance.** Loosening the 2-point tolerance after seeing
  pilot data would undo its pre-declaration, so 211 curated text items take the benchmark
  to 443 (projected half-width about 0.019; merged in #95).

## Consequences

- A new registry entry states its budget and runs a one-item memory check before it ships:
  `ember eval context --models <name> --items 1 --lengths <lengths>`, without 16,384 (that
  length starts the sizing gate, which one item always fails). The fallback is the longest
  length whose peak leaves 4 GiB of the budget free; the worker stops at the first length
  over the budget. To check 16,384, run it alone: the gate's pilot records that row before
  the run exits 2.
- Deployments outside the registry (`EMBER_MODEL_DIR`, `EMBER_MODEL_S3_URI`) default to the
  lowest registry cap, 24,576 today, instead of 32,768. Operators who know their model's
  memory set `EMBER_MAX_REQUEST_LENGTH`.
- Harnesses have their own tool-call limits (Claude Code's `MCP_TOOL_TIMEOUT`, for one), so
  a long full request may need those raised too.
- The 4 GiB reserve applies to the fallbacks only. The pre-declared FR-010 rule still
  compares a measured cap's peak with the whole budget, so a measured cap could land closer
  to the budget than its fallback. Revisit that before the measured caps ship.
- The measured caps still need the re-run pilot and then a canonical run on a clean tree.
