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
  - evals/context/items.py
  - evals/context/run_context.py
  - evals/clef-flash.jsonl
---

# give each model its own memory-checked fallback request cap

Part of [[ember]]. Until the long-context probe measures a model's cap, each registry model
falls back to the longest probe length that fits its own memory budget instead of a shared
32,768. The benchmark grows so that the probe can resolve its accuracy tolerance.

## Context

- The pilot could not resolve the 2-point accuracy tolerance with 232 text items
  ([[2026-10-10-probe-items-cannot-resolve-the-tolerance]]).
- A memory check found that 32,768 tokens peak at 32.35 GiB on flash, over its 32 GiB
  budget ([[2026-10-10-memory-checks-bound-each-models-cap]]).
- Asked whether to lower the shared fallback, the maintainer answered that more models are
  coming, each with its own memory requirements, so no single value fits them all.

## Decision

- **No shared fallback.** `ModelSpec` declares `memory_budget_bytes`, moved from the probe's
  `MEMORY_BUDGETS`, and `fallback_request_length`, the longest probe length whose peak fits
  that budget. `default_request_cap` returns the measured cap when there is one and
  otherwise the model's own fallback, reported as `fallback`. A model outside the registry
  gets the lowest registry cap, measured or fallback, because nothing is known about its
  memory. `FALLBACK_REQUEST_CAP` is gone.
- **flash falls back to 24,576** (27.83 GiB of 32 GiB) and **full to 16,384** (63.54 GiB
  of 64 GiB, a thin margin; 24,576 peaked at 68.40 GiB).
- **Grow the benchmark; keep the tolerance.** Loosening the 2-point tolerance after seeing
  pilot data would undo its pre-declaration, so 211 curated text items take the benchmark
  to 443 (projected half-width about 0.019). Their labels need a human review before any
  run cites them.

## Consequences

- A new registry entry states its budget and runs a one-item memory check before it ships:
  `ember eval context --models <name> --items 1 --lengths <lengths>`, without 16,384 (that
  length starts the sizing gate, which one item always fails). The fallback is the longest
  length that fit; the worker stops at the first length that doesn't. To check 16,384, run
  it alone: the gate's pilot records that row before the run exits 2.
- Deployments outside the registry (`EMBER_MODEL_DIR`, `EMBER_MODEL_S3_URI`) default to the
  lowest registry cap, 16,384 today, instead of 32,768. Operators who know their model's
  memory set `EMBER_MAX_REQUEST_LENGTH`.
- The measured caps still need the re-run pilot and then a canonical run on a clean tree.
