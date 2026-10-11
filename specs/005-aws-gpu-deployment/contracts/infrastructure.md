# Contract: CloudFormation stacks and the instance

Unit tests check these invariants (FR-025) by parsing `deployment/aws/template.yaml` and
`deployment/aws/cache-template.yaml`. They never call AWS.

## Stack `ember-<name>` (`template.yaml`)

**Parameters** (no `UserData` parameter, because CloudFormation caps parameter values at
4,096 bytes; the CLI inlines the user data into the template body at the
`__EMBER_USER_DATA__` placeholder; body ≤ 51,200 bytes, user data ≤ 16,384 bytes):
`DeploymentName`, `InstanceType`, `Capacity` (`on-demand|spot`),
`ImageId` (type `AWS::EC2::Image::Id`; the CLI resolves the DLAMI SSM parameter once and
passes the ID so the image is recorded in the stack; R2), `SubnetId`, `VpcId`,
`CacheBucket`, `ModelPrefix` (`models/<model>/<revision>/`), `TailscaleTag`.

**Resources** (and nothing else):

| Resource | Invariants |
| --- | --- |
| `SecurityGroup` | **no `SecurityGroupIngress`** (SC-004); egress all |
| `InstanceRole` + `InstanceProfile` | exactly the statements in research R8; every ARN scoped to `/ember/${DeploymentName}/` or `${CacheBucket}/${ModelPrefix}`; no `*` resource, no managed policies |
| `Instance` | `ImageId` from the parameter; `InstanceInitiatedShutdownBehavior: stop`; IMDSv2 required (`HttpTokens: required`); root gp3 100 GiB, encrypted, `DeleteOnTermination: true`; `InstanceMarketOptions` only when `Capacity=spot` (persistent, interruption `stop`); `UserData` = cloud-init that installs the instance files and enables the units (first boot only) |

**Tags** on every taggable resource: `ember:deployment=<name>`, `ember:managed-by=ember_aws`
(FR-018).

**Outputs**: `InstanceId`, `RoleArn`. No secrets in parameters or outputs.

## Stack `ember-model-cache` (`cache-template.yaml`)

One `AWS::S3::Bucket`: `DeletionPolicy: Retain` and `UpdateReplacePolicy: Retain`, all four
`PublicAccessBlockConfiguration` flags true, SSE-S3, `OwnershipControls:
BucketOwnerEnforced`, and a bucket policy denying non-TLS access. Output: `BucketName`.

## Instance files (`deployment/aws/instance/`, installed by cloud-init)

| File | Contract |
| --- | --- |
| `ember-tailscale.service` (oneshot, `Before=ember-converge.service`) | If not yet joined: read the join key, run `tailscale up --auth-key … --hostname ember-<name> --advertise-tags <tag> --ssh`, delete the key parameter. Then `tailscale serve --bg --https=443 http://127.0.0.1:8765`; if that fails, log "enable HTTPS Certificates in the Tailscale admin console" and exit non-zero (ember still starts on loopback) |
| `ember-converge.service` (oneshot, every boot) | Read `/ember/<name>/config` and the server token; if `generation` changed, `uv tool install ember-advise==<v>` and sync `model_s3_uri` to the local cache, verifying every file's SHA-256 against the manifest (a partial download is never left looking complete); `chown -R ember:ember` the cache directory; write `/etc/ember/env` (0600) with `EMBER_HOST=127.0.0.1`, `EMBER_DEVICE=cuda`, `EMBER_MODEL_S3_URI`, `EMBER_MAX_REQUEST_LENGTH`, `EMBER_SERVER_AUTH_TOKEN`, `EMBER_AUTOSTART=0` |
| `ember.service` (`After=ember-converge.service`, `Restart=on-failure`) | `ember serve`, running as the unprivileged user `ember`, with `EnvironmentFile=/etc/ember/env` |
| `ember-idle.timer` / `ember-idle.service` | Enabled only when `idle_minutes > 0` (R10) |

ember binds only to `127.0.0.1:8765`. The only listener reachable on the tailnet is
Tailscale's 443, plus Tailscale SSH (FR-009a).

## Cached model layout (S3)

```
s3://<bucket>/models/<model>/<revision>/
  config.json, joint_schema_model.py, joint_head.safetensors, joint_head_config.json,
  model.safetensors.index.json, model-*.safetensors, …   (same allowlist as ember/models.py)
  manifest.json   # {"model","revision","files":[{"path","size","sha256"}],"total_bytes"} — written last
```
