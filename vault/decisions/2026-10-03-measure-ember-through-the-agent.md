---
code-refs:
  - evals/agent/scenarios.py
  - evals/agent/opencode.py
  - evals/agent/judge.py
  - scripts/run_agent_evals.py
created: 2026-10-03
tags:
  - type/decision
  - domain/tooling
  - domain/agent-kit
  - domain/opencode
  - status/draft
title: measure ember through the agent
type: decision
updated: 2026-10-03
---

# measure ember through the agent

Part of [[ember]]. The headline measure of ember is an agent-in-the-loop eval: opencode
works through scripted scenarios with and without ember, and it is judged by what it
did. The model benchmark stays as the calibration measure underneath it.

## Context

The model benchmark ([[2026-10-03-eval-benchmark-harness]]) calls the HTTP endpoint
directly. It cannot see whether an agent consults ember, asks the kit's questions, or
acts on the answer, which was the user's first complaint ("the MCP does not seem to get
called"). The maintainer chose opencode only, two driver models (DeepSeek V4.1 Flash and
Claude Sonnet 5), a with/without comparison plus onboarding variants, and an opt-in runner
under a clarified Article IV (constitution 1.3.1).

## Decision

- 48 scenarios in `evals/agent/scenarios.py` (sandbox repo in `evals/agent/template.py`):
  readiness (8 vague, 4 precise), failure triage (logic, outdated test, missing service,
  config, env var, tool, flaky), change risk (6 trivial, 6 risky commits), routing,
  effort, and 4 controls. Doubled from 24 on 2026-10-03. Gold behaviour is judged from
  files, commits, tests, and the reply, never from whether ember was called, and a test
  asserts that doing nothing fails every scenario.
- Four conditions add the kit's channels one at a time: `none`, `mcp` (server plus
  `initialize.instructions`), `skill`, and `full` (AGENTS.md policy). They are committed
  into each sandbox's first commit, so diffs show only the agent's work.
- Isolation, verified against the opencode source: `opencode run --pure --format json`,
  HOME and XDG redirected into the sandbox, no `--port` (in-process server), the
  provider key passed only via the child env, and timeouts kill only the session's own
  process group.
- Metrics per model and condition: gold-action accuracy with the paired change against
  `none`, consult rate at decision points, unneeded consults on controls, consult before
  acting, recipe-question fidelity, evidence in `state`, and following ember's answer
  under the kit's rules.

## Consequences

- The smoke run showed that agents often write their own question sets instead of the
  kit's recipes, which ember has not been calibrated on. The fidelity metric tracks this.
- The `asks` check originally required a "?"; a clarification written as "Let me know
  the file..." was scored a miss. It now also matches explicit requests for details. This
  was a checker bug, not a gold change, and it was fixed before the full run.
- A full run costs provider credit (Sonnet at about $0.03 to $0.05 per session) and
  never runs in `make check`, `make test`, or CI.
