# Feature Specification: Benchmark Hygiene — Label Stability, Kinds, Tiers, and One Controlled Comparison

**Feature Branch**: `006-benchmark-hygiene`

**Created**: 2026-10-11

**Status**: Draft

**Parent programme**: `specs/004-benchmark-categories/spec.md`. This feature is **Phase 1 (Hygiene)** of that programme's Delivery Series. Every requirement, protocol rule, bar, share, and size target of the parent applies unchanged; this document may refine option wording, seed items, and counts upward as the parent permits, and never weakens a rule.

**Input**: User description: "Phase 1 — Hygiene (the second phase of the benchmark programme): a label-stability pass on the `risk` and `effort` recipes; rubric-anchored levels; the same dataset rerun at float16 on MPS and CUDA; difficulty tiers tagged from the first full runs on the versioned dataset with non-easy accuracy in the report; probe cap, first-drop length, and worst depth in each row; a session-capture pipeline; existing items re-tagged by kind; the first dataset card. Gate to Phase 2: label stability published (single-rater) and one controlled comparison committed."

## Context

Phase 0 made every published number carry its direction, its risk, and its provenance. Phase 1 makes every existing number **explainable**:

- The judgment-heavy score recipes are the weak spot (`risk` roughly 52% exact, `effort` roughly 42%), and their gold is single-rater with no published stability evidence. A reader cannot yet tell a genuinely hard question from a wobbly label.
- All 475 committed items are `authored`; none carries an item kind or a difficulty tier. The dataset lint consequently reports kind-share gaps across every recipe, and the report cannot separate easy from non-easy performance.
- Leaderboard rows do not yet carry the long-context shape (request cap, first-drop length, worst depth) that spec 003's probe produces.
- There is no pipeline for capturing real agent sessions, and no dataset-card edition carrying kind, tier, and stability content.
- The controlled comparison the parent requires (the same dataset at float16 on MPS and on CUDA) is now practical: an AWS CUDA deployment is live and its full run is a committed bundle.

Nothing in this phase changes what is scored unless a human adjudication changes a gold label; kinds and tiers are annotations, and the parent's hash rules govern.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A reader can see how stable the gold labels are (Priority: P1)

A benchmark reader opening the `risk` and `effort` recipes sees, beside accuracy, a published **label stability** measurement: every item was re-labelled blind after a cooling-off period, agreement per label and per recipe is reported, and the report states plainly that gold is single-rater until a second reviewer exists. An unstable label is visible as such instead of reading as a verdict.

**Why this priority**: It is one of the two phase gates, and it is the precondition for trusting the two weakest recipes. The parent's clarification fixes the protocol: rubric anchoring, a blinded re-label after cooling-off published as label stability, and a plain single-rater statement; the model never labels.

**Independent Test**: Run the stability pass on the current `risk` and `effort` items and render the report: every item carries a stability record, the recipes show agreement figures, and the single-rater statement appears. Delivers trustworthiness of the weakest recipes without needing any later phase.

**Acceptance Scenarios**:

1. **Given** the `risk` and `effort` items, **When** the stability pass runs, **Then** each item receives a second, blinded label after the cooling-off period, and a stability record (agreement, round, date, method) exists for it.
2. **Given** the assembled stability results, **When** the report renders, **Then** each recipe shows its label stability (overall and per label where the recipe has labels), and the report states that gold is single-rater and derived from one person's blinded re-label.
3. **Given** a re-label that disagrees with the original, **When** the item is published, **Then** the disagreement is recorded, the item is queued for review, and the label is never changed to match the model.

---

### User Story 2 - One controlled comparison proves MPS and CUDA agree (Priority: P1)

A benchmark reader sees the same dataset version scored at float16 on two devices — MPS (the maintainer's Mac) and CUDA (the AWS deployment) — as one controlled comparison with everything except the device held constant. Both runs are committed bundles; a comparison view names any per-recipe differences instead of leaving them to be inferred.

**Why this priority**: It is the second phase gate, and it is the evidence behind every claim that a deployment change does not change what the benchmark measures.

**Independent Test**: Score the current dataset at float16 on both devices, commit both runs, and render the comparison. Delivers deployment-equivalence evidence for the current dataset version.

**Acceptance Scenarios**:

1. **Given** the current dataset version, **When** it is scored at float16 on MPS and at float16 on the CUDA deployment, **Then** both runs share the same dataset content hash and the same settings except the device, and both are recorded with their hashes and settings.
2. **Given** the two committed runs, **When** the comparison renders, **Then** it shows per-recipe figures side by side and names any difference (with the numerics note: MPS may differ slightly from CUDA).
3. **Given** the comparison does not exist for the current dataset version, **When** the build checks the phase gate, **Then** the gate is reported as not green.

---

### User Story 3 - Every score level is anchored to a rubric (Priority: P2)

A contributor writing or reviewing a score question finds, at every level, an anchor description that distinguishes that level from its neighbours — for `risk` and `effort` first, and for every score scale thereafter. Adjacent levels cannot be confused because the rubric says what separates them.

**Why this priority**: Anchors are what make the stability pass meaningful and what prevent a reversed or ambiguous scale from shipping; they support the P1 stories rather than gating the phase alone.

**Independent Test**: Inspect the `risk` and `effort` scales and their anchors; attempt to land a scale with a missing or indistinguishable anchor and see the dataset check fail. Delivers rubric clarity without any other phase.

**Acceptance Scenarios**:

1. **Given** the `risk` and `effort` scales, **When** their registry entries are read, **Then** every level carries an anchor description that names what distinguishes it from the level below and above.
2. **Given** a score scale whose anchors are missing or identical for adjacent levels, **When** the dataset is validated, **Then** validation fails naming the scale and the level.
3. **Given** an anchor changes, **When** the change lands, **Then** the protocol record names the dataset version the new anchor first applies to (`since`), and history is not rewritten.

---

### User Story 4 - Every item carries a kind and a difficulty tier, and the report shows non-easy accuracy (Priority: P2)

A reader picks any item and sees what kind it is (a negative, a control, a hard negative, an adversarial, an insufficient-context, a variant, or another declared kind) and how hard it proved to be (a tier assigned by a declared rule over the first full runs on the current dataset version). The report publishes accuracy on non-easy items beside overall accuracy, so a strong headline cannot hide a collapse on the hard slice.

**Why this priority**: Kinds and tiers are the substance behind the parent's composition rule and difficulty reporting; they close the largest current lint gaps (kind shares) and make every later recipe's lint meaningful.

**Independent Test**: Re-tag the existing items by kind and tier, regenerate the report and the card content: kind-share findings close or carry documented exemptions, non-easy accuracy appears, and the dataset content hash is unchanged.

**Acceptance Scenarios**:

1. **Given** the existing items, **When** they are re-tagged, **Then** every item carries exactly one kind from the declared vocabulary and one difficulty tier, and the lint's kind-share rules either pass or carry a documented exemption naming the kind and the shortfall.
2. **Given** the tier assignment, **When** it is audited, **Then** each tier traces to a declared rule and the full runs it was computed from, and the assignment is annotation-only: the dataset content hash is unchanged.
3. **Given** a run on the current version, **When** the report renders, **Then** accuracy on non-easy items appears beside overall accuracy for each recipe that has tiers.
4. **Given** a human adjudication changes a gold label, **When** the change lands, **Then** a new dataset version is recorded (append-only) with the change named, and the pinned split of the affected item is preserved.

---

### User Story 5 - Every leaderboard row carries the long-context shape (Priority: P3)

A reader comparing rows sees, for each row, the request cap, the first-drop length, and the worst depth — or an explicit "not measured" — so a row that only shines at short contexts cannot look equal to one that holds everywhere.

**Why this priority**: It completes the reporting surface the parent requires per row, but it hangs off spec 003's existing probe and gates nothing.

**Independent Test**: Produce probe results for a row's model, device, and settings and render the leaderboard: the row carries the three figures; without a probe it says "not measured".

**Acceptance Scenarios**:

1. **Given** a row whose model, device, and settings have a probe run, **When** the leaderboard renders, **Then** the row shows the request cap, the first-drop length, and the worst depth.
2. **Given** a row with no probe run, **When** the leaderboard renders, **Then** the row states "not measured" rather than omitting the fields.
3. **Given** a probe run, **When** it is recorded, **Then** it names the model, device, settings, and dataset version it measured, and only matching rows may use it.

---

### User Story 6 - Real agent sessions can become captured items (Priority: P3)

The maintainer can take a consented, redacted real agent session and turn it into candidate benchmark items. The choice reviewed after the fact is gold; the choice made in the moment is kept beside it, and items where the two differ are tagged as the most informative cases. Nothing unredacted is ever captured.

**Why this priority**: Captured items are the parent's highest-fidelity source and feed later phases; the pipeline must exist and be safe before any capture happens, but no phase gate depends on it.

**Independent Test**: Convert a sample session into an item: consent and redaction records are required, the reviewed choice becomes gold, the acted choice is retained, disagreement is tagged, and a session lacking a redaction record fails validation.

**Acceptance Scenarios**:

1. **Given** a consented session, **When** it is converted, **Then** the item's source names the session and its redaction record, gold is the reviewed choice, and the in-session choice is recorded as secondary.
2. **Given** an item whose reviewed and acted choices differ, **When** it is published, **Then** it is tagged as a disagreement item.
3. **Given** a session whose content cannot be redacted (any live secret remains), **When** conversion is attempted, **Then** it is refused; the no-live-secret rule is never relaxed.

---

### User Story 7 - The dataset card publishes the hygiene edition (Priority: P3)

A reader opening the dataset card sees, in one generated document: per-recipe sizes and split coverage, the kind and tier composition, the source kinds with their licences from the register, and the label-stability results — with the register hash embedded and regeneration checked by the build.

**Why this priority**: The card is the dataset's shop window; it should carry the hygiene content, but it is a presentation of P1–P4 work rather than new measurement.

**Independent Test**: Regenerate the card from the dataset and the stability results: it carries the hygiene sections, the register hash is embedded, and the freshness check passes.

**Acceptance Scenarios**:

1. **Given** the re-tagged dataset and the stability results, **When** the card regenerates, **Then** it reports kinds, tiers, split coverage, source kinds with licences, and label stability, and it embeds the register hash.
2. **Given** a dataset or register change without a card regeneration, **When** the build checks, **Then** the card is reported stale.

### Edge Cases

- **A re-label round is itself unstable** (a label flips back and forth across rounds): the item is recorded as unstable, queued for review, and reported as such; no round is silently dropped.
- **A cooling-off period is skipped or shortened**: the stability record names the actual window; the report discloses it rather than presenting a partial pass as complete.
- **An item fits no declared kind**: it is assigned the closest declared kind only with a written rationale, or the lint exemption path is used; a blank kind is never allowed.
- **Tier rule inputs are missing for an item** (e.g., a recipe not yet scored on the current version): the item is left untiered and the report names the gap; tiers are never guessed.
- **The two devices of the controlled comparison disagree on a recipe**: the difference is named in the comparison with the numerics note; labels are never adjusted to reduce the difference, and the gate still requires the comparison to be committed.
- **A probe run predates a dataset or settings change**: it does not attach to rows it no longer matches; those rows say "not measured".
- **A captured session predates a redaction-policy change**: it is re-checked before publication; if it cannot be re-verified, it is not published.
- **A stability adjudication changes a gold label**: this changes what is scored, so a new dataset version is recorded and the pinned split is preserved (a resolved `dev` disagreement stays in `dev`).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `risk` and `effort` items MUST receive a blinded re-label pass, after a declared cooling-off period, recorded per item with agreement, round, date, and method.
- **FR-002**: Label stability MUST be published per recipe (and per label where a recipe has labels), derived from the re-label records; the pass MUST be reproducible from committed evidence.
- **FR-003**: Every report showing stability MUST state plainly that gold is single-rater until a second reviewer exists, and that the model never labels.
- **FR-004**: Every level of the `risk` and `effort` scales — and, from this phase forward, every score scale — MUST carry an anchor description that distinguishes it from its adjacent levels; validation MUST fail on a missing or indistinguishable anchor.
- **FR-005**: Anchor and protocol changes MUST name the dataset version they first apply to (`since`); the versions record stays append-only.
- **FR-006**: The current dataset version MUST be scored at float16 on MPS and at float16 on a CUDA deployment as one controlled comparison: identical dataset content hash, identical settings except the device; BOTH runs MUST be recorded and committed as bundles.
- **FR-007**: The comparison MUST render per-recipe figures side by side and name any difference with the numerics note (MPS may differ slightly from CUDA).
- **FR-008**: Every item MUST carry exactly one kind from the declared kind vocabulary; the lint's kind-share rules MUST pass or carry a documented exemption naming the kind and the shortfall.
- **FR-009**: Every item MUST carry one difficulty tier assigned by a declared rule over named full runs on the current dataset version; untiered items MUST be reported as a named gap, never guessed.
- **FR-010**: Kind and tier assignments MUST be annotation-only: the dataset content hash MUST NOT change because of them.
- **FR-011**: Each recipe's report and each leaderboard row on the current version MUST publish accuracy on non-easy items beside overall accuracy where tiers exist.
- **FR-012**: Each leaderboard row MUST carry the request cap, the first-drop length, and the worst depth from a probe run matching the row's model, device, settings, and dataset version; a row without a matching probe MUST state "not measured".
- **FR-013**: A session-capture pipeline MUST convert a consented, redacted real session into candidate items whose source names the session and its redaction record; the reviewed choice is gold and the in-session choice is kept as a secondary field.
- **FR-014**: Captured items whose reviewed and acted choices differ MUST be tagged as disagreement items.
- **FR-015**: Capture MUST refuse any session whose content cannot be fully redacted; the no-live-secret rule remains enforced without exception.
- **FR-016**: The dataset card MUST be regenerated to carry the hygiene content (sizes, split coverage, kinds, tiers, source kinds with register licences, label stability) and MUST embed the register hash; staleness MUST be a build-visible failure.
- **FR-017**: If a human adjudication changes a gold label, a new dataset version MUST be recorded (append-only) naming the change; the item's pinned split MUST be preserved.
- **FR-018**: No parent-programme rule, bar, share, size target, or split pin may be weakened by this phase; the phase's exit gate (label stability published, one controlled comparison committed) MUST be mechanically checkable.

### Key Entities

- **Stability record**: one item's blinded re-label after cooling-off — agreement with the original, round, date, method, and any review queue entry.
- **Anchor**: a level's rubric description in a score scale, with the dataset version it first applies to (`since`).
- **Item kind**: one of the declared vocabulary values (negative, control, hard negative, adversarial, insufficient context, variant, and the vocabulary the parent fixes), with any documented exemption.
- **Difficulty tier**: an item's tier with the declared rule and the named run(s) it derives from.
- **Probe shape**: a row's request cap, first-drop length, and worst depth, tied to the model, device, settings, and dataset version measured.
- **Controlled comparison**: a pair of runs identical in dataset hash and settings but differing in device, committed together with their comparison view.
- **Capture record**: a session's consent and redaction provenance, the reviewed choice (gold), the acted choice (secondary), and the disagreement tag.
- **Card edition**: a generated dataset card carrying the hygiene sections and the embedded register hash.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of `risk` and `effort` items carry a stability record; both recipes publish an agreement figure; the single-rater statement appears in every rendered report.
- **SC-002**: 100% of items carry a kind and (where a rule can assign one) a difficulty tier; kind-related lint findings for the current dataset are closed or documented, and the lint's enforced rules stay green.
- **SC-003**: Every recipe's report on the current version shows non-easy accuracy beside overall accuracy once tiers exist.
- **SC-004**: Two committed bundles — MPS and CUDA, float16, same dataset content hash — exist for the current version, and a comparison view renders them side by side with any difference named.
- **SC-005**: Every leaderboard row shows the three probe figures or an explicit "not measured"; no row renders with the fields omitted.
- **SC-006**: A sample consented session converts to a schema-valid captured item in the build's tests, and a session without a redaction record is refused.
- **SC-007**: The dataset card embeds the current register hash and reports kinds, tiers, split coverage, and stability; a stale card fails the build.
- **SC-008**: The phase gate is mechanically verifiable: the build reports green only when the stability publication and the committed comparison exist for the current dataset version.

## Assumptions

- **Single maintainer; no second reviewer.** Per the parent's clarification, every dual-labelling requirement is replaced by the one-person protocol: rubric anchoring, a blinded re-label after cooling-off published as label stability, and a plain single-rater statement. No new dual-review dependency is introduced.
- **The CUDA half of the comparison is the AWS deployment** (a committed bundle from the live endpoint). MPS runs on the maintainer's Apple Silicon Mac; both at float16, the same dataset version, and the same request settings.
- **Re-tagging is annotation-only.** Kinds and tiers do not enter the content hash (the parent fixes what the hash covers); the committed bundles keep matching the current version unless a gold label changes.
- **The card tool, the scales registry, the tier tool, and the probe already exist** from Phases 0 and spec 003; this phase extends their content and surfaces it, rather than building new measurement machines.
- **Existing lint findings may be closed or exempted.** The parent permits a documented exemption for a kind short on items; size targets and split-share rules are not relaxed by this phase.
- **Session capture begins with the maintainer's own sessions**, under consent, with redaction records; imports remain governed by the register and are not part of this phase.
- **The stability pass covers `risk` and `effort` first**; other recipes' stability passes follow in their own phases or later rounds, as the parent's series provides.
