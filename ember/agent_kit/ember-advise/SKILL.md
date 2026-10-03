---
name: ember-advise
description: Playbook for the ember_advise MCP tool, a local advisor that returns calibrated probabilities. Use when classifying user intent, triaging errors or failing tests, routing work, checking yes/no gates (needs review, safe to retry, specific enough to act), scoring risk, severity, or effort, or weighing approaches; and when designing questions for ember or interpreting its probabilities.
---

# ember-advise

ember is a little buddy for judgment calls. Its `advise` tool (opencode:
`ember_advise`; Claude Code: `mcp__ember__advise`) runs Cloudflare's Clef-Flash
model locally: you describe a situation in `state`, ask typed questions, and it radiates a
feeling about every option as a calibrated probability. It never writes prose and never
decides for you — it advises, you decide.

| Property | Value |
| --- | --- |
| Latency | ~1 s per call when warm (1–3 questions cost the same); ~5–15 s for the first call while the model loads |
| Determinism | The same request always gets the same feeling |
| Privacy | Runs on this machine; `state` never leaves it |
| Sees | Only `state` and your questions — no files, history, or web |
| Returns | Calibrated probabilities over the options you define |

## When to consult it

Reach for `ember_advise` at **decision points** where you would otherwise guess or
apply an unexamined heuristic:

| Decision point | Question type | Example id |
| --- | --- | --- |
| What is the user asking for? | `choice` | `intent` |
| Is the request specific enough to act on? | `noul` | `specific_enough` |
| Why did this test or command fail? | `choice` | `failure_kind` |
| Will a retry fix it? | `noul` | `retry` |
| Which component or team owns this? | `choice` | `owner` |
| How risky is this change? | `score` | `risk` |
| Does it need human review? | `noul` | `needs_review` |
| How much effort is this task? | `score` | `effort` |
| Which approach fits the constraints? | `choice` | `approach` |

## When not to

- Writing code or prose, explaining, or summarizing — it returns probabilities, not text.
- Multi-step reasoning, arithmetic, or anything that needs facts absent from `state`.
- Questions a deterministic check answers better: run the test, grep the code, read the type.
- As the sole authority for an irreversible or high-stakes action — weigh it alongside your own
  judgment and the user's.

## Calling it

```json
{
  "input": {
    "state": "<string or JSON with ALL the evidence>",
    "questions": {
      "<id>": {"type": "noul", "instructions": "<a proposition, phrased positively>"},
      "<id>": {"type": "choice", "instructions": "<what to weigh>",
               "criteria": {"<option_id>": "<description>"}},
      "<id>": {"type": "score", "instructions": "<what to rate>",
               "criteria": ["<lowest>", "<...>", "<highest>"]}
    }
  }
}
```

Each answer is keyed by question id:

| Type | Answer fields |
| --- | --- |
| `noul` | `noul` = P(true) |
| `choice` | `choice` (the leading option), `confidence`, `probabilities` |
| `score` | `score` (expected index; 0 is the first criterion), `confidence` (top option), `legend`, `probabilities` |

The response also carries `usage.input_tokens` and `latency_ms`.

## Asking well

1. **Put all evidence in `state` — and only evidence.** ember sees nothing else. Prefer
   structured JSON with labeled fields (`{"test": ..., "output": ..., "diff_summary": ...}`)
   and trim logs to the relevant lines; inputs are capped at 16,384 tokens. Don't write your
   own verdict into `state` ("this is an infrastructure issue"): it gets echoed back and you
   lose the independent read you asked for.
2. **Ask exactly what you need.** Confidence is about the question asked, not about overall
   ambiguity. In testing, "update the thing" scored `intent=implement` at **0.96** but
   `specific_enough` at only **0.09**; a precise request scored **0.91**. If you need to know
   whether you can act, ask that.
3. **Make options mutually exclusive and exhaustive**, each with a crisp description. When the
   space is open, add an `unclear` or `other` option so the answer is not forced into a wrong
   bucket.
4. **Batch related questions.** One call with three questions costs the same as one with one.
5. **Fix the question set per decision type.** Questions are weighed jointly: changing a sibling
   question moved one intent confidence from 0.65 to 0.57. Use the same set every time you
   check the same kind of decision.
6. **Keep option ids short and stable** (`logic_bug`, `needs_review`) and put the meaning in
   the descriptions.
7. **Phrase `noul` questions as positive propositions** ("Is re-running likely to make it
   pass?"), and add `criteria: {"true": ..., "false": ...}` when the boundary needs defining.

## Reading the feeling

Starting thresholds, calibrated from observed outputs — tune them per decision:

| Type | Trust it | Act, but flag and verify | Gather evidence or ask the user |
| --- | --- | --- | --- |
| `choice` | confidence ≥ 0.85 with a clear margin over the runner-up | 0.60–0.85 | below 0.60, or a top-two margin under 0.20 |
| `noul` | P ≥ 0.80 (yes) or P ≤ 0.20 (no) | — | 0.20 < P < 0.80 |
| `score` | read the expected `score`, e.g. ≥ 2.0 of 3 means escalate | — | `probabilities` split between distant levels |

- **Don't threshold `score` on `confidence`.** The top option sat near 0.63 for both a trivial
  and a dangerous change, while their expected scores (0.75 vs 2.43 of 3) separated cleanly.
- **Don't re-ask.** Identical requests get identical answers. Change the evidence or the
  question instead.
- **It advises; you decide.** When you have strong contrary evidence, override it and say why.
- **Name the signal.** Quote what you relied on, e.g. `ember: failure_kind=environment (0.84)`.

## Recipes

Observed outputs come from Cloudflare's Clef-Flash (revision `17f0b0a`) on an Apple M4 Max.

### Intent and readiness check

Run it before changing files in response to a conversational request.

```json
{"state": "<the user's latest message>",
 "questions": {
   "intent": {"type": "choice", "instructions": "What is the user asking the coding agent to do?",
     "criteria": {"question": "Explain or answer something; no code changes requested",
                  "implement": "Make a change: add, modify, or configure something",
                  "investigate": "Look into a problem and report findings",
                  "fix": "Repair a specific broken behavior"}},
   "specific_enough": {"type": "noul",
     "instructions": "Is the request specific enough to act on without asking a clarifying question?",
     "criteria": {"true": "The target and desired outcome are both identifiable",
                  "false": "The target or desired outcome is unclear"}}}}
```

| Message | Observed | Action |
| --- | --- | --- |
| "update the thing" | `implement` 0.96, `specific_enough` 0.09 | ask what to update |
| "bump the torch upper bound in pyproject.toml to <2.16 and re-run make test" | `implement` 0.92, `specific_enough` 0.91 | act |

With the `intent` question alone, "how does the llm know how to call the tool?" scored
`question` 0.89 and "the tests are failing on main since yesterday, can you look?" scored
`investigate` 0.94.

### Failure triage

Run it before retrying or "fixing" a failing test or command.

```json
{"state": {"test": "<node id or command>", "output": "<the relevant error lines>"},
 "questions": {
   "failure_kind": {"type": "choice", "instructions": "What most likely caused this failure?",
     "criteria": {"logic_bug": "The code under test returns a wrong result",
                  "environment": "Missing service, dependency, port, file, or configuration",
                  "flaky": "Timing, ordering, or nondeterminism; may pass on retry",
                  "test_bug": "The test itself is wrong or outdated"}},
   "retry": {"type": "noul", "instructions": "Is simply re-running likely to make it pass?"}}}
```

| Output | Observed | Action |
| --- | --- | --- |
| `httpx.ConnectError: [Errno 61] Connection refused` | `environment` 0.84, `retry` 0.15 | start the missing service |
| `assert add(2, 2) == 4 … where 5 = add(2, 2)` | `logic_bug` 0.93, `retry` 0.05 | fix the code |
| `TimeoutError after 5.0s; passed on 3 of last 5 CI runs` | `flaky` 0.89, `retry` 0.67 | retry, then stabilize the test |

### Change-risk check

Run it before committing, pushing, or merging.

```json
{"state": {"diff_summary": "<what changed and why>", "files": ["<path>"], "lines_changed": 0},
 "questions": {
   "risk": {"type": "score", "instructions": "How risky is shipping this change without human review?",
            "criteria": ["Negligible", "Low", "Medium", "High"]},
   "needs_review": {"type": "noul", "instructions": "Should a human review this change before it is merged?"}}}
```

| Change | Observed | Action |
| --- | --- | --- |
| Rename a local variable in a test (4 lines) | `risk` 0.75 of 3, `needs_review` 0.09 | proceed |
| Skip auth token validation for localhost (180 lines) | `risk` 2.43 of 3, `needs_review` 0.93 | stop and ask for review |

### Routing and ownership

```json
{"state": {"error": "<message>", "path": "<file or module>"},
 "questions": {
   "owner": {"type": "choice", "instructions": "Which part of the system should handle this?",
     "criteria": {"api": "HTTP handlers and request validation",
                  "storage": "Database, migrations, and persistence",
                  "ui": "Frontend rendering and client state",
                  "infra": "Build, CI, deployment, and configuration",
                  "unclear": "Not enough information to tell"}}}}
```

### Effort and approach

```json
{"state": {"task": "<the task>", "constraints": ["<constraint>"]},
 "questions": {
   "effort": {"type": "score", "instructions": "How much work is this task?",
              "criteria": ["Trivial (minutes)", "Small (under an hour)",
                           "Medium (a few hours)", "Large (a day or more)"]},
   "approach": {"type": "choice", "instructions": "Which approach best fits the constraints?",
     "criteria": {"minimal_patch": "Smallest change that fixes the symptom",
                  "refactor": "Restructure the code so the fix is natural",
                  "new_component": "Add a new module or service",
                  "ask_user": "The trade-off needs a human decision"}}}}
```

The routing and effort recipes are templates: replace their option sets with ones that describe
your project, measure them, and keep each set fixed once your checks depend on it.

## Operations

- **The first call is slow.** The model server starts on demand and loads in ~5–15 s; later
  calls take ~1 s. Pre-warm it with `ember start`.
- **"model … is not pulled"** means the weights are missing: run `ember model pull`.
- **"not reachable … EMBER_AUTOSTART=0"** means the server is off; run
  `ember start`. For anything else, run `ember doctor` and `ember logs`.
- **`ember status`** prints the engine (device, dtype, model) when the server is up.
