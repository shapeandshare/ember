---
title: "232 text items cannot resolve the probe's 2-point accuracy tolerance"
type: discovery
tags:
  - type/discovery
  - domain/tooling
  - domain/models
  - status/draft
created: "2026-10-10"
updated: "2026-10-10"
code-refs:
  - evals/context/run_context.py
  - evals/context/scoring.py
  - evals/clef-flash.jsonl
---

# 232 text items cannot resolve the probe's 2-point accuracy tolerance

Part of [[ember]]. The long-context probe's sizing pilot showed that the benchmark's 232
text-only items cannot resolve the pre-declared 2-point accuracy tolerance at 16K tokens,
so a canonical run could neither pass nor fail a length on accuracy.

## What was tested

`ember eval context --pilot` (run `context_20261010T015823Z`, not canonical because the
tree was dirty): flash at 2,048 and 16,384 tokens, middle depth, on every text-only item;
464 rows, all `ok`. The gate projects the 95% half-width of the per-item accuracy delta as
`1.96 · sd / √n` and stops the run above 0.02 (`_pilot_width` in
`evals/context/run_context.py`, `projected_half_width` in `evals/context/scoring.py`).

## Finding

- Projected half-width 0.0264 over 232 items, so `sizing_passed` is false and the run
  exits 2.
- Accuracy 0.7802 at 2K and 0.7694 at 16K: mean delta −0.0108, sd 0.2052. Only 24 of the
  232 items changed accuracy. Resolving 0.02 at this sd needs at least 405 items.
- Brier 0.2297 at 2K and 0.2360 at 16K (delta +0.0063), with an item-level half-width of
  0.0133: Brier alone would resolve. Question-level accuracy is wider (336 questions,
  half-width 0.0303).
- Median latency 5.7 s at 2K and 47.7 s at 16K; peak memory 19.78 and 25.83 GiB. At about
  2.9 ms per token, a canonical flash run on 232 items takes 3.5 to 4 days.

## Relevance

Accuracy can't be checked against the tolerance without more items, and loosening the
tolerance after seeing pilot data would undo its pre-declaration. The maintainer chose to
grow the benchmark (to 443 text items) and keep the defaults unmeasured meanwhile; see
[[2026-10-10-per-model-request-caps]]. Re-run the pilot once the new labels are reviewed.

## References

- `specs/003-context-window-audit/research.md`: R10 (sizing gate) and R12 (cap rule)
- `specs/003-context-window-audit/tasks.md`: T059
- [[2026-10-03-freeze-benchmark-labels-before-runs]]
