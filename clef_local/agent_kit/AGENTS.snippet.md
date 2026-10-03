## Decision support: Clef

This project can call a local decision model through the `clef_decide` MCP tool (Claude
Code: `mcp__clef__decide`). Use it for bounded, typed decisions instead of guessing: user
intent, error and test-failure triage, routing, yes/no gates, and risk, severity, or effort
scores. Put all evidence in `state`. Act on confidence >= 0.85, flag and verify between 0.60
and 0.85, and ask the user below 0.60. Load the `clef-decide` skill or read the MCP resource
`clef://guide` for schemas and recipes.

Decision policy for this project (edit to fit):

- Before modifying files for a conversational request, run the intent and readiness gate;
  ask a clarifying question when `specific_enough` is at or below 0.20.
- Before retrying or fixing a failing test, run failure triage and follow `failure_kind`.
- Before committing or pushing, run the change-risk gate; stop and request review when
  `needs_review` is at least 0.80 or `risk` is at least 2.0 of 3.
- Quote the deciding signal in your reply, e.g. `clef: needs_review P=0.93`.
