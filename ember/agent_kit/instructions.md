ember is your little buddy for judgment calls: a decision model (Clef-Flash, local by default) behind this server's `advise` tool (opencode/Kilo Code: `ember_advise`). It reads a situation and radiates a feeling about each option you define, as calibrated probabilities, in about a second, on this machine by default. It advises; you decide.

Consult it at bounded decision points: what the user is asking for, why something failed, who owns a problem, yes/no gates (needs human review? safe to retry? specific enough to act on?), and risk, severity, or effort on an ordered scale.

Don't ask it to write text or code, explain, do math, or judge facts that are not in the evidence you pass.

Asking well:
- Put ALL evidence in `state` (a string or structured JSON); attach images or video frames as base64 data URIs in `images`/`videos`. It sees only what you pass.
- Pass raw evidence, not your conclusion: a verdict written into `state` gets echoed back.
- Make options mutually exclusive with crisp descriptions; add an "unclear" option when the space is open.
- Batch related questions in one call (same cost). Keep a fixed question set per decision type: questions are weighed jointly.
- Ask exactly what you need. Confidence is about the question asked: a vague request scored 0.96 "implement" yet 0.09 "specific enough to act on".

Reading the feeling:
- choice: trust it at confidence >= 0.85; between 0.60 and 0.85 act but say so and verify; below 0.60 gather evidence or ask the user.
- noul: P(true) >= 0.80 means yes, <= 0.20 means no, anything between is unsure.
- score: read the expected `score`, not the top option's confidence.
- The same request always gets the same feeling; change the evidence instead of re-asking.
- Strong contrary evidence wins: override it and say why. Name the signal you used, e.g. "ember: needs_review P=0.93".

Full playbook with recipes: read the MCP resource ember://guide, or load the `ember-advise` skill.
