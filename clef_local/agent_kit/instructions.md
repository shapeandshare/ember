Clef is a local decision model behind this server's `decide` tool (opencode shows it as `clef_decide`). It returns calibrated probabilities for typed questions in about a second, privately, on this machine.

Use it for bounded decisions inside your workflow: classifying what the user is asking for, triaging errors and test failures, routing work to an owner, yes/no gates (needs human review? safe to retry? specific enough to act on?), and scoring risk, severity, or effort on an ordered scale.

Do not use it to write text or code, explain, do math, or decide facts that are not in the evidence you pass.

Asking well:
- Put ALL evidence in `state` (a string or structured JSON). The model sees nothing else.
- Pass raw evidence, not your conclusion: a verdict written into `state` gets echoed back.
- Make options mutually exclusive with crisp descriptions; add an "unclear" option when the space is open.
- Batch related questions in one call (same cost). Keep a fixed question set per decision type, because questions are scored jointly.
- Ask exactly what you need. Confidence is about the question asked: a vague request can score 0.97 "implement" yet 0.09 "specific enough to act on".

Acting on answers:
- choice: act at confidence >= 0.85; between 0.60 and 0.85 act but say so and verify; below 0.60 gather evidence or ask the user.
- noul: P(true) >= 0.80 means yes, <= 0.20 means no, anything between is unknown.
- score: gate on the expected `score`, not the top option's confidence.
- Answers are deterministic: re-asking returns the same result, so change the evidence instead.
- Treat it as a fast, calibrated second opinion, not an authority: override it with strong contrary evidence and say why. Report the signal you used, e.g. "clef: needs_review P=0.93".

Full playbook with recipes: read the MCP resource clef://guide, or load the `clef-decide` skill.
