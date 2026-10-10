# Research: Context Window Audit — Explicit, Measured Length Limits

**Feature**: `003-context-window-audit` | **Date**: 2026-10-09 | **Spec**: [spec.md](./spec.md)

This document resolves every NEEDS CLARIFICATION in the plan's Technical Context. Code
references were checked against the working tree on 2026-10-09 (`main` @ `c65e705`).
Upstream references were checked against Cloudflare's `joint_schema_model.py` at both
pinned revisions, flash `17f0b0ad` and full `2f3de3dd`, which are byte-identical
(576 lines each).

## R1. Count exactly what the model sees (FR-004, SC-003)

**Decision**: Count with upstream `encode_record` itself, using `max_length=sys.maxsize`
so it cannot truncate, on up to three shapes of the same request:

| Encode | Request shape | Gives |
|--------|---------------|-------|
| full | as sent (state, questions, media) | `total = len(full.input_ids)` |
| no-media | media removed | `media = total − len(nomedia.input_ids)` |
| bare | media removed, `state` set to `""` | `fixed = len(bare.input_ids)`; `state = len(nomedia) − fixed` |

Text-only requests skip the no-media encode, which would equal the full one.

**Rationale**:
- `encode_record` (upstream L103–197) tokenizes prefix, media prompt, state, schema, and
  suffix as separate segments and concatenates them. Media is folded into the prefix
  (`prefix_ids = prefix_ids + media_ids`).
- With `max_length=sys.maxsize`, neither the silent slice
  `state_ids[: max_length - fixed_length]` (L170) nor the `fixed_length > max_length`
  error (L166) can fire. `len(input_ids)` is therefore the exact untruncated length: zero
  error, inside the ±1% bar.
- The split is made of differences between whole encodes, so the parts sum to the total
  whatever upstream's segmentation.
- Only the public function is used. It tracks whatever `joint_schema_model.py` is loaded,
  which matters because ember runs any model that fits its loader contract (Article V).

**Alternatives considered**:
- `render()` plus the tokenizer, with estimates for schema, wrapper, and media (the
  handoff's first suggestion): rejected because it drifts from upstream and needs its own
  model of media.
- Counting media tokens by id (`image_token_id` 248056, `video_token_id` 248057 in the
  flash `config.json`): rejected because it depends on per-model ids and misses the vision
  start and end tokens.
- Encoding once and reusing the record for inference: rejected because it would mean
  re-implementing `systemone`'s forward and decode outside upstream (Article XV §15.4).

**Cost**: Media preprocessing runs twice, once to count and once inside `systemone`.
Text-only requests pay two extra tokenizations. The spec sets no latency budget (it was
deferred as low impact). The quickstart measures and records the overhead.

## R2. Where the check runs, validation order, and a runtime invariant (FR-005, FR-007, FR-014)

**Decision**:
- The check runs in `Engine._run_advise` (`ember/serving/runtime.py`), after the request
  is built (media decoded, `media_kwargs` allowlist checked) and before the engine lock.
- If `total` exceeds the enforced limit, ember raises `RequestTooLargeError` (HTTP 413).
- Otherwise ember calls `systemone` with `max_length` equal to the effective maximum,
  which is at least `total`, so upstream never truncates.
- If measuring raises `KeyError`, `TypeError`, `AttributeError`, or `ValueError` (a
  malformed request), ember skips the check. `systemone` then raises its own validation
  error, which maps to 422 as today.
- If the loaded joint module has no `encode_record` at all, that is a loader-contract
  violation, not a malformed request. `measure()` raises `RuntimeError` (HTTP 500, with an
  actionable log line), and the size check is never skipped silently.
- After `systemone` returns, ember asserts `usage.input_tokens == total`. On a mismatch it
  logs an error and raises `RuntimeError` (HTTP 500). It never returns an answer computed
  from a shortened input.

**Rationale**:
- Skipping the check on a malformed request is safe. Counting and inference call the same
  `encode_record` on the same record, so any record that fails to count also fails inside
  `systemone`.
- The only failure that depends on `max_length` is fixed overhead larger than the maximum.
  It cannot happen at `sys.maxsize`, and the enforced-limit comparison already covers it,
  because `total ≥ fixed`.
- The existing 422 test (`tests/test_mcp_tool.py:222`, "criteria must not be empty") keeps
  passing. An empty criteria map counts fine and then fails `systemone`'s validation.
- The invariant costs three lines. It keeps "never silent" true even for an unpinned
  `joint_schema_model.py` loaded through `EMBER_MODEL_DIR` or `EMBER_MODEL_S3_URI`.

**Documented consequence**: A request that is oversized and malformed in a way that still
encodes (an empty criteria map, say) gets 413 first; the retry, once trimmed, surfaces the
422. One that `encode_record` can't encode at all skips the size check and gets the 422
directly.

**Alternatives considered**: Copying `systemone`'s eight validation lines (L547–561) into
ember so that 422 always wins. Rejected because it duplicates upstream logic and can drift
(§15.4).

## R3. Limit resolution, sources, and the configuration sentinel (FR-002, FR-010, FR-013)

**Decision**:
- **New module** `ember/serving/limits.py` (torch-free). It holds the frozen Pydantic
  `Limits` model and the resolution functions.
- **Moved functions**: `FALLBACK_MAX_LENGTH` and `model_max_length()` move there from
  `runtime.py`. A new `declared_max_length()` returns `None` when `config.json` can't be
  read.
- **Source enum**: `LimitSource` (StrEnum: `model`, `fallback`, `operator`, `measured`)
  lives in `ember/serving/limit_source.py`.
- **Registry field**: `ModelSpec` gains `max_request_length: int | None = None`, the
  measured cap. `None` means not yet measured.
- **Config default**: `config.DEFAULTS["max_request_length"]` changes from `32768` to
  `None`, meaning "use the loaded model's measured default". `0` still disables the cap.

| Input | Effective maximum | Per-request cap |
|-------|-------------------|-----------------|
| Nothing set | declared maximum (`model`); 32,768 if `config.json` is unreadable (`fallback`) | registry model: its measured value (`measured`); 32,768 until measured (`fallback`) |
| Model outside the registry (`EMBER_MODEL_DIR` or `EMBER_MODEL_S3_URI` set) | as above | lowest measured registry cap; 32,768 if none is measured yet (`fallback`) |
| Operator value | value clamped to the declared maximum when it is known (`operator`, or `model` when clamped, with a warning); used as given when the declared maximum is unknown | value (`operator`); `0` means disabled |
| Invalid or negative value | treated as unset, with a warning | treated as unset, with a warning |

**Enforced limit** = `min(cap, max)` when the cap is enabled; otherwise `max`.

**Rationale**:
- `ember/cfg/config.py` must not import `ember/models.py` (L16–19). A resolver that needs
  both config and `REGISTRY` therefore can't live in `cfg/`.
- `ember/serving/` already holds torch-free modules that the CLI imports (`process.py`,
  `hosted.py`).
- `Limits` crosses the HTTP-to-engine boundary and carries configuration, so it is
  Pydantic (§13.4, §10.8).
- `None` avoids overloading `0`, which already means "disabled".
- `config.resolve()` converts env strings only when the default is an int or bool
  (L104–114). With a `None` default, the resolver parses the value itself.
- A negative value silently disables the cap today (`if self.max_request_length > 0`).
  The new rule removes that trap.
- `config.save()` is called only by a test (`tests/test_endpoint.py:113`). No user config
  file has a persisted `32768` to migrate.

**Alternatives considered**:
- A `-1` sentinel: rejected because it leaks into `ember config show` and config files.
- A static default: rejected because it contradicts the per-model clarification.
- Resolving limits inside `ember/models.py`: rejected because it mixes the download
  lifecycle with config precedence.

## R4. Reporting limits: load log, `/health`, `ember doctor` (FR-001, SC-001, SC-007)

**Decision**:
- **Load log**: `lifespan` (`ember/serving/server.py` L129–210) logs one line once the
  engine is built: `limits: enforced …; max_length … (source), max_request_length … (source)`.
- **Health**: `Engine.describe()` (L455–471) adds `max_length_source`,
  `max_request_length`, and `max_request_length_source`. `/health` already returns it as
  `engine`.
- **Doctor**: `ember doctor` gains one `limits` line.
  - Live: from the health body of the configured endpoint. `commands/endpoint.endpoint_status`
    (L80–113) already fetches it through `process.health` (local) or `remote_health`
    (remote), and will now return it.
  - Configured: a local endpoint with no server running shows the values computed by the
    same resolver the server uses.
  - Unknown: an unreachable remote, or a health body without limit fields.

**Rationale**: One probe and no new endpoint. Doctor stays torch-free (Article XIV §14.4),
because `limits.py` imports only `cfg`, `models`, and `hosted`.

**Alternatives considered**:
- A new `/limits` endpoint: rejected (YAGNI).
- Having doctor import `runtime.py`: rejected because it imports torch at module load
  (L39).

## R5. The refusal reaches the agent intact (FR-006)

**Decision**: The MCP layer needs no code change. The refusal message must contain no `/`
and no `\`.

**Rationale**: `_sanitize_error` forwards a 4xx `detail` through `_redact`
(`ember/mcp/mcp_server.py` L150–187). `_redact` replaces anything matching `/[^\s:]+`, or
a drive-letter path, with `<path>` (L48, L69). A message containing "state/media" would
arrive as "state<path>". With that constraint met, the agent sees exactly
`ember server error 413: <message>`, and a test asserts it.

## R6. Fitting the guidance into the agent kit (FR-008, SC-005)

**Decision**:
- **`instructions.md`**: The file is 1,955 of its 2,048 bytes (Article III §3.2), leaving
  93 bytes. It gets one compact sentence: requests over the default cap are refused,
  never truncated, and the refusal's split says what to trim. The sentence states flash's
  number. Existing wording is trimmed if needed.
- **`ember-advise/SKILL.md`**: Carries the full statement: the per-model table, the
  enforced-limit rule, the refusal shape, and what to do.
  - Its "Asking well" claim (L85) that "inputs are capped at the model's 262,144-token
    window" is replaced. It has been wrong since D-002 introduced the 32,768 cap.
  - The Claude Code plugin copy is updated byte for byte (`tests/test_distribution.py`).
- **`AGENTS.snippet.md`**: Gets one line.
- **Kit test**: Asserts that every number in the kit equals the resolver's defaults, so
  measured values cannot drift from the text.

## R7. `runtime.py` size debt (Article X §10.3, §10.18)

**Fact**: `ember/serving/runtime.py` is 471 lines. §10.18 records it at 445, so the debt
has already grown without being recorded.

**Decision**: This feature rewrites the file's size check, so it pays the debt down:
- limits move to `limits.py`
- sizing and the refusal message move to `request_size.py`
- the `media_kwargs` allowlist and its check move to `media.py`
- `pick_device` and `pick_dtype` move to `devices.py`

That brings `runtime.py` under 400 lines. The same change removes its §10.18 entry with a
PATCH amendment, following the 2.0.3 precedent.

**Alternatives considered**: Extracting only what this feature needs (about 430 lines).
Rejected: that is below the recorded 445 but still over the ceiling, and the extra
`devices.py` move is mechanical.

## R8. The probe runs an in-process engine, one model per worker process (FR-009, FR-012)

**Decision**: The probe builds an `Engine` in-process, with the cap disabled and the
effective maximum at the model's declared value. It calls `Engine.advise`, the server's
own path minus HTTP. Each model runs in its own worker subprocess. The parent starts each
worker, waits for it, and writes the manifest and the summary.

**Rationale**:
- Peak MPS memory can only be sampled inside the process that owns the allocations.
- The benchmark runner's HTTP pattern (`evals/eval/run_evals.py` L158–175) would need the
  user's server restarted with the cap disabled.
- Long-context inferences can outlast the client's 300-second timeout.
- `runtime.py` (L20–24) requires one model per process.
- **Article IV**: The probe opens no ports and starts no servers, and it waits only for
  the workers it started. If an ember server is running, the probe warns about memory
  contention and leaves the server alone. The probe is never part of `make check`,
  `make test`, or CI.

**Alternatives considered**: The live server, with memory sampled from outside via `ps`.
Rejected: RSS excludes private Metal allocations, and the approach requires reconfiguring
the server.

## R9. Items, evidence, and filler (FR-009)

**Decision**:
- **Items**: All 232 text-only items in `evals/clef-flash.jsonl`, from both splits (264
  items in total; the 32 media items are excluded).
  - Using test-split items is safe. The probe tunes no label, prompt, or threshold, and
    benchmark items (about 220–360 tokens) sit far below any cap, so benchmark scores are
    unaffected.
  - Items whose unpadded request exceeds 2,048 − 64 tokens are excluded and listed in the
    manifest.
- **Evidence**: The item's state exactly as the model renders it (`render(state)`: strings
  unchanged, dicts as compact sorted JSON). It is embedded in a string state as
  `before + "\n\n" + evidence + "\n\n" + after`.
  - The item's questions and gold labels are unchanged.
  - The whole question set stays together, because questions are scored jointly.
- **Depths**: `start` (no filler before the evidence), `middle` (filler split evenly), and
  `end` (no filler after, so the evidence sits right before the schema).
- **Lengths**: 2,048, 4,096, 8,192, 16,384, 24,576, 32,768, and 65,536 tokens (K = 1,024).
  - Length is measured on the full encoded request, the same quantity the cap governs.
  - Each padded request's `total` lands in [L − 32, L], using R1's count.
  - The 2K baseline is padded too, so every cell is compared like with like.
- **Filler**: One public-domain, pre-1919 book from Project Gutenberg (following the PG19
  corpus convention), with the Gutenberg boilerplate stripped.
  - Vendored at `evals/context/filler.txt`.
  - Its SHA-256 is pinned in code and recorded in the manifest; its source and licence go
    in `THIRD_PARTY_NOTICES.md`.
  - Each item's filler starts at a deterministic offset derived from its id.

**Rationale**:
- The filler is topically neutral, so it cannot change a coding decision.
- It is offline: nothing downloads during a run (Article I).
- Neutral book text is standard long-context practice (PG19 and BABILong haystacks).

**Alternatives considered**:
- Repository docs: rejected because they discuss risk, tests, and failures, which would
  contaminate change-risk and triage answers.
- Other benchmark items: rejected because their gold labels conflict.
- Repeated synthetic sentences: rejected because a model can ignore them easily, which
  makes results optimistic.

## R10. Metrics, paired intervals, and sizing (FR-009, FR-010)

**Decision**:
- **Per item, per cell**: accuracy is the mean correctness of the item's `noul` and
  `choice` questions, from `evals.metrics.score_question` (L172–215: `noul` is true at
  p ≥ 0.5; `choice` is an exact match).
  - Brier is the mean of `brier_binary` (noul, L124–129) and `brier_multiclass` (choice,
    L110–121).
  - `score` questions are recorded (MAE) but don't gate.
- **Per cell**: accuracy and Brier are means over items. Top-label ECE comes from
  `calibration_error` (L96–107) over the pooled questions; it is reported, not gated.
- **Paired intervals**: Per-item deltas between cell (L, d) and cell (2K, d), for the same
  item and depth, are fed to `evals.metrics.bootstrap_ci` (L149–164) with
  `resamples=10000, seed=0`. The repo has no paired helper, and resampling the deltas
  reuses this one as is.
- **Sizing gate**: Before the full run, a pilot runs flash at 2K and 16K, middle depth, on
  all included items.
  - It projects the 95% half-width at the included item count as `1.96 · sd(delta) / √n`.
  - If that half-width exceeds 2 percentage points, the run stops and reports it: the
    available items can't resolve the pre-declared tolerance. A human then decides what to
    do, for example add items.
  - The full run reuses the pilot's cells.
- **Compute control**:
  - Memory is measured first at each length. Lengths that exceed the budget or run out of
    memory skip their quality runs.
  - After the first length that fails the rule, longer lengths run a fixed stratified
    48-item subset. Those cells are marked exploratory and the rule ignores them.
  - This satisfies US3's "results at each length" without days of extra compute.

## R11. Peak memory on MPS (FR-009, FR-010)

**Fact**: torch 2.14's `torch.mps` provides `current_allocated_memory`,
`driver_allocated_memory`, and `recommended_max_memory`. It has no `max_memory_allocated`
and no `reset_peak_memory_stats`; CUDA has both.

**Decision**:
- A `MemorySampler` thread polls `torch.mps.driver_allocated_memory()` every 20 ms during
  each inference, with `torch.mps.synchronize()` before and after.
- It also records the process RSS at the start of the inference (`ps -o rss= -p <pid>`;
  no new dependency).
- `peak_bytes = rss_start + driver_peak`. A length's peak is the maximum over all its
  inferences.
- The budget is the pre-declared one: 32 GiB for flash, 64 GiB for full.
- An MPS out-of-memory error ("MPS backend out of memory") is recorded as `oom`. It fails
  that length, and the longer lengths are skipped because they would fail too.
- `recommended_max_memory()` is recorded for context.
- **Sanity check**, in the smoke run and before any canonical run:
  - `rss_start_bytes` must be well under the model's weights: at most 25% of
    `ModelSpec.approx_bytes`.
  - The 2K `driver_peak_bytes` must be close to the weights plus activations:
    0.9–1.5 × `approx_bytes`.
  - If either fails, the CPU copy made while loading wasn't released and the formula
    double-counts. Revise it before the canonical run.
  - The worker logs a warning whenever `rss_start_bytes` exceeds 25% of `approx_bytes`.

**Note for the decision record**: On a machine with the documented minimum, the GPU
working-set limit is well below total RAM. The pre-declared rule compares against total
RAM and is applied unchanged. The decision record should show both numbers.

## R12. The cap rule (FR-010, SC-004)

**Decision**: The rule is one pure function, and it works only on the summary.
- **A length passes** when, at every depth:
  - accuracy ≥ that depth's 2K accuracy − 0.02
  - Brier ≤ that depth's 2K Brier + 0.02
  - the length's peak memory fits the model's budget
  - every inference at that depth succeeded: a cell with an errored row can't be scored,
    so it fails the length with reason `error` instead of being scored on fewer items
- **The cap** is the longest length that passes, along with every shorter length.
- **If no length passes** (2K over budget), there is no cap. The default stays unchanged
  and the summary says so, leaving the call to a human.
- Rounding is fixed at 6 decimals, so recomputing the rule is exact.

## R13. Artifacts, storage, and reproducibility (FR-012, SC-006)

**Decision**:
- **Working output**: `results/context/<run_id>/` (`results/` is gitignored,
  `.gitignore:25`). It holds `manifest.json`, append-only `rows-<model>.jsonl`, and
  `summary.json`.
  - Each row is flushed and fsynced.
  - A resumed run drops a torn last line.
- **Decision runs**: The run a decision cites is copied with `copy_atomic`
  (`evals/export.py` L32–37) into tracked `evals/context/runs/<run_id>/`.
  - That is outside `benchmark/`. The site renders `benchmark/` by globbing
    `benchmark/*/model.json` (`scripts/build_site_benchmark.py` L34).
- **Run id**: `context_<UTC %Y%m%dT%H%M%SZ>`, following `run_evals.py` L222–223.
- **Records**: Pydantic models. Article X applies to `evals/` at full strictness, and
  §10.8 requires Pydantic for on-disk data; the existing harness's plain-dict idiom
  predates that. The metrics functions receive `model_dump()` dicts.
- **Provenance**: The git, host, package, and model-spec helpers move out of
  `run_evals.py` (L80–139) into a public `evals/eval/provenance.py` that both runners
  import (§15.4). They gain a `git_dirty` flag.
- **Rescore**: `--rescore` regenerates `summary.json` byte for byte from the rows and
  manifest, using sorted keys and fixed rounding.
- **Reproduce**: `--reproduce` re-runs the manifest's pinned inputs into a new run and
  compares the two. It passes when:
  - counted tokens are identical
  - every probability is within ±0.001
  - per-question correctness is identical
  - the cap verdict is the same (full reproductions only; a reproduction narrowed with
    `--items N` compares rows only)
- **Modules**: Each concern has its own module, so `run_context.py` only orchestrates
  and every module stays under 400 lines (Article X §10.3).
  - `evals/context/items.py`: item selection and manifest assembly
  - `evals/context/reproduce.py`: the reproduction comparator
  - `evals/context/scoring.py`: the sizing-gate math

## R14. CLI and make wiring

**Decision**: `ember eval context` is wired the same way as the existing eval subcommands:
- A subparser in `ember/commands/parser.py::register_eval` (L242–338).
- A handler, `cmd_eval_context`, in `ember/commands/eval.py`. It imports
  `evals.context.run_context` lazily, behind `_EVAL_CHECKOUT_ERROR` (L9–13).
- Wiring in `ember/cli.py` (L21–26, L105–112).
- Make targets `eval-context` and `eval-context-smoke` in `shared/testing.mk`, as one-line
  `$(PY) evals/context/run_context.py …` recipes next to `eval-snapshot`.

## R15. Very large states (FR-014)

**Decision**:
- Exact counting is linear in state size.
- A state of hundreds of thousands of tokens (the spec's example) is counted and refused
  in bounded time and memory. A model-backed test verifies this with a state of about
  1M tokens.
- Multi-gigabyte request bodies are parsed by the HTTP layer before ember's code runs.
  That exposure predates this feature and is out of scope; it is recorded as a STRIDE
  follow-up.

## R16. What changes for users before the probe lands

**Decision**:
- **Until US3**: `ModelSpec.max_request_length` stays `None`, so every model keeps today's
  32,768 cap, with source `fallback`.
- **Counting**: requests are now counted in full: questions, schema, and media included.
  A request that passed today's state-only check can now be refused; image-heavy requests
  are the likely case. README, COMPATIBILITY, and the kit say so when US2 ships.
- **US3**: replaces the fallback with measured per-model values and supersedes D-002. The
  STRIDE review and tracker entries are updated, and a vault decision is added.
