# Implementation Plan: AWS GPU Deployment over Tailscale

**Branch**: `005-aws-gpu-deployment` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/005-aws-gpu-deployment/spec.md`

## Summary

The operator provides AWS credentials and a Tailscale OAuth client, and `make aws-up`
produces a healthy ember server on an NVIDIA GPU instance. Clients reach it only at
`https://ember-<name>.<tailnet>.ts.net`, and every lifecycle step has its own `make`
target. The approach:

- **Provisioning**: one committed CloudFormation template, driven by a small Python CLI
  (`deployment/aws/ember_aws/`) that uses only libraries ember already depends on (boto3,
  httpx, huggingface-hub).
- **Weights**: copied once per region into a shared, retained S3 cache. Instances pull
  only from S3, through the existing `EMBER_MODEL_S3_URI` path.
- **Network**: the instance joins the tailnet with a single-use key minted per boot.
  `tailscale serve` provides HTTPS in front of ember, which listens only on loopback.
- **Updates**: applied in place by a converge unit that runs on every boot.
- **CUDA**: verified on real L40S hardware before the feature is done.

## Technical Context

- **Language/Version**: Python 3.12 (uv), operator side. Bash and systemd on the instance
  (Ubuntu 24.04 DLAMI, `/usr/bin/python3.12`).
- **Primary Dependencies**: boto3 (CloudFormation, EC2, SSM, S3, STS, Service Quotas),
  httpx (Tailscale API), and huggingface-hub (cache fill), all existing runtime
  dependencies. CloudFormation YAML. On the operator's machine, the `tailscale` CLI for
  logs and ssh. **No new runtime dependency.** Dev only: widen `boto3-stubs` extras.
- **Storage**: An S3 model cache, one per account and region, retained. SSM Parameter
  Store holds the config and two SecureStrings. The instance's root gp3 volume holds the
  local weights.
- **Testing**: pytest unit tests (`tests/test_aws_*.py`). They use `botocore.stub.Stubber`,
  `httpx.MockTransport`, and YAML assertions on the templates. The real-cloud checks are
  `quickstart.md` plus `make aws-verify`, and are never part of `make check`, `make test`,
  or CI.
- **Target Platform**: AWS EC2 `g6e.xlarge` (L40S 48 GB) by default; the G5/G6/G6e
  families are allowed via the sizing table. The operator runs macOS or Linux.
- **Project Type**: Deployment tooling (a CLI plus infrastructure as code), outside the
  `ember` package.
- **Performance Goals**: first deploy under 20 minutes; start under 10 minutes; idle stop
  within the timeout plus 10 minutes.
- **Constraints**:
  - No inbound ports in AWS.
  - The instance role is scoped to its own parameters and its model's S3 prefix.
  - Secrets never appear in templates, outputs, logs, or generated configs.
  - The ember version is pinned.
  - Idempotent commands.
- **Scale/Scope**: single instance per named deployment; single region per deployment;
  `flash` only in v1 (`full` is refused until a single ≥80 GB GPU type is sized).

## Constitution Check

*Gate: checked before Phase 0 and again after Phase 1.*

| Article | Assessment | Status |
| --- | --- | --- |
| I — Local or Remote, Never Silent | Remote mode, configured explicitly with `ember init --server-url`. Weights go to an S3 bucket the user chose, in their own account, and are never redistributed from this repo. Loopback stays the default. | ✅ |
| II — Typed Decisions | API unchanged. | ✅ |
| III — Agent-Legible Contract | Kit unchanged. README and COMPATIBILITY updated (FR-026). | ✅ |
| IV — Non-Interfering Lifecycle | The operator-side tooling starts and stops only the AWS and Tailscale resources it created, matched by tag and name, never by pattern on the host. It never edits the operator's AWS or Tailscale config. On the instance, ember starting at boot is the operator's explicit opt-in (they deployed it). Tests open no ports and touch no cloud. | ✅ |
| V — Model Loading | Uses `EMBER_MODEL_S3_URI` as designed. `uv.lock` is unchanged apart from stub extras. The instance installs a pinned `ember-advise==X.Y.Z`. | ✅ |
| VI — Apple Silicon and CUDA | CUDA via `device_map={"": "cuda"}`. FR-024 makes real-hardware verification a gate (CUDA is unverified today). | ✅ (gated) |
| VII — Verification | `quickstart.md` and `make aws-verify` exercise the real system. | ✅ |
| VIII — Tooling | ruff, mypy `--strict`, and bandit extended to `deployment/aws/ember_aws`. Configuration stays in `pyproject.toml`. | ✅ |
| IX — Vault | A decision note (`vault/decisions/2026-10-11-aws-gpu-deployment-over-tailscale.md`) records R1, R4, and R6. | ✅ (task) |
| X — Python Conventions | New code: one class per file, Pydantic at boundaries, StrEnums, NumPy docstrings, relative imports inside `ember_aws`. | ✅ |
| XI — TDD and Coverage | Red-green per module. The coverage source is extended to `ember_aws`, and the floor (94) is not lowered. | ✅ |
| XII — Async-First | No FastAPI routes. The CLI is a short-lived synchronous process (boto3 is sync). No async I/O path is added inside ember. | ✅ (N/A) |
| XIII — Layers | No change to `ember/`. `ember_aws` talks to ember only over HTTPS (`/health`). | ✅ |
| XIV — Pit of Success | Preflight fails before any change, with a fix for each failure. Destroy is idempotent and guarded. Partial caches are detected. | ✅ |
| XV — Simplicity | CloudFormation and boto3 rather than CDK or Terraform (R1). No separate data volume (R4). Default VPC (R9). No interface endpoints (R8). Static pricing (R12). Spec FR-007 narrowed to match. | ✅ |

**Result: PASS.** No violations, so Complexity Tracking is empty. Post-design re-check:
PASS. Phase 1 added no new dependency, layer, or ingress.

## Project Structure

### Documentation (this feature)

```text
specs/005-aws-gpu-deployment/
├── spec.md
├── plan.md              # this file
├── research.md          # R1–R14
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   └── infrastructure.md
├── checklists/requirements.md
└── tasks.md             # /speckit.tasks
```

### Source Code (repository root)

```text
deployment/
├── README.md                 # + one-line index: Outerbounds here, AWS in aws/
├── flash.yaml full.yaml requirements.txt   # Outerbounds, unchanged
└── aws/
    ├── README.md             # prerequisites, costs, every command, teardown (FR-026)
    ├── template.yaml         # stack ember-<name>
    ├── cache-template.yaml   # stack ember-model-cache
    ├── sizing.json           # SizingEntry rows (data-model.md)
    ├── instance/             # cloud-init and systemd units, converge.sh, idle.sh, tailscale-join.sh
    └── ember_aws/
        ├── __init__.py       # bare docstring
        ├── __main__.py       # argparse composition root
        ├── names.py          # DeploymentName + derived names
        ├── capacity.py deployment_state.py stop_reason.py sizing_status.py cap_source.py preflight_check.py   # one StrEnum each
        ├── deployment.py     # Deployment model
        ├── instance_config.py
        ├── sizing_entry.py sizing_table.py
        ├── check_result.py preflight.py
        ├── user_data.py      # renders cloud-init, inlines it into the template body
        ├── model_cache.py cached_model.py   # cache add/list/rm/destroy + manifest
        ├── aws_clients.py health.py
        ├── tailscale_client.py
        ├── stack.py          # create/update/delete, change sets, waiters
        ├── lifecycle.py      # stop/start/replace/destroy orchestration
        ├── deployment_status.py status_reader.py   # status + cost
        └── remote.py         # tailscale ssh: logs, ssh, verify
shared/aws.mk                 # aws-* targets (wired into Makefile + help)
tests/
├── test_aws_template.py      # infrastructure.md invariants (no ingress, scoped IAM, IMDSv2, tags, retain)
├── test_aws_names_sizing.py
├── test_aws_preflight.py
├── test_aws_model_cache.py
├── test_aws_tailscale.py
├── test_aws_stack_lifecycle.py
├── test_aws_status.py
└── test_aws_instance_scripts.py   # render + assert invariants (loopback bind, 0600 env, key deletion)
evals/context/                # + CUDA device switch and CUDA memory sampler (R13)
```

**Structure Decision**: Everything lives under `deployment/aws/`, next to the Outerbounds
files, which stay where they are so `shared/release.mk`, the freeze script and its test,
and the release workflow keep working (R14). `ember_aws` is not part of the wheel.

## Delivery order (for /speckit.tasks)

1. **Foundation**: names, enums, sizing, and the template plus its invariant tests (P1).
2. **US1 deploy**: preflight → model cache → Tailscale client → stack create → instance
   units → health wait → output.
3. **US2 control**: status (with cost), stop, start, destroy, logs, ssh, token.
4. **CUDA gate**: CUDA support in `evals/context`, then `aws-verify` on real hardware;
   record the cap, update COMPATIBILITY.
5. **US3 update/replace**: config generation, in-place reboot, instance-type stop/start,
   replace.
6. **US4 cost**: idle timer, spot.
7. **Docs and memory**: README sections, `deployment/aws/README.md`, AGENTS.md (structure,
   commands, "watch out for"), vault decision note.

## Complexity Tracking

No violations, so nothing to justify.
