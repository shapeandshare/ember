## Gut feeling: a local advisor

This project has an advisor, ember, available as the `ember_advise` MCP
tool (Claude Code: `mcp__ember__advise`). Consult it at bounded decision points
instead of guessing: user intent, error and test-failure triage, routing, yes/no gates, and
risk, severity, or effort scores. It advises; you decide. Put all evidence in `state`;
attach images as base64 data URIs in `images`.
Trust confidence >= 0.85, flag and verify between 0.60 and 0.85, and ask the user below
0.60. Load the `ember-advise` skill or read the MCP resource `ember://guide`
for schemas and recipes.

Project policy for consulting ember (edit to fit):

- Before modifying files for a conversational request, run the intent and readiness
  check; ask a clarifying question when `specific_enough` is at or below 0.20.
- Before retrying or fixing a failing test, run failure triage and follow `failure_kind`.
- Before committing or pushing, run the change-risk check; stop and request review when
  `needs_review` is at least 0.80 or `risk` is at least 2.0 of 3.
- Quote the signal you relied on, e.g. `ember: needs_review P=0.93`.
- When evidence is visual (screenshot, chart, diagram), attach pixels as base64 `images`
  and use the `dominant_colour`, `alert_level`, and `colour_changed` question ids from the
  visual evidence recipe.
