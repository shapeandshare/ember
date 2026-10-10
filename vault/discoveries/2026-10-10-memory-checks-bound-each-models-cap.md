---
title: "Memory checks bound each model's request cap"
type: discovery
tags:
  - type/discovery
  - domain/models
  - domain/runtime
  - status/draft
created: "2026-10-10"
updated: "2026-10-10"
code-refs:
  - evals/context/memory_sampler.py
  - evals/context/worker.py
  - ember/models.py
---

# Memory checks bound each model's request cap

Part of [[ember]]. A one-item memory check showed that the old shared 32,768-token fallback
let flash requests peak above flash's pre-declared 32 GiB budget, which is the memory of the
smallest Mac flash is documented to run on.

## What was tested

`ember eval context --models flash --items 1 --lengths 24576,32768,65536 --run-id
memory-check-flash` on the M4 Max (128 GB): one item at 2,048, 24,576, 32,768, and 65,536
tokens, at three depths each. Peak memory is `rss_start + driver_peak`
(`evals/context/memory_sampler.py`), and the worker stops at the first length over the
budget (`evals/context/worker.py`). The lengths leave out 16,384 because that length starts
the sizing gate, which a one-item run always fails: one delta gives an infinite half-width.

## Finding

| flash | Peak | Latency |
| --- | --- | --- |
| 2,048 | 19.77 GiB | 5.7 s |
| 24,576 | 27.83 GiB | 75 s |
| 32,768 | 32.35 GiB, over 32 GiB | 103 s |
| 65,536 | not run: the worker stopped at 32,768 | |

The driver alone peaked at 31.38 GiB at 32,768 tokens; the process RSS (0.97 GiB) puts it
over the budget. Peaks barely move with evidence depth (within 0.06 GiB). MPS's recommended
working set on this host is 107.5 GiB, so the host was never at risk; only the budget
failed. The run's one-item quality cells, including its "cap 2048" verdict, are noise.

## Relevance

Under the pre-declared rule, flash's measured cap can never exceed 24,576, so a 32,768
default was inadmissible on memory alone. Each model now carries its own memory-checked
fallback; see [[2026-10-10-per-model-request-caps]].

## References

- `results/context/memory-check-flash/`, a local run (`results/` is not tracked)
- `specs/003-context-window-audit/research.md`: R11 (peak memory) and R12 (cap rule)
