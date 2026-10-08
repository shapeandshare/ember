---
title: "ember config show silently ignored env-var overrides for most keys"
type: discovery
tags:
  - type/discovery
  - domain/cli
  - domain/models
  - status/reviewed
created: "2026-10-08"
updated: "2026-10-08"
code-refs:
  - ember/commands/config.py
  - tests/test_cli.py
---

# ember config show silently ignored env-var overrides for most keys

Part of [[ember]]. `cmd_config_show` (`ember/commands/config.py`) built its output from
`config.load()` (config file merged over defaults) plus a hardcoded, explicit re-resolve of
only `server_url` and the four secret keys (`auth_token`, `server_auth_token`,
`anaconda_s3_access_key_id`, `anaconda_s3_secret_access_key`). Every other `DEFAULTS` key —
`host`, `port`, `device`, `max_length`, `max_request_length`, `auth_header`,
`allow_insecure_transport`, `request_timeout`, and the newly-added `anaconda_s3_region`/
`anaconda_s3_bucket` — bypassed `config.resolve()`'s flag > env > file > default precedence
entirely, so an active `EMBER_*` env var override was never reflected in `ember config show`'s
output, with no error or warning.

## What was tested

Found while critically re-reviewing the `specs/002-anaconda-models-provider/` AWS S3 pivot
(correcting the download target from a hypothesized Cloudflare R2 catalog to a plain AWS S3
bucket). Manually ran:

```sh
EMBER_ANACONDA_S3_BUCKET=my-test-bucket EMBER_ANACONDA_S3_REGION=us-west-2 ember config show
```

and observed `anaconda_s3_bucket`/`anaconda_s3_region` both reporting `null` despite the env
vars being set. Confirmed the same gap pre-existed for an unrelated key:

```sh
EMBER_HOST=0.0.0.0 ember config show   # also reported the default "127.0.0.1"
```

## Finding

`cmd_config_show`'s `effective = dict(config.load())` reads only the config-file-over-defaults
layer; only the keys explicitly listed afterward (`server_url` and the four secrets) were ever
re-resolved through `config.resolve()`, which is the function that actually implements env-var
precedence. Every other key's env var override was silently invisible in `config show`'s
output, even though `config.resolve()` (used correctly everywhere else — `cli.py`, `doctor.py`,
`anaconda_s3.py`) honored it at actual use time. This was a display-only bug: the override
still worked functionally everywhere it mattered, but a user debugging "why isn't my
`EMBER_ANACONDA_S3_BUCKET` being picked up?" via `ember config show` would see a false
negative.

**Fixed**: `cmd_config_show` now builds `effective` by calling `config.resolve(key)` for every
key in `config.DEFAULTS`, masking only the four secret keys. This is a one-line structural
change (a dict comprehension over `config.DEFAULTS` instead of `config.load()` plus a
hardcoded re-resolve list) with no behavior change for any key that was already correctly
resolved (`server_url`, secrets) and a bug fix for every other key.

## Relevance

- Any future new config key automatically gets correct env-var reflection in `config show` —
  no need to remember to add it to a hardcoded re-resolve list (which is exactly how this bug
  was introduced in the first place: new keys were added to `DEFAULTS` without updating the
  explicit resolve list in `cmd_config_show`).
- Regression test: `tests/test_cli.py::test_config_show_reflects_env_var_overrides_for_every_key`
  exercises both a pre-existing key (`host`) and the two new non-secret Anaconda S3 keys
  (`anaconda_s3_bucket`, `anaconda_s3_region`) to lock this in.
- No spec/constitution change required — this is a bugfix within existing `ember config show`
  behavior, not a new feature or contract change.

## References

- `ember/commands/config.py::cmd_config_show`
- `tests/test_cli.py::test_config_show_reflects_env_var_overrides_for_every_key`
- Found during critical review of `specs/002-anaconda-models-provider/` (the Anaconda-hosted
  AWS S3 model-download feature) — see
  `vault/decisions/2026-10-07-anaconda-models-as-preferred-provider.md`.
