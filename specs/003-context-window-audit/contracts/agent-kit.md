# Contract: Agent guidance on length limits

**Feature**: `003-context-window-audit`
**Date**: 2026-10-09
**Scope**: What `ember/agent_kit/` tells agents about limits and refusals (FR-008, SC-005).
Under Article III this is public API.

| Surface | Must say | Budget |
|---------|----------|--------|
| `instructions.md` (MCP `initialize.instructions`) | Requests over the default cap ({flash cap} tokens for flash) are refused, never truncated. The error's split shows whether to cut state, media, or questions | Whole file ≤ 2,048 bytes. 93 bytes are free today, so trim existing wording if needed |
| `ember-advise/SKILL.md` (`ember://guide`, installed skill) | The per-model defaults (flash, full, and models outside the registry), why each value holds (measured by the probe, citing its run ID, or the 32,768 fallback until measured), the enforced-limit rule, what counts toward a request (state, media, questions and schema, prompt wrapper), the refusal shape, and what to do on refusal. Replaces "inputs are capped at the model's 262,144-token window" (L85) | Frontmatter unchanged; `description` ≤ 1,024 characters |
| `packages/claude-plugin/skills/ember-advise/SKILL.md` | A byte-identical copy of the above | Enforced by `tests/test_distribution.py` |
| `AGENTS.snippet.md` | One line: oversized requests are refused with a token split; trim the largest part and retry | — |

## Numbers

Every cap that appears in kit text must equal what the resolver
(`ember/serving/limits.py`) returns for that model: the measured value once US3 lands,
and 32,768 until then. `tests/test_agent_kit.py` asserts this, so a re-measured cap can't
ship with stale text (Article III §3.3).

The refusal-message fragments that the skill quotes (`request too large:`,
`Split: state`) must appear in the output of `refusal_message(...)`. The same test checks
this, so the kit never carries a copy of the message that has drifted from the original
(Article III §3.1).
