---
title: "Pilot gate, memory checks, and per-model caps"
type: session-log
tags:
  - type/session-log
  - domain/models
  - domain/tooling
  - domain/agent-kit
created: "2026-10-10"
updated: "2026-10-10"
---

# Pilot gate, memory checks, and per-model caps

Part of [[ember]]. Act on the long-context probe's pilot (T059), which could not resolve the
accuracy tolerance, and on a memory check showing that the shared fallback was too high for
flash.

## What happened

- **Pilot.** `ember eval context --pilot` on flash and 232 text items gave a half-width of
  0.0264, over 0.02, so the run exited 2. The maintainer chose to grow the benchmark, keep
  the defaults unmeasured, and add a cheap memory-only check.
- **Memory check (flash).** 24,576 tokens peaked at 27.83 GiB, and 32,768 at 32.35 GiB,
  over the 32 GiB budget. Asked about the shared fallback, the maintainer asked for
  per-model values.
- **Benchmark.** 211 curated text items (443 text items, 475 in total) came from a one-off
  generator that copies each recipe's question set, alternates splits within each label
  group, and checks the frozen label rules. The labels await human review.
- **Per-model caps.** `ModelSpec` gained `memory_budget_bytes` and
  `fallback_request_length`, `FALLBACK_REQUEST_CAP` is gone, and flash falls back to
  24,576. The README, COMPATIBILITY, the agent kit and its plugin mirror, and the config
  contract say so.
- **Memory check (full).** Pulled full (51 GiB) and checked it: 8,192 tokens peaked at
  59.54 GiB, 16,384 at 63.54 GiB (run alone, through the sizing gate's pilot), and 24,576
  at 68.40 GiB, over its 64 GiB budget.
- **Review.** Copilot flagged that the spec, the agent-kit contract, the quickstart, and the
  data model still required the shared 32,768; they now state the per-model rule. It then
  flagged that 16,384 would leave full 0.46 GiB of its budget. The maintainer chose to keep
  4 GiB of every budget free for the OS, so full falls back to 8,192; flash's 24,576
  already leaves 4.17 GiB.

## Decisions and discoveries written back

- [[2026-10-10-probe-items-cannot-resolve-the-tolerance]]
- [[2026-10-10-memory-checks-bound-each-models-cap]]
- [[2026-10-10-per-model-request-caps]]

## Follow-ups

- Review the 211 new labels, then re-run the pilot.
- Before the measured caps ship, decide whether the FR-010 rule should keep the same 4 GiB
  reserve.
- Run a canonical `make eval-context` on a clean tree, then set the measured caps
  (T060 to T065).
