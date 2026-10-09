# Security Policy

## Reporting a vulnerability

**Do not open a public GitHub issue for a security vulnerability.**

Report vulnerabilities privately through GitHub's
[private vulnerability reporting](https://github.com/shapeandshare/ember/security/advisories/new):
open the repository's **Security** tab and choose **Report a vulnerability**. Only you and
the maintainers can see the report.

Include as much detail as you can: the affected component, a description of the issue, steps
to reproduce, and your assessment of impact. A minimal proof-of-concept is helpful but not
required for the initial report.

## Response timeline

| Stage | Target |
| --- | --- |
| Acknowledgment | Within 5 business days of receipt |
| Assessment and confirmation | Within 10 business days |
| Coordinated disclosure | Agreed with reporter before any public disclosure |

If you haven't received an acknowledgment within 5 business days, follow up via the same
channel. Response times may be longer around public holidays.

## Scope

### In scope

The following areas are in scope for security reports:

- **`ember/serving/server.py`**: FastAPI HTTP endpoint, bound to `127.0.0.1:8765` by default
  (`EMBER_HOST` can widen it; `EMBER_SERVER_AUTH_TOKEN` then gates it). Potential issues
  include request-validation bypasses, denial-of-service via malformed payloads, bearer-auth
  bypass, or unintended exposure of the endpoint beyond localhost.
- **`ember/cfg/endpoint.py`**: client endpoint resolution for remote inference. Potential
  issues include loopback misclassification, bypass of the insecure-transport guard, or
  credential leakage through the auth headers it builds.
- **`ember/serving/media.py`**: base64 media decoding for `images` and `videos`. Potential
  issues include malformed media references or resource exhaustion during decode.
- **`ember/mcp/mcp_server.py`**: MCP stdio boundary between the agent and the HTTP server.
  Potential issues include prompt-injection via malformed `state` or `questions` fields, or
  tool-schema confusion that causes an agent to misuse the `advise` tool.
- **`ember/serving/process.py`**: PID-file lifecycle management. Potential issues include
  TOCTOU races on the pidfile, privilege-escalation risks, or stale-pidfile attacks.
- **`ember/cli.py`, `ember/commands/`**: CLI command handling. Potential issues include unsafe subprocess
  invocation patterns or argument-injection vulnerabilities.
- **Dependency vulnerabilities** in the pinned ranges declared in `pyproject.toml` and
  `uv.lock`, particularly in `torch`, `transformers`, `fastapi`, `uvicorn`, and `mcp`.
- **CI and release workflows** (`.github/workflows/`): for example, a way for a pull request
  from a fork to obtain a write token or a secret, or to run code outside a GitHub-hosted
  runner.

### Out of scope

- **Model weights** (`clef-flash` and related files): report weight-level issues to Cloudflare
  or the Hugging Face repository directly.
- **`joint_schema_model.py`** from the Hugging Face snapshot: this file is Apache-2.0 upstream
  code imported at runtime from the model directory. Report issues to the upstream maintainer.
- **Issues that require physical access** to the machine running the server.
- **Misconfiguration by the operator** that intentionally exposes the server beyond localhost.

## Security-sensitive design notes

The HTTP server binds to `127.0.0.1` by default. A user may configure a remote inference
endpoint (`EMBER_SERVER_URL`); the client refuses plaintext `http` to a non-loopback host
unless `EMBER_ALLOW_INSECURE_TRANSPORT` is set, and a custom credential header is meant for a
proxy that translates it. To serve other machines, set `EMBER_HOST` and set
`EMBER_SERVER_AUTH_TOKEN` so `/v1/systemone` requires `Authorization: Bearer <token>`
(compared with `secrets.compare_digest`); `/health` and `/metrics` stay unauthenticated for
probes. Ember does not terminate TLS, so front remote-serving deployments with a proxy. When
`EMBER_SERVER_AUTH_TOKEN` is unset the HTTP endpoint has no authentication layer and the
security boundary is the network (loopback or an operator-managed proxy).

If you deploy ember in an environment where the loopback interface is shared (e.g., a
multi-user server or a container with a shared network namespace), you are responsible for
adding appropriate access controls. This configuration is not supported and is outside the
intended threat model.

### Hosted deployment (EMBER_MODEL_S3_URI) — operator trust model

When `EMBER_MODEL_S3_URI` is set, ember downloads a model snapshot from that S3 location at
startup and imports `joint_schema_model.py` from the downloaded directory as executable
Python. **Ember performs no cryptographic integrity check on the downloaded content** —
this is an explicit architectural decision (constitution Article V, "Model Loading"). The
security of a hosted deployment therefore depends entirely on the controls the operator
applies to that S3 location:

- **Restrict write access.** The IAM principal that manages the model artifacts should be the
  only entity with write (`s3:PutObject`, `s3:DeleteObject`) permission on the bucket prefix
  named by `EMBER_MODEL_S3_URI`. Compute roles that only _run_ ember need `s3:GetObject` and
  `s3:ListBucket` only.
- **Use immutable infrastructure.** Set `EMBER_MODEL_S3_URI` as a sealed, non-user-supplied
  environment variable in your deployment platform (e.g., an Outerbounds parameter or a
  Kubernetes secret). An attacker who can override this variable at deployment time can
  redirect ember to an arbitrary S3 bucket and achieve arbitrary code execution in the model
  server process.
- **Enable S3 versioning and object lock.** Versioning gives you rollback; object lock
  (WORM) prevents silent replacement of model artifacts.
- **Prefer IAM roles over long-lived credentials.** `EMBER_S3_ACCESS_KEY_ID` /
  `EMBER_S3_SECRET_ACCESS_KEY` in the config file or environment are a credential-leakage
  risk if the deployment environment is not fully isolated. Attached IAM roles (e.g., an
  Outerbounds execution role) are preferred; boto3's default credential chain picks them up
  automatically when the explicit keys are unset.

The same principle applies to `EMBER_MODEL_DIR`: any directory pointed to by that variable is
loaded and its `joint_schema_model.py` executed without verification. Keep its value out of
user-supplied input.

### Accepted residual risks (single-user loopback deployment)

The following are known, accepted risks for the default single-user loopback deployment. They are tracked in `docs/stride-review.md` and will not be fixed unless the deployment model changes.

**Pidfile integrity (T-005):** `server.pid` is a plain-text file with no cryptographic signature. The `_is_ember_server` check (verifying the process command string via `/bin/ps`) plus cross-checking the `/health` endpoint's reported PID are strong compensating controls. An attacker would need local write access to the state directory *and* the ability to spawn a process with matching argv — a high bar on a single-user workstation.

**`/health` and `/metrics` information disclosure (I-005, I-006):** `GET /health` returns the server PID, package version, and whether bearer auth is required. `GET /metrics` exposes `ember_model_info{model,device,dtype}`. These endpoints are intentionally unauthenticated (they are used for health probes and Prometheus scraping). In the default loopback-only deployment any process on the same host can read them; in a shared-namespace environment (see above) they disclose server identity. If this is a concern, front the server with an authenticating reverse proxy.

**No structured access log on `/health` / `/metrics` (R-005):** uvicorn logs HTTP requests to `server.log` but in an unstructured format. For a single-user local tool this is acceptable. For shared environments, use a reverse proxy with structured access logging.

**PID reuse TOCTOU (S-003):** Between `_is_ember_server` confirming the PID and `os.kill` sending SIGTERM, the ember server could exit and the OS could reuse its PID for an unrelated process. The combined `_is_ember_server` + `/health` PID cross-check reduces this window to near-zero in practice. This is an OS-level race that cannot be fully closed in userspace without kernel support (e.g., `pidfd`). Documented here as an accepted residual risk.

## Disclosure policy

This project follows coordinated disclosure. Once a fix is ready and tested, the maintainer
will:

1. Publish a patched release.
2. Open a GitHub Security Advisory with full details.
3. Credit the reporter (unless they prefer to remain anonymous).

Public disclosure happens after the patch is available, or after 90 days from the initial
report if no fix is forthcoming, whichever comes first.
