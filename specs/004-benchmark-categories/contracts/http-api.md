# Contract: HTTP API — `usage` token split

**Scope**: `POST /v1/systemone` response, `ember/serving/runtime.py`, README, tests.
**Status**: additive response-field change under constitution Article II; reviewed as an
API change (README and tests land with it).

## Before

```json
"usage": {"input_tokens": 220, "output_tokens": 0}
```

## After

```json
"usage": {
  "input_tokens": 220, "output_tokens": 0,
  "state_tokens": 34, "fixed_tokens": 186, "media_tokens": 0
}
```

Rules:
- `state_tokens + fixed_tokens + media_tokens == input_tokens` (the existing invariant
  already requires `input_tokens` to equal the counted total; the parts are the same
  `RequestSize` the limit check measured).
- Present on every `200`; absent on `413`/`422`/`503`/`500` (unchanged bodies).
- Text-only requests report `media_tokens: 0`.
- The MCP layer passes the body through unchanged; `AdviseInput` is untouched.
- A client older than this change ignores the fields; a harness newer than a server
  without them must not infer them (see [run-artifacts.md](./run-artifacts.md)).

## Tests

- `tests/test_runtime_unit.py`: `advise()` copies the `RequestSize` parts into `usage`;
  parts sum to `input_tokens`.
- `tests/test_http_api.py`: the three keys are present on `200` across `noul`/`choice`/
  `score`; absent on error bodies.
- `tests/test_mcp_tool.py`: the keys survive the MCP round trip (stub endpoint).
- README "Usage" example updated; `COMPATIBILITY.md` notes the minimum server version that
  returns the split.
