# Data Model: AWS GPU Deployment over Tailscale

The operator-side Python tooling (`deployment/aws/ember_aws/`) owns these records. Records
that cross a boundary are Pydantic `BaseModel`s: AWS (SSM parameter JSON, stack
parameters), the instance (the config parameter), and on-disk files (the sizing table and
cache manifest). Values from a fixed set are `StrEnum`s (Article X).

## Enums

| Enum | Values |
| --- | --- |
| `Capacity` | `on-demand`, `spot` |
| `DeploymentState` | `absent`, `creating`, `running`, `stopping`, `stopped`, `updating`, `replacing`, `destroying`, `failed` |
| `StopReason` | `operator`, `idle`, `spot-interruption`, `unknown` |
| `SizingStatus` | `supported`, `tight` (allowed with a warning), `unsupported` (refused) |

Each enum, and each record below, lives in its own module in `ember_aws` (Article X §10.2, which the plan adopts).
| `CapSource` | `measured`, `fallback` (matches `ember/serving/limit_source.py` vocabulary when reported) |
| `PreflightCheck` | `aws-identity`, `region`, `tooling`, `gpu-quota`, `instance-offering`, `tailscale-oauth`, `tailscale-tag`, `tailscale-magicdns`, `tailscale-https`, `model-cached` |

## DeploymentName

- A string matching `^[a-z][a-z0-9-]{1,30}[a-z0-9]$`, default `default`.
- Derived names: stack `ember-<name>`, tailnet hostname `ember-<name>`, SSM path
  `/ember/<name>/`, tag `ember:deployment=<name>`.
- Unique per account and region. Two operators pick different names, so their
  deployments don't collide (spec edge case).

## Deployment (the desired state the operator provides)

| Field | Type | Rule |
| --- | --- | --- |
| `name` | `DeploymentName` | as above |
| `region` | `str` | default `us-west-2` |
| `model` | `str` | a `REGISTRY` key (`flash`; `full` refused until sized) |
| `revision` | `str` | from `REGISTRY[model].revision`; must be in the cache (FR-006a) |
| `instance_type` | `str` | default from `SizingEntry`; an `unsupported` type is refused (FR-005) |
| `capacity` | `Capacity` | default `on-demand` (FR-021) |
| `idle_minutes` | `int ≥ 0` | default `0` = off (FR-020) |
| `ember_version` | `str` | exact `X.Y.Z`; defaults to the checkout's `pyproject.toml` version (FR-008) |
| `subnet_id` | `str \| None` | default: an automatically chosen subnet in the default VPC (R9) |
| `tailscale_tag` | `str` | default `tag:ember` |

## InstanceConfig (SSM `/ember/<name>/config`, read by the instance at every boot)

| Field | Type | Rule |
| --- | --- | --- |
| `ember_version` | `str` | pinned |
| `model_s3_uri` | `str` | `s3://<cache>/models/<model>/<revision>` |
| `max_request_length` | `int > 0` | from `SizingEntry.request_cap` (FR-006c) |
| `idle_minutes` | `int ≥ 0` | |
| `generation` | `int` | goes up on every deploy that changes anything; the converge unit compares it with the value it last applied |

## Secrets (SSM SecureString; never in a model's `repr`, never logged)

| Parameter | Lifetime | Written by | Read by |
| --- | --- | --- | --- |
| `/ember/<name>/server-token` | until `rotate-token` or destroy | deploy (only if missing) | instance (converge), operator (`--show-token`) |
| `/ember/<name>/tailscale-join-key` | ≤ 1 h, single use | deploy / start-after-replace | instance, which deletes it after joining |

The Tailscale OAuth client is only ever in the operator's environment. No record stores it.

## SizingEntry (`deployment/aws/sizing.json`)

| Field | Type |
| --- | --- |
| `model` | `str` |
| `instance_type` | `str` |
| `gpu`, `gpu_memory_gib` | `str`, `int` |
| `status` | `SizingStatus` |
| `default` | `bool` (exactly one `supported` default per model) |
| `request_cap`, `cap_source` | `int`, `CapSource` |
| `hourly_usd` | `dict[region, float]` |
| `priced_on` | ISO date |
| `note` | `str` |

Validation: `gpu_memory_gib` must cover the model's weights plus 4 GiB, or `status` is
`unsupported`. Seed rows: flash/`g6e.xlarge` (default, L40S 48, cap 24,576 fallback);
flash/`g5.2xlarge` (tight, A10G 24); full (no row, so it is refused).

## ModelCache and CachedModel

- **ModelCache**: `bucket`, `prefix` (default `models/`), `region`, `managed: bool` (whether
  the tooling created it). It has its own stack, `ember-model-cache`, with
  `DeletionPolicy: Retain`.
- **CachedModel**: `model`, `revision`, `s3_uri`, `total_bytes`, and `files:
  list[CachedFile(path, size, sha256)]`. Its manifest is `<prefix><model>/<revision>/manifest.json`,
  written last. A cached model is **complete** only if the manifest exists and every listed
  object exists with a matching size. The SHA-256 is checked on the instance after
  download.
- Removing a cached model is refused while any `ember-*` stack's `InstanceConfig` points at
  it. Removing the whole cache needs typed confirmation and no deployments left (FR-017).

## DeploymentStatus (output of `status`)

| Field | Source |
| --- | --- |
| `state`, `stop_reason` | stack status and EC2 state, plus `StateReason` (R10, R11) |
| `instance_id`, `instance_type`, `capacity`, `az` | EC2 |
| `tailnet_name`, `url` | Tailscale API device: `https://ember-<name>.<tailnet>.ts.net` |
| `health` | `GET <url>/health` (model, device, version, limits with sources), or the error text |
| `uptime`, `hourly_usd`, `cost_since_start_usd` | `LaunchTime`, sizing table / spot price history |
| `idle_minutes` | `InstanceConfig` (always shown; `off` when 0) |

## State transitions

```
absent ──deploy──► creating ──healthy──► running
running ──stop──► stopping ──► stopped(operator)
running ──idle timer──► stopped(idle)            running ──spot reclaim──► stopped(spot-interruption)
stopped ──start──► running
running|stopped ──deploy(changed)──► updating ──► running        (in place: reboot or stop/start)
running|stopped ──replace──► replacing ──► running              (delete tailnet device, mint key, new instance)
any ──destroy──► destroying ──► absent                           (delete tailnet device, delete stack, delete /ember/<name>/*)
creating|updating|replacing ──error──► failed ──deploy|destroy──► …
```

Every transition is idempotent (FR-015). Running a command again while already in the
target state does nothing and reports so.
