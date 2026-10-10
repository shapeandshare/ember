# Feature Specification: Context Window Audit — Explicit, Measured Length Limits

**Feature Branch**: `003-context-window-audit`

**Created**: 2026-10-09

**Status**: Draft

**Input**: User description: "docs/ember — Handoff Context Window Audit & Integration Eval Harness.md" — Workstream A (context window audit). This is the first phase of the handoff's five-phase plan; the integration eval harness (Workstream B) is out of scope for this specification.

## Clarifications

### Session 2026-10-09

- Q: When a request's full encoded content would exceed the limit the model can fully see,
  what should ember's default over-limit behavior be — refuse with an actionable error,
  truncate explicitly with a machine-readable signal, or either? → A: Refuse with an
  actionable error (HTTP 413-class) carrying exact counts; ember never truncates a request
  and never answers from partial content.
- Q: In the long-context probe, should the decision's key evidence be tested at several
  depths at each context length, or at one fixed spot? → A: Three depths per length — near
  the start, middle, and end of the state — at each of 2K–64K; results are reported per
  depth, and the cap is judged on the worst depth.
- Q: What rule should pick the default request cap from the probe results? → A: The
  longest tested length where, at the worst evidence depth, accuracy is at most 2
  percentage points below and Brier score at most 0.02 above that model's own 2K result,
  with the probe sized so this tolerance is measurable; the probe also records peak memory
  and latency per length, and any length whose peak memory exceeds the model's documented
  minimum (32 GB for flash, 64 GB for full) is ruled out.
- Q: Should the measured cap be one default shared by every model, or a separate default
  for each registered model? → A: Per-model: each registered model (flash, full) gets its
  own measured cap as its default, as the effective maximum already derives from the
  loaded model; a model outside the registry (custom directory or S3 location) falls back
  to the lower of the two; an explicit setting overrides either.
- Q: What should the over-limit refusal tell the caller, so that an agent knows what to
  cut before retrying? → A: One message stating the total counted tokens, the limit and
  the setting that governs it, and how the total splits between the state, any media, and
  the fixed overhead (questions, schema, prompt wrapper); the response shape stays as
  today.
- Q: When `ember doctor` runs while no model server is reachable, or while the configured
  endpoint is remote, where should the limits it reports come from? → A: Live values from
  a reachable server (local or remote); with no local server running, the limits the
  local settings and model files would produce, labeled as configured; an unreachable
  remote, or one too old to advertise limits, is reported as unknown.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the real limits of the loaded model (Priority: P1)

An operator (or the maintainer) can see, without reading code, exactly how many tokens
the loaded model will actually process and what per-request cap ember enforces: when the
model loads, in the `ember doctor` surface, and in the server's health response. Both
numbers reflect the loaded model itself, and a device-backed check proves they match what
the model really encodes.

**Why this priority**: Every other guarantee in this feature is meaningless if the
announced limit is wrong or invisible. Today no status surface reports the per-request
cap, the effective maximum is derived from the model's configuration file with a silent
fallback, and nothing on the device verifies that the announced number corresponds to the
model's real encoding path.

**Independent Test**: Start the server with a model loaded, read `ember doctor` and the
health response, and confirm both limits appear; run the device-backed encoding check and
confirm the announced effective limit corresponds to the model's real encoded length.

**Acceptance Scenarios**:

1. **Given** a reachable model server (local or remote) with a model loaded, **When**
   `ember doctor` is read, **Then** it reports the effective maximum token count and the
   per-request cap that server advertises for its model.
2. **Given** the same running server, **When** its health response is read, **Then** both
   limits are reported as part of the loaded model's state.
3. **Given** a model is loading, **When** it finishes loading, **Then** the load log
   states both limits.
4. **Given** the model's own configuration cannot be read, **When** limits are reported,
   **Then** the documented fallback value is shown and is identifiable as a fallback,
   never presented as model-derived.
5. **Given** weights are present, **When** the model-backed encoding check runs, **Then**
   a known-length input is encoded through the same path the server uses and the
   resulting token count is asserted, so the announced limit cannot drift from the
   model's real behavior.
6. **Given** no local model server is running, **When** `ember doctor` is read, **Then**
   it reports the limits the local settings and model files would produce, labeled as
   configured rather than live.
7. **Given** a remote endpoint that is unreachable or too old to advertise limits, **When**
   `ember doctor` is read, **Then** the limits are reported as unknown, never as the local
   settings' values.

---

### User Story 2 - Never answer on silently shortened evidence (Priority: P1)

An agent that sends a state larger than the model can take is refused with an actionable
error that says exactly how large the request was and what the limit is. The model never
reads a shortened state, and the agent is never answered from partial content.

**Why this priority**: This is the safety core of the feature. Upstream model code
silently keeps the start of a state and drops the tail past its limit; ember currently
overrides that limit upward and pre-checks size with a count that does not match what the
model sees. Both paths can produce a confident answer derived from partial evidence — the
worst failure mode for a decision tool whose answers feed an agent's actions.

**Independent Test**: Send requests whose full encoded content exceeds the enforced limit
— including dictionary, string, and image states — under the default configuration, with
the request cap disabled, and with a reduced effective maximum. Confirm every over-limit
request is refused with the actionable error and that reported counts match the model's
own encoding within tolerance.

**Acceptance Scenarios**:

1. **Given** a request whose full encoded content exceeds the enforced limit, **When** it
   is sent to the server, **Then** it is refused with an actionable error (FR-005) stating
   the exact counted size and the limit — never passed to inference on a shortened state.
2. **Given** a request whose full encoded content is within the limit, **When** it is
   sent, **Then** it is processed normally with no refusal.
3. **Given** a configuration where the request cap is disabled and the request would
   exceed the model's effective maximum, **When** it is sent, **Then** the
   no-silent-shortening guarantee still holds.
4. **Given** a configuration with a reduced effective maximum, **When** an over-limit
   request is sent, **Then** the guarantee still holds.
5. **Given** dictionary, string, and image states sized near the boundary, **When** each
   is counted, **Then** the reported count matches the model's actual encoded length
   within ±1%.
6. **Given** an over-limit refusal, **When** the agent reads it, **Then** it names the
   exact counted size, how that size splits between the state, media, and fixed overhead,
   the limit, and the setting that governs it, so the agent can trim the right part and
   retry.

---

### User Story 3 - Limits chosen from measured quality, not from a default (Priority: P2)

The maintainer runs one repeatable probe that asks the same decision at increasing context
lengths — 2K, 4K, 8K, 16K, 24K, 32K, and 64K tokens — with its key evidence placed near
the start, middle, and end of the state at each length, on both registered models, on the
device, and records accuracy and calibration against length and depth, and peak memory
and latency against length. Each registered model's default request cap is then chosen
from its measured curve by a rule fixed in advance (FR-010), judged on the worst depth,
and recorded as a decision that supersedes the current unmeasured mitigation (D-002),
citing the probe run.

**Why this priority**: The 32,768-token cap from D-002 was a safety mitigation, not a
measured choice, and the model ships with an untested 16,384-token reference default;
Cloudflare's published results are at that default. Without the curve, any cap is a guess.
It ranks below US1/US2 because the guarantees must exist before the number is tuned, but
it is what makes the number trustworthy.

**Independent Test**: Run the probe with both models cached; confirm per-model accuracy
and calibration are recorded per context length and evidence depth, and peak memory and
latency per length, with a run ID; change each model's default cap citing that run;
confirm the decision record supersedes D-002.

**Acceptance Scenarios**:

1. **Given** both registered models are cached locally, **When** the long-context probe
   runs, **Then** for each model it reports results at 2K, 4K, 8K, 16K, 24K, 32K, and 64K
   tokens, each with the key evidence near the start, middle, and end of the state, with
   accuracy and calibration per length and depth and peak memory and latency per length,
   under a recorded run ID.
2. **Given** the recorded curves, **When** the default caps are set, **Then** each
   registered model's default equals its own longest length that passes the FR-010 rule,
   the change cites the run ID, and a recorded decision supersedes D-002.
3. **Given** a recorded probe run's pinned inputs, **When** the probe is re-run, **Then**
   it reproduces the recorded results.

---

### User Story 4 - Limits stated wherever model behavior is described (Priority: P3)

A user or agent reading the documentation — README configuration, COMPATIBILITY, the
`ember://guide` resource, or the `ember-advise` skill — can find, in each place limits are
described, the effective limit, why it has that value, and exactly what happens to
requests beyond it. Agents are told what to do when their request is too large.

**Why this priority**: Documentation is how the contract reaches users and agents; it is
what turns an enforced behavior into a usable one. It follows the behavior changes
because it must describe them accurately.

**Independent Test**: Read each of the four documentation surfaces and confirm each states
the limit, its reason, and the past-limit behavior; confirm the agent guidance tells
agents how to react when a request is refused.

**Acceptance Scenarios**:

1. **Given** the four documentation surfaces (README configuration, COMPATIBILITY, the
   guide, the skill), **When** each is read, **Then** each states the effective limit,
   why it has that value, and what happens beyond it.
2. **Given** an agent that hits the limit, **When** it consults its guidance, **Then**
   the guidance tells it that the request was refused (not truncated) and how to use the
   refusal's split to reduce the right part and retry.
3. **Given** the measured cap changes the limit (US3), **When** the documentation is
   updated, **Then** the stated numbers match the enforced defaults.

---

### Edge Cases

- The model's configuration is unreadable or missing its maximum: the fallback is
  reported and identifiable; `ember doctor` does not fail.
- A local server started with different settings than doctor's environment: doctor
  reports the running server's live values, not what its own settings would produce.
- An image or video request whose text is small but whose media pushes the encoded size
  over the limit: media is part of the count, the refusal applies, and its split shows
  media as the part to reduce.
- Content exactly at the limit is served normally (the limit is inclusive).
- A state vastly larger than any limit (e.g., hundreds of thousands of tokens): a
  bounded, actionable outcome; no crash, no memory exhaustion.
- Both `flash` and `full`: each has its own measured default cap; limits are reported
  and enforced for the loaded model, and the probe covers both.
- A model outside the registry (a custom weights directory or an S3 model location): its
  default cap is the lowest registry cap, measured or fallback, reported as a fallback.
- The request cap is set above the model's effective maximum (including cap disabled):
  the lower effective bound governs so nothing is silently shortened.
- Empty or trivial states are unaffected; no spurious refusals.
- Content that cannot fit in any form (questions, schema, or prompt wrapper alone exceeds
  the limit): refused with the same actionable error, whose split shows the fixed overhead
  alone over the limit; there is no partial-processing fallback.
- A call to a remote endpoint: the client's behavior is unchanged; the guarantee is
  enforced by the serving ember and depends on its version.
- The rule yields a cap below the model's memory-checked fallback: the default decreases,
  some requests accepted before are refused, and the documentation states the change.
- A longer length passes the rule after a shorter one fails (noise or non-monotone
  quality): the cap stops at the last length before the first failure.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST report, for the active model, both the effective maximum
  token count the model will process and the per-request cap — in the model-load
  log, in `ember doctor`, and in the server's health response. `ember doctor` MUST report
  the values a reachable server advertises (local or remote); with no local server
  running, the values the local settings and model files would produce, labeled as
  configured; and for an unreachable remote endpoint, or one too old to advertise limits,
  unknown.
- **FR-002**: The reported limits MUST reflect the loaded model's own configuration; when
  that cannot be read, the system MUST report the documented fallback and identify it as
  a fallback — never a silent, wrong number. The reported cap MUST also identify its
  source: the model's measured default, the fallback (for a model not yet measured, or
  outside the registry), or an operator setting.
- **FR-003**: A model-backed check MUST encode a known-length input through the same path
  the server uses and assert the resulting token count, so the announced effective limit
  cannot drift from the model's real encoding behavior.
- **FR-004**: Size checks MUST count what the model will actually see — the state as the
  model renders it, the questions and schema, the prompt wrapper, and any media — using
  the same encoding path as inference, not a proxy such as a string representation of
  the state alone.
- **FR-005**: When a request's full encoded content would exceed the enforced limit, the
  system MUST refuse it with an actionable error (HTTP 413-class) — it is never passed to
  inference on a silently shortened state, and ember never truncates it. The refusal is
  one human-readable message, keeping today's response shape, that states the exact
  counted size, how it splits between the state, any media, and the fixed overhead
  (questions, schema, prompt wrapper), the limit, and the setting that governs the limit
  that was hit, so the caller can reduce the right part and retry.
- **FR-006**: The refusal message MUST reach the agent intact through the agent tool, with
  its counts and split, rather than degrading to a generic tool failure.
- **FR-007**: The no-silent-shortening guarantee MUST hold under every supported
  configuration: per-request cap at its default, disabled, or set above or below the
  model's effective maximum, and effective maximum derived from the model or reduced by
  configuration.
- **FR-008**: Agent guidance (MCP instructions, the `ember://guide` resource, the
  `ember-advise` skill, and the AGENTS.md snippet) MUST tell agents that an over-limit
  request is refused (not truncated) and to use the refusal's split to decide what to
  reduce — state, media, or questions — and retry. The MCP instructions MUST also state
  the default model's cap; the guide resource and the skill MUST also state each model's
  limit, why it has that value, and what happens to requests beyond it.
- **FR-009**: A repeatable long-context probe MUST exist: it asks the same decision at
  total context lengths of 2K, 4K, 8K, 16K, 24K, 32K, and 64K tokens, with the key
  evidence placed at three depths at each length (near the start, middle, and end of the
  state), for both registered models, on the device. It MUST record accuracy and
  calibration (Brier score and expected calibration error) per length and depth, with a
  95% interval for each paired difference from the 2K result, plus peak memory and
  latency per length; its sample size MUST be chosen so the FR-010 tolerance can be told
  apart from sampling noise.
- **FR-010**: Each registered model's default per-request cap MUST be chosen by a rule
  fixed before the probe runs: the longest tested length at which it, and every shorter
  tested length, meets all of the following for that model at the worst of the three
  evidence depths — accuracy at most 2 percentage points below, and Brier score at most
  0.02 above, that model's own 2K result — and whose peak memory stays within that model's
  documented minimum (32 GB for `flash`; 96 GB for `full`, raised from 64 GB on
  2026-10-10). Until a model is measured, its
  default is its own fallback: the longest tested length whose peak memory leaves at least
  4 GiB of that minimum free for the OS, reported as a fallback (updated 2026-10-10; it was
  a shared 32,768). A
  model outside the registry (a custom weights directory or an S3 model location)
  defaults to the lowest registry cap, measured or fallback. This refines the
  clarification answer "the lower of the two" for the case where fewer than two models
  are measured. The resulting change
  MUST cite the probe run ID and MUST be recorded as a decision superseding the D-002
  record.
- **FR-011**: README's configuration table and COMPATIBILITY.md MUST state the effective
  limit, why it has that value, and what happens to requests beyond it. (The agent-facing
  surfaces, including the guide resource and the skill, are covered by FR-008.)
- **FR-012**: A probe run MUST record its provenance (run ID, model revisions, device,
  dtype, and the pinned inputs) and MUST be reproducible: re-running from the recorded
  inputs regenerates the recorded results.
- **FR-013**: Existing configuration controls for limits MUST keep working with unchanged
  precedence (flag > environment > file > default), where the default tier for the cap is
  the loaded model's measured default (FR-010); new defaults change values only and MUST
  NOT break or silently override explicit operator settings.
- **FR-014**: An over-limit request MUST return a bounded, actionable response from the
  existing error contract; it MUST NOT crash the server, exhaust memory, or leave the
  model in a failed state. A state of about one million tokens MUST be refused within 60
  seconds while the serving process's resident memory grows by less than 2 GiB.

### Key Entities *(include if feature involves data)*

- **Effective maximum**: The token count the loaded model will process in full; derived
  from the loaded model's configuration, with an identifiable documented fallback.
- **Per-request cap**: The operator-configurable limit (which can be disabled) that ember
  checks before inference; its default is the loaded model's measured cap (FR-010). A
  model not yet measured gets its own memory-checked fallback (24,576 for `flash`, 65,536
  for `full`), and a model outside the registry gets the lowest registry cap; both are
  reported as fallbacks.
- **Enforced limit**: The lower of the per-request cap (when enabled) and the effective
  maximum; the refusal names whichever of the two was hit.
- **Encoded request size**: The count of everything the model would see: the state as the
  model renders it, questions and schema, the prompt wrapper, and media; reported as a
  total and split by part (state, media, fixed overhead).
- **Over-limit refusal**: The actionable error returned instead of a silently shortened
  run; one message carrying the total counted size, its split by part, the limit, and the
  setting that governs it.
- **Long-context probe run**: A recorded measurement: run ID, model, device, context
  lengths 2K–64K × evidence depths (start, middle, end), accuracy and calibration per
  length and depth with 95% intervals on the differences from 2K, and peak memory and
  latency per length.
- **Cap decision record**: The recorded decision choosing each registered model's default
  cap by the FR-010 rule, citing the probe run; supersedes D-002, the unmeasured
  32,768-token mitigation, and the memory-checked fallbacks that replaced it in the
  interim.
- **Limit report**: What `ember doctor` shows for the effective maximum and the cap: each
  value labeled live (advertised by a server's health response), configured (from local
  settings), or unknown, plus the cap's source (measured default, fallback, or operator
  setting).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For the active model, a single read of `ember doctor` (or the health
  response) exposes both limits, and a device-backed check proves the announced effective
  limit matches the model's actual encoding — zero drift; verified by test.
- **SC-002**: Zero requests are silently shortened: across a fixture set including
  dictionary, string, and image states and configurations with the cap disabled or the
  effective maximum reduced, 100% of over-limit requests are refused with the actionable
  error; verified by test.
- **SC-003**: Reported total token counts for dictionary, string, and image fixtures are
  within ±1% of the length the model actually encodes, and the parts of each split sum
  exactly to the reported total; verified by test.
- **SC-004**: Recomputing the FR-010 rule from the recorded probe run yields exactly each
  registered model's shipped default cap; the change cites that run ID and a decision
  record supersedes D-002; verified by recomputation.
- **SC-005**: README configuration, COMPATIBILITY, the guide, and the skill each state
  the limit and the past-limit behavior, and the guidance tells agents how to react;
  verified by tests.
- **SC-006**: One command reproduces a probe run from pinned inputs and regenerates the
  recorded results; verified by re-run.
- **SC-007**: `ember doctor` labels every reported limit as live, configured, or unknown,
  and never shows local settings' values for a remote endpoint; verified by tests covering
  a running local server, no server, and reachable, unreachable, and older remote
  endpoints.

## Assumptions

- Upstream behavior at the pinned revisions is as inspected: a 16,384-token default that
  silently drops a state's tail, prefix/schema/questions protected, no truncation signal,
  and a 262,144-token declared maximum. ember owns the decision before calling upstream
  and does not modify the upstream module.
- The probe's exact decision and fixtures are a planning-phase detail chosen from the
  project's existing benchmark recipes; this spec fixes the lengths, evidence depths,
  models, device, and recorded metrics.
- The ±1% count tolerance is the agreed bar; it accounts for rendering and tokenization
  subtleties, including media token accounting.
- Both registered models can be run on the maintainer's MPS machine (the `full` model is
  27B and is not yet verified locally — verifying it is part of this work).
- Peak memory is measured on the maintainer's reference machine (M4 Max, 128 GB) and
  compared against each model's documented minimum memory; a length that cannot run there
  fails the rule.
- Operators may still raise or lower limits through the existing settings; the
  no-silent-shortening guarantee holds regardless of the values they choose.
- Until the probe measures a model, its default cap is its own memory-checked fallback
  (24,576 for `flash`, 65,536 for `full`), reported as a fallback. Because requests are
  now counted in full (questions, schema, and media included) and flash's fallback is
  below the old 32,768, some requests accepted before may be refused before the measured
  caps land.
- The over-limit default is refusal only: ember never truncates a request, silently or
  otherwise. Explicit truncation-with-signal is not a path in this feature; if caller UX
  later demands it, it would be an additive, documented change.
- The trust model is unchanged (Article I): this feature changes what ember tells its
  caller, not where inference happens.
- Documentation updates remain governed by the agent kit rules (single source of truth;
  the Claude Code plugin's mirrored copy updates together).
- D-002's record lives in the STRIDE review/tracker; superseding it updates those records
  and adds a vault decision.
- The integration eval harness (Workstream B) and its harness gaps (G1–G7) are out of
  scope; the measured cap chosen here is an input to that later phase.
