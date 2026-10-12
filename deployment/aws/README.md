# Deploying ember to AWS over Tailscale

Deploy ember's model server to a single NVIDIA GPU instance on AWS, reachable
only over your Tailscale network. No public ports are opened. Clients connect
over HTTPS at the node's MagicDNS name (`https://ember-<name>.<tailnet>.ts.net`).

See `deployment/README.md` for the sibling Outerbounds deployment.

## What it deploys

One CloudFormation stack (`ember-<name>`) containing:

- An EC2 GPU instance (default `g6e.xlarge`, 1x NVIDIA L40S, 48 GB VRAM)
- An IAM instance role scoped to read its own SSM parameters and its model
  prefix in S3 — nothing else
- A security group with **no inbound rules** (Tailscale connects outbound)

On first boot, cloud-init installs `uv`, `tailscale`, and the AWS CLI v2, then
runs three systemd units:

1. `ember-tailscale.service` — joins the tailnet with a short-lived key from
   SSM, then runs `tailscale serve --https=443 http://127.0.0.1:8765`
2. `ember-converge.service` — reads the config from SSM, installs
   `ember-advise==<version>`, syncs the model from S3, and writes
   `/etc/ember/env`
3. `ember.service` — runs `ember serve` bound to `127.0.0.1`

A shared S3 bucket (`ember-model-cache-<account>-<region>`) holds the model
weights. It is created once per account and region and shared by all
deployments there. Destroying a deployment never touches this bucket.

## Prerequisites

### AWS

- An AWS account with permission to create EC2, S3, IAM, CloudFormation, and
  SSM resources.
- GPU quota: "Running On-Demand G and VT instances" needs at least 4 vCPU in
  the target region. Request it at the [Service Quotas console](https://console.aws.amazon.com/servicequotas/home/services/ec2/quotas/L-DB2E81BA)
  if you don't have it yet.
- AWS credentials configured locally (`aws configure`, `aws sso login`, or
  environment variables).

### Tailscale

- **MagicDNS** enabled (Admin console → DNS → MagicDNS).
- **HTTPS Certificates** enabled (Admin console → DNS → HTTPS Certificates).
  Preflight can't check this through the API; it prints a reminder. If it's
  off, `tailscale serve` fails on the instance and the deploy health check
  times out. Check `make aws-logs NAME=<name> UNIT=tailscale` if that happens.
- **`tag:ember` created** in your tailnet. ember instances join the tailnet
  under this tag; the OAuth client must own it so it can mint auth keys.

  **UI path** (recommended): Admin console → Access Controls → Tags →
  "Create tag". Set:
  - Tag name: `ember` (Tailscale prepends `tag:` automatically)
  - Tag owner: your admin user, group, or `autogroup:admin`

  **ACL JSON path**: add to the `tagOwners` block in Admin console →
  Access Controls:

  ```json
  "tagOwners": {
    "tag:ember": ["autogroup:admin"]
  }
  ```

  Preflight mints and immediately deletes a test key to catch tag-ownership
  errors before anything is created.

- **An OAuth client** scoped to `tag:ember`. Create it at Admin console →
  Settings → OAuth clients. Required scopes:

  | Category | Scope | Access |
  | --- | --- | --- |
  | Keys | Auth Keys | Write |
  | Devices | Core | Write |
  | DNS | DNS | Read |

  In the **Tags** field enter `tag:ember` (the tag you created above). Export:

  ```bash
  export TS_OAUTH_CLIENT_ID=<client-id>
  export TS_OAUTH_CLIENT_SECRET=<client-secret>
  ```

  The secret never leaves your machine. The instance only ever sees a
  short-lived, single-use join key that expires in one hour.

- **A Tailscale SSH rule** permitting your user (or `autogroup:admin`) to
  reach `tag:ember` nodes as `root` **and** `ember` — `make aws-logs` and
  `make aws-ssh` connect as root; `make aws-verify` runs its checks as the
  unprivileged `ember` user.

  Add it in Admin console → Access Controls → **SSH** → **Add rule**. The
  console is a form, not a JSON editor: fill these fields and its live JSON
  preview will read like the fragment below.

  | Form field | Enter |
  | --- | --- |
  | Source | `autogroup:admin` — or your own login |
  | Destination | `tag:ember` |
  | As destination user | `root` and `ember` (add both) |
  | Check mode | **Off** — On re-prompts for approval every session |
  | Description | optional, e.g. `ember AWS deployment ops` |

  The rule you end up with (the console's preview; the policy file is
  HuJSON, so the `//` comment and trailing comma it shows are accepted):

  ```json
  // ember AWS deployment ops
  {
    "src": ["autogroup:admin"],
    "dst": ["tag:ember"],
    "users": ["root", "ember"],
    "action": "accept",
  }
  ```

- Your machine is on the same tailnet (`tailscale status` shows it connected).

### Local tooling

```bash
make aws-tools    # installs tailscale CLI via brew on macOS; prints the URL on Linux
```

`make aws-tools-rm` removes only what `aws-tools` installed (tracked in
`.aws-tools.installed`).

## Costs

All prices are on-demand in `us-east-1` as of 2026-10-11 (from
`deployment/aws/sizing.json`). Cost estimates for a region with no price row of
its own fall back to these rates, so estimates outside `us-east-1` are
approximate.

| Instance | GPU | VRAM | Model | Status | Hourly (us-east-1) |
| --- | --- | --- | --- | --- | --- |
| `g6e.xlarge` | NVIDIA L40S | 48 GB | `flash` | supported (default) | $1.861 |
| `g5.2xlarge` | NVIDIA A10G | 24 GB | `flash` | tight (warns) | $1.212 |

`full` (27B, ~55 GiB weights) has no default instance type yet. It needs a
single GPU with at least 80 GB of VRAM and is refused until a row is added to
`sizing.json` with `status: supported`.

**S3 model cache**: storing the `flash` model (~18 GiB) costs roughly $0.41/month
at S3 Standard pricing ($0.023/GiB-month in us-east-1). Data transfer from S3
to EC2 in the same region is free. The cache bucket persists after `aws-down`
and is shared by all deployments in the account and region.

## Lifecycle commands

All commands are `make` targets wrapping `python -m ember_aws`. Variables
(`NAME`, `REGION`, `MODEL`, etc.) can be set on the command line. `REGION`
defaults to `us-west-2`; pass `REGION=<region>` to target another region.

### Preflight

```bash
make aws-preflight
make aws-preflight NAME=team-a REGION=us-west-2 MODEL=flash
```

Checks AWS identity, region, GPU quota, required tooling, Tailscale OAuth
credentials, tag ownership, and MagicDNS. Exits 1 if any blocking check
fails, printing `✗ <check>: <problem> — fix: <action>` for each failure.
Prints a non-blocking notice for HTTPS certificates (can't be checked via API).
Makes no mutating AWS calls.

### Cache the model

```bash
make aws-cache                        # flash in us-west-2 (default)
make aws-cache MODEL=flash REGION=us-east-1
```

Creates the `ember-model-cache` stack if absent, then uploads the pinned model
revision from Hugging Face to S3. Idempotent: a second run prints
`cached: flash@<rev> (already complete)`. A partial upload is resumed.

```bash
make aws-cache-list                   # list cached models, revisions, and sizes
make aws-cache-rm MODEL=flash         # remove one cached revision (exit 3 if a deployment uses it)
```

### Deploy

```bash
make aws-up                           # deploy with defaults (flash, g6e.xlarge, on-demand)
make aws-up NAME=team-a REGION=us-east-1 MODEL=flash
make aws-up INSTANCE_TYPE=g5.2xlarge  # warns "tight"; proceeds
make aws-up EMBER_VERSION=0.12.0      # pin a specific release
make aws-up CAPACITY=spot             # opt-in spot capacity
make aws-up IDLE_MINUTES=60           # stop after 60 minutes of no advise requests
```

On success, prints:

```
ember deployed
  url:     https://ember-default.<tailnet>.ts.net
  token:   (retrieve with: make aws-token)
  connect: ember init --server-url https://ember-default.<tailnet>.ts.net
           export EMBER_AUTH_TOKEN="$(make -s aws-token)"
```

The token is never printed automatically. Retrieve it once with `make aws-token`
and export it in the shell that launches your agent.

Re-running `aws-up` with no changes prints `up to date: <url>` and exits 0.

### Status

```bash
make aws-status
make aws-status NAME=team-a --json    # JSON output
```

Reports instance state, type, tailnet address, ember health (model, device,
version, limits), uptime, and an estimated cost since the last start.

### Stop and start

```bash
make aws-stop                         # stop the EC2 instance; GPU billing stops
make aws-start                        # start it back; same URL and token, no re-download
```

Stop and start are idempotent: `aws-stop` on a stopped instance prints
`already stopped`; `aws-start` on a running one prints `already running: <url>`.

A stopped instance restarts in its own Availability Zone, so `aws-start` can
fail with `InsufficientInstanceCapacity` while that AZ is out of the instance
type — retry until capacity returns. `aws-down` + `aws-up` can land in another
AZ (deploy retries candidate AZs on capacity), at the cost of new SSM
parameters: the server token is regenerated and clients must re-export
`EMBER_AUTH_TOKEN`.

### Replace

```bash
make aws-replace                      # re-resolve the latest DLAMI, replace the instance
```

Use this to pick up a new machine image (new NVIDIA driver, CUDA version). The
tailnet name and auth token are preserved. The instance downloads weights from
the S3 cache on first boot (~18 GiB from the same region, well under 10 minutes).

### Logs and SSH

```bash
make aws-logs                         # stream ember logs (default unit: ember)
make aws-logs UNIT=converge           # converge script output (install, sync, env)
make aws-logs UNIT=tailscale          # tailscale join and serve output
make aws-logs UNIT=idle               # idle-stop timer output
make aws-logs FOLLOW=1                # follow the journal live
make aws-ssh                          # open a Tailscale SSH shell as root
```

Logs and SSH go through Tailscale; no AWS Session Manager permissions are
needed and no port 22 is open in AWS.

### Token

```bash
make aws-token                        # print the server auth token
export EMBER_AUTH_TOKEN="$(make -s aws-token)"
```

### Rotate token

```bash
make aws-rotate-token                 # generate a new token and reboot the instance
```

Clients need to re-export `EMBER_AUTH_TOKEN` after a rotation.

### Verify (CUDA gate)

```bash
make aws-verify                       # run model-backed tests on CUDA, measure the request cap
```

Runs over Tailscale SSH: `make test-strict` with `EMBER_DEVICE=cuda` on the
instance, then `ember eval context --device cuda` to measure the L40S request
cap, then `ember eval run` from your machine against the tailnet URL compared
to the MPS baseline. Record the measured cap in `deployment/aws/sizing.json`
(`cap_source: measured`) and `COMPATIBILITY.md` afterward.

### Teardown

```bash
# Destroy the deployment (keeps the S3 cache)
make aws-down NAME=default CONFIRM=default

# After all deployments are gone, destroy the cache too
make aws-cache-destroy CONFIRM=ember-model-cache-<account>-<region>
```

`aws-down` requires `CONFIRM=<name>` to prevent accidents. It removes the
CloudFormation stack, all SSM parameters under `/ember/<name>/`, and the
tailnet node. The S3 model cache is never touched by `aws-down`.

`aws-cache-destroy` requires `--confirm <bucket-name>` and exits 3 while any
deployment still uses the bucket.

## Connecting clients

After `aws-up` succeeds:

```bash
# Retrieve the token once
export EMBER_AUTH_TOKEN="$(make -s aws-token)"

# Register with your agent harness
ember init --opencode --server-url https://ember-default.<tailnet>.ts.net
ember init --kilocode --server-url https://ember-default.<tailnet>.ts.net
ember init --codex    --server-url https://ember-default.<tailnet>.ts.net

# Verify from the shell
export EMBER_SERVER_URL=https://ember-default.<tailnet>.ts.net
ember doctor          # reports: remote endpoint, reachable, auth_required: true, device: cuda
```

`EMBER_AUTH_TOKEN` is never written to any config file. Export it in the shell
that launches your agent (or your GUI app's environment). The credential is
sent as `Authorization: Bearer <token>` by default; pass `--auth-header
X-API-KEY` to `ember init` if you prefer a different header name.

Clients on the tailnet reach the server over HTTPS with a certificate Tailscale
issues, so `EMBER_ALLOW_INSECURE_TRANSPORT` is never needed.

## Updating

```bash
make aws-up EMBER_VERSION=<next>      # reboot in place; same URL and token
make aws-up INSTANCE_TYPE=g5.2xlarge  # warns "tight"; stop/start, same tailnet name
make aws-up MODEL=flash               # re-run with no changes: "up to date"
```

An ember version change updates the SSM config parameter and reboots the
instance. `ember-converge.service` reads the new version on boot and runs
`uv tool install ember-advise==<next>`. The tailnet name and auth token are
unchanged; clients need no reconfiguration.

An instance type change goes through a CloudFormation change set (stop/start
by CloudFormation). A change that forces instance replacement (e.g. a new
image from `aws-replace`) deletes the tailnet device and mints a new join key
first, so the name stays stable.

## Troubleshooting

**Preflight fails with `✗ tailscale-oauth`**
Export `TS_OAUTH_CLIENT_ID` and `TS_OAUTH_CLIENT_SECRET` and re-run. If you
haven't created the OAuth client yet, go to Admin console → Settings → OAuth
clients and create one with scopes **Auth Keys (write)**, **Devices → Core
(write)**, and **DNS (read)**; set the Tags field to `tag:ember`. See the
Tailscale prerequisites above for step-by-step instructions.

**Preflight fails with `✗ tailscale-tag`**
The OAuth client can't mint keys for `tag:ember`. Two things must both be true:
1. The tag `ember` exists in your tailnet (Admin console → Access Controls →
   Tags, or `tagOwners` in the ACL JSON).
2. The OAuth client was created with `tag:ember` in its Tags field.

Re-create the OAuth client with the Tags field set to `tag:ember` after
ensuring the tag exists. See the Tailscale prerequisites above.

**Preflight fails with `✗ tailscale-magicdns`**
Enable MagicDNS in the Tailscale admin console (DNS page) and re-run.

**Preflight fails with `✗ gpu-quota`**
Request "Running On-Demand G and VT instances" quota at the Service Quotas
console. The preflight output includes the direct link.

**`make aws-logs` says "tailnet policy does not permit you to SSH to this node"**
Fill in the SSH form as in the Tailscale prerequisites above — source your
user (or `autogroup:admin`), destination `tag:ember`, destination users
`root` **and** `ember` (root for `aws-logs`/`aws-ssh`, ember for
`aws-verify`). The node joined and serves traffic without the rule; only
SSH-based commands are denied.

**Deploy fails and the stack rolls back**
The failed stack stays in `ROLLBACK_COMPLETE`, which blocks changes and
cannot be updated. Fix the cause, remove it with
`make aws-down NAME=<name> CONFIRM=<name>`, then re-run `make aws-up`.
Capacity failures are handled automatically: `aws-up` retries the next
availability zone when the instance type has no capacity in one.

**Deploy health check times out**
The instance joined the tailnet but ember isn't healthy yet. Check:

```bash
make aws-logs UNIT=tailscale   # did tailscale serve succeed?
make aws-logs UNIT=converge    # did the model sync and install finish?
make aws-logs                  # is ember serving?
```

If `tailscale serve` failed, HTTPS Certificates is likely off in the Tailscale
admin console (DNS page). Enable it and run `make aws-replace`.

**`make aws-logs` hangs or says "no route to host"**
Your machine isn't on the tailnet, or the instance hasn't joined yet. Check
`tailscale status` and wait for the deploy health check to pass.

**Status shows `stopped: idle`**
The idle timeout fired. Run `make aws-start` to bring it back.

**`ember doctor` reports the wrong endpoint**
`ember init` writes `server_url` into the MCP entry's environment block, not
into ember's own config file. Export `EMBER_SERVER_URL` in your shell too, or
persist it with `ember config path` (see `deployment/README.md`'s "Verifying
from the shell").
