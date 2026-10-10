# Contract: Length-limit configuration

**Feature**: `003-context-window-audit`
**Date**: 2026-10-09
**Scope**: The `max_length` and `max_request_length` keys in `ember/cfg/config.py`
`DEFAULTS`, their environment variables, and how the server turns them into the effective
maximum, the per-request cap, and the enforced limit. This is a public contract: README,
COMPATIBILITY.md, and the tests change with it.

## Precedence

Precedence is unchanged: **command-line flag > environment variable > config file >
default**. What changes is where the default comes from: the default tier of
`max_request_length` is now the loaded model's measured cap (FR-010, FR-013).

## Keys

| Key | Env var | Type | Default | Meaning |
|-----|---------|------|---------|---------|
| `max_length` | `EMBER_MAX_LENGTH` | int | `0` | Effective maximum: the most tokens the model processes. `0` or unset means the model's declared maximum, `config.json` `max_position_embeddings` (262,144 for both flash and full) |
| `max_request_length` | `EMBER_MAX_REQUEST_LENGTH` | int or unset | unset (`None`) | Per-request cap, checked before inference. Unset means the loaded model's measured default. `0` disables the cap, though the effective maximum still applies |

## Resolution

| Input | Effective maximum | Source | Per-request cap | Source |
|-------|-------------------|--------|-----------------|--------|
| unset | declared maximum | `model` | registry model with a measured cap: that cap | `measured` |
| unset, `config.json` unreadable | 32,768 | `fallback` | registry model not yet measured: its own `fallback_request_length` | `fallback` |
| unset, model outside the registry (`EMBER_MODEL_DIR` or `EMBER_MODEL_S3_URI` set) | declared maximum | `model` | lowest registry cap, measured or fallback | `fallback` |
| positive N | min(N, declared maximum) when the declared maximum is known, logging a warning if N is larger; N when it is unknown | `operator` (`model` when clamped) | N | `operator` |
| `0` | same as unset | — | disabled | `operator` |
| non-integer or negative | same as unset, with a warning | — | same as unset, with a warning | — |

The **enforced limit** is min(cap, effective maximum) when the cap is enabled, and the
effective maximum otherwise. A request whose encoded size equals the enforced limit is
served; one token more is refused (see [http-api.md](./http-api.md)).

## Behavior changes

- **Cap default**: `max_request_length`'s default changes from `32768` to unset. Until a
  model has a measured cap, unset resolves to that model's own fallback, the longest probe
  length that fits its memory budget. (Updated 2026-10-10, replacing a shared 32,768: see
  `vault/decisions/2026-10-10-per-model-request-caps.md`.)
- **Counting**: requests are now counted in full: questions, schema, prompt wrapper, and
  media, not just `str(state)`. Requests that passed before can now be refused, and the
  refusal says why.
- **Negative values**: a negative `EMBER_MAX_REQUEST_LENGTH` used to disable the cap
  silently. It is now ignored, with a warning.
- **`ember config show`**: prints `max_request_length: None` when unset. README explains
  that this means the model's measured default.

## Unchanged

- Key names and environment variable names.
- The meaning of `0` for each key.
- Flag > env > file precedence.
