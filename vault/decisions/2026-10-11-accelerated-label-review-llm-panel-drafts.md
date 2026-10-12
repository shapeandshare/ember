---
code-refs:
  - specs/006-benchmark-hygiene/
  - evals/dataset/
created: 2026-10-11
tags:
  - type/decision
  - domain/tooling
  - status/draft
title: "Accelerated label review: LLM panel drafts, the maintainer adjudicates"
type: decision
updated: 2026-10-11
---
# Accelerated label review: LLM panel drafts, the maintainer adjudicates

Part of [[ember]]. Maintainer direction (2026-10-11): get the benchmark programme's remaining phases and new recipe families out for use and feedback as fast as possible. The blocking steps are labeling-shaped (the stability re-label, T012; the 475-item kind tagging, T028). This note fixes the accelerated method and its disclosure so the speed trade is explicit and the paper trail stays real.

## The method

- **Panel-drafted labels.** Two or more independent LLM judges receive the blinded material (state, question, criteria, rubric anchors — **never the gold**) and each produces an independent label set. For stability rounds this re-labels the `risk`/`effort` items; for kinds it drafts one `ItemKind` per item.
- **The maintainer adjudicates, alone.** Disagreements (panel-vs-gold, or judge-vs-judge) go to a review queue; the maintainer resolves them. Gold remains human-owned and human-final — no label changes without the maintainer, and the model under test never labels its own benchmark.
- **The disclosure is exact.** Reports and the card state the method plainly: gold is single-rater human; the re-label pass was panel-assisted and human-adjudicated; per-judge and inter-judge agreement are published beside the human figures. No "human ceiling" claim is made for machine labels.
- **Records mirror the stability rounds.** Judge identity and date are recorded with the round; a judge model that changes version later does not retroactively change a published round.

## Why this is compatible with the parent programme

Spec 004 already carries the pattern for items: a `drafted` source is "drafted by a model and adjudicated by the maintainer". This note extends the same pattern from items to review passes and annotations, with one added guard: the disclosure wording changes from "one person's blinded re-label" to the panel-assisted method, so no reader is misled. The rule "the model never labels" is preserved in its load-bearing sense — the benchmarked system never grounds its own exam, and gold is adjudicated by a human.

## Fast-feedback consequences

- Phase 1's gate (T012/T057) can close this week; Phase 2 (mined vault recipes) is specced and built immediately after — the family the team can dogfood first.
- Kind tagging (T028/T029) becomes an LLM draft + a maintainer confirmation pass, not 475 cold judgments.
- The probe snapshot (T040) stays on the original schedule (hours of machine time, no labeling involved).

## References

- `specs/006-benchmark-hygiene/` — tasks T012, T028/T029, T057
- `specs/004-benchmark-categories/spec.md` — the `drafted` source kind and the label-reliability clarification
- [[2026-10-11-hygiene-stability-records-and-probe-key]] — the round-record design this extends
