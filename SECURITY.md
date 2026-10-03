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

- **`ember/server.py`**: FastAPI HTTP endpoint bound to `127.0.0.1:8765`. Potential
  issues include request-validation bypasses, denial-of-service via malformed payloads, or
  unintended exposure of the endpoint beyond localhost.
- **`ember/mcp_server.py`**: MCP stdio boundary between the agent and the HTTP server.
  Potential issues include prompt-injection via malformed `state` or `questions` fields, or
  tool-schema confusion that causes an agent to misuse the `advise` tool.
- **`ember/process.py`**: PID-file lifecycle management. Potential issues include
  TOCTOU races on the pidfile, privilege-escalation risks, or stale-pidfile attacks.
- **`ember/cli.py`**: CLI command handling. Potential issues include unsafe subprocess
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

The HTTP server binds to `127.0.0.1` by default and is intended for local use only. It
**must not** be exposed to external networks. There is no authentication layer on the HTTP
endpoint; the security boundary is the loopback interface.

If you deploy ember in an environment where the loopback interface is shared (e.g., a
multi-user server or a container with a shared network namespace), you are responsible for
adding appropriate access controls. This configuration is not supported and is outside the
intended threat model.

## Disclosure policy

This project follows coordinated disclosure. Once a fix is ready and tested, the maintainer
will:

1. Publish a patched release.
2. Open a GitHub Security Advisory with full details.
3. Credit the reporter (unless they prefer to remain anonymous).

Public disclosure happens after the patch is available, or after 90 days from the initial
report if no fix is forthcoming, whichever comes first.
