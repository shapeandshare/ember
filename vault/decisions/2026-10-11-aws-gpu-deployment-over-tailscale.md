---
title: "AWS GPU deployment over Tailscale"
type: decision
tags:
  - type/decision
  - domain/server
  - domain/tooling
  - status/draft
created: "2026-10-11"
updated: "2026-10-11"
code-refs:
  - deployment/aws/ember_aws/
  - deployment/aws/template.yaml
  - deployment/aws/sizing.json
  - shared/aws.mk
  - ember/serving/hosted.py
---

# AWS GPU deployment over Tailscale

Part of [[ember]]. Deploy ember to a single NVIDIA GPU instance on AWS, reachable only over the operator's Tailscale network, with no public ports, using CloudFormation and a small Python CLI (`ember_aws`).

## Context

The spec (`specs/005-aws-gpu-deployment/spec.md`) required a fully automated path from AWS credentials to a healthy CUDA ember endpoint, with full lifecycle management (deploy, status, stop, start, replace, rotate-token, destroy) and no manual console steps. Several architectural choices had to be resolved before implementation.

**R1 — Provisioning tool**: CDK and Terraform both require extra toolchains (Node.js or a binary plus remote-state management). Raw boto3 calls would require writing idempotency, ordering, and rollback by hand. CloudFormation with a small Python CLI reuses boto3 (already a runtime dependency), keeps the stack as the state (status and destroy work with no local state), and gives actionable errors from stack events. Chosen: one `template.yaml` driven by `ember_aws` via `create_stack`/`update_stack`/`delete_stack` and change sets.

**R4 — Weights on the instance**: A retained EBS data volume would tie the instance to one AZ, require attach/mount handling, and need a purge step on destroy. The weights can be replaced from S3 in the same region (~18 GiB, well under 10 minutes). Chosen: root gp3 volume (100 GiB, `DeleteOnTermination: true`). Weights survive stop/start and every in-place update; only an explicit `replace` re-downloads from S3. This narrows FR-007: the spec said weights survive "stop/start and instance replacement"; with this design they survive everything except an explicit replace.

**R5 — Tailscale integration**: The OAuth secret must never reach the instance. Ephemeral nodes change identity on every stop/start. Chosen: a non-ephemeral node with a short-lived, single-use join key minted per boot, stored as an SSM SecureString, and deleted by the instance after joining. `tailscale serve --https=443` provides the HTTPS listener with a Tailscale-issued certificate, satisfying ember's transport check with no client flags. The old device is deleted before a replacement joins, keeping the tailnet name stable.

**R6 — Updates without replacing the instance**: Putting the version in UserData would require a replacement on every update (cloud-init runs only on first boot). Chosen: an SSM parameter `/ember/<name>/config` (JSON: version, model S3 URI, request cap, idle minutes) read by `ember-converge.service` on every boot. Only when something changed does converge install and sync. Deploy updates the parameter, then reboots the instance (or lets CloudFormation stop/start it for an instance-type change).

**R8 — Instance permissions**: The instance role allows only `ssm:GetParameter` on its own prefix, `ssm:DeleteParameter` on the join-key parameter, `kms:Decrypt` via SSM, `s3:GetObject` on its model prefix, and `s3:ListBucket` with a prefix condition. No EC2, no CloudWatch, no SSM agent policy. The security group has no inbound rules.

**FR-007 amendment**: The original spec said weights survive "stop/start and instance replacement". Research R4 narrowed this: weights survive stop/start and every in-place update, but not an explicit `replace`. The spec was amended to match.

## Decision

- One CloudFormation template (`deployment/aws/template.yaml`) driven by `deployment/aws/ember_aws/` (a Python package run as `PYTHONPATH=deployment/aws uv run python -m ember_aws`), wrapped by `shared/aws.mk`.
- Default instance: `g6e.xlarge` (1x NVIDIA L40S, 48 GB VRAM, ~$1.86/h on demand in us-east-1) for `flash`. `full` is refused until a single-GPU instance with at least 80 GB of VRAM is measured.
- Model weights live in a private S3 bucket (`ember-model-cache-<account>-<region>`, `DeletionPolicy: Retain`), shared by all deployments in the account and region. Instances load only from S3 via `EMBER_MODEL_S3_URI`; they never download from Hugging Face.
- Tailscale provides the HTTPS endpoint (`https://ember-<name>.<tailnet>.ts.net`) and SSH access. No public ports.
- The auth token is stored as an SSM SecureString and never written to any config file, template, or log.
- All unit tests use `botocore.stub.Stubber`, `httpx.MockTransport`, `tmp_path`, and `monkeypatch`. No test touches a real AWS account or tailnet (FR-025).

## Consequences

- `make aws-up` is the single command from prerequisites to a healthy CUDA endpoint.
- Clients connect with `ember init --server-url https://ember-<name>.<tailnet>.ts.net` and `export EMBER_AUTH_TOKEN="$(make -s aws-token)"`. No client reconfiguration is needed for version, model, or idle-timeout updates.
- `make aws-down` removes the deployment but never the S3 cache. `make aws-cache-destroy` removes the cache with typed confirmation and exits 3 while any deployment uses it.
- The CUDA verification gate (`make aws-verify`, T042) must pass before the feature is called done (FR-024). Until then, `sizing.json` uses the fallback cap (24,576 tokens, `cap_source: fallback`).
- `ember/serving/hosted.py` now uses a `_download_complete` marker to detect partial downloads (R4 fix; see `vault/discoveries/2026-10-11-hosted-cache-treats-partial-dir-as-complete.md`).
