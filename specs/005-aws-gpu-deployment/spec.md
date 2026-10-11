# Feature Specification: AWS GPU Deployment over Tailscale

**Feature Branch**: `005-aws-gpu-deployment`

**Created**: 2026-10-11

**Status**: Draft

**Input**: User description: "Automate as much as possible: given AWS credentials, get a deployed ember inference instance. NVIDIA/CUDA only on AWS; reach it over Tailscale; keep it as a separate deployment directory alongside the Outerbounds deployment; full lifecycle management."

## Clarifications

### Session 2026-10-11

- Q: Which accelerator on AWS? → A: NVIDIA GPUs (CUDA) only. Apple Silicon (EC2 Mac) is out of scope.
- Q: How do clients reach the deployed server? → A: Tailscale. The server is reachable only on the operator's tailnet; it has no public inbound port.
- Q: How should the deployment get access to your Tailscale account? → A: A Tailscale OAuth client scoped to one tag (e.g. `tag:ember`); the tooling mints a short-lived join key per boot, removes the node on destroy, and frees the name before a replacement joins.
- Q: How should clients connect over the tailnet: HTTPS, or plain HTTP with the transport check off? → A: HTTPS via `tailscale serve` on the node's `https://<name>.<tailnet>.ts.net` address with an automatic certificate; ember binds only to 127.0.0.1.
- Q: With no idle timeout set, should an idle instance stop itself by default? → A: No. Off by default; the instance runs until the operator stops it, and the idle timeout is opt-in.
- Q: Where should the instance get model weights? → A: From S3, always. The tooling caches each model (pinned Hugging Face revision) into an S3 model cache once; hosted instances load only from that cache via `EMBER_MODEL_S3_URI`, never from Hugging Face.
- Q: Where does the deployment live? → A: A separate deployment directory next to the existing Outerbounds deployment (`deployment/`), not inside the `ember` Python package.
- Q: How much lifecycle? → A: Full lifecycle: create, status, update, stop/start, replace, destroy, plus cost controls.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Deploy from AWS credentials to a working endpoint (Priority: P1)

An operator who has AWS credentials and a Tailscale account runs one command and, without
further manual steps, ends up with an ember server on an NVIDIA GPU instance that their
agents can call over the tailnet.

**Why this priority**: This is the feature. Nothing else has value until one instance
answers `advise` requests.

**Independent Test**: In a clean AWS account meeting the stated prerequisites, run the deploy
command, then point `ember init --server-url <tailnet URL>` at the result and get calibrated
answers from `advise`.

**Acceptance Scenarios**:

1. **Given** valid AWS credentials and a tag-scoped Tailscale OAuth client, **When** the operator runs
   the deploy command, **Then** an instance is created, joins the tailnet, loads the model on
   the GPU, and reports healthy, and the command prints the tailnet URL and the exact
   `ember init` line to use.
2. **Given** the deploy finished, **When** a client on the tailnet calls `advise`, **Then** it
   gets answers computed on the GPU (the health endpoint reports device `cuda`).
3. **Given** a host not on the tailnet, **When** it tries to reach the instance, **Then** no
   ember port is reachable from the public internet.
4. **Given** prerequisites are missing (credentials, tooling, GPU quota, Tailscale OAuth
   credential), **When** the operator runs the deploy command, **Then** it stops before
   creating anything and lists each missing item with how to fix it.

---

### User Story 2 — See and control what is running (Priority: P1)

The operator can ask what is deployed, whether it is healthy, what it costs, and stop, start,
or destroy it, with one command each.

**Why this priority**: A GPU instance left running by accident costs real money; status and
destroy ship with deploy, not after it.

**Independent Test**: After a deploy, run status, stop, status, start, status, destroy, and
confirm each reports the true AWS and model state and that destroy leaves no billable
resources behind.

**Acceptance Scenarios**:

1. **Given** a deployment, **When** the operator runs status, **Then** it shows instance state,
   instance type, tailnet address, model loaded or not, ember version, uptime, and estimated
   hourly cost.
2. **Given** a running deployment, **When** the operator stops it, **Then** GPU billing stops,
   and start brings the same endpoint back with the same tailnet name.
3. **Given** a deployment, **When** the operator destroys it, **Then** every resource the
   deployment created is removed, the tailnet node is removed, and a follow-up status reports
   nothing deployed. The shared S3 model cache is kept; removing it is a separate, confirmed
   command.
4. **Given** destroy is interrupted, **When** it is run again, **Then** it finishes the job
   without error (idempotent).

---

### User Story 3 — Update and replace without changing the client setup (Priority: P2)

The operator can roll the deployment to a new ember release, model, or instance type, and
clients keep working with the same URL and token.

**Why this priority**: Releases ship often; redeploying must not mean re-onboarding every
agent.

**Independent Test**: Deploy version N, update to version N+1, and confirm the client config
is untouched and `/health` reports N+1.

**Acceptance Scenarios**:

1. **Given** a running deployment, **When** the operator updates the ember version, **Then** the
   instance runs the new version and the tailnet URL and auth token are unchanged.
2. **Given** a running deployment, **When** the operator changes the instance type or model,
   **Then** the instance is updated in place where AWS allows it (otherwise replaced), the tailnet name
   is preserved, and local weights are reused where the model is unchanged.
3. **Given** the deploy command is re-run with no changes, **Then** nothing is replaced and the
   command reports "up to date" (idempotent).

---

### User Story 4 — Keep costs bounded (Priority: P2)

The operator can make an idle instance stop itself and can choose cheaper capacity.

**Why this priority**: The main cost risk of a GPU deployment is idle time.

**Independent Test**: Deploy with a short idle timeout, send no traffic, and confirm the
instance stops itself and status reports why.

**Acceptance Scenarios**:

1. **Given** an idle timeout is set, **When** no `advise` requests arrive for that long, **Then**
   the instance stops itself and status reports "stopped: idle".
2. **Given** the operator opts into spot capacity, **When** spot is unavailable or reclaimed,
   **Then** the deployment reports it clearly and the operator can fall back to on-demand with
   one command.
3. **Given** a deployment, **When** the operator runs status, **Then** it shows the estimated
   running cost since the last start.

---

### Edge Cases

- No GPU quota in the region, or the instance type is unavailable in every zone: deploy fails
  before creating anything, naming the quota and how to request it.
- The model does not fit the chosen GPU's memory: deploy refuses instance types below the
  model's declared requirement rather than starting a server that runs out of memory.
- The Tailscale OAuth client is revoked, lacks the tag, or the join fails: deploy reports the
  failure, the instance does not sit unreachable unnoticed, and status shows it.
- The tailnet lacks MagicDNS: preflight fails before creating anything and names the setting.
  Tailscale's API does not expose whether HTTPS certificates are on, so preflight prints a
  reminder; if they are off, the instance's `tailscale serve` fails with a message naming the
  setting, and status and the deploy health timeout surface it.
- A node with the deployment's tailnet name already exists (left over from a crash): the
  tooling removes it before the new instance joins, so the name does not drift (e.g. `-1`).
- The model fails to load on CUDA (driver or library mismatch): status reports the server's
  actual error, not just "unhealthy".
- Two operators deploy into the same account: deployments are named and do not collide or
  destroy each other.
- The operator's local state is lost: status and destroy can still find the deployment from
  AWS (resources are tagged), so nothing is orphaned.
- Hugging Face is unavailable while caching: the cache command fails and resumes on re-run;
  instances are unaffected because they never read from Hugging Face.
- A cache upload was interrupted: deploy refuses to use a partial cached model (checksums
  missing or mismatched) and the cache command completes it.
- The first request after a start arrives before the model is loaded: the server answers 503
  (existing behavior), and the client sees a "loading" message, not a crash.

## Requirements *(mandatory)*

### Functional Requirements

**Setup and prerequisites**

- **FR-001**: The deployment MUST live in its own directory next to the Outerbounds deployment
  and MUST NOT add cloud-provisioning code or dependencies to the `ember` package.
- **FR-002**: A preflight MUST check, before creating anything: AWS credentials and identity,
  target region, GPU quota for the chosen instance type, required local tooling, and a
  Tailscale OAuth client that can mint keys for the configured tag; each failure MUST name the fix.
- **FR-003**: Any required local tooling MUST be installable and removable by one make target
  each, following the repo's lifecycle convention.

**Provisioning**

- **FR-004**: One command MUST take the operator from prerequisites to a healthy endpoint with
  no manual steps in the AWS console or on the instance.
- **FR-005**: Only NVIDIA GPU instance types are supported. The instance type MUST default per
  model from a recorded sizing table and MAY be overridden; an override below the model's
  memory requirement MUST be refused.
- **FR-006**: The instance MUST run `ember serve` with device `cuda` and load weights only from
  the S3 model cache (`EMBER_MODEL_S3_URI`). Instances MUST NOT download from Hugging Face.
- **FR-006a**: A cache command MUST copy a model's pinned Hugging Face revision into the S3
  model cache under a key that names the model and revision, and MUST be idempotent (skips
  files already present and verified by size and checksum). Deploy MUST run it automatically
  when the chosen model and revision are not yet cached.
- **FR-006b**: The S3 model cache MUST be created by the tooling by default (private,
  encrypted, public access blocked, one per account and region, shared by all deployments
  there); the operator MAY supply an existing bucket and prefix instead. The cache MUST be
  listable (which models and revisions are cached, and their size) and a cached revision
  removable.
- **FR-006c**: Because an S3-loaded model bypasses the model registry (and would otherwise
  get the lowest registry request cap), deploy MUST set the instance's request cap explicitly
  from the sizing table's measured cap for that model on that instance type, and `/health`
  MUST report it with source "operator".
- **FR-007**: The instance MUST keep a local copy of the weights that survives stop/start and
  every in-place update (version, model setting, idle timeout, instance type), so those never
  re-download. An explicit replace MAY re-pull from the in-region S3 model cache (amended at
  planning, research R4: a retained data volume was rejected under Article XV).
- **FR-008**: The installed ember version MUST be the pinned release (`ember-advise==X.Y.Z`),
  never an unpinned "latest".

**Network and security**

- **FR-009**: The instance MUST join the operator's tailnet on first boot and MUST have no
  public inbound ports (no SSH, no ember port open to the internet).
- **FR-009a**: Clients MUST reach ember only over HTTPS at the node's MagicDNS name
  (`https://<name>.<tailnet>.ts.net`), served by `tailscale serve` with a certificate
  Tailscale issues. The ember server MUST bind to 127.0.0.1 only, so the sole listener on the
  tailnet is 443. Clients MUST NOT need `EMBER_ALLOW_INSECURE_TRANSPORT`.
- **FR-010**: The ember server MUST require bearer authentication even on the tailnet; the
  token MUST be generated at deploy, stored in a secret store, and never written to any
  committed file, generated client config, or log.
- **FR-011**: Tailscale access MUST come from an operator-supplied Tailscale OAuth client
  scoped to a single tag (default `tag:ember`), kept in a secret store and never on the
  instance. For each boot the tooling MUST mint a short-lived, single-use, pre-authorized
  join key carrying that tag, deliver it through a secret store, and delete it once the
  node has joined. Before a replacement joins, the tooling MUST remove the old node so the
  tailnet name stays the same.
- **FR-012**: The instance's cloud permissions MUST be the minimum needed: read its own secrets
  and read-only access to its model's prefix in the S3 model cache. Nothing account-wide, and
  no write access to the cache.
- **FR-013**: The operator MUST have shell access only through Tailscale or the cloud's
  session manager, never an open SSH port.

**Lifecycle**

- **FR-014**: The deployment MUST provide commands for: cache (add, list, remove a cached
  model), deploy (create or update), status, stop, start, replace, logs, and destroy, each
  runnable via `make`.
- **FR-015**: Every command MUST be idempotent: re-running after success or interruption
  converges without error or duplication.
- **FR-016**: Status MUST report instance state, type, tailnet address, ember health (model,
  device, version, limits), uptime, and an hourly and since-start cost estimate.
- **FR-017**: Destroy MUST remove every created resource (including the instance's local
  weights) and the tailnet node. Destroying
  a deployment MUST NEVER delete the shared S3 model cache; removing the cache is its own
  command with typed confirmation, and it refuses while any deployment still uses it.
- **FR-018**: All resources MUST carry a deployment-name tag so status and destroy work without
  local state, and so multiple named deployments can share an account.
- **FR-019**: An update to ember version, model, or instance type MUST keep the tailnet name
  and auth token, so clients need no reconfiguration.
- **FR-020**: The idle timeout MUST be off by default (the instance runs until stopped). When
  the operator sets it, the instance MUST stop itself after that many minutes with no `advise`
  requests (using the server's existing request metrics); `0` or unset means off. Status MUST
  show whether an idle timeout is set, so an always-on instance is visible.
- **FR-021**: Spot capacity MUST be opt-in, with on-demand as the default.

**Client hand-off**

- **FR-022**: On success, deploy MUST print the tailnet HTTPS URL and the exact `ember init
  --server-url …` command (adding `--auth-header` only for a non-default header), and tell the operator to export `EMBER_AUTH_TOKEN`
  (the token is never placed in config files).
- **FR-023**: `ember doctor` on a client pointed at the deployment MUST report it as a remote
  server with its version and device, with no new client code required beyond what exists.

**Verification and documentation**

- **FR-024**: Before this feature is called done, the CUDA path MUST be verified on real NVIDIA
  hardware: model-backed tests pass with `EMBER_DEVICE=cuda`, and each supported model's
  request cap on its default instance type is measured with the long-context probe and
  recorded (`COMPATIBILITY.md`, registry).
- **FR-025**: Unit tests MUST cover the deployment definition (permissions, no public ingress,
  tags, secret handling, pinned version) without touching a real AWS account; anything that
  creates real resources stays out of `make check`, `make test`, and CI.
- **FR-026**: README, COMPATIBILITY, and the deployment directory's own README MUST document
  prerequisites, costs, every lifecycle command, and teardown.

### Key Entities

- **Deployment**: A named ember server in one AWS account and region; has an instance type,
  model, ember version, capacity mode (on-demand or spot), idle timeout, and lifecycle state.
- **Instance**: The current GPU machine backing a deployment; replaceable.
- **S3 model cache**: A private bucket (or operator-supplied prefix) per account and region,
  holding one copy of each cached model revision; shared by all deployments; outlives them.
- **Cached model**: One model at one pinned revision in the S3 model cache; keyed by model name
  and revision; has size and per-file checksums.
- **Local weights**: An instance's copy of its cached model on its own disk; survives stop/start
  and in-place updates, not replacement.
- **Tailnet node**: The deployment's identity on Tailscale; stable name across replacement.
- **Secrets**: The ember bearer token (long-lived, rotatable), the Tailscale OAuth client
  (operator-side, tag-scoped, never on the instance), and the per-boot join key (short-lived,
  single-use, deleted after join).
- **Sizing table**: Per model, the default GPU instance type, its memory, and the measured
  request cap on it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From valid prerequisites, an operator gets a healthy, callable endpoint with one
  command and zero manual console steps, in under 20 minutes on first deploy (us-west-2, model already cached in the region;
  caching itself happens once per region and is not counted).
- **SC-002**: A stop followed by a start returns a healthy endpoint in under 10 minutes
  (us-west-2, default instance type),
  without re-downloading weights.
- **SC-002a**: After a model is cached, a new deployment (or replacement) downloads nothing
  from Hugging Face, and a second deployment of the same model in the same region does not
  re-cache it.
- **SC-003**: After destroy, the account holds nothing tagged with the deployment's name; only
  the shared S3 model cache remains.
- **SC-004**: A port scan from the public internet finds no open port on the instance, and a
  scan from the tailnet finds only 443 (plus Tailscale SSH, if FR-013 uses it).
- **SC-005**: Updating the ember version requires no change to any client configuration.
- **SC-006**: With an idle timeout set, an unused instance stops within the timeout plus 10
  minutes.
- **SC-007**: Benchmark accuracy on the GPU deployment matches the MPS baseline for the same
  model and dataset version within the benchmark's confidence interval.
- **SC-008**: Re-running any lifecycle command after it succeeded changes nothing.

## Assumptions

- The operator has an AWS account with permission to create compute, storage, networking,
  identity, and secrets resources, and has (or can request) GPU quota.
- The operator has a Tailscale account, can create an OAuth client with the `auth_keys` and
  `devices` scopes for the chosen tag, has that tag defined in the tailnet policy, and uses
  MagicDNS (checked by preflight) and HTTPS certificates (reminded by preflight, detected
  on the instance) enabled.
- Default region is `us-west-2`; the operator can override it. Single region, single account
  per deployment.
- Initial instance defaults: an NVIDIA GPU with at least 48 GB of memory for `flash` (for
  example L40S-class); `full` needs a larger GPU and is a P2 target pending measurement.
- Provisioning reuses the proven pattern from the sibling `darkharbour` repo
  (`component/ec2/`: infrastructure-as-code stack, first-boot Tailscale join from a secret
  store, minimal role, preflight); the choice of IaC tool is a planning
  decision.
- The existing `deployment/` directory (Outerbounds) is the "deploy" directory the user
  referred to; whether Outerbounds files move into a subdirectory is a planning decision and
  must keep `tests/test_freeze_deployment_requirements.py` and the release workflow working.
- A stock GPU-ready machine image with NVIDIA drivers is used; no custom image pipeline in v1.
- Constitution Article IV (never interfere with the host) applies to the operator's machine:
  the tooling never kills processes by pattern and never edits the operator's global Tailscale
  or AWS config.
- Out of scope for v1: multi-instance scaling or load balancing, public (non-tailnet) access,
  EC2 Mac, other clouds, and auto-start on incoming requests.
