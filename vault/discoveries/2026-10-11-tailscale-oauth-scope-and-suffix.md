---
title: "Tailscale OAuth: request dns:read, and the tailnet suffix comes from
  device names"
type: discovery
tags:
  - type/discovery
  - domain/server
  - domain/tooling
  - status/draft
created: 2026-10-11
updated: 2026-10-11
code-refs:
  - deployment/aws/ember_aws/tailscale_client.py
  - deployment/aws/ember_aws/preflight.py
---
# Tailscale OAuth: request dns:read, and the tailnet suffix comes from device names

Part of [[ember]]. Two constraints discovered while making `make aws-preflight` pass against the live Tailscale API: the token exchange must request exactly the scopes the OAuth client can grant (`dns:read`, not `dns`), and the tailnet's `.ts.net` suffix is not exposed by any DNS endpoint — it must be read from a device's MagicDNS name.

## What was tested

Direct probes of the live API with the operator's OAuth client (created with Auth Keys, Devices Core, and DNS *read*):

- The original symptom: `✗ tailscale-magicdns: cannot check MagicDNS: not found` — the token exchange requested no DNS scope at all, so `GET /dns/preferences` failed.
- `POST /api/v2/oauth/token` with `scope=auth_keys devices:core dns` → **403**, `OAuth client cannot grant scopes "devices:core dns auth_keys"`.
- The same request with `scope=auth_keys devices:core dns:read` → **200**.
- `GET /api/v2/tailnet/-/dns/preferences` → `{"magicDNS": true}` (no `domains` field); `dns/searchpaths` → `{"searchPaths": []}`; `dns/configuration` → `{"preferences": {"magicDNS": true}}`. None of the three carries the tailnet suffix.
- `GET /api/v2/tailnet/-/devices` → device `name` is the full MagicDNS name (`gh-runner-01.tail5be351.ts.net`).
- Cross-check: `tailscale status --json` on the same machine reports `MagicDNSSuffix: tail5be351.ts.net`.

## Finding

1. **Scope grants are exact.** The token exchange succeeds only if the client can grant every requested scope. The admin console's "DNS (read)" selection maps to the API scope `dns:read`; requesting `dns` (read+write) fails the entire exchange with 403 — even though the client legitimately holds *read*. `dns:read` is also the least privilege that suffices: every DNS call ember makes is a GET.
2. **No DNS endpoint exposes the tailnet suffix.** `dns/preferences` returned only `{"magicDNS": true}`, so the old `domains[0]["suffix"]` extraction produced an empty suffix — which would have rendered URLs as `https://ember-<name>.` and left `aws-status`'s tailnet URL `None`. The suffix must be derived from a device's MagicDNS name: `<host>.<tailnet>.ts.net` → split off the first label (`_tailnet_suffix`). Any device works; the tailnet prerequisite guarantees at least the operator's machine.

## Relevance

- The docs and preflight messages now name all three client scopes: Auth Keys (write), Devices → Core (write), DNS (read).
- Both bugs were invisible to unit tests: the fixtures mocked a response shape the API never returns (a `domains` list on `dns/preferences`), and the token scope was never asserted against a live exchange. The tests now use the live shapes and assert `dns:read`.
- Anyone automating Tailscale device joins with an OAuth client should expect exact-scope grants and derive the tailnet DNS name from device names or the local `tailscale status --json` (`.MagicDNSSuffix`), not the DNS API.

## References

- `deployment/aws/ember_aws/tailscale_client.py` — `token()`, `tailnet_dns()`, `_tailnet_suffix()`
- `deployment/aws/ember_aws/preflight.py` — `_check_tailscale_oauth`, `_check_tailscale_magicdns`
- `vault/decisions/2026-10-11-aws-gpu-deployment-over-tailscale.md`
