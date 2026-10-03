---
title: freeze benchmark labels before runs
type: decision
tags:
  - type/decision
  - domain/tooling
  - domain/agent-kit
  - status/draft
created: 2026-10-03
updated: 2026-10-03
code-refs:
  - evals/clef-flash.jsonl
  - evals/metrics.py
  - tests/test_eval_benchmark.py
---

# freeze benchmark labels before runs

Part of [[ember]]. Gold labels in the ember benchmark are judged from the evidence
alone and fixed before any model run; disagreements go to a person, never back into
the labels.

## Context

The first 29-item draft reached "100%" only after three failing items were relabelled
or loosened to match the model's answers, and its per-item floors and ceilings were set
from observed outputs. A benchmark built that way measures agreement with itself, not
the model. See [[2026-10-03-eval-benchmark-harness]].

## Decision

- Each question's gold label comes from `state` plus the recipe's option descriptions
  only, with a one-line `rationale` per item. Rules: `needs_review` is true exactly
  when `risk` is Medium or High; `retry` is true only for `flaky` failures.
- Labels are frozen before a run. After a run, misses are listed for human review. A
  label changes only when a reviewer finds it wrong on the merits, never because the
  model disagreed.
- An item whose evidence fits two options is rewritten or dropped at authoring time.
- No thresholds derived from model output live in the dataset; regression bounds stay
  in `tests/test_advise_evals.py`.
- `make check` enforces structure (`tests/test_eval_benchmark.py`): valid gold
  labels, one fixed question set per recipe, and every label present in both splits.

## Consequences

Scores fall below 100% and mean something: the v1 run scored 84.0% question accuracy
[79.2, 89.1]. Every relabel is a dataset change, so the SHA-256 changes, and
`ember eval report --compare` warns when two runs scored different item sets.
