# Quickstart: validate the AWS GPU deployment

This guide runs end to end against a real AWS account and tailnet. It spends money: a
`g6e.xlarge` is about $1.86/h on demand. None of it runs in `make check`, `make test`,
or CI (FR-025). Command contracts: [contracts/cli.md](contracts/cli.md). Resource
invariants: [contracts/infrastructure.md](contracts/infrastructure.md).

## 0. Prerequisites

- AWS credentials for an account with G-series quota: "Running On-Demand G and VT
  instances" needs at least 4 vCPU in the region.
- Tailscale:
  - MagicDNS and HTTPS certificates enabled.
  - In the tailnet policy, `tag:ember` defined, owned by the OAuth client's tag (see
    research R5).
  - An OAuth client with scopes `auth_keys` and `devices:core` and tag `tag:ember`. Export
    `TS_OAUTH_CLIENT_ID` and `TS_OAUTH_CLIENT_SECRET`.
- This machine is on the same tailnet (`tailscale status`).
- A checkout of this repository at the release tag you mean to deploy, after `make setup`.

## 1. Unit gate (no cloud)

```bash
make check            # includes tests/test_aws_*.py: template invariants, stubbed AWS/Tailscale
make typecheck lint security
```

Expected: green. The template tests confirm no ingress, scoped IAM, IMDSv2, and tags.

## 2. Preflight fails safely

```bash
TS_OAUTH_CLIENT_SECRET= make aws-preflight
```

Expected: exit 1, one `✗ tailscale-oauth … — fix: …` line, and **no** AWS resources
created (`aws cloudformation list-stacks` shows no `ember-*` stack).

## 3. Cache, then deploy (US1, SC-001, SC-002a)

```bash
make aws-cache MODEL=flash          # ~18 GiB, once per region; re-run prints "already complete"
time make aws-up                    # < 20 min on first deploy
```

Expected: the success block from contracts/cli.md. Then:

```bash
export EMBER_SERVER_URL=https://ember-default.<tailnet>.ts.net
export EMBER_AUTH_TOKEN="$(make -s aws-token)"
ember doctor                         # remote endpoint, reachable, auth_required, device cuda
curl -s "$EMBER_SERVER_URL/health" | jq .engine.device   # "cuda"
```

Run one `advise` call through the MCP tool and confirm the probabilities come back.

## 4. Exposure (SC-004)

```bash
nmap -Pn -p- <instance public IP>              # from off-tailnet: no open ports
tailscale ping ember-default && nmap -p- ember-default   # on tailnet: 443 (+ 22 Tailscale SSH) only
```

## 5. Lifecycle (US2, SC-002, SC-008)

```bash
make aws-status; make aws-stop; make aws-stop      # second prints "already stopped"
time make aws-start                                # < 10 min, logs show no S3 re-download
make aws-up                                        # "up to date"
```

## 6. In-place update (US3, SC-005)

```bash
make aws-up EMBER_VERSION=<next>      # reboot in place; same URL and token
ember doctor                          # unchanged client config; version = <next>
make aws-up INSTANCE_TYPE=g5.2xlarge  # warns "tight"; stop/start, same tailnet name
```

## 7. Idle stop (US4, SC-006)

```bash
make aws-up IDLE_MINUTES=15           # then send nothing
sleep 1500; make aws-status           # state stopped, reason idle
```

## 8. CUDA verification (FR-024, SC-007)

```bash
make aws-verify       # model-backed tests on CUDA, long-context cap on L40S, benchmark vs MPS baseline
```

Then record the measured cap in `deployment/aws/sizing.json` (`cap_source: measured`) and
`COMPATIBILITY.md`.

## 9. Teardown (SC-003)

```bash
make aws-down NAME=default            # asks for --confirm default
aws resourcegroupstaggingapi get-resources --tag-filters Key=ember:deployment,Values=default   # empty
tailscale status | grep ember-default  # gone
make aws-cache-list                    # cache still present
make aws-cache-destroy                 # only when you're done with every deployment
```
