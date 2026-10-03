# Responsible Use

> **Warning:** ember returns calibrated probabilities, not facts. It is a decision aid.
> A high confidence is not evidence that an answer is correct. Human review stays with
> you.

## What ember is

ember runs Cloudflare's Clef decision model locally and answers typed questions about a
situation you describe. It returns one calibrated probability per option and generates no
text. It advises; the agent or person decides.

Intended uses:

- Bounded classification and triage where the options are yours to define
- Yes or no gates such as "needs review", "safe to retry", or "specific enough to act"
- Risk, severity, or effort on an ordered scale
- Research into local decision models and calibration

Not intended for:

- Writing text or code, explaining, doing math, or judging facts not in the evidence
- High-stakes decisions in medicine, law, finance, security, or safety without a qualified
  human in the loop
- Any setting where an unaudited model's output is the sole basis for an action

## Reading the result

- Treat confidence at or above 0.85 as usable, between 0.60 and 0.85 as act-and-verify, and
  below 0.60 as a signal to gather evidence or ask.
- For `noul` (yes or no), read P(true): at or above 0.80 is yes, at or below 0.20 is no,
  and anything between is unsure.
- For `score`, read the expected score, not the top option's confidence.
- The same request always returns the same feeling. Change the evidence instead of
  re-asking.
- Strong contrary evidence overrides the model. Say which signal you used, for example
  `ember: needs_review P=0.93`.

## Limits

- The model sees only what you pass in `state`, `images`, and `videos`. A conclusion you
  write into `state` is echoed back, so pass raw evidence.
- The model can be miscalibrated, including on inputs unlike the ones used to build it. The
  thresholds above come from observed output and are re-measured when the pinned model
  revision changes.
- ember is not audited by shapeandshare. Weight-level behavior is upstream Cloudflare work,
  licensed Apache-2.0. Report weight issues upstream.

## Privacy

Inference runs on your machine. The decision path (`ember-mcp` to the local HTTP server)
does not send `state`, questions, or answers over the network. The only network access is
the explicit weight download. The state you pass is processed on this machine and the
server keeps local logs, so avoid passing secrets you would not keep locally.

Model server logs live at `~/Library/Application Support/ember/logs/server.log`.

See also: [`SECURITY.md`](SECURITY.md) for the threat model and
[`COMPATIBILITY.md`](COMPATIBILITY.md) for tested versions.
