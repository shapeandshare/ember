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
  - evals/context/run_context.py
  - ember/models.py
---

# Memory checks bound each model's request cap

Part of [[ember]]. One-item memory checks showed two things. The old shared 32,768-token
fallback let flash requests peak above flash's 32 GiB budget. And full needs more than its
old 64 GiB budget for any request of 16K tokens or more that leaves room for the OS. The
budget is the memory of the smallest Mac the model is documented to run on.

## What was tested

One benchmark item, padded to each length at three depths, on the M4 Max (128 GB). Peak
memory is `rss_start + driver_peak` (`evals/context/memory_sampler.py`), and the worker
stops at the first length over the budget (`evals/context/worker.py`). Every full run
below used code with full's old 64 GiB budget, so each one stopped after its first length
over 64 GiB.

- flash: `ember eval context --models flash --items 1 --lengths 24576,32768,65536`
- full: `--models full --items 1 --lengths 4096,8192,24576,32768,65536`, then 16384,
  32768, and 65536 each on their own

A run that includes 16,384 starts the sizing gate (`evals/context/run_context.py`), and a
one-item gate always fails: one delta gives an infinite half-width. Its pilot still records
the 2,048 and 16,384 rows at the middle depth before the run exits 2, which is how full's
16,384 row was taken.

## Finding

| Length | flash peak (32 GiB budget) | full peak (96 GiB budget, was 64) |
| --- | --- | --- |
| 2,048 | 19.77 GiB | 54.53 GiB |
| 4,096 | | 56.54 GiB |
| 8,192 | | 59.54 GiB |
| 16,384 | 25.83 GiB (pilot, all items) | 63.54 GiB |
| 24,576 | 27.83 GiB | 68.40 GiB |
| 32,768 | 32.35 GiB, over | 73.10 GiB |
| 65,536 | not run | 90.80 GiB |

- The driver's peak is the same at every depth; only the process RSS (0.7 to 1.0 GiB)
  varies, so a middle-depth row stands for all three depths.
- flash's driver alone peaked at 31.38 GiB at 32,768 tokens; the RSS puts it over.
- full at 16,384 left only 0.46 GiB of its old 64 GiB budget; at 65,536 it leaves 5.20 GiB
  of 96 GiB.
- Latency per inference: flash 5.7 s at 2,048 and 103 s at 32,768; full 18 s at 2,048,
  153 s at 16,384, 234 s at 24,576, 325 s at 32,768, and 740 s at 65,536.
- MPS's recommended working set on this host is 107.5 GiB, so the host was never at risk;
  only the budgets failed. The one-item quality cells in these runs, and their "cap"
  verdicts, are noise.

## Relevance

Each model now carries its own memory-checked fallback, the longest probe length that
leaves 4 GiB of its budget free for the OS: 24,576 for flash and, with full's budget raised
to 96 GiB, 65,536 for full. full's long requests outlast the old 300 s client timeout; see
[[2026-10-10-per-model-request-caps]].

## References

- `results/context/memory-check-flash/`, `memory-check-full/`, `memory-check-full-16k/`,
  `memory-check-full-32k/`, and `memory-check-full-64k/`, local runs (`results/` is not
  tracked)
- `specs/003-context-window-audit/research.md`: R11 (peak memory) and R12 (cap rule)
