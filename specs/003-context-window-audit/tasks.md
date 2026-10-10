---

description: "Task list for 003-context-window-audit"
---

# Tasks: Context Window Audit — Explicit, Measured Length Limits

**Input**: Design documents from `/specs/003-context-window-audit/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included and mandatory. Constitution Article XI (TDD, Red-Green-Refactor) and
the spec's "verified by test" success criteria require them. Write every test task first
and confirm it fails (`.venv/bin/python -m pytest tests/<file> -k <name> -x` must FAIL)
before starting the implementation task that makes it pass.

**Organization**: Tasks are grouped by user story (US1–US4 in spec.md) so each story can be
implemented and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: The user story the task belongs to (US1, US2, US3, US4)
- Every task names exact file paths. "R#" refers to research.md, and `contracts/x.md`
  refers to `specs/003-context-window-audit/contracts/x.md`

## Path Conventions

This is a single Python project at the repository root:
- `ember/`: the package
- `evals/`: the eval harness, which runs only from a checkout
- `tests/`: pytest
- `scripts/`
- `shared/*.mk`: make targets

---

## Phase 1: Setup

**Purpose**: Confirm a green baseline and confirm the upstream contract the plan relies on.

- [X] T001 Run `make check` and `make test-cov` on branch `003-context-window-audit` before
  changing anything. Coverage must be at least 81% (`fail_under = 81` in `pyproject.toml`
  `[tool.coverage.report]`). Note the measured coverage and `wc -l ember/serving/runtime.py`
  (expected: 471); T074 and T077 compare against them.
- [X] T002 [P] Confirm the local flash snapshot matches the upstream API the plan relies on
  (R1):
  - In the directory printed by `ember model path flash`, `joint_schema_model.py` defines
    `encode_record(tokenizer, record, max_length=16384, max_state_tokens=None,
    processor=None)` and `systemone(model, processor, request, max_length=16384)`.
  - Check with `.venv/bin/python -c "import inspect, sys; sys.path.insert(0, '<dir>');
    import joint_schema_model as j; print(inspect.signature(j.encode_record),
    inspect.signature(j.systemone))"`.
  - If either signature differs, stop and re-plan.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The limit resolver, the request-size counter, and the constructor and config
changes every story needs.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. Every
checkpoint stays green: until US2, the engine keeps today's `str(state)` pre-check, now
reading its cap from `Limits`.

### Tests (write first; must fail)

- [X] T003 [P] Create `tests/test_limits.py` with failing tests for
  `ember.serving.limit_source` and `ember.serving.limits` (data-model.md §Limits,
  contracts/config.md):
  - (a) `LimitSource` has `MODEL="model"`, `FALLBACK="fallback"`, `OPERATOR="operator"`,
    `MEASURED="measured"`. `GoverningLimit` (`ember.serving.governing_limit`) has
    `CAP="cap"` and `MAXIMUM="maximum"`.
  - (b) `Limits` enforces these constraints, and is frozen (assigning to a field raises):
    - "`max_length` ≥ 1, and never above the model's declared maximum when it is known
      (operator values are clamped). When the declared maximum is unknown, an operator
      value is used as given"
    - "`max_length_source` … `model`, `fallback`, or `operator`"
    - "`max_request_length` ≥ 0; `0` means the cap is disabled"
    - "`max_request_length_source` … `measured`, `fallback`, or `operator`; always
      `operator` when the value is `0`"
  - (c) `enforced` is `min(max_request_length, max_length)` when
    `max_request_length > 0`, else `max_length`. `governing` is `GoverningLimit.CAP`
    when the cap is enabled and ≤ `max_length`, else `GoverningLimit.MAXIMUM`.
  - (d) Every row of the contracts/config.md resolution table, through
    `resolve(declared, registry_key, *, max_length=None, max_request_length=None)`.
    Include:
    - an operator `max_length` above the declared maximum is clamped to the declared
      value, with source `model` and a logged warning (use `caplog`)
    - `declared=None` gives `32768` with source `fallback`
    - `declared=None` with an operator `max_length` of 65536 gives 65536 with source
      `operator`: no clamping when the declared maximum is unknown
  - (e) `default_request_cap(...)`:
    - `default_request_cap("flash")` returns `(32768, LimitSource.FALLBACK)` while
      `REGISTRY["flash"].max_request_length is None`.
    - It returns `(N, LimitSource.MEASURED)` after `REGISTRY["flash"]` is monkeypatched to
      `dataclasses.replace(spec, max_request_length=N)`.
    - `default_request_cap(None)` returns the lowest measured registry cap with source
      `fallback`, or `(32768, LimitSource.FALLBACK)` when nothing is measured.
  - (f) `from_config(model_dir, registry_key)` with:
    - `EMBER_MAX_REQUEST_LENGTH="16384"`: operator, 16384
    - `"0"`: disabled, operator
    - `"-5"` and `"abc"`: treated as unset, with a warning
    - `EMBER_MAX_LENGTH="1024"`: operator, 1024
  - (g) `declared_max_length(tmp_path)` returns `None` without a readable `config.json`,
    and the `text_config.max_position_embeddings` value otherwise. Move the four
    `test_model_max_length_*` tests from `tests/test_runtime_unit.py` (L125–147) here,
    importing `model_max_length` from `ember.serving.limits`. Move them; never delete
    tests (Article XI §11.3).
  - (h) A subprocess check that
    `import sys, ember.serving.limits; assert 'torch' not in sys.modules` passes.
- [X] T004 [P] Create `tests/test_request_size.py` with failing tests for
  `ember.serving.request_size.measure(js, processor, request)`.
  - **Fake joint module**: `encode_record(tokenizer, record, max_length, processor=None)`
    returns an object whose `input_ids` length is a known function of the record, for
    example `len(str(state)) + 7·len(images) + 3·len(questions) + 5`.
  - **Assertions**:
    - (a) The returned `RequestSize(total, state, media, fixed)` matches the telescoping
      definitions in data-model.md §RequestSize, and "Invariant:
      `state + media + fixed == total`" holds.
    - (b) Every `encode_record` call passes `max_length=sys.maxsize`.
    - (c) Text-only requests make exactly two calls (full, bare); media requests make
      three.
    - (d) The bare call uses `state=""` and no `images` or `videos`.
    - (e) A joint module without `encode_record` raises `RuntimeError` (R2).
    - (f) `KeyError`, `TypeError`, `AttributeError`, and `ValueError` raised by
      `encode_record` propagate unchanged.
- [X] T005 [P] Add failing tests to `tests/test_media.py` for
  `ember.serving.media.check_media_kwargs(kwargs)`:
  - The allowed keys pass: `min_pixels`, `max_pixels`, `fps`, `min_frames`, `max_frames`,
    `do_resize`, `size`, `do_convert_rgb`.
  - An unknown key raises `ValueError`. The message lists the disallowed and permitted
    keys exactly as `ember/serving/runtime.py` L436–445 does today.
  - The formerly reserved key `text` is rejected.
- [X] T006 [P] Update `tests/test_runtime_unit.py` for the new imports and constructor. These
  fail until T016.
  - **Devices**: the device tests (L29–87) import `pick_device` and `pick_dtype` from
    `ember.serving.devices` and monkeypatch `devices.torch`.
  - **Model maximum**: `test_pinned_model_declares_the_model_maximum` (L216) imports
    `model_max_length` from `ember.serving.limits`.
  - **D-002 config tests** (L920–950):
    - `config.DEFAULTS["max_request_length"] is None`
    - the env-override and zero-means-no-cap tests assert through
      `limits.from_config(...)` (operator 16384; disabled)
  - **Engine construction**: every `Engine(...)` call passes
    `limits=Limits(max_length=..., max_length_source=LimitSource.MODEL,
    max_request_length=..., max_request_length_source=LimitSource.OPERATOR)` in place of
    `max_length=` and `max_request_length=`. The D-002 behavioral tests (L950–1078) keep
    their current assertions under the interim `str(state)` check.
  - **Fake joint modules**: every one gains an `encode_record`, shaped as in T004, next to
    `systemone`. This includes the fakes in the media-kwargs tests (L316–359).
- [X] T007 [P] Update the lifespan tests in `tests/test_http_api.py`
  (`test_lifespan_uses_hosted_source_when_configured`, L264;
  `test_lifespan_falls_back_to_registry_when_hosted_not_configured`, L301).
  - `_FakeEngine` accepts `limits=` and records it.
  - With `REGISTRY["flash"]` monkeypatched to `dataclasses.replace(spec,
    max_request_length=8192)`:
    - the registry path records `max_request_length=8192`, source `measured`
    - the hosted path records 8192, source `fallback` (outside the registry)

### Implementation (make the tests pass)

- [X] T008 [P] Create the two limit enums, one class per file (Article X §10.2, §10.7). Each
  starts with `from __future__ import annotations` and has a NumPy docstring. Makes
  T003(a) pass.
  - `ember/serving/limit_source.py`: `class LimitSource(StrEnum)` with `MODEL="model"`,
    `FALLBACK="fallback"`, `OPERATOR="operator"`, `MEASURED="measured"`.
  - `ember/serving/governing_limit.py`: `class GoverningLimit(StrEnum)` with `CAP="cap"`
    and `MAXIMUM="maximum"`.
- [X] T009 [P] In `ember/models.py`:
  - Add `max_request_length: int | None = None` to `ModelSpec`. Document it as: "The cap
    the FR-010 rule chose for this model, set from the canonical probe run. `None` until
    measured. When set, 2,048 ≤ value ≤ declared maximum".
  - Add `registry_key(name: str | None) -> str | None`. It returns `get(name).name`,
    except when `EMBER_MODEL_DIR` is set, when it returns `None`.
  - Leave both `REGISTRY` values at `None` until T062.
- [X] T010 [P] In `ember/cfg/config.py`:
  - Set `DEFAULTS["max_request_length"] = None`.
  - Replace the D-002 comment with: unset (`None`) means the loaded model's measured
    default, resolved in `ember/serving/limits.py`; `0` disables the cap; a positive value
    caps the full encoded request.
  - Do not import `ember.models` (L16–19).
- [X] T011 Create `ember/serving/limits.py`. It stays torch-free: imports only stdlib,
  pydantic, `..cfg.config`, `..models`, `.limit_source`, and `.governing_limit`.
  - Copy `FALLBACK_MAX_LENGTH = 32768` and `model_max_length()` from
    `ember/serving/runtime.py` (L47–48, L93–123); T015 deletes the originals.
  - Add `declared_max_length(model_dir) -> int | None`.
  - Add `FALLBACK_REQUEST_CAP = 32768` and
    `default_request_cap(registry_key) -> tuple[int, LimitSource]`.
  - Add `class Limits(BaseModel)`, frozen, with these field rules and with properties
    `enforced` and `governing` (a `GoverningLimit`):
    - "`max_length` ≥ 1, and never above the model's declared maximum when it is known"
    - "`max_request_length` ≥ 0; `0` means the cap is disabled"
    - the source sets in data-model.md
  - Add `resolve(declared, registry_key, *, max_length=None, max_request_length=None) ->
    Limits`. It implements the contracts/config.md table, clamps an operator
    `max_length` only when the declared maximum is known, and logs a warning whenever it
    clamps a value or ignores an invalid one.
  - Add `from_config(model_dir, registry_key) -> Limits`. It parses
    `config.resolve("max_length")` and `config.resolve("max_request_length")`, each of
    which may be an env `str`, an `int`, or `None`, and calls `resolve`.
  - Depends on T008–T010. Makes T003 pass.
- [X] T012 [P] Create `ember/serving/devices.py` containing `pick_device()` and
  `pick_dtype()`, copied unchanged from `ember/serving/runtime.py` (L166–207). T015
  deletes the originals.
- [X] T013 [P] In `ember/serving/media.py`, add `ALLOWED_MEDIA_KWARGS` (copied from
  `ember/serving/runtime.py` L74–88) and `check_media_kwargs(kwargs: dict[str, Any]) ->
  None`. It raises the same `ValueError` message as `runtime.py` L436–445. Makes T005 pass.
- [X] T014 [P] Create `ember/serving/request_size.py` with two pieces:
  - `@dataclass(frozen=True) class RequestSize` with `total`, `state`, `media`, and
    `fixed`, and a `__post_init__` that enforces `state + media + fixed == total`.
  - `measure(js, processor, request) -> RequestSize`, per R1 and R2:
    - full, no-media, and bare `encode_record` calls, all with `max_length=sys.maxsize`;
      text-only requests skip the no-media call
    - raises `RuntimeError` when `js` has no `encode_record`
    - lets every other exception propagate

  Makes T004 pass.
- [X] T015 Refactor `ember/serving/runtime.py`:
  - **Constructor**: `Engine.__init__(model_dir, device=None, dtype=None, model_name=None,
    limits: Limits | None = None)` stores `self.limits`.
    - Import the names directly (`from .limits import Limits, declared_max_length,
      resolve`), so the `limits` parameter doesn't shadow a module.
    - When `limits` is `None`, use `resolve(declared_max_length(model_dir), None)`, with
      no config read.
    - `self.max_length` becomes `self.limits.max_length`.
  - **Imports and moved code**: import `pick_device` and `pick_dtype` from `.devices`, and
    `check_media_kwargs` from `.media`. Delete the code T011–T013 copied out:
    `FALLBACK_MAX_LENGTH`, `model_max_length`, `pick_device`, `pick_dtype`,
    `ALLOWED_MEDIA_KWARGS`, and the inline allowlist check.
  - **Interim pre-check**: keep today's `str(state)` pre-check, but read the cap from
    `self.limits.max_request_length`. T034 replaces it.
  - **Scripts**: update `scripts/smoke_mps.py` (L24, L75) to import `model_max_length`
    from `ember.serving.limits`.

  Makes T006 pass.
- [X] T016 In `ember/serving/server.py` `lifespan` (L129–210), replace the
  `raw_length`/`raw_request_length` parsing (L164–165):
  - Hosted path: `limits.from_config(hosted_source.model_dir, None)`.
  - Registry path: `limits.from_config(model_dir, models.registry_key(name))`.
  - Pass `limits=` to `Engine` on both paths.

  Makes T007 pass.
- [X] T017 Checkpoint:
  - `make check`, `make lint`, and `make typecheck` are green.
  - `.venv/bin/python -c "import sys, ember.mcp.mcp_server, ember.commands.doctor,
    ember.serving.limits, ember.serving.request_size; assert 'torch' not in
    sys.modules"` passes.
  - `wc -l ember/serving/runtime.py` is below 445, the recorded debt. T074 confirms the
    final figure is below 400.

**Checkpoint**: Foundation ready. Each user story can now start.

---

## Phase 3: User Story 1 - See the real limits of the loaded model (Priority: P1) 🎯 MVP

**Goal**: An operator can see the effective maximum and the per-request cap, each with its
source, in the load log, in `/health`, and in `ember doctor`. A device-backed check proves
the announced limit matches the model's real encoding.

**Independent Test**: Start the server, then:
- Read `/health` and `ember doctor`. Both show both limits, labeled live.
- Stop the server. Doctor now labels them configured.
- Point doctor at an unreachable remote. It reports unknown.
- Run the model-backed FR-003 check (quickstart.md §2–§3).

### Tests for User Story 1 (write first; must fail)

- [X] T018 [P] [US1] In `tests/test_runtime_unit.py`, add a failing test for
  `Engine.describe()`:
  - It returns `model`, `device`, `dtype`, `max_length`, `max_length_source`,
    `max_request_length`, and `max_request_length_source`.
  - The values come from its `Limits`, and the sources are their `LimitSource` string
    values.
  - It still omits `model_dir` (I-001).
- [X] T019 [P] [US1] In `tests/test_http_api.py`, add failing tests that use the TestClient
  and the `_FakeEngine` from T007:
  - `/health` `engine` carries `max_length_source`, `max_request_length`, and
    `max_request_length_source`.
  - `lifespan` logs exactly one line (assert with `caplog`) in the format
    `limits: enforced {E} tokens; max_length {M} ({src}), max_request_length {C} ({src})`,
    where `{C}` is `disabled` when the cap is `0`.
- [X] T020 [P] [US1] In `tests/test_cli.py`, add failing tests:
  - `endpoint_status()` returns the health body's `engine`. Extend
    `test_endpoint_status_marks_reachable_when_health_returns_body` (L507).
  - `ember doctor` prints the limits line from contracts/cli.md for each situation, using
    the existing `sandbox`, `models.resolve_dir`, `process.health`, and
    `endpoint_cmd.remote_health` monkeypatch patterns:
    - **live local**: `process.health` returns a body with the limit fields, so the line
      ends `live from local server`
    - **live remote**: `EMBER_SERVER_URL=https://decisions.example.com` and
      `remote_health` returns a body, so the line ends
      `live from https://decisions.example.com`
    - **configured**: `process.health` returns `None` and `sandbox` has no `config.json`,
      so the line shows `max_length 32768 (fallback)` and ends
      `configured, server not running`
    - **unreachable remote**: `remote_health` returns `None`, so the line is
      `limits: unknown; remote endpoint unreachable`
    - **older server**: the body's `engine` lacks the fields, so the line is
      `limits: unknown; the server does not report limits (older ember)`
  - Doctor's exit code is unchanged in every case.
- [X] T021 [P] [US1] Create `tests/test_limits_model.py` with `pytestmark =
  pytest.mark.model`. These tests need only the snapshot files, no weights in memory.
  - **Declared maximum**: `limits.declared_max_length(models.resolve_dir(name))` is
    `262144` for `flash`, and for `full` when it is pulled.
  - **FR-003**:
    - Load `AutoProcessor.from_pretrained(dir, local_files_only=True)` and
      `runtime.joint_module(dir)`.
    - Build a string state of exactly N tokens by repeating a word the tokenizer encodes
      as one token, and confirm the count with the tokenizer.
    - Assert `request_size.measure(...).state == N` and that `.total` equals
      `len(js.encode_record(processor.tokenizer, request, max_length=sys.maxsize,
      processor=processor).input_ids)`.

### Implementation for User Story 1

- [X] T022 [US1] In `ember/serving/runtime.py`, extend `Engine.describe()` with
  `max_length_source`, `max_request_length`, and `max_request_length_source` (string
  values) from `self.limits`, and update its docstring. Makes T018 pass.
- [X] T023 [P] [US1] In `ember/serving/server.py` `lifespan`, log one INFO line after the
  engine is built:
  `limits: enforced {E} tokens; max_length {M} ({src}), max_request_length {C} ({src})`,
  with `{C}` set to `disabled` when the cap is `0`. Makes T019 pass.
- [X] T024 [P] [US1] In `ember/commands/endpoint.py` `endpoint_status()` (L80–113), add an
  `"engine"` key to the returned dict: the health body's `engine`, or `None`.
- [X] T025 [US1] In `ember/commands/doctor.py`, add
  `_doctor_limits(info, status, model_dir, registry_key)` and call it after the
  `endpoint` line in `cmd_doctor` (L197–206). Makes T020 pass.
  - **Model directory and registry key**: compute them the way `_doctor_check_models`
    does. A configured hosted source gives `(hosted_source.model_dir, None)`; otherwise
    use `(models.resolve_dir(selected), models.registry_key(selected))`.
  - **Line selection**, with formats exactly as contracts/cli.md:
    - **live**: `status["engine"]` contains `max_request_length`. The line ends
      `live from local server` for a local endpoint, or `live from {url}` for a remote one.
    - **configured**: the endpoint is local and nothing answers. Compute the values with
      `limits.from_config(...)`; the line ends `configured, server not running`.
    - **unknown**: either of the two `unknown` lines.
  - Never import torch, and never change the exit code.
- [ ] T026 [US1] Checkpoint:
  - T018–T021 are green: `make check`, plus `make test` for T021.
  - Run quickstart.md §3 for real:
    - `ember start`, then check `/health`, `ember logs | grep "limits:"`, and
      `ember doctor`
    - `ember stop`: doctor shows configured
    - `EMBER_SERVER_URL=https://ember.invalid ember doctor`: doctor shows unknown (a
      loopback URL such as `https://127.0.0.1:9` counts as the local endpoint)

**Checkpoint**: US1 is fully functional and testable on its own.

---

## Phase 4: User Story 2 - Never answer on silently shortened evidence (Priority: P1) 🎯 MVP

**Goal**: Any request over the enforced limit gets an actionable refusal that states its
exact token split. Nothing is ever silently shortened, and the refusal reaches the agent
intact.

**Independent Test**: Send over-limit dictionary, string, and image requests under three
configurations: the default, the cap disabled, and a reduced `EMBER_MAX_LENGTH`. Each
gets a 413 with the contract message. Every served request's `usage.input_tokens` equals
its counted total. The MCP tool error text is intact (quickstart.md §4).

### Tests for User Story 2 (write first; must fail)

- [X] T027 [P] [US2] In `tests/test_request_size.py`, add failing tests for
  `refusal_message(size, limits, declared)` against contracts/http-api.md:
  - **Template**: the output matches the exact template, and starts with
    `request too large: {total} tokens exceeds the {limit}-token`.
  - **Limit name**: `per-request cap (EMBER_MAX_REQUEST_LENGTH)` when
    `limits.governing is GoverningLimit.CAP`; otherwise
    `maximum length (EMBER_MAX_LENGTH)`.
  - **Operator hint when the maximum governs**:
    - `Operators can raise EMBER_MAX_LENGTH up to the model's {declared} tokens.` when
      `max_length_source` is `operator`
    - `This is the model's own maximum and cannot be raised.` when it is `model` or
      `fallback`
  - **Advice**: the "questions alone exceed the limit" text when `fixed > limit`.
  - **Constraints**: the message contains no `/` and no `\`, is ASCII, and is at most 600
    characters.
- [X] T028 [P] [US2] In `tests/test_runtime_unit.py`, rewrite the D-002 behavioral tests
  (L950–1078) for full counting, and add failing tests. Use fake joint modules that have
  both `encode_record` and `systemone`.
  - **Refuse or serve**: a request is refused when `total > limits.enforced` and served
    when `total == limits.enforced`.
  - **Enforced limit**: it is `min(cap, max)`, including when the cap is `0` and
    `max_length` is reduced (FR-007).
  - **Error contents**: `RequestTooLargeError` carries `.size` and `.limits`, and its
    `str()` equals `refusal_message(...)`.
  - **Malformed request**: a fake `encode_record` that raises `KeyError` skips the check,
    and the fake `systemone`'s `ValueError` surfaces.
  - **Missing counter**: a module without `encode_record` raises `RuntimeError`.
  - **Invariant**: a served response whose `usage.input_tokens` differs from the counted
    total raises `RuntimeError` and logs an error (R2).
  - **Ordering**: media are decoded and `check_media_kwargs` runs before counting. A
    disallowed key raises `ValueError` without any `encode_record` call.
- [X] T029 [P] [US2] In `tests/test_http_api.py`, add failing TestClient tests with a fake
  engine:
  - `RequestTooLargeError` maps to 413 with the body `{"detail": <message>}`; the body
    shape is unchanged. Build the fake engine's error with the new signature,
    `RequestTooLargeError(refusal_message(size, limits, 262144), size=size,
    limits=limits)`, and assert `detail` equals that message. The test then fails until
    T032 and T034 land.
  - A `RuntimeError` from the invariant maps to 500.
  - `ember_advise_requests_total{status="413"}` increments, as read from `/metrics`.
- [X] T030 [P] [US2] In `tests/test_mcp_tool.py`, add a failing stub-endpoint test (see
  contracts/mcp-tool.md):
  - **Setup**: use the existing `stub_env` and `stub_server` fixtures. The stub answers
    with status `413`, `raw=json.dumps({"detail": MESSAGE})`, and a JSON content type,
    where `MESSAGE` is in the contract format.
  - **Assertion**: call `mcp_server.advise` the way the neighboring stub tests do. It
    must raise `ToolError` with text equal to `"ember server error 413: " + MESSAGE`,
    character for character.
  - **End to end** (Article XI §11.4): add a `@pytest.mark.model` test that uses the
    `base_url` session server and `mcp_stdin_params`. Read the enforced limit from
    `/health` `engine`, call the `advise` tool over MCP stdio with a string state larger
    than it, and assert the tool error text starts with
    `ember server error 413: request too large:` and contains `Split: state`. The
    refusal happens before inference, so the test is fast.
- [X] T031 [P] [US2] In `tests/test_limits_model.py`, add failing model-backed tests:
  - **Exact totals**: for a dict state, a string state, and a state with one inline PNG
    (built like `tests/test_http_api.py::test_systemone_accepts_an_inline_image`),
    `measure(...).total == len(js.encode_record(..., max_length=sys.maxsize,
    processor=processor).input_ids)`. That is zero drift, so the ±1% bar holds a
    fortiori. Also check `state + media + fixed == total`.
  - **Boundary and invariant**: use a module-scoped in-process
    `runtime.Engine(models.resolve_dir("flash"), limits=...)`, so the model loads once,
    and `monkeypatch.setattr(engine, "limits", ...)` per case. First measure a request.
    - With the cap at its total, it is served, and `usage.input_tokens` equals the total.
    - With the cap at total − 1, it is refused.
  - **Refusal matrix (SC-002)**: parametrize over {dict, string, image} states × three
    configurations: the default cap, taken from `limits.default_request_cap("flash")`
    (32,768 until T062 sets the measured value); cap `0` with `max_length=1024`; and cap
    `1024` with the declared maximum.
    - Every over-limit request is refused, and nothing is served.
    - Each message names the governing setting (`EMBER_MAX_REQUEST_LENGTH` or
      `EMBER_MAX_LENGTH`).
  - **Huge state (FR-014)**: a string state of about 1M tokens raises
    `RequestTooLargeError` in under 60 seconds. While it runs, a thread polls the test
    process's RSS every 50 ms (`ps -o rss= -p <pid>`); assert RSS grows by less than
    2 GiB. Run it a second time with the cap disabled (`0`) and `max_length` at the
    declared maximum: the refusal names `EMBER_MAX_LENGTH` and says this is the model's
    own maximum, which cannot be raised.

### Implementation for User Story 2

- [X] T032 [US2] In `ember/serving/request_size.py`, implement
  `refusal_message(size, limits, declared)` exactly as contracts/http-api.md specifies.
  Makes T027 pass.
- [X] T033 [P] [US2] In `ember/serving/server.py`:
  - Update the `/v1/systemone` `responses` entry for 413 to read: "Encoded request
    exceeds the enforced limit; detail carries the token split".
  - Update the endpoint docstring to match.
  - Keep the mapping `RequestTooLargeError → 413 detail=str(exc)`, and confirm that a
    `RuntimeError` yields 500 through the existing middleware.

  Makes T029 pass with T034.
- [X] T034 [US2] In `ember/serving/runtime.py` `_run_advise`, replace the interim
  `str(state)` pre-check. Makes T028 pass.
  - **Build the request first**: decode media and call `media.check_media_kwargs`.
  - **Measure**: call `size = request_size.measure(js, self.processor, request)`. Catch
    `KeyError`, `TypeError`, `AttributeError`, and `ValueError`, and set `size = None` on
    any of them.
  - **Refuse**: if `size` is set and `size.total > self.limits.enforced`, raise
    `RequestTooLargeError(refusal_message(...), size=size, limits=self.limits)`.
    - When a per-call `max_length` override is given, the enforced value uses
      `min(cap, override)`.
  - **Invariant**: after `systemone`, if `size` is set and
    `response["usage"]["input_tokens"] != size.total`, log an error and raise
    `RuntimeError("size check mismatch; refusing to answer from a possibly shortened
    input")`.
  - **Error class**: update `RequestTooLargeError`'s docstring and attributes.
- [X] T035 [P] [US2] Update D-002 in `docs/stride-review.md` (rows L104–105 and L535,
  detail L542–543, summary L727–728) and in `docs/stride-tracker.csv` (row 26) to describe
  the new mechanism. The status stays `fixed`. The new description:
  - The mitigation counts the full encoded request (state, media, questions, schema,
    prompt wrapper) using upstream `encode_record`, in `ember/serving/request_size.py`.
  - It is enforced in `ember/serving/runtime.py`.
  - Limits come from `ember/serving/limits.py`.
- [X] T036 [US2] Update `AGENTS.md` in the same change as the MVP (constitution workflow
  gate 4):
  - **Header**: refresh the "Last updated" line.
  - **Project structure tree**: add `ember/serving/limits.py`, `limit_source.py`,
    `governing_limit.py`, `request_size.py`, and `devices.py`.
  - **"What to watch out for"**: replace the `max_length` bullet with the counting and
    refusal rules. That bullet cites `runtime.model_max_length`, which moves to
    `ember/serving/limits.py`. The new rules:
    - size checks use upstream `encode_record`, never `str(state)`
    - refusals never truncate
    - agent-facing error text contains no `/`
    - an unset `max_request_length` means the model's measured default (32,768 until
      measured)
  - **Testing table**: add rows for `tests/test_limits.py`, `tests/test_request_size.py`,
    and `tests/test_limits_model.py`. In the `tests/test_runtime_unit.py` row, note that
    the model-max-length tests moved to `tests/test_limits.py`; in the
    `tests/test_media.py` row, add the allowlist tests.
  - **Recent Changes**: add an entry for exact counting, refusal, and limit reporting.
- [ ] T037 [US2] Checkpoint:
  - T027–T031 are green: `make check`, plus `make test` for T031.
  - Run quickstart.md §4 for real:
    - cap 1024: 413 with the split
    - cap 0 plus `EMBER_MAX_LENGTH=1024`: the model-maximum refusal
    - an image request: the split shows the media share
    - through MCP: the `ToolError` arrives intact

**Checkpoint**: US1 and US2 both work independently. The MVP safety guarantee is in place.

---

## Phase 5: User Story 3 - Limits chosen from measured quality, not from a default (Priority: P2)

**Goal**: A repeatable long-context probe records, for each length and evidence depth:
accuracy, calibration, peak memory, and latency. A pre-declared rule (FR-010) uses those
results to pick each registered model's default cap. The resulting decision supersedes
D-002.

**Independent Test**:
- `make eval-context-smoke` writes a valid run, and `--rescore` reproduces its
  `summary.json` byte for byte.
- The canonical run records every length and depth, with a run ID.
- Recomputing the rule from the snapshot gives each registered model's shipped default.
- The decision note supersedes D-002.

(See quickstart.md §6–§7.)

### Setup for User Story 3

- [X] T038 [P] [US3] Create the probe package markers `evals/context/__init__.py` and
  `evals/context/records/__init__.py`. They are docstring-only, with no imports (Article X
  §10.1). Also create the tracked snapshot directory with `evals/context/runs/.gitkeep`.
- [X] T039 [P] [US3] Vendor the filler corpus as `evals/context/filler.txt` (R9):
  - **Source**: Project Gutenberg eBook #2701, *Moby-Dick; or, The Whale* by Herman
    Melville (public domain), UTF-8 text from
    `https://www.gutenberg.org/ebooks/2701.txt.utf-8`.
  - **Trimming**: keep only the text between the `*** START OF THE PROJECT GUTENBERG
    EBOOK` and `*** END OF THE PROJECT GUTENBERG EBOOK` markers, excluding the markers
    themselves, and remove any remaining "Project Gutenberg" references.
  - **Provenance**: record the file's SHA-256, and add a `THIRD_PARTY_NOTICES.md` entry
    with the title, author, source URL, public-domain status, a note that the boilerplate
    was stripped, and the SHA-256.
- [X] T040 [P] [US3] Create `evals/eval/provenance.py` by moving four helpers out of
  `evals/eval/run_evals.py` and making them public:
  - `git_hash()` (was `_git_hash`, L80)
  - `cpu()` (was `_cpu`, L93)
  - `host_info()` (was `_host`, L105)
  - `model_spec_info(model_dir)` (was `_model_spec`, L120)

  Add `git_dirty()`, which returns `True` when `git status --porcelain` prints anything.
  Then make `run_evals.py` import and use these helpers. Its behavior and the shape of
  `results.json` must not change, and `tests/test_eval_report.py` and
  `tests/test_eval_benchmark.py` must stay green.

### Tests for User Story 3 (write first; must fail; one file, so run them in order)

- [X] T041 [US3] Create `tests/test_context_probe.py` with failing tests for the records in
  data-model.md §Long-context probe records:
  - **Enums**: `Depth` is `start`/`middle`/`end`; `RowStatus` is `ok`/`oom`/`error`;
    `FailureReason` is `memory`/`oom`/`accuracy`/`brier`.
  - **`ProbeManifest`**:
    - `run_id` "matches `^context_\d{8}T\d{6}Z$`, or the value given by `--run-id`"
    - `lengths` are "ascending ints; the first is 2048"
  - **`ProbeRow`**:
    - "the parts sum to the total; for an `ok` row, total ∈ [L − 32, L]"
    - `answers` is "empty unless the status is `ok`"
    - "`peak = rss_start + driver_peak`"
  - **Manifest subset**: `exploratory_item_ids` has `exploratory_items` entries, all
    drawn from `item_ids`.
  - **Verdicts**: `LengthVerdict.reason` and `ModelVerdict.first_failure_reason` accept
    only `FailureReason` values or `None`; `failed_depth` and `first_failure_depth`
    accept only `Depth` values or `None`.
  - **Round trip**: a JSON round trip preserves every record model.
  - **Provenance**: `evals.eval.provenance.git_dirty()` returns a `bool`.
- [X] T042 [US3] Add failing tests to `tests/test_context_probe.py` for
  `evals/context/filler.py` and `evals/context/padding.py`. Use a fake whitespace
  tokenizer and a fake counter.
  - **`load_filler()`**: raises `ValueError` on a SHA-256 mismatch.
  - **`offset_for(item_id, needed, available)`**: deterministic, and always in range.
  - **`build_state(...)`**:
    - for each `Depth`, the counted total lands in `[target − 32, target]`
    - the evidence comes first for `start`, sits in the center for `middle`, and comes
      last for `end`
    - the evidence is embedded verbatim between `"\n\n"` separators
    - raises `ValueError` when the evidence alone exceeds `target − 32`
- [X] T043 [US3] Add failing tests to `tests/test_context_probe.py` for
  `evals/context/scoring.py` and `evals/context/rule.py`:
  - **Per-item scores**: accuracy and Brier use only the `noul` and `choice` questions,
    via `evals.metrics.score_question`, `brier_binary`, and `brier_multiclass`.
  - **Pairing**: deltas pair by item id at the same depth.
  - **Intervals**: `bootstrap_ci` intervals are deterministic with `seed=0` and
    `resamples=10000`.
  - **The rule**:
    - a length passes only if, at every depth, accuracy ≥ the 2K accuracy − 0.02 and
      Brier ≤ the 2K Brier + 0.02, and its peak memory fits the budget
    - the cap is the longest length where it and every shorter length pass, so a pass
      after a failure is ignored
    - a memory failure or an `oom` fails that length and every longer one
    - each failing `LengthVerdict` carries a `FailureReason`, plus `failed_depth` for an
      `accuracy` or `brier` failure
    - when no length passes, `cap` is `None`
- [X] T044 [US3] Add failing tests to `tests/test_context_probe.py` for
  `evals/context/summarize.py`, resume, `evals/context/items.py`, the sizing gate, and
  `evals/context/reproduce.py`. Write the synthetic rows in the `rows-<model>.jsonl`
  shape.
  - **`summarize(run_dir)`**: two calls produce byte-identical output, following the
    contracts/eval-context.md serialization rules. Each `LengthVerdict` carries
    `latency_ms_median` over that length's `ok` rows.
  - **Resume**: a torn last line is dropped, and keys that already finished are skipped.
  - **Items**: selection keeps only text-only items and records every exclusion with its
    reason. The seed fixes `exploratory_item_ids`: the same seed gives the same subset.
  - **Sizing gate** (`scoring.projected_half_width`): passes if and only if
    `1.96 · sd(delta) / √n ≤ 0.02`.
  - **Reproduce comparator**: flags any of these:
    - a token-count difference
    - a probability difference greater than 0.001
    - a change in correctness
    - a change in cap (full reproductions only; a subset compares rows only)
  - **No MPS**: with `torch.backends.mps.is_available()` monkeypatched to `False`,
    `run_context.main(["--smoke"])` returns 1 with an actionable message.
- [X] T045 [US3] Add failing tests to `tests/test_context_probe.py` for
  `evals.context.memory_sampler.MemorySampler`. Inject fake `read_driver` and `read_rss`
  functions and a short `interval`.
  - The peak is the highest driver value sampled during the block.
  - `peak_bytes == rss_start_bytes + driver_peak_bytes`.
  - The sampling thread stops on exit.
  - An exception raised inside the block propagates.

### Implementation for User Story 3

- [X] T046 [P] [US3] Create three `StrEnum`s, one class per file:
  - `evals/context/records/depth.py`: `Depth`
  - `evals/context/records/row_status.py`: `RowStatus`
  - `evals/context/records/failure_reason.py`: `FailureReason` (`memory`, `oom`,
    `accuracy`, `brier`)
- [X] T047 [US3] Create the Pydantic records in `evals/context/records/`, one class per
  file. Use the fields exactly as data-model.md defines them. Makes T041 pass.
  - **Files**: `probe_model.py` (`ProbeModel`), `probe_manifest.py` (`ProbeManifest`),
    `probe_row.py` (`ProbeRow`), `cell_result.py` (`CellResult`), `length_verdict.py`
    (`LengthVerdict`), `model_verdict.py` (`ModelVerdict`), and `probe_summary.py`
    (`ProbeSummary`).
  - **Constraints to enforce**:
    - `run_id` matches `^context_\d{8}T\d{6}Z$` unless explicitly given
    - `lengths` ascending, with the first equal to 2048
    - `length_tolerance_tokens` 32
    - `tolerance_accuracy` and `tolerance_brier` 0.02
    - `bootstrap_resamples` 10000, `bootstrap_level` 0.95, `seed` 0
    - `exploratory_items` 48
    - in `ProbeRow`: the token parts sum to the total; an `ok` row's total is in
      [L − 32, L]; `answers` is empty unless the status is `ok`;
      `peak_bytes = rss_start_bytes + driver_peak_bytes`
    - (`model`, `item_id`, `length`, `depth`) is unique within a run
    - `exploratory_item_ids` has `exploratory_items` entries, all drawn from `item_ids`
    - `LengthVerdict`:
      - `reason` is a `FailureReason`, or `None` when the length passes
      - `failed_depth` is a `Depth`, set only for an `accuracy` or `brier` failure
      - `latency_ms_median` is `None` when no row ran
    - `ModelVerdict`: `first_failure_reason` is a `FailureReason` and
      `first_failure_depth` is a `Depth`; each is `None` when nothing failed
- [X] T048 [P] [US3] Create `evals/context/filler.py` with:
  - `FILLER_PATH` and `FILLER_SHA256` (the digest from T039)
  - `load_filler()`, which verifies the SHA-256
  - `filler_ids(tokenizer)`, which tokenizes the text once with `add_special_tokens=False`
  - `offset_for(item_id, needed, available)`: the SHA-256 of the item id, taken modulo
    the free span
- [X] T049 [US3] Create `evals/context/padding.py` with
  `build_state(evidence, filler_ids, tokenizer, depth, target, count, *, offset,
  tolerance=32)`. It decodes slices of the filler, assembles
  `before + "\n\n" + evidence + "\n\n" + after` for the given depth, and adjusts the
  filler until `count(state)` lands in `[target − tolerance, target]`. The real counter
  is `request_size.measure(...).total`. With T048, makes T042 pass.
- [X] T050 [P] [US3] Create `evals/context/memory_sampler.py` with `class MemorySampler`, a
  context manager. Its constructor takes three injected parameters:
  - `read_driver`, defaulting to `torch.mps.driver_allocated_memory`
  - `read_rss`, defaulting to `ps -o rss= -p <pid>`, converted from KiB to bytes
  - `interval`, defaulting to `0.02`

  When MPS is available, it calls `torch.mps.synchronize()` before and after the block.
  Makes T045 pass.
- [X] T051 [P] [US3] Create `evals/context/scoring.py` with:
  - `item_scores(item, answers)`
  - `paired_deltas(base, other)`
  - `delta_ci(deltas, *, resamples, level, seed)`, which wraps
    `evals.metrics.bootstrap_ci`
  - `cell_ece(...)`, which wraps `evals.metrics.calibration_error`. It is reported only
    and does not gate.
  - `projected_half_width(deltas)`: `1.96 · sd(deltas) / √n`, used by the sizing gate
- [X] T052 [US3] Create `evals/context/rule.py` with a pure function
  `evaluate(cells, memory, *, tolerance_accuracy, tolerance_brier, budget_bytes) ->
  tuple[list[LengthVerdict], ModelVerdict]` that implements R12. With T051, makes T043
  pass.
- [X] T053 [US3] Create `evals/context/summarize.py` with
  `summarize(run_dir) -> ProbeSummary` and `write_summary(run_dir)`. Output must be
  deterministic, and is written with `evals.export.write_atomic`:
  - floats rounded to 6 decimals
  - `json.dumps(..., sort_keys=True, indent=2)`
  - rows sorted by (model, length, depth, item)
  - `inputs_sha256` holding the digests of the rows files and the manifest
  - each `LengthVerdict.latency_ms_median`, computed over that length's `ok` rows
- [X] T054 [US3] Create `evals/context/worker.py` with
  `run_model(run_dir, model, *, pilot=False) -> int`:
  - **Engine**: build an in-process `runtime.Engine(models.resolve_dir(model,
    override=False), limits=Limits(max_length=<declared>,
    max_length_source=LimitSource.MODEL, max_request_length=0,
    max_request_length_source=LimitSource.OPERATOR))`.
  - **Memory check**: go through the lengths in ascending order. At each length, run the
    first item at all three depths inside `MemorySampler`, and record these three
    inferences as the first item's rows for that length (the quality pass skips them by
    key).
    - Fail the length when `peak_bytes` exceeds the model's budget, or when an MPS
      "out of memory" `RuntimeError` occurs; on OOM, call `torch.mps.empty_cache()`.
    - A failed length also fails every longer length.
    - Log a warning when `rss_start_bytes` exceeds 25% of the model's
      `ModelSpec.approx_bytes`: peak memory may be double-counted (R11).
  - **Quality cells**: run all items before the first failing length. After it, run only
    the manifest's `exploratory_item_ids`, marked `exploratory`.
  - **Rows**: append one `ProbeRow` per inference, then flush and fsync. On resume, drop
    a torn last line and skip keys that already finished.
  - **Rule**: re-evaluate the rule after each length finishes.
- [X] T055 [US3] Create `evals/context/items.py`, `evals/context/reproduce.py`, and
  `evals/context/run_context.py`, keeping each under 400 lines (Article X §10.3). Makes
  T044 pass.
  - **`items.py`**:
    - select the 232 text-only items, and record each excluded item with its reason
    - draw the seeded 48-item `exploratory_item_ids`, stratified by category
    - assemble the `ProbeManifest`: provenance from T040, the rule parameters, and the
      memory budgets (flash `32 * 2**30`, full `64 * 2**30`)
  - **`reproduce.py`**: the comparator from contracts/eval-context.md. It compares
    verdicts only for a full reproduction; a reproduction narrowed with `--items N`
    compares rows only.
  - **`run_context.py`**: `main(argv: list[str] | None = None) -> int`. It only
    orchestrates.
  - **Flags**: everything in contracts/cli.md, plus internal
    `--worker --run-dir --model [--pilot]` flags.
  - **Imports**: use the same repo-root `sys.path` bootstrap as
    `evals/eval/run_evals.py`.
  - **Device**: when `torch.backends.mps.is_available()` is false, exit 1 with an
    actionable message. The probe measures MPS only.
  - **Run flow**:
    - warn if `process.is_up(...)` finds a running ember server
    - run the pilot sizing gate; exit 2 if it fails
    - launch one worker subprocess per model with
      `subprocess.run([sys.executable, __file__, "--worker", ...])`
    - call `summarize`, then print one verdict line per model
  - **Modes**: `--rescore`, `--reproduce`, `--snapshot`, `--resume`, and `--smoke`.
    `--snapshot` copies the run into `evals/context/runs/<id>/` with
    `evals.export.copy_atomic`.
- [X] T056 [US3] Wire up `ember eval context`, test first.
  - **Test**: add a failing test to `tests/test_cli.py` that `ember eval context --smoke`
    calls a monkeypatched `evals.context.run_context.main` with `["--smoke"]`.
  - **Parser**: in `ember/commands/parser.py`, add a `cmd_context` parameter to
    `register_eval`, and a `context` subparser with `add_help=False` and
    `context_args` (`nargs=argparse.REMAINDER`), modeled on the `agent` subparser.
  - **Handler**: add `cmd_eval_context(args)` to `ember/commands/eval.py`. It lazily
    imports `from evals.context.run_context import main`, raising `_EVAL_CHECKOUT_ERROR`
    on `ImportError`, and returns `main(args.context_args)`.
  - **CLI**: in `ember/cli.py`, import the handler (imports at L21–26) and pass
    `cmd_context=cmd_eval_context` to `register_eval` (call at L105–112).
- [X] T057 [P] [US3] In `shared/testing.mk`, add `eval-context` and
  `eval-context-smoke` after `eval-snapshot`:
  - one-line recipes: `$(PY) evals/context/run_context.py` and
    `$(PY) evals/context/run_context.py --smoke`
  - each with prerequisite `$(EMBER)` and `##` help text
  - add both to the `.PHONY` line (L4)
- [ ] T058 [US3] Smoke run (quickstart.md §6):
  - `make eval-context-smoke` writes `results/context/<run_id>/manifest.json`,
    `rows-flash.jsonl`, and `summary.json`.
  - After `ember eval context --rescore <run_id>`, `summary.json`'s SHA-256 is unchanged.
  - Memory sanity check (R11). In `rows-flash.jsonl`:
    - `rss_start_bytes` is at most 25% of flash's `approx_bytes` (18 GiB)
    - the 2K `driver_peak_bytes` is 0.9–1.5× `approx_bytes`

    If either check fails, stop and revise the peak-memory formula before T059.
- [ ] T059 [US3] Pilot: run `ember eval context --pilot`. If it exits 2:
  - stop US3 here
  - record the projected half-width and the item count in a new vault discovery,
    `vault/discoveries/<date>-probe-items-cannot-resolve-the-tolerance.md`, linked from
    `vault/ember.md`
  - ask the maintainer how to proceed (R10)
- [ ] T060 [US3] Canonical run, on a clean tree (`git status` empty, and
  `results/context/<run_id>/manifest.json` shows `git_dirty: false`):
  - Run `make eval-context`. After an interruption, resume with
    `ember eval context --resume <run_id>`.
  - Spot-check reproducibility: `ember eval context --reproduce <run_id> --items 24` must
    exit 0. It compares rows only, because a 24-item subset can't reproduce the run's
    verdicts.
  - Snapshot it with `ember eval context --snapshot <run_id>`, creating the tracked copy
    under `evals/context/runs/<run_id>/`.
- [ ] T061 [US3] Review `evals/context/runs/<run_id>/summary.json` before changing any
  default:
  - each model's per-length verdicts and first failure
  - peak memory against the budgets and against `recommended_max_memory_bytes`
  - that 2K accuracy is consistent with the benchmark's accuracy on the same items
  - that no length is marked `oom` unexpectedly

  Record anything surprising in the T063 decision note.
- [ ] T062 [US3] Set the measured caps and update everything that states them, in one
  change:
  - **Registry**: in `ember/models.py` `REGISTRY`, set `max_request_length` for `flash`
    and `full` to each model's `verdicts[].cap` from
    `evals/context/runs/<run_id>/summary.json`. A `None` cap leaves the entry at `None`,
    and the decision note explains why.
  - **Stated numbers**: update every number in:
    - `ember/agent_kit/instructions.md`
    - `ember/agent_kit/ember-advise/SKILL.md` and its mirror
      `packages/claude-plugin/skills/ember-advise/SKILL.md`
    - `README.md`
    - `COMPATIBILITY.md`
  - **Test**: add a case to `tests/test_limits.py` that recomputes the rule from the
    snapshot and asserts that each registry cap equals the recomputed verdict (SC-004).
    Recompute with
    `evals.context.summarize.summarize(Path("evals/context/runs/<run_id>"))`, which reads
    only the rows and the manifest.
  - **Range test**: add a case to `tests/test_limits_model.py` asserting that every
    non-`None` `REGISTRY[name].max_request_length` lies within [2048,
    `limits.declared_max_length(models.resolve_dir(name))`] (data-model.md §ModelSpec).
  - `make test` passes; the US4 kit-numbers test checks the text.
- [ ] T063 [US3] Write `vault/decisions/<date>-measured-per-model-request-caps.md` from
  `vault/_meta/templates/decision.md`:
  - **Tags**: `type/decision`, `domain/runtime`, `domain/models`, `status/draft`.
  - **Contents**:
    - the FR-010 rule exactly as pre-declared
    - the snapshot path and run ID
    - each model's cap and first failure
    - peak memory against `recommended_max_memory` (R11)
    - that this decision supersedes D-002
    - that the caps hold only for the measured `revision`s: re-run the probe and re-set
      the caps whenever a model's `revision` changes (Article V, Article III §3.3)
  - Link it under Decisions in `vault/ember.md`, and confirm `make vault-audit` is clean.
- [ ] T064 [US3] Mark D-002 superseded in `docs/stride-review.md` and
  `docs/stride-tracker.csv`. The fixed 32,768 default is replaced by measured per-model
  caps; link the T063 note and the snapshot. Also add a new open DoS entry for the
  out-of-scope exposure to multi-GB request bodies (R15).
- [ ] T065 [US3] Checkpoint: quickstart.md §6–§7 complete, and `make test` green.

**Checkpoint**: US3 is complete. Each registered model's default cap is measured and
recorded.

---

## Phase 6: User Story 4 - Limits stated wherever model behavior is described (Priority: P3)

**Goal**: README configuration, COMPATIBILITY, `ember://guide`, and the `ember-advise`
skill each state:
- the effective limit
- why it has that value
- what happens to a request beyond it

The MCP instructions state the default cap. Every agent-facing surface, including the
`AGENTS.md` snippet, tells agents what to do when a request is refused (FR-008).

**Independent Test**: Read the four surfaces. Then confirm the guidance tells an agent
that an oversized request is refused (not truncated) and how to use the split.
`tests/test_agent_kit.py` proves that every number shown matches the resolver's defaults
(quickstart.md §5).

### Tests for User Story 4 (write first; must fail)

- [X] T066 [P] [US4] In `tests/test_agent_kit.py`, add failing tests per
  contracts/agent-kit.md:
  - **`instructions.md`**:
    - still at most 2048 bytes (the existing test)
    - says over-cap requests are refused and never truncated
    - contains `f"{limits.default_request_cap('flash')[0]:,}"`
  - **`SKILL.md`**:
    - contains each registered model's `default_request_cap(name)` value and the
      outside-the-registry fallback `default_request_cap(None)`
    - uses the words "refused" and "split"
    - explains why each value holds by saying both "measured" and "fallback" (FR-008)
    - every refusal-message fragment it quotes (`request too large:`, `Split: state`)
      appears in the output of `refusal_message(...)` for a sample `RequestSize` and
      `Limits`, so the skill cannot drift from the real message (Article III §3.1)
    - no longer contains "262,144-token window"
  - **`AGENTS.snippet.md`**: mentions refused requests and trimming the largest part.
  - **`README.md` and `COMPATIBILITY.md`** (SC-005): README's `EMBER_MAX_REQUEST_LENGTH`
    row and COMPATIBILITY's "Context length" bullet each contain every registered
    model's `default_request_cap(name)` value, written with a thousands separator, and
    each says that oversized requests are refused.

### Implementation for User Story 4

- [X] T067 [P] [US4] Edit `ember/agent_kit/instructions.md`:
  - Add one sentence, for example: "Requests over the token cap (32,768 for flash) are
    refused, never truncated; the error's split shows whether to cut state, media, or
    questions."
  - Trim existing wording so the file stays at or under 2048 bytes (check with `wc -c`).
  - Keep the Observed numbers unchanged (Article III §3.3).
- [X] T068 [P] [US4] Edit `ember/agent_kit/ember-advise/SKILL.md`:
  - Replace "inputs are capped at the model's 262,144-token window" (L85) with the
    enforced-limit rule.
  - Add a short "Size limits" passage covering:
    - the per-model defaults: flash, full, and models outside the registry
    - why each value holds: measured by the probe (cite its run ID), or the 32,768
      fallback until a model is measured
    - what counts toward a request: state, media, questions and schema, and the prompt
      wrapper
    - the refusal message shape, quoting the fragments `request too large:` and
      `Split: state` exactly as `refusal_message` produces them
    - what to do when refused
  - Copy the file byte for byte to `packages/claude-plugin/skills/ember-advise/SKILL.md`
    (enforced by `tests/test_distribution.py::test_plugin_skill_mirrors_the_agent_kit_skill`).
- [X] T069 [P] [US4] Edit `ember/agent_kit/AGENTS.snippet.md` to add one line: oversized
  requests are refused with a token split; trim the largest part and retry.
- [X] T070 [P] [US4] Edit `README.md`:
  - **Configuration**: update the `max_request_length` sentence (L274–276) and the
    `EMBER_MAX_LENGTH`/`EMBER_MAX_REQUEST_LENGTH` rows (L284–285) per contracts/config.md.
    Unset means the loaded model's measured default; the whole request counts; an
    oversized request is refused, never truncated.
  - **Metrics**: add `413` to the status list for `ember_advise_requests_total{status}`
    (L382).
  - **Benchmark**: add a "Long-context probe" paragraph covering `make eval-context`,
    what it measures, the rule, that it runs for hours, and where output goes
    (`results/context/`, with snapshots in `evals/context/runs/`).
  - **Make targets table**: add rows for `eval-context` and `eval-context-smoke`.
  - **Limits reporting**: after the Configuration table, add one sentence saying that
    `ember doctor` and `GET /health` (`engine`) report the loaded limits and their
    sources.
- [X] T071 [P] [US4] Rewrite the "Context length" bullet in `COMPATIBILITY.md` (L132–134)
  to cover:
  - the effective maximum: 262,144, declared by both models
  - the per-model caps: 32,768 as the interim fallback until measured, then the measured
    values with the probe run ID
  - full-request counting, including media; image-heavy requests near the cap may now be
    refused
  - the refusal behavior
  - the measurement device: MPS on an M4 Max with 128 GB
  - that the caps hold for the pinned revisions and are re-measured whenever a revision
    changes
- [X] T072 [US4] Checkpoint:
  - T066 is green.
  - `make test` passes `tests/test_agent_kit.py` and `tests/test_distribution.py`.
  - Run quickstart.md §5.

**Checkpoint**: All four user stories work independently.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Governance, agent docs, and the final gates across all stories.

- [ ] T073 [P] Update `AGENTS.md` for the probe and the measured caps. T036 already made
  the MVP edits.
  - **Project structure tree**: add `evals/context/`.
  - **Commands table**: add `make eval-context` and `make eval-context-smoke`.
  - **"What to watch out for"**:
    - add a probe bullet: it runs in-process, uses one worker per model, and is not a test
    - in the `max_request_length` bullet, replace "32,768 until measured" with the
      measured per-model caps
    - add a bullet: re-run `make eval-context` and re-set the caps whenever a model's
      `revision` changes
  - **Testing table**: add a row for `tests/test_context_probe.py`.
  - **Recent Changes**: add an entry for the probe and the measured caps.
- [X] T074 Check that `wc -l ember/serving/runtime.py` is under 400, then amend
  `.specify/memory/constitution.md`:
  - **Sync Impact Report**: prepend one for 3.1.1 → 3.1.2 (PATCH). It records that
    `ember/serving/runtime.py` was paid down to N lines by moving limits, sizing, media
    kwargs, and device selection out, and that the recorded 445 lines had grown to 471
    without being recorded.
  - **§10.18**: remove `runtime.py` from the oversize list and add it to the "previously
    tracked items now resolved" sentence.
  - **Version footer**: update it to `**Version**: 3.1.2 | … | **Last Amended**: <date>`.
- [X] T075 [P] Update
  `vault/discoveries/2026-10-09-request-size-checks-miss-what-the-model-sees.md`: note
  which findings this feature resolved, with file references, and bump `updated`. Then
  confirm `make vault-audit` is clean.
- [X] T076 Run the layer and import gate:
  `.venv/bin/python -c "import sys, ember.mcp.mcp_server, ember.commands.doctor,
  ember.serving.limits, ember.serving.request_size; assert 'torch' not in sys.modules"`.
  Also confirm that `ember/serving/runtime.py`, `request_size.py`, and `limits.py` import
  no FastAPI, httpx, or MCP modules (Article XIII §13.3).
- [X] T077 Run the full gates:
  - `make pr-ready`
  - `make test` (model-backed); note any pre-existing failures
  - `make test-cov`: coverage at or above the T001 baseline and at least 81%; never lower
    `fail_under` in `pyproject.toml`
  - `make vault-audit`
- [ ] T078 Run quickstart.md §1–§6 end to end on the reference machine. Record the size
  check's added latency on a warm short text request in the performance notes in
  `COMPATIBILITY.md` (L116). The target is 5% or less; it is informational only.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup, and blocks every user story.
- **US1 (Phase 3)** and **US2 (Phase 4)**: Depend only on Foundational. Both are P1; do
  them in order (US1 → US2) or in parallel. US2 ends with T036, the `AGENTS.md` update the
  MVP ships with.
- **US3 (Phase 5)**: Depends only on Foundational. It needs `Limits` and
  `request_size.measure`, but not US1 or US2. T058–T061 take hours to days of MPS
  compute.
- **US4 (Phase 6)**: Depends on Foundational (for `default_request_cap`) and on T032 (for
  T066's refusal-fragment check). It can run in parallel with US3. Whichever finishes
  second keeps the kit numbers in sync: T062 updates the text when the caps change.
- **Polish (Phase 7)**: Depends on every story. T074 needs T015 and T034 done, so that
  `runtime.py` is under 400 lines.

### Within Each Story

- Write the test tasks first, and confirm they fail.
- Order: records and models → services (`limits`, `request_size`, scoring, rule) →
  integration (engine, server, CLI, probe runner).
- Each story ends with a checkpoint that runs its quickstart section for real.

### Key Task Dependencies

- T011 ← T008, T009, T010
- T036 ← T025, T034
- T066 ← T032
- T015 ← T011, T012, T013, T014
- T016 ← T011, T015
- T025 ← T024
- T034 ← T032
- T047 ← T046
- T049 ← T048, T014
- T052 ← T047, T051
- T053 ← T047, T051, T052
- T054 ← T049, T050, T053
- T055 ← T040, T054
- T056 ← T055
- T058 ← T055, T057
- T059 ← T058
- T060 ← T059
- T061 ← T060
- T062 ← T061
- T063 ← T062
- T064 ← T063
- T074 ← T015, T034

---

## Parallel Examples

```text
# Phase 2 tests together (separate files):
Task: "T003 tests/test_limits.py"      Task: "T004 tests/test_request_size.py"
Task: "T005 tests/test_media.py"       Task: "T006 tests/test_runtime_unit.py"
Task: "T007 tests/test_http_api.py"

# Phase 2 leaf modules together:
Task: "T008 limit_source.py + governing_limit.py"  Task: "T009 ember/models.py"
Task: "T010 ember/cfg/config.py"             Task: "T012 ember/serving/devices.py"
Task: "T013 ember/serving/media.py"          Task: "T014 ember/serving/request_size.py"

# US1 tests together, then T023 and T024 together:
Task: "T018 test_runtime_unit"   Task: "T019 test_http_api"   Task: "T020 test_cli"   Task: "T021 test_limits_model"

# US2 tests together:
Task: "T027 test_request_size"   Task: "T028 test_runtime_unit"   Task: "T029 test_http_api"
Task: "T030 test_mcp_tool"       Task: "T031 test_limits_model"

# US3 setup together, then independent probe modules together:
Task: "T038 package markers"   Task: "T039 filler.txt"         Task: "T040 evals/eval/provenance.py"
Task: "T046 records enums"     Task: "T048 filler.py"          Task: "T050 memory_sampler.py"
Task: "T051 scoring.py"        Task: "T057 shared/testing.mk"

# US4: every edit is a separate file:
Task: "T067 instructions.md"   Task: "T068 SKILL.md + mirror"   Task: "T069 AGENTS.snippet.md"
Task: "T070 README.md"         Task: "T071 COMPATIBILITY.md"
```

---

## Implementation Strategy

### MVP first (both P1 stories)

1. Phase 1, then Phase 2. Foundational blocks everything else.
2. Phase 3 (US1): limits become visible everywhere. **Validate**: quickstart.md §3.
3. Phase 4 (US2): exact counting and refusal, never truncation. **Validate**: quickstart.md
   §4.
4. **Stop and ship**. Defaults stay at the interim 32,768 (`fallback`), and only the
   counting changes. Ship T036's `AGENTS.md` update and US4's first pass (Phase 6, interim
   numbers) in the same change, so the docs match the behavior (constitution workflow
   gate 4).

### Incremental delivery

5. Phase 5 (US3): build the probe, run it (hours to days, resumable), then set the
   measured caps (T062) and supersede D-002 (T063–T064).
6. Phase 6 (US4): if it already shipped, T062 has updated its numbers.
7. Phase 7: governance and the final gates.

### Parallel team strategy

After Phase 2:
- **Developer A**: US1, then US2.
- **Developer B**: the US3 probe code, T038–T057.
- **Developer C**: US4.

The long US3 runs (T058–T061) need the reference Mac to themselves.

---

## Notes

- **[P]** means a different file with no unmet dependency. Tasks in the same file (for
  example T041–T045 in `tests/test_context_probe.py`) run in order.
- **Commits**: one per task or logical group, using Conventional Commits with a scope.
  - `feat(ember): …` for `ember/`
  - `feat(evals): …` for `evals/`
  - `docs: …` for root docs
  - tests land in the same commit as the code they cover (Article XI)
- **Never delete a test to get green.** Moved tests (T003g) are moves, not deletions.
- **Article IV**: the probe never runs in `make check`, `make test`, or CI.
- **Article VII**: model-backed tests run on a maintainer's Apple Silicon machine.
- **Placeholders**: values in angle brackets (`<date>`, `<run_id>`, `<dir>`) and `N` are
  filled in at execution time. They are not open decisions.
