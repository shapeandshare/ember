# Contract: HTTP API (`/health` limits, `/v1/systemone` refusal)

**Feature**: `003-context-window-audit`
**Date**: 2026-10-09
**Scope**: Additive `/health` fields and the 413 refusal on `POST /v1/systemone`. This is
public API: change it together with README and `tests/test_http_api.py`.

## `GET /health`: additive `engine` fields

`engine` is `Engine.describe()`, or `null` while the model loads. The existing fields
(`model`, `device`, `dtype`, `max_length`) are unchanged. Three fields are added:

| Field | Type | Values |
|-------|------|--------|
| `max_length` | int | effective maximum (existing field) |
| `max_length_source` | string | `model`, `fallback`, `operator` |
| `max_request_length` | int | per-request cap; `0` means disabled |
| `max_request_length_source` | string | `measured`, `fallback`, `operator` |

```json
{
  "status": "ok",
  "pid": 41234,
  "engine": {
    "model": "flash",
    "device": "mps",
    "dtype": "float16",
    "max_length": 262144,
    "max_length_source": "model",
    "max_request_length": 24576,
    "max_request_length_source": "fallback"
  },
  "version": "0.9.0",
  "auth_required": false
}
```

The enforced limit is not a field. Clients compute it as defined in
[config.md](./config.md).

Older servers send none of the new fields. Clients must accept such a body and treat the
limits as unknown.

## `POST /v1/systemone`: 413 refusal

**When**: The request's full encoded size is greater than the enforced limit (see
[data-model.md](../data-model.md), RequestSize).
- The check runs after media decoding and the `media_kwargs` allowlist, and before
  inference. A disallowed `media_kwargs` key still gets 422 from the allowlist.
- A request that is oversized and malformed in a way that still encodes (an empty
  criteria map, say) gets 413 first. One that `encode_record` can't encode at all skips the
  size check and gets the 422 from validation.

**Body**: The FastAPI shape is unchanged, `{"detail": "<message>"}`. `<message>` is a
single line:

```
request too large: {total} tokens exceeds the {limit}-token {limit_name} ({setting}). Split: state {state}, media {media}, fixed overhead {fixed} (questions, schema, prompt wrapper). {advice} {operator_hint}
```

| Placeholder | Value |
|-------------|-------|
| `{total}`, `{state}`, `{media}`, `{fixed}` | exact counts, with `state + media + fixed = total` |
| `{limit}` | the enforced limit |
| `{limit_name}`, `{setting}` | `per-request cap` and `EMBER_MAX_REQUEST_LENGTH` when the cap governs (`GoverningLimit.CAP`); `maximum length` and `EMBER_MAX_LENGTH` when the effective maximum governs (`GoverningLimit.MAXIMUM`) |
| `{advice}` | if `fixed > limit`: `The questions alone exceed the limit: ask fewer or shorter questions, then retry.`; otherwise: `Reduce the largest part (shorten the state, attach fewer or smaller images or frames, or ask fewer questions), then retry.` |
| `{operator_hint}` | when the cap governs: `Operators can raise EMBER_MAX_REQUEST_LENGTH (0 removes the cap; the maximum length then applies).`; when an operator lowered the maximum: `Operators can raise EMBER_MAX_LENGTH up to the model's {declared} tokens.`; when the declared maximum is unknown (the 32,768 fallback, or an operator value over an unreadable declaration): `Operators can raise EMBER_MAX_LENGTH.`; when the declared maximum governs: `This is the model's own maximum and cannot be raised.` |

**Constraints**:
- The message never contains `/` or `\`. That keeps it intact through the MCP layer's
  path redaction (see [mcp-tool.md](./mcp-tool.md)).
- It is ASCII and at most 600 characters.
- It keeps the `request too large: N tokens exceeds the M-token …` prefix that existing
  clients and tests match.

**Example (the cap governs)**:

```json
{"detail": "request too large: 41230 tokens exceeds the 32768-token per-request cap (EMBER_MAX_REQUEST_LENGTH). Split: state 39800, media 0, fixed overhead 1430 (questions, schema, prompt wrapper). Reduce the largest part (shorten the state, attach fewer or smaller images or frames, or ask fewer questions), then retry. Operators can raise EMBER_MAX_REQUEST_LENGTH (0 removes the cap; the maximum length then applies)."}
```

## `POST /v1/systemone`: 500 on a size-check mismatch

If a served request's `usage.input_tokens` differs from its counted total, the server logs
an error and returns 500 instead of an answer (see [research.md](../research.md) R2). This
should never happen. It guards the no-silent-shortening guarantee for unpinned model code.

## Metrics

There are no new metrics. Refusals are already counted as
`ember_advise_requests_total{status="413"}`, because the middleware labels every status.
README's list of statuses adds `413`.
