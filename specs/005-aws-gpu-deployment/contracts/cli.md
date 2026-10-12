# Contract: operator commands

Every command is a `make` target (`shared/aws.mk`) that wraps
`uv run python -m ember_aws <command>` with `PYTHONPATH=deployment/aws`. Make variables map
to flags: `NAME`, `REGION`, `MODEL`, `INSTANCE_TYPE`, `CAPACITY`, `IDLE_MINUTES`,
`EMBER_VERSION`.

Exit codes: `0` success, including "nothing to do"; `1` a preflight or validation failure,
before any change; `2` an AWS or Tailscale operation failed, with the stack event or API
message included; `3` a guarded deletion was refused.

Output is plain lines to stdout, plus `--json` for `status` and `cache list`. Secrets are
never printed except the server token on `--show-token`.

| make target | command | Effect | Idempotent result |
| --- | --- | --- | --- |
| `aws-preflight` | `preflight` | Runs every `PreflightCheck`. Each failure gives one line: `✗ <check>: <problem> — fix: <action>` | — |
| `aws-cache` | `cache add [--model M] [--bucket B --prefix P]` | Creates the cache stack if needed and uploads the pinned revision with a manifest written last | `cached: flash@<rev> (already complete)` |
| `aws-cache-list` | `cache list` | Lists models, revisions, sizes, complete or partial, and the deployments using each | — |
| `aws-cache-rm` | `cache rm --model M --revision R` | Removes one cached model. Refused (exit 3) while a deployment uses it | `not cached` |
| `aws-cache-destroy` | `cache destroy --confirm <bucket-name>` | Deletes the cache bucket. Refused while any deployment exists | `no cache` |
| `aws-up` | `deploy` | Runs preflight, `cache add` if the model isn't cached, then creates or updates the stack and waits for health over the tailnet. Prints the URL and the client setup lines | `up to date: <url>` |
| `aws-status` | `status [--json]` | `DeploymentStatus` (data-model.md) | — |
| `aws-stop` | `stop` | Stops the EC2 instance and waits for `stopped` | `already stopped` |
| `aws-start` | `start` | Starts the instance and waits for health | `already running: <url>` |
| `aws-replace` | `replace` | Deletes the tailnet device, mints a key, replaces the instance (latest DLAMI), waits for health | — |
| `aws-logs` | `logs [--follow] [--unit ember\|converge\|idle\|tailscale]` | `tailscale ssh root@ember-<name> journalctl -u …` | — |
| `aws-ssh` | `ssh` | `tailscale ssh root@ember-<name>` | — |
| `aws-token` | `token` | Print only the server token to stdout (for `export EMBER_AUTH_TOKEN="$(…)"`); never logged | — |
| `aws-rotate-token` | `rotate-token` | New server token, then reboots the instance. Clients must export the new token | — |
| `aws-down` | `destroy --confirm <name>` | Deletes the tailnet device, the stack, and `/ember/<name>/*`. Keeps the cache | `nothing deployed` |
| `aws-verify` | `verify` | FR-024 run (research R13) over Tailscale SSH, plus a benchmark from the operator's machine | — |
| `aws-tools` / `aws-tools-rm` | — | Installs or removes the local `aws` CLI and `tailscale` CLI checks (brew) | — |

## Deploy success output (FR-022)

```
ember deployment "default" is healthy on g6e.xlarge (cuda, ember 0.12.0)
  url:   https://ember-default.<tailnet>.ts.net
  next:  export EMBER_AUTH_TOKEN="$(make -s aws-token NAME=default)"   # or: ember_aws status --show-token
         ember init --opencode --server-url https://ember-default.<tailnet>.ts.net
```

The token never appears in this output unless `--show-token` is passed. `ember init`
writes `EMBER_SERVER_URL` only (existing behavior: the credential is never written to a
config file).

## Required operator environment

| Variable | Needed by |
| --- | --- |
| AWS credentials (standard chain: `AWS_PROFILE`, env, SSO) | all commands |
| `TS_OAUTH_CLIENT_ID`, `TS_OAUTH_CLIENT_SECRET` (scopes `auth_keys devices:core dns:read`, tag `tag:ember`) | preflight, deploy, start-after-replace, replace, destroy, status (URL) |
| `tailscale` CLI, logged in to the same tailnet | logs, ssh, verify, and reaching the URL |
