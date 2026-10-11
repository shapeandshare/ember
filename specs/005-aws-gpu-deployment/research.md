# Research: AWS GPU Deployment over Tailscale

Feature: `specs/005-aws-gpu-deployment/spec.md`. Every unknown from the plan's Technical
Context is resolved here. Format: Decision / Rationale / Alternatives considered.

## R1. Provisioning tool

- **Decision**: One CloudFormation template (`deployment/aws/template.yaml`), committed as
  plain YAML and driven by a small Python CLI that uses boto3 (`create_stack` /
  `update_stack` / `delete_stack`, plus change sets for "up to date" detection).
- **Rationale**: Article XV (§15.1, §15.2, §15.4). boto3 is already a runtime dependency
  (`pyproject.toml`, for `EMBER_MODEL_S3_URI`), so the AWS side adds **no new dependency
  and no new toolchain**. The stack itself is the state, kept in AWS: status and destroy
  work with no local state (spec edge case, FR-018). Delete-stack is a complete teardown,
  and stack events give actionable errors.
- **Alternatives considered**:
  - **AWS CDK (Python)**: proven in `../darkharbour/src/darkharbour/component/ec2/`, but it
    needs Node.js and the CDK CLI on every operator machine, plus `aws-cdk-lib`/`constructs`
    dependencies, all to generate the same CloudFormation. Rejected: two toolchains for one
    instance.
  - **Terraform** (`../infrastructure/terraform/`): needs a binary and remote-state
    management (a lost local state file orphans resources unless an S3 backend is
    bootstrapped first). Rejected for the same reason.
  - **Raw boto3 calls, no template**: idempotency, ordering, and rollback would all be ours
    to write and test. Rejected.

## R2. Instance type and machine image

- **Decision**: Default `g6e.xlarge` for `flash`: 1× NVIDIA L40S with 48 GB, 4 vCPU,
  32 GiB RAM, about $1.86/h on demand in us-east-1, as recorded with a date in the sizing
  table. The image comes from the public SSM parameter
  `/aws/service/deeplearning/ami/x86_64/base-oss-nvidia-driver-gpu-ubuntu-24.04/latest/ami-id`.
  That is the AWS Deep Learning Base OSS NVIDIA Driver GPU AMI on Ubuntu 24.04: NVIDIA
  driver 595.x, CUDA 12.8–13.2, `/usr/bin/python3.12`, and the SSM agent, and it supports
  G5, G6, G6e, G7e and P-series. The template reads it as an
  `AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>` parameter. **The resolved AMI ID is
  recorded in the stack**, so an update never changes the image silently. A new image
  comes only from an explicit `replace`.
- **Rationale**: The ~18 GiB of fp16 weights leave only ~4 GiB of headroom on an A10G
  (24 GB). `deployment/flash.yaml` already flags A10G as "tight" and names L40S/G6e as the
  fix. The base DLAMI ships matching drivers, so v1 needs no image pipeline (spec
  assumption). torch's default PyPI Linux wheel already bundles CUDA (as in
  `deployment/flash.yaml`), so no special package index is needed.
- **`full` (27B, ~55 GiB)**: no default in v1. It needs one GPU with at least 80 GB,
  because ember loads with `device_map={"": "cuda"}` onto a single device. The sizing
  table lists it as `unsupported` until a single-GPU ≥80 GB type is measured, so deploy
  refuses it with the reason (FR-005).
- **Alternatives considered**: `g5.2xlarge`/`g5.4xlarge` (A10G 24 GB): rejected as the
  default because they're too tight, but allowed as an explicit override with a warning,
  because their 24 GB is above flash's floor. `g6.xlarge` (L4 24 GB): same reasoning.
  P-series: overkill for 9B.

## R3. Model cache in S3

- **Decision**: The tooling creates one bucket per account and region in its own small
  stack `ember-model-cache`, named
  `ember-model-cache-<account-id>-<region>`. The bucket has public access blocked, SSE-S3
  encryption, versioning off, `BucketOwnerEnforced`, and `DeletionPolicy: Retain`. Its
  layout is `models/<model-name>/<revision>/<files>`, plus a `manifest.json` that lists
  each file with its size and SHA-256 and is written **last**. A cached model is complete
  only when its manifest exists and every file matches it. The cache command runs on the
  operator's machine: `huggingface_hub.snapshot_download` at the registry's pinned
  `revision` into a temporary directory, then a multipart upload with boto3
  `TransferConfig`. It skips files whose size and checksum already match. The operator can
  pass `--bucket`/`--prefix` to use an existing bucket instead.
- **Rationale**: This reuses `huggingface_hub` and boto3, which ember already depends on,
  and the Hugging Face file allowlist from `ember/models.py`. A manifest written last makes
  partial uploads detectable (spec edge case). One cache per region serves every deployment
  (SC-002a). This is consistent with Article I: the weights go to a location the user
  chose, in their own account, and are never redistributed from this repository.
- **Alternatives considered**: Copying from Hugging Face on the instance itself: rejected,
  because the instance would need write access to the cache and would depend on Hugging
  Face at boot. Mounting the bucket with Mountpoint for S3: rejected, because ember's
  existing `ember/serving/hosted.py` already downloads `EMBER_MODEL_S3_URI` to a local
  directory.

## R4. Weights on the instance

- **Decision**: The weights live on the instance's root gp3 volume, 100 GiB with
  `DeleteOnTermination: true`. Stop and start keep the volume, so nothing is downloaded
  again. Updates to the ember version, model, idle timeout, or instance type change the
  instance in place (R6), so the volume survives those too. Only an explicit `replace`
  (a new image, or recovery) creates a new volume, and that new instance pulls the
  weights from the S3 cache in the same region, about 18 GiB at S3's in-region rate, so
  well under the 10-minute target. **This narrows FR-007**: the spec said the weights
  survive "stop/start and instance replacement"; with this design they survive everything
  except an explicit replace. The spec has been amended to match.
- **Rationale**: Article XV. A data volume kept separate from the instance would tie the
  instance to one availability zone, would need its own attach and mount handling plus an
  orphan sweep, and would need a purge step. All of that to save a fast pull from S3 in
  the same region, which only happens on the rare replace. Removing it also removes
  FR-017's typed-confirmation purge for the volume; the S3 cache keeps its own guarded
  removal.
- **Alternatives considered**: A retained EBS data volume, as in darkharbour's FR-018. That
  exists there to protect state that can't be replaced (age keys, mesh identity); ember's
  weights can be replaced from S3. Rejected.

## R5. Tailscale integration

- **Decision**:
  - **Operator side** (`tailscale.py`, httpx, already a dependency): exchange the OAuth
    client (`TS_OAUTH_CLIENT_ID`/`TS_OAUTH_CLIENT_SECRET`, read from the environment or a
    file the operator names, never written anywhere) for a token at
    `POST https://api.tailscale.com/api/v2/oauth/token` with scopes
    `auth_keys devices:core`. Before every boot that needs to join, mint a key with
    `POST /api/v2/tailnet/-/keys` and
    `capabilities.devices.create = {reusable: false, ephemeral: false, preauthorized: true,
    tags: ["tag:ember"]}` and `expirySeconds: 3600`. Store it as the SSM SecureString
    `/ember/<deployment>/tailscale-join-key`. Before a replace or destroy, list devices
    (`GET /api/v2/tailnet/-/devices`), match the hostname `ember-<deployment>` together
    with the tag, and delete them (`DELETE /api/v2/device/{id}`).
  - **Instance side**: read the key, run
    `tailscale up --auth-key=… --hostname=ember-<deployment> --advertise-tags=tag:ember --ssh`,
    then delete the parameter. Then run
    `tailscale serve --bg --https=443 http://127.0.0.1:8765`.
  - **Preflight**: exchange the token; mint and immediately delete a test key, to catch
    the "requested tags are invalid or not permitted" tag-ownership failure (tailscale
    issue #15456); and check MagicDNS with `GET /api/v2/tailnet/-/dns/preferences`. The
    public API does not expose whether HTTPS certificates are enabled, so preflight prints a
    non-blocking reminder, and the instance detects the problem: a failing `tailscale serve`
    logs a message naming the admin-console setting, which status and the deploy health
    timeout surface.
  - **Template size**: the CLI inlines the user data into the template body at the
    placeholder `__EMBER_USER_DATA__`; it is never a stack parameter, because CloudFormation
    caps parameter values at 4,096 bytes. Limits asserted in tests: inline `TemplateBody`
    ≤ 51,200 bytes, EC2 user data ≤ 16,384 bytes.
- **Rationale**: A non-ephemeral node keeps its identity across stop and start. Deleting
  the old device before a replacement joins keeps the name stable (no `-1` suffix). The
  instance never sees the OAuth secret, only a single-use key that expires in an hour.
  `tailscale serve` provides the HTTPS listener with a certificate Tailscale issues, which
  satisfies ember's transport check (`ember/cfg/endpoint.py`) with no client flags, and
  ember stays on loopback (FR-009a). Tailscale SSH serves as both the shell (FR-013) and
  the logs path, so the instance needs no SSM Session Manager permissions and no port 22
  open in AWS.
- **Alternatives considered**: Passing the OAuth secret to the instance with
  `?ephemeral=false&preauthorized=true`: rejected, because it puts a long-lived credential
  on the instance. Ephemeral nodes: rejected, because the identity would change on every
  stop and start.

## R6. Updates without replacing the instance

- **Decision**: The desired configuration is stored as an SSM parameter
  `/ember/<deployment>/config`: a JSON object with the ember version, model S3 URI, request
  cap, and idle minutes. A systemd unit `ember-converge.service` runs **on every boot**,
  before `ember.service`. It reads the config and, only if something changed, runs
  `uv tool install ember-advise==<v>` and syncs the model from S3. Then it writes the
  environment file and starts ember. Deploy updates the parameter, then:
  - changing the instance type: CloudFormation stops and starts the instance (it does not
    replace it);
  - anything else: the CLI reboots the instance through EC2 and waits for health over the
    tailnet.

  Replacement happens only on an explicit `replace`, or when the template changes a
  property that forces replacement. In both cases the tailnet device is deleted and a new
  join key minted first.
- **Rationale**: This is darkharbour's pull-based converge token, reduced to a single
  parameter read at boot. It keeps the instance role to `ssm:GetParameter` (FR-012), needs
  no `ssm:SendCommand`, and keeps the volume and tailnet identity through every routine
  update (FR-019, SC-005).
- **Alternatives considered**: Putting the version in UserData: rejected, because cloud-init
  runs user data only on first boot, so every update would need a replacement.

## R7. Secrets

- **Decision**: SSM Parameter Store SecureString, using the AWS-managed `aws/ssm` key:
  - `/ember/<deployment>/server-token`: 32 random bytes, generated by deploy if it doesn't
    exist, never regenerated except by `rotate-token`. It is printed once, on the first
    deploy, behind an explicit `--show-token`.
  - `/ember/<deployment>/tailscale-join-key`: short-lived, deleted by the instance.

  On the instance, the converge unit writes `EMBER_SERVER_AUTH_TOKEN` into
  `/etc/ember/env` (root-owned, mode 0600), which `ember.service` reads with
  `EnvironmentFile`.
- **Rationale**: Parameter Store is free, the instance role is already scoped to it, and a
  SecureString read is a single IAM action plus `kms:Decrypt` through the AWS-managed key.
  The token never appears in templates, stack parameters, user data, logs, or the output
  of `ember init` (FR-010, FR-022).
- **Alternatives considered**: Secrets Manager: rotation features we don't need, and it
  costs per secret. Rejected (YAGNI).

## R8. Instance permissions

- **Decision**: The instance profile allows only:
  - `ssm:GetParameter` on `arn:aws:ssm:<r>:<a>:parameter/ember/<deployment>/*`;
  - `ssm:DeleteParameter` on `…/ember/<deployment>/tailscale-join-key`;
  - `kms:Decrypt` with the condition `kms:ViaService = ssm.<r>.amazonaws.com`;
  - `s3:GetObject` on `arn:aws:s3:::<cache>/models/<model>/<revision>/*`;
  - `s3:ListBucket` on the bucket with the condition `s3:prefix` = that prefix.

  Nothing else: no EC2, no CloudWatch, no SSM agent policy. The security group allows
  **no inbound traffic**. Outbound is all (needed for Tailscale's coordination and
  DERP/UDP 41641, PyPI, S3).
- **Rationale**: FR-012 and FR-009. Tailscale connects outbound and NAT-traverses, so
  there's no inbound rule. An S3 gateway VPC endpoint is unnecessary in the default VPC;
  S3 traffic in the same region is free over the internet gateway path.
- **Alternatives considered**: darkharbour's interface endpoints plus deny-by-default
  outbound: that's justified there by a fleet threat model, but costs about $7 per
  endpoint per month and adds complexity here. Deferred until there's a requirement.

## R9. Network placement

- **Decision**: The default VPC and one of its default subnets, chosen by the first
  availability zone that offers the instance type (`describe_instance_type_offerings`). The
  instance gets a public IPv4 address (needed for outbound traffic without a NAT gateway;
  the security group has no inbound rules). `--subnet-id` overrides it.
- **Rationale**: Zero network resources to create or destroy. A NAT gateway would cost
  about $32 per month.
- **Alternatives considered**: A dedicated VPC per deployment: more resources and no
  present need.

## R10. Idle stop

- **Decision**: When `idle_minutes > 0`, a systemd timer `ember-idle.timer` runs every
  minute. It reads `ember_advise_requests_total` from `http://127.0.0.1:8765/metrics`,
  stores the last value it saw and when, and runs `shutdown -h now` once the count hasn't
  changed for `idle_minutes`. The instance sets
  `InstanceInitiatedShutdownBehavior: stop`. Status reports "stopped: idle" when the EC2
  state reason is `Client.InstanceInitiatedShutdown` and the deployment's idle timeout is
  set.
- **Rationale**: It reuses the server's existing metrics (FR-020) and needs no extra
  permission or service. The timer is off by default (spec clarification).
- **Alternatives considered**: Lambda, EventBridge, or CloudWatch alarms: more resources,
  more permissions, and more teardown.

## R11. Spot capacity

- **Decision**: `--capacity spot` sets `InstanceMarketOptions` to a persistent spot request
  with `InstanceInterruptionBehavior: stop`. On-demand is the default. Status shows the
  spot interruption state reason. `--capacity on-demand` on a later deploy replaces the
  instance, with the usual tailnet device cleanup.
- **Rationale**: FR-021 and acceptance scenario US4-2. "Stop" on interruption keeps the
  volume.

## R12. Cost estimate

- **Decision**: The sizing table records the on-demand hourly price for each instance type
  and region, with a `priced_on` date. For spot, the current price comes from
  `describe_spot_price_history`. Status shows the hourly rate and
  `hourly × hours since the last start (LaunchTime)`, labelled "estimate".
- **Rationale**: The Pricing API needs a fixed region (us-east-1) and a product-filter
  parser, which is complexity for an estimate. Recording a dated price is honest and
  testable.

## R13. Verification on real hardware (FR-024)

- **Decision**: After the first successful deploy, run a documented script
  (`make aws-verify`) over Tailscale SSH on the instance. It runs:
  `EMBER_DEVICE=cuda make test-strict` (model-backed tests, from a checkout at the
  release tag); `make eval-context` with a `--device cuda` path to measure flash's cap on
  an L40S; and `ember eval run` from the operator's machine against the tailnet URL,
  compared to the MPS baseline (SC-007). The measured cap goes into the sizing table and
  `COMPATIBILITY.md`.
- **Gap found**: `evals/context/` documents itself as MPS-only ("runs in-process on MPS",
  with a peak MPS memory sampler). Supporting CUDA needs a device switch and a CUDA
  memory sampler (`torch.cuda.max_memory_allocated`). That is a task in this feature. Until
  the measurement exists, the sizing table uses flash's fallback cap, 24,576 tokens (its
  MPS-derived value, conservative on a 48 GB GPU), marked `source: fallback`.

## R14. Where the code lives, and gates

- **Decision**:
  - `deployment/aws/` holds the template, the instance-side files (systemd units, the
    converge and idle scripts), the sizing table, and a Python package
    `deployment/aws/ember_aws/` that is run as `uv run python -m ember_aws …` with
    `PYTHONPATH=deployment/aws`, wrapped by `shared/aws.mk`.
  - It isn't shipped in the wheel: `[tool.hatch.build.targets.wheel] packages = ["ember"]`
    is unchanged (FR-001).
  - The existing Outerbounds files stay where they are (`deployment/flash.yaml`,
    `full.yaml`, `requirements.txt`, `README.md`). Moving them would break
    `shared/release.mk`, `scripts/freeze_deployment_requirements.py` and its test, and the
    release workflow, for no gain. `deployment/README.md` gains a one-line index pointing
    to `aws/`.
  - The new code follows Article X and passes ruff, mypy `--strict` (the `typecheck`
    target is extended to `deployment/aws/ember_aws`), and bandit.
  - Tests live in `tests/test_aws_*.py`. They use `botocore.stub.Stubber`, part of
    botocore, so no new dependency, and `httpx.MockTransport` for Tailscale. Template
    checks parse the YAML with `pyyaml` (already a dev dependency) and assert the
    properties FR-025 requires. No test touches AWS or Tailscale.
  - Dev dependency change: `boto3-stubs[s3]` → `boto3-stubs[s3,ec2,cloudformation,ssm,sts,service-quotas]`
    (types only).
- **Rationale**: FR-001, FR-025, Articles VIII, X, XI, XV.
