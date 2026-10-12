# Tasks: AWS GPU Deployment over Tailscale

**Input**: Design documents from `specs/005-aws-gpu-deployment/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md,
contracts/infrastructure.md, quickstart.md

**Tests**: REQUIRED. Constitution Article XI (TDD) and spec FR-025 apply. Within every
phase, write each test task first and confirm it fails
(`uv run pytest tests/<file> -x` → FAIL) before starting the implementation task it covers.
No test may call AWS or Tailscale: use `botocore.stub.Stubber`, `httpx.MockTransport`,
`tmp_path`, and `monkeypatch`.

**Conventions for every Python task** (Article X): `from __future__ import annotations`;
NumPy docstrings; one primary class per file; Pydantic `BaseModel` for anything that
crosses AWS, SSM, the instance, or disk; `StrEnum` for fixed sets; relative imports inside
`ember_aws`; files ≤ 400 lines; atomic writes (`.tmp` + `os.replace`). Never log or `repr`
a secret: use `pydantic.SecretStr`.

**Path root**: `deployment/aws/` (runtime code), `tests/` (tests). Run with
`PYTHONPATH=deployment/aws uv run python -m ember_aws <cmd>`.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Create directories `deployment/aws/`, `deployment/aws/ember_aws/`, and `deployment/aws/instance/`, and add `deployment/aws/ember_aws/__init__.py` containing only the docstring `"""Operator tooling that deploys ember to an AWS GPU instance reachable over Tailscale."""`
- [X] T002 Update `pyproject.toml`:
  - widen the dev dependency `boto3-stubs[s3]` to `boto3-stubs[s3,ec2,cloudformation,ssm,sts,service-quotas]`;
  - add `deployment/aws` to `[tool.pytest.ini_options] pythonpath`;
  - add `deployment/aws/ember_aws` to the mypy `files` (or `packages`), the ruff `src`/include (with `D` rules applied), the bandit targets, and `[tool.coverage.run] source`;
  - keep `[tool.hatch.build.targets.wheel] packages = ["ember"]` unchanged (FR-001);
  - run `uv lock`.
- [X] T003 Update the `typecheck`, `lint`, `format`, `security`, and `compile` recipes in `shared/python.mk` so they cover `deployment/aws/ember_aws` (and `deployment/aws` for compile)
- [X] T004 Create `shared/aws.mk`:
  - define the `NAME ?= default`, `REGION ?= us-east-1`, `MODEL ?= flash`, `INSTANCE_TYPE`, `CAPACITY ?= on-demand`, `IDLE_MINUTES ?= 0`, and `EMBER_VERSION` variables, plus `AWS_CLI = PYTHONPATH=deployment/aws $(UV) run python -m ember_aws`;
  - add `.PHONY` placeholders with `##` help text for every target in `contracts/cli.md`: `aws-preflight`, `aws-cache`, `aws-cache-list`, `aws-cache-rm`, `aws-cache-destroy`, `aws-up`, `aws-status`, `aws-stop`, `aws-start`, `aws-replace`, `aws-logs`, `aws-ssh`, `aws-token`, `aws-rotate-token`, `aws-down`, `aws-verify`, `aws-tools`, `aws-tools-rm`;
  - `include` it from `Makefile` and list it in the Makefile header comment.

---

## Phase 2: Foundational (blocks all stories)

- [X] T005 [P] Write `tests/test_aws_names_sizing.py` (names part):
  - `DeploymentName` accepts `default` and `team-a1`;
  - it rejects `A`, `-x`, `x-`, a 33-character name, and `under_score` (regex `^[a-z][a-z0-9-]{1,30}[a-z0-9]$`);
  - the derived names are stack `ember-<name>`, hostname `ember-<name>`, SSM prefix `/ember/<name>/`, and tag `ember:deployment=<name>`.
- [X] T006 [P] Implement `deployment/aws/ember_aws/names.py`: a `DeploymentName` Pydantic model with the derived-name properties `stack_name`, `hostname`, `ssm_prefix`, `config_param`, `token_param`, `join_key_param`, and `tag`
- [X] T007 [P] Implement one `StrEnum` per file (Article X §10.2, which the plan adopts for `ember_aws`), each module named after its enum:
  - `capacity.py` `Capacity`: `on-demand`, `spot`;
  - `deployment_state.py` `DeploymentState`: `absent`, `creating`, `running`, `stopping`, `stopped`, `updating`, `replacing`, `destroying`, `failed`;
  - `stop_reason.py` `StopReason`: `operator`, `idle`, `spot-interruption`, `unknown`;
  - `sizing_status.py` `SizingStatus`: `supported`, `tight`, `unsupported`;
  - `cap_source.py` `CapSource`: `measured`, `fallback`;
  - `preflight_check.py` `PreflightCheck`: `aws-identity`, `region`, `tooling`, `gpu-quota`, `instance-offering`, `tailscale-oauth`, `tailscale-tag`, `tailscale-magicdns`, `tailscale-https`, `model-cached`.

  All live in `deployment/aws/ember_aws/`. Add a one-line test per enum in `tests/test_aws_names_sizing.py`.
- [X] T008 Write the sizing tests in `tests/test_aws_names_sizing.py`:
  - the table loads;
  - exactly one `default: true` row with status `supported` per model;
  - a row whose `gpu_memory_gib` < the model's weights GiB + 4 must have status `unsupported`;
  - `resolve("flash", None)` → `g6e.xlarge`;
  - `resolve("flash", "g5.2xlarge")` → the row, status `tight` (the caller warns);
  - `resolve("flash", "g4dn.xlarge")` and `resolve("full", None)` raise `SizingError` with a message naming the reason (FR-005).
- [X] T009 Create `deployment/aws/sizing.json` with:
  - flash/`g6e.xlarge`: `gpu: "L40S"`, `gpu_memory_gib: 48`, `status: supported`, `default: true`, `request_cap: 24576`, `cap_source: fallback`, `hourly_usd: {"us-east-1": 1.861}`, `priced_on: "2026-10-11"`, `note: "fallback cap until aws-verify measures it"`;
  - flash/`g5.2xlarge`: `A10G`, 24, `tight`, `default: false`, cap 24576, fallback, `hourly_usd {"us-east-1": 1.212}`;
  - no `full` rows.

  Weights GiB per model come from `REGISTRY` in `ember/models.py` (import it absolutely, since this is outside the package).
- [X] T010 Implement `deployment/aws/ember_aws/sizing_entry.py` (`SizingEntry` BaseModel, the data-model.md fields) and `deployment/aws/ember_aws/sizing_table.py` (`SizingTable.load(path)` with the validation from T008 and `resolve(model, instance_type)`; `SizingError`, raised only by `SizingTable`, shares that file)
- [X] T011 [P] Write `tests/test_aws_template.py` against `deployment/aws/template.yaml` and `cache-template.yaml`. Use a YAML loader that tolerates the CFN tags `!Ref`, `!Sub`, `!GetAtt`, `!If`, `!Equals`, `!Not`. Assert every invariant in `contracts/infrastructure.md`:
  - the security group has no `SecurityGroupIngress`, and the template has no `AWS::EC2::SecurityGroupIngress` resource;
  - IAM statements are exactly the R8 set, with no `"*"` resource and no `ManagedPolicyArns`;
  - every `Resource` is scoped with `${DeploymentName}`, `${CacheBucket}`, or `${ModelPrefix}`;
  - `MetadataOptions.HttpTokens == required`;
  - the root volume is gp3 ≥ 100 GiB, `Encrypted: true`, `DeleteOnTermination: true`;
  - `InstanceInitiatedShutdownBehavior: stop`;
  - spot options are conditional on `Capacity == spot`, persistent, with interruption `stop`;
  - every taggable resource carries the `ember:deployment` and `ember:managed-by` tags;
  - no parameter or output name contains `token`, `secret`, or `key`;
  - the cache bucket has `DeletionPolicy: Retain`, `UpdateReplacePolicy: Retain`, all four public-access-block flags, SSE-S3, `BucketOwnerEnforced`, and a TLS-only deny policy.
- [X] T012 [P] Write `deployment/aws/cache-template.yaml` (stack `ember-model-cache`, bucket name `ember-model-cache-${AWS::AccountId}-${AWS::Region}`, output `BucketName`) to pass T011's cache assertions
- [X] T013 Write `deployment/aws/template.yaml` to pass T011:
  - parameters `DeploymentName`, `InstanceType`, `Capacity`, `ImageId` (type `AWS::EC2::Image::Id`), `SubnetId`, `VpcId`, `CacheBucket`, `ModelPrefix`, `TailscaleTag`. **No `UserData` parameter**: CloudFormation caps parameter values at 4,096 bytes;
  - resources `SecurityGroup`, `InstanceRole`, `InstanceProfile`, `Instance`;
  - `Instance.UserData`: `Fn::Base64` of the literal placeholder `__EMBER_USER_DATA__`, which T026 replaces with the rendered cloud-init before the template body is sent;
  - outputs `InstanceId` and `RoleArn`.
- [X] T014 [P] Write `tests/test_aws_deployment_models.py`:
  - `Deployment` defaults: region `us-east-1`, capacity `on-demand`, `idle_minutes` 0, `ember_version` = the `pyproject.toml` version, tag `tag:ember`;
  - `idle_minutes` < 0 is rejected;
  - `ember_version` must match `^\d+\.\d+\.\d+$` (FR-008);
  - `InstanceConfig` JSON round-trips;
  - `model_s3_uri` must start with `s3://` and end with `/<revision>`;
  - `max_request_length` must be > 0.
- [X] T015 [P] Implement `deployment/aws/ember_aws/deployment.py` (`Deployment`) and `deployment/aws/ember_aws/instance_config.py` (`InstanceConfig`, with `generation: int`) to pass T014
- [X] T016 Implement `deployment/aws/ember_aws/aws_clients.py`: an `AwsClients` dataclass(frozen) built from one `boto3.Session(region_name=…)` that exposes `cfn`, `ec2`, `ssm`, `s3`, `sts`, and `quotas`. This is the single seam that tests replace with stubbed clients (constructor injection; no module singletons).

**Checkpoint**: `make check typecheck lint` green. The templates and models are fixed.

---

## Phase 3: User Story 1 — Deploy from AWS credentials to a working endpoint (P1) 🎯 MVP

**Goal**: `make aws-cache && make aws-up` gives a healthy CUDA ember server at the
tailnet HTTPS URL, with no public ports.

**Independent test**: quickstart.md §1–§4.

### Tests (write first, confirm they fail)

- [X] T017 [P] [US1] `tests/test_aws_tailscale.py`, using `httpx.MockTransport`:
  - the token exchange posts `client_id`, `client_secret`, `grant_type=client_credentials`, and scope `auth_keys devices:core` to `/api/v2/oauth/token`;
  - `mint_join_key(tag)` posts `{"capabilities":{"devices":{"create":{"reusable":false,"ephemeral":false,"preauthorized":true,"tags":["tag:ember"]}}},"expirySeconds":3600}` to `/api/v2/tailnet/-/keys`;
  - `delete_devices(hostname, tag)` deletes only devices whose hostname equals `ember-<name>` **and** whose tags include the tag;
  - `tailnet_dns()` returns the MagicDNS flag from `GET /api/v2/tailnet/-/dns/preferences` and the `<tailnet>.ts.net` suffix. It makes no claim about HTTPS certificates, which the public API does not expose;
  - errors raise `TailscaleError` carrying the API `message`, and the secret is never in the `str()`.
- [X] T018 [P] [US1] `tests/test_aws_preflight.py`, with stubbed STS, Service Quotas (`L-DB2E81BA`, the G and VT on-demand vCPU quota), EC2 `describe_instance_type_offerings`, a mock Tailscale client, and a fake `shutil.which`. Each failing `PreflightCheck` produces exactly one `✗ <check>: <problem> — fix: <action>` line and exit code 1. The fixes are:
  - missing credentials → `aws sso login` / `AWS_PROFILE`;
  - quota < the instance's vCPUs → a link to the quota request;
  - type not offered → list the zones;
  - OAuth env missing;
  - a tag-ownership error → `tagOwners` guidance;
  - MagicDNS off.

  HTTPS certificates can't be checked through the API. Preflight prints one non-blocking notice, `! tailscale-https: cannot be checked before deploy — confirm "HTTPS Certificates" is on (admin console → DNS)`, which does not change the exit code.

  Also assert that **no** mutating AWS call (create/update/put/delete) is made by preflight. Preflight's test key must be deleted right after minting.
- [X] T019 [P] [US1] `tests/test_aws_model_cache.py`, with a stubbed S3/CFN, a fake `snapshot_download` writing files to `tmp_path`, and `ember.models.REGISTRY`:
  - `cache add` creates the `ember-model-cache` stack only if it is absent;
  - it uploads every file under `models/<model>/<revision>/`;
  - `manifest.json` (`{"model","revision","files":[{"path","size","sha256"}],"total_bytes"}`) is the **last** `put_object`;
  - a second run uploads nothing and prints `cached: flash@<rev> (already complete)`;
  - a missing manifest or a size mismatch reports `partial`;
  - `cache rm` exits 3 when an `ember-*` stack's config points at it;
  - `cache destroy` requires `--confirm <bucket>` and exits 3 while any deployment exists;
  - `--bucket/--prefix` skips stack creation.
- [X] T020 [P] [US1] `tests/test_aws_stack_lifecycle.py` (deploy part), with stubbed CFN/EC2/SSM and a mock Tailscale client:
  - `deploy` order: preflight → `ModelCache.status`; if not `complete`, `ModelCache.add` (a `partial` cache is resumed) → SSM `put_parameter` for the config (with an incremented `generation`) → token only if absent (`SecureString`, 32 random bytes, urlsafe) → delete tailnet devices → mint and put the join key (`SecureString`) → `create_stack` with resolved `ImageId` and subnet parameters and the tags → wait → health poll;
  - the health poll is `GET https://ember-<name>.<tailnet>.ts.net/health`, must return 200 with `engine.device == "cuda"`, and uses a timeout from the `EMBER_AWS_HEALTH_TIMEOUT` env (default 1200 s);
  - the success output exactly matches the contracts/cli.md block and **never contains the token**;
  - a stack failure exits 2 and prints the first `CREATE_FAILED` event reason.
- [X] T021 [P] [US1] `tests/test_aws_instance_scripts.py`. Render the instance files with test values and assert:
  - `tailscale-join.sh` runs `tailscale up` with `--hostname ember-<name> --advertise-tags <tag> --ssh`, then `aws ssm delete-parameter` on the join key, then `tailscale serve --bg --https=443 http://127.0.0.1:8765`;
  - it skips joining when `tailscale status` already shows it logged in;
  - if `tailscale serve` fails (HTTPS certificates disabled), it writes `ember: tailscale serve failed — enable HTTPS Certificates in the Tailscale admin console (DNS page)` to the journal and exits non-zero, while `ember.service` still starts on loopback;
  - `converge.sh` writes `/etc/ember/env` with `umask 077` / `chmod 600`, containing `EMBER_HOST=127.0.0.1`, `EMBER_DEVICE=cuda`, `EMBER_AUTOSTART=0`, `EMBER_MODEL_S3_URI`, `EMBER_MAX_REQUEST_LENGTH`, `EMBER_SERVER_AUTH_TOKEN`;
  - it installs exactly `ember-advise==<v>`;
  - it verifies SHA-256 against `manifest.json` and deletes and re-downloads a mismatching file;
  - `ember.service` runs as `User=ember` with `EnvironmentFile=/etc/ember/env` and `After=ember-converge.service`;
  - `converge.sh` runs `chown -R ember:ember` on the model cache directory after syncing;
  - no script echoes the token (no `set -x`, no `echo $EMBER_SERVER_AUTH_TOKEN`).

### Implementation

- [X] T022 [US1] Implement `deployment/aws/ember_aws/tailscale_client.py`: a `TailscaleClient(client_id: SecretStr, client_secret: SecretStr, transport: httpx.BaseTransport | None = None)` with `token()`, `mint_join_key(tag, expiry_s=3600)`, `delete_key(id)`, `devices()`, `delete_devices(hostname, tag)`, and `tailnet_dns()`. Base URL `https://api.tailscale.com`. `TailscaleError` lives in the same file. Read credentials from `TS_OAUTH_CLIENT_ID` and `TS_OAUTH_CLIENT_SECRET` in `from_env()`. Passes T017.
- [X] T023 [US1] Implement `deployment/aws/ember_aws/preflight.py`: a `Preflight(clients, tailscale, which=shutil.which)` with `run(deployment) -> list[CheckResult]`. `CheckResult` (BaseModel: `check`, `ok`, `problem`, `fix`, `blocking: bool`) lives in `deployment/aws/ember_aws/check_result.py`; `tailscale-https` is non-blocking. Required tools: `tailscale` (for logs, ssh, and reaching the URL). It must be read-only apart from minting and deleting one test key. Passes T018.
- [X] T024 [US1] Implement `deployment/aws/ember_aws/model_cache.py`:
  - a `ModelCache(clients, downloader=huggingface_hub.snapshot_download)` with `ensure_bucket()`, `add(model, bucket=None, prefix="models/")`, `list()`, `remove(model, revision)`, `destroy(confirm)`, and `status(model, revision) -> complete|partial|absent`;
  - use the same file allowlist as `ember/models.py`, uploading with `boto3.s3.transfer.TransferConfig(multipart_threshold=64MiB, max_concurrency=16)`;
  - skip files whose size and `x-amz-meta-sha256` already match;
  - write the manifest last;
  - put `CachedModel` and `CachedFile` BaseModels in `deployment/aws/ember_aws/cached_model.py`.

  Passes T019.
- [X] T025 [P] [US1] Write the instance files in `deployment/aws/instance/`: `tailscale-join.sh`, `converge.sh`, `ember-tailscale.service` (oneshot, `Before=ember-converge.service`), `ember-converge.service` (oneshot, runs every boot), `ember.service`, and `cloud-init.yaml`. `cloud-init.yaml`:
  - installs `uv` to `/usr/local/bin`, `tailscale` (official apt repo), and the `aws` CLI v2 if absent;
  - creates the user `ember`;
  - writes the files;
  - runs `systemctl enable --now ember-tailscale ember-converge ember`.

  `converge.sh` reads `/ember/<name>/config` and the token through `aws ssm get-parameter --with-decryption`. It keeps the last applied `generation` in `/var/lib/ember/generation` and installs and syncs only when it changes. It syncs the model to `ember`'s `paths.hosted_model_cache(uri)` directory, then verifies it against the manifest before `ember.service` starts (this fixes the R4 partial-dir risk). Passes T021.
- [X] T026 [US1] Implement `deployment/aws/ember_aws/user_data.py` (`UserData`):
  - `render(deployment, names) -> str` inlines the `deployment/aws/instance/` files into the cloud-init YAML with the values substituted (deployment name, region, tag, and parameter paths, never secrets);
  - `template_body(rendered) -> str` replaces `__EMBER_USER_DATA__` in `template.yaml` with the rendered cloud-init as a YAML block scalar and returns the full body `stack.py` sends as `TemplateBody`.

  Write these tests first, in `tests/test_aws_instance_scripts.py`: rendered user data ≤ 16,384 bytes (EC2 limit); the full template body ≤ 51,200 bytes (CloudFormation's inline `TemplateBody` limit); the result still parses and passes every T011 invariant; no stack parameter carries user data.
- [X] T027 [US1] Implement `deployment/aws/ember_aws/stack.py`:
  - a `Stack(clients, names)` with `exists()`, `create(params, tags)`, `update(params) -> changed: bool` (through a change set; an empty change set → `False`), `delete()`, `wait(op)`, `first_failure_reason()`, and `outputs()`;
  - `resolve_image_id(region)` reads `/aws/service/deeplearning/ami/x86_64/base-oss-nvidia-driver-gpu-ubuntu-24.04/latest/ami-id`, and only on create or replace;
  - `pick_subnet(instance_type)` picks the first default-VPC subnet in an AZ from `describe_instance_type_offerings(LocationType=availability-zone)`.
- [X] T028 [US1] Implement `deployment/aws/ember_aws/health.py`: `wait_healthy(url, token, timeout_s, transport=None)` polls `/health` every 10 s with `Authorization: Bearer <token>`. It treats 503 as "loading" (prints the `status` text once per change) and returns the parsed body when `engine.device == "cuda"`. On timeout it raises `HealthTimeout`, which carries the last response or error text (spec edge case: CUDA load failure shows the real error). When the URL never resolves or TLS fails, the message points at `make aws-logs UNIT=tailscale` and the HTTPS-certificates setting.
- [X] T029 [US1] Implement `deployment/aws/ember_aws/lifecycle.py` `Lifecycle.deploy(deployment)` in the T020 order. It warns on a `tight` sizing and refuses `unsupported` (exit 1). It also implements `token()`, which prints only the token. Passes T020.
- [X] T030 [US1] Implement `deployment/aws/ember_aws/__main__.py`: an argparse composition root with the subcommands `preflight`, `cache {add,list,rm,destroy}`, `deploy`, and `token` (US1 subset), mapping exceptions to exit codes 1, 2, and 3 (contracts/cli.md); `--json` where specified; `main()` returns an int. Fill the `aws-preflight`, `aws-cache`, `aws-cache-list`, `aws-cache-rm`, `aws-cache-destroy`, `aws-up`, and `aws-token` recipes in `shared/aws.mk`.
- [X] T031 [US1] Add `tests/test_aws_cli.py`, which checks the argparse wiring and the exit-code mapping for the US1 subcommands, using a fake `Lifecycle`/`ModelCache` injected through a `build(argv, factory)` seam.

**Checkpoint**: unit tests green. Run quickstart.md §2–§4 for real (needs an account).

---

## Phase 4: User Story 2 — See and control what is running (P1)

**Goal**: status, stop, start, logs, ssh, rotate-token, and destroy, each idempotent;
destroy leaves nothing tagged.

**Independent test**: quickstart.md §5 and §9.

### Tests

- [X] T032 [P] [US2] `tests/test_aws_status.py`:
  - `DeploymentStatus` is built from stubbed CFN/EC2/SSM, the Tailscale client, and a mocked `/health`;
  - `state` maps from the stack and instance states;
  - `stop_reason = idle` when the EC2 `StateReason.Code == "Client.InstanceInitiatedShutdown"` and `idle_minutes > 0`;
  - `spot-interruption` for the spot codes;
  - `cost_since_start = hourly × hours since LaunchTime`, rounded to cents and labelled `estimate`;
  - the spot price comes from `describe_spot_price_history`;
  - `idle_minutes` is shown as `off` when 0;
  - `absent` when there is no stack;
  - `--json` output validates against the model.
- [X] T033 [P] [US2] Add to `tests/test_aws_stack_lifecycle.py`:
  - `stop` on a running instance calls `stop_instances` and waits; on a stopped one it prints `already stopped` and makes no call;
  - `start` mints a fresh join key only if the device is missing from the tailnet, then starts and waits for health; on running it prints `already running: <url>`;
  - `destroy` without `--confirm <name>` exits 3;
  - `destroy` order: delete tailnet devices → `delete_stack` → wait → delete every `/ember/<name>/*` parameter (`get_parameters_by_path` + `delete_parameters`); it **never** touches the cache stack;
  - a second destroy prints `nothing deployed` (exit 0);
  - `rotate-token` overwrites the token parameter and reboots, then waits for health.
- [X] T034 [P] [US2] `tests/test_aws_remote.py`: `logs --unit ember --follow` builds the argv `["tailscale","ssh","root@ember-<name>","journalctl","-u","ember","-f"]`, with each `--unit` mapped to its systemd unit; `ssh` builds `["tailscale","ssh","root@ember-<name>"]`; it runs through an injected runner, never `shell=True`.

### Implementation

- [X] T035 [US2] Implement `deployment/aws/ember_aws/deployment_status.py` (`DeploymentStatus` BaseModel) and `deployment/aws/ember_aws/status_reader.py` (`StatusReader(clients, tailscale, sizing, http_transport=None).read(names)`), which tolerates any missing part (no stack, stopped, health unreachable → `health.error`). Passes T032.
- [X] T036 [US2] Extend `deployment/aws/ember_aws/lifecycle.py` with `stop`, `start`, `destroy(confirm)`, and `rotate_token`. Passes T033.
- [X] T037 [P] [US2] Implement `deployment/aws/ember_aws/remote.py`: `Remote(names, runner=subprocess.run)` with `logs(unit, follow)` and `ssh()`. Passes T034.
- [X] T038 [US2] Wire `status [--json]`, `stop`, `start`, `logs`, `ssh`, `rotate-token`, and `destroy --confirm` into `deployment/aws/ember_aws/__main__.py`, and fill the matching recipes in `shared/aws.mk` (`aws-down` passes `--confirm $(CONFIRM)` and prints how to set `CONFIRM=<name>`). Extend `tests/test_aws_cli.py`.

**Checkpoint**: run quickstart.md §5 and §9. SC-003: `get-resources` with the
deployment's tag is empty.

---

## Phase 5: CUDA verification gate (FR-024, SC-007)

Every story depends on this before the feature is called done. It runs once US1 can
deploy.

- [X] T039 [P] `tests/test_context_probe.py`: a new test asserting that the probe accepts `device="cuda"` and that `evals/context/memory_sampler.py` picks `torch.cuda.max_memory_allocated` (after `torch.cuda.synchronize`) when the device is CUDA, using a fake torch module. The existing MPS behaviour stays unchanged.
- [X] T040 Implement CUDA support in `evals/context/memory_sampler.py` and `evals/context/items.py` (remove the hard-coded `device="mps"`; take the device from `EMBER_DEVICE`/`--device`), and add `--device {mps,cuda}` to `ember eval context` in `ember/commands/eval.py`, with a test in `tests/test_cli_eval_dataset.py` or `tests/test_context_probe.py`. The cap rule takes the memory budget from the sizing row's `gpu_memory_gib` when the device is CUDA.
- [X] T041a Write the failing argv tests for `verify` in `tests/test_aws_remote.py`:
  - on the instance, through `tailscale ssh ember@ember-<name>`: `git clone --depth 1 --branch v<ember_version> https://github.com/shapeandshare/ember /opt/ember-src && cd /opt/ember-src && uv sync --locked && EMBER_MODEL_DIR=<local cache dir> EMBER_DEVICE=cuda make test-strict && .venv/bin/ember eval context --device cuda`, copying the summary back;
  - on the operator side: `ember eval run` with `EMBER_SERVER_URL`/`EMBER_AUTH_TOKEN` set only in the child environment, then `ember eval report --compare` against the newest MPS bundle in `benchmark/`.
- [X] T041 Implement `verify` in `deployment/aws/ember_aws/remote.py` and the `aws-verify` recipe in `shared/aws.mk` to pass T041a. It calls `ember eval context --device cuda` directly, so no new make variable is needed.
- [ ] T042 Run `make aws-verify` on a real `g6e.xlarge`. Then record the measured cap in `deployment/aws/sizing.json` (`request_cap`, `cap_source: "measured"`), add an "NVIDIA L40S (g6e.xlarge)" row and update "Running in the cloud" in `COMPATIBILITY.md`, and write a vault discovery for any CUDA-specific failure found. Fix CUDA defects in `ember/serving/` test-first.

---

## Phase 6: User Story 3 — Update and replace without changing the client setup (P2)

**Goal**: a version, model, or instance-type change keeps the URL and token. Running it
again with no change does nothing.

**Independent test**: quickstart.md §6.

- [X] T043 [P] [US3] Add to `tests/test_aws_stack_lifecycle.py`:
  - deploy with only `ember_version` changed → the config `generation` goes up, an empty change set means no stack update, `reboot_instances` is called, and health is waited on; the token is unchanged and no tailnet devices are deleted;
  - an `instance_type` change → a change set with `InstanceType` (stop/start by CFN), the tailnet devices are **not** deleted;
  - no change at all → no `put_parameter`, no reboot, prints `up to date: <url>`;
  - a change set whose resource change has `Replacement: True` → the tailnet devices are deleted and a new join key minted **before** `execute_change_set`;
  - `replace` → re-resolve the DLAMI ID, force replacement (a new `ImageId`), delete the devices and mint a key first, then wait for health.
- [X] T044 [P] [US3] Add to `tests/test_aws_instance_scripts.py`: `converge.sh` with an unchanged `generation` skips install and sync; with a new generation and the same `model_s3_uri` it skips the model sync; with a new `model_s3_uri` it syncs the new prefix (SC-002, FR-007).
- [X] T045 [US3] Extend `Lifecycle.deploy` in `deployment/aws/ember_aws/lifecycle.py` with the update path: compare the desired `InstanceConfig` to the stored one; inspect the change set's `Replacement`; reboot only when only the config changed. Add `Lifecycle.replace()`. Passes T043.
- [X] T046 [US3] Wire `replace` into `__main__.py` and the `aws-replace` recipe in `shared/aws.mk`, and extend `tests/test_aws_cli.py`

---

## Phase 7: User Story 4 — Keep costs bounded (P2)

**Goal**: an opt-in idle stop, opt-in spot capacity, and cost shown in status.

**Independent test**: quickstart.md §7.

- [X] T047 [P] [US4] Add to `tests/test_aws_instance_scripts.py`. `idle.sh`, with a fake `/metrics` body and a state file in `tmp_path`:
  - it parses `ember_advise_requests_total` summed over all `status` labels;
  - it resets the timestamp when the count changes;
  - it calls the injected shutdown command once the count is unchanged for ≥ `idle_minutes`;
  - it does nothing when `idle_minutes` is 0.

  `converge.sh` enables `ember-idle.timer` only when `idle_minutes > 0` and disables it otherwise.
- [X] T048 [P] [US4] Add to `tests/test_aws_stack_lifecycle.py`: `CAPACITY=spot` passes `Capacity=spot`; changing spot to on-demand is treated as a replacement (devices deleted first). Add to `tests/test_aws_status.py`: the spot hourly rate comes from `describe_spot_price_history` for the instance's AZ.
- [X] T049 [US4] Write `deployment/aws/instance/idle.sh`, `ember-idle.service`, and `ember-idle.timer` (`OnUnitActiveSec=1min`), and enable or disable them in `converge.sh`. Passes T047.
- [X] T050 [US4] Finish the spot handling in `template.yaml` (the condition), `lifecycle.py`, and `status_reader.py`. Passes T048.

---

## Phase 8: Polish and cross-cutting

- [X] T051 [P] Write `deployment/aws/README.md`: what it deploys; prerequisites (AWS quota, Tailscale OAuth client with scopes and tags, the `tagOwners` example, MagicDNS + HTTPS certificates); costs (hourly from `sizing.json`, the S3 cache storage cost); every `make aws-*` command with examples; how to connect clients (`ember init --server-url`, `export EMBER_AUTH_TOKEN`); updating; teardown (the deployment, then the cache); troubleshooting (preflight lines, `aws-logs --unit converge`). Add a one-line index at the top of `deployment/README.md` pointing to `aws/` (FR-026).
- [X] T052 [P] Update `README.md`: a "Hosted on AWS over Tailscale" subsection under "Ways to run ember" / "Remote inference", the `make aws-*` rows in the Make targets table, and a link to `deployment/aws/README.md`
- [ ] T053 [P] Update `COMPATIBILITY.md` "Running in the cloud" with the AWS path and its status (after T042)
- [X] T054 [P] Update `AGENTS.md`: `deployment/aws/` and `shared/aws.mk` in Project structure; the `make aws-*` rows in Commands; the new test files in the Testing table; "What to watch out for" entries: never run AWS/Tailscale in tests or CI; the instance has no inbound rules; the OAuth secret never leaves the operator machine; the cache stack is `Retain` and is never deleted by `aws-down`; `full` is refused until sized. Also add a Recent Changes entry.
- [X] T055 [P] Write the vault decision note `vault/decisions/2026-10-11-aws-gpu-deployment-over-tailscale.md` from `vault/_meta/templates/decision.md`. It covers research R1, R4, R5, R6, and R8 and the FR-007 amendment, with tags from `vault/_meta/tags.md`, `[[ember]]`, `status/draft`. List it in `vault/ember.md`. Write a discovery note `vault/discoveries/2026-10-11-hosted-cache-treats-partial-dir-as-complete.md` for the `ember/serving/hosted.py` non-empty-dir check (research R4). Run `make vault-audit`.
- [X] T056 Fix `ember/serving/hosted.py` test-first. Add a failing test in `tests/test_model_integrity.py` (or the existing hosted test module): a partially downloaded cache dir is re-downloaded. Then use a completion marker written after the download finishes.
- [X] T056a [P] Implement `aws-tools` / `aws-tools-rm` in `shared/aws.mk` (FR-003):
  - `aws-tools` checks for the `tailscale` CLI and installs it with `brew install --cask tailscale` on macOS (on Linux it prints the install URL). It is idempotent and records what it installed in `.aws-tools.installed` (gitignored);
  - `aws-tools-rm` removes only what that file lists;
  - both print what they did; add help lines and a `make -n` dry-run test in `tests/test_aws_cli.py`.
- [X] T056b [P] Add a test in `tests/test_cli.py` (FR-023): with `EMBER_SERVER_URL` pointed at a stub `/health` (random port, never 8765) that reports `version`, `auth_required: true`, and `engine.device: "cuda"`, `ember doctor` reports the endpoint as remote and prints its version and device. If it doesn't, fix `ember/commands/doctor.py` test-first.
- [ ] T057 Run `make pr-ready` and `make test-cov` (floor 94, never lowered), then the full real-cloud `specs/005-aws-gpu-deployment/quickstart.md` §1–§9, recording the results in a session log `vault/sessions/2026-10-11-aws-gpu-deployment.md`

---

## Dependencies and execution order

- **Phase 1 → Phase 2 → stories.** T002/T003 come before any typecheck. T009 comes before T010. T011 comes before T012/T013. T014 comes before T015.
- **US1 (Phase 3)** depends on Phase 2. Inside it: T017–T021 (tests) → T022–T025 → T026 → T027/T028 → T029 → T030/T031.
- **US2 (Phase 4)** depends on T027 (`stack.py`), T022, and T029. Its tests can be written in parallel with late US1 work.
- **CUDA gate (Phase 5)**: T039/T040 depend only on Phase 1. T041a → T041; T041 depends on T037. T042 depends on US1 being deployable (real hardware).
- **US3 (Phase 6)** depends on US1 (`deploy`) and US2 (`start`/health).
- **US4 (Phase 7)** depends on US1. Its status parts depend on T035.
- **Polish**: T053 depends on T042. T056, T056a, and T056b are independent; do them early if convenient. T057 is last.

```
Setup → Foundational → US1 ──► US2 ──► US3
                         │       └────► US4
                         └──► CUDA gate (T042 needs real deploy) ──► Polish
```

## Parallel examples

- **Phase 2**: T005, T007, T011, and T014 at the same time (different test files). Then T006, T012, and T015.
- **US1 tests**: T017, T018, T019, T020, and T021 at the same time. Then T022, T024, and T025 in parallel (different files), then T023 (uses the Tailscale client).
- **US2**: T032, T033, and T034 at the same time; T037 alongside T035.
- **Phase 5**: T039/T040 can run any time after Phase 1, alongside US1.
- **Polish**: T051–T055 at the same time.

## Implementation strategy

1. **MVP = Phases 1–3 (US1) plus `aws-down` from US2 (T033's destroy subset, T036, and T038).** Never ship a deploy without a destroy, because GPU time is billed per second. Validate with quickstart §1–§4 and §9.
2. Then the rest of US2 (status, stop, start), then the **CUDA gate** (T042). The feature is not "done" until it passes (FR-024).
3. Then US3, then US4, then Polish.
4. Commit atomically per task group with scoped Conventional Commits: `feat(deploy): …` is cross-cutting, so the scope may be omitted under AGENTS.md rule 6; use `feat(evals): …` for T039/T040 and `fix(ember): …` for T056. Tests go in the same commit as the code they cover.
