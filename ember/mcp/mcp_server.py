"""ember MCP stdio server: the ``advise`` tool plus its agent guidance.

A thin, async client. Each tool call goes to the configured inference endpoint
(``ember.serving.server`` by default on loopback; a remote endpoint when configured).
A loopback server is started on demand through ``process.start`` — the same model
resolution, pid file, and log as ``ember start``. The model never loads in this
process, so the MCP handshake stays instant.

opencode and Kilo Code both namespace tools as ``<server>_<tool>``: with the
server key ``ember`` the tool appears as ``ember_advise`` (Claude Code:
``mcp__ember__advise``).

Env:
    EMBER_SERVER_URL              default http://127.0.0.1:8765 (endpoint)
    EMBER_AUTH_TOKEN              optional client credential (secret)
    EMBER_AUTH_HEADER             default Authorization (else a custom header)
    EMBER_ALLOW_INSECURE_TRANSPORT  default 0 (refuse plaintext to non-local)
    EMBER_REQUEST_TIMEOUT         default 900 seconds
    EMBER_AUTOSTART               default 1 (0 disables; loopback only)
    EMBER_START_TIMEOUT           default 300 seconds
"""

from __future__ import annotations

import json
import logging
import os
import re
import ssl
import sys
from typing import Any

import anyio
import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from ..agent_kit import api as agent_kit
from ..cfg.endpoint import (
    Endpoint,
    InsecureEndpointError,
    InvalidEndpointError,
    build_auth_headers,
)
from ..serving import process
from .mcp_types import AdviseInput

_PATH_RE = re.compile(r"(/[^\s:]+|[A-Za-z]:\\[^\s:]+)")
_TRACEBACK_RE = re.compile(r"Traceback \(most recent call last\)", re.IGNORECASE)


def _redact(text: str) -> str:
    """Strip filesystem paths and traceback markers from an error message.

    Prevents internal paths and stack traces from leaking to the calling agent
    via ToolError messages (I-002).

    Parameters
    ----------
    text : str
        The raw error string to clean.

    Returns
    -------
    str
        The input with filesystem paths replaced by ``<path>`` and any
        traceback header stripped.
    """
    text = _PATH_RE.sub("<path>", text)
    text = _TRACEBACK_RE.sub("<traceback>", text)
    return text


# stdout is the JSON-RPC wire; log to stderr only.
# R-003: configure the named logger directly (not basicConfig, which is a no-op
# when any handler already exists) so the timestamp format is always present.
log = logging.getLogger("ember-mcp")
if not log.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [ember-mcp] %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    log.addHandler(_handler)
    log.setLevel(logging.INFO)

AUTOSTART = os.environ.get("EMBER_AUTOSTART", "1").lower() not in (
    "0",
    "false",
    "no",
    "",
)
START_TIMEOUT = float(os.environ.get("EMBER_START_TIMEOUT", "300"))

mcp = MCPServer("ember", instructions=agent_kit.instructions())


@mcp.resource(
    agent_kit.GUIDE_URI,
    name="ember-guide",
    description="Full playbook for the advise tool: schemas, thresholds, and recipes.",
    mime_type="text/markdown",
)
def guide() -> str:
    """Return the full ``ember-advise`` playbook for the ``ember://guide`` resource.

    Returns
    -------
    str
        The skill's ``SKILL.md`` content.
    """
    return agent_kit.skill()


def _ensure_server(endpoint: Endpoint) -> None:  # async-first:exception - worker thread
    """Start the local model server on first use, for loopback endpoints only.

    Remote endpoints are never autostarted and are not health-probed here; the
    advise request itself surfaces reachability failures.

    Parameters
    ----------
    endpoint : Endpoint
        The resolved inference endpoint.

    Raises
    ------
    RuntimeError
        If a loopback endpoint is down, ``EMBER_AUTOSTART`` is disabled, or the
        server fails to start.
    """
    if not endpoint.is_local:
        return
    if process.is_up(endpoint.host, endpoint.port):
        return
    if not AUTOSTART:
        raise RuntimeError(
            f"ember server not reachable at {endpoint.url} and EMBER_AUTOSTART=0. "
            "Start it with: ember start"
        )
    log.info(
        "ember server not running; starting it on %s:%s", endpoint.host, endpoint.port
    )
    process.start(host=endpoint.host, port=endpoint.port, timeout=START_TIMEOUT)
    log.info("ember server is ready")


def _sanitize_error(status_code: int, body: str) -> str:
    """Build a safe ToolError message from an HTTP error response.

    For 4xx errors, extract only the ``detail`` field from FastAPI's JSON
    error body so that internal file paths and stack traces never reach the
    calling agent (I-002). For 5xx errors, return a generic message and log
    the full body to stderr — the agent cannot act on server internals, and
    the body may contain filesystem paths or tracebacks.

    Parameters
    ----------
    status_code : int
        The HTTP status code returned by the server.
    body : str
        The raw response body text.

    Returns
    -------
    str
        A sanitized, agent-safe error message that always includes the status
        code.
    """
    if status_code >= 500:
        log.error(
            "ember server %d (body redacted from ToolError): %s", status_code, body
        )
        return f"ember server error {status_code}: server-side error (see ember logs)"
    try:
        parsed = json.loads(body)
        detail = parsed.get("detail")
        if detail is not None:
            if isinstance(detail, list):
                msgs = ", ".join(_redact(str(d.get("msg") or d)) for d in detail if d)
                return f"ember server error {status_code}: {msgs}"
            return f"ember server error {status_code}: {_redact(str(detail))}"
    except (json.JSONDecodeError, AttributeError):
        pass
    return f"ember server error {status_code}"


def _client_error_message(exc: httpx.HTTPError, endpoint: Endpoint) -> str:
    """Map an httpx failure to a distinct, actionable message.

    Parameters
    ----------
    exc : httpx.HTTPError
        The transport failure raised by the request.
    endpoint : Endpoint
        The endpoint that was contacted.

    Returns
    -------
    str
        A message distinguishing timeout, TLS certificate failure, and a plain
        unreachable endpoint.
    """
    if isinstance(exc, httpx.TimeoutException):
        return (
            f"ember server timed out after {endpoint.request_timeout}s "
            f"at {endpoint.url}"
        )
    if isinstance(exc.__cause__, ssl.SSLError):
        return (
            f"TLS certificate verification failed for {endpoint.url}: {exc.__cause__}"
        )
    if isinstance(exc, httpx.ConnectError):
        return f"ember server not reachable at {endpoint.url}"
    return f"ember server request failed at {endpoint.url}: {exc}"


@mcp.tool()
async def advise(input: AdviseInput) -> dict[str, Any]:
    """Get ember's read on a situation, as calibrated probabilities.

    ember (a decision model) advises; you decide. Consult it at bounded decision
    points: intent, triage, routing, yes/no gates, and risk, severity, or effort
    scores. It sees only what you pass, so include every piece of evidence the call
    depends on and attach images or video frames as base64 `data:` URIs in
    `images`/`videos` when pixels are the evidence. For 'choice' the answer has the
    leading option, its confidence, and full probabilities; for 'score' an expected
    score over the ordered criteria; for 'noul' the probability the proposition is true.
    """
    # Only ToolError messages reach the agent; anything else is reported generically.
    try:
        endpoint = Endpoint.resolve()
    except (InvalidEndpointError, InsecureEndpointError) as exc:
        raise ToolError(str(exc)) from exc
    if endpoint.is_local:
        try:
            await anyio.to_thread.run_sync(_ensure_server, endpoint)
        except RuntimeError as exc:
            raise ToolError(str(exc)) from exc
    payload: dict[str, Any] = {
        "model": input.model,
        "state": input.state,
        "questions": {
            key: question.model_dump(exclude_none=True)
            for key, question in input.questions.items()
        },
    }
    if input.images is not None:
        payload["images"] = input.images
    if input.videos is not None:
        payload["videos"] = input.videos
    if input.media_kwargs is not None:
        payload["media_kwargs"] = input.media_kwargs
    try:
        async with httpx.AsyncClient(timeout=float(endpoint.request_timeout)) as client:
            resp = await client.post(
                f"{endpoint.url}/v1/systemone",
                json=payload,
                headers=build_auth_headers(),
            )
    except httpx.HTTPError as exc:
        raise ToolError(_client_error_message(exc, endpoint)) from exc
    if resp.status_code in (401, 403):
        raise ToolError(
            f"ember server authentication failed ({resp.status_code}) at "
            f"{endpoint.url}; check auth_token/auth_header"
        )
    if resp.status_code >= 400:
        raise ToolError(_sanitize_error(resp.status_code, resp.text))
    try:
        answer: dict[str, Any] = resp.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ToolError(
            f"endpoint at {endpoint.url} did not return a valid ember response"
        ) from exc
    loaded = str(answer.get("model") or "")
    log.info(
        "advise: questions=%s model=%s",
        repr(",".join(sorted(input.questions))),
        repr(loaded or input.model),
    )
    # Only an explicitly requested label can mismatch; the schema default is a
    # placeholder and would otherwise warn on every call.
    requested = "model" in input.model_fields_set
    if requested and loaded and input.model and loaded != input.model:
        answer["warning"] = (
            f"endpoint loaded model {loaded!r}, not the requested {input.model!r}"
        )
        log.warning("%s", answer["warning"])
    return answer


def main() -> None:
    """Run the MCP stdio server; blocks until the client disconnects."""
    try:
        endpoint = Endpoint.resolve()
        url = endpoint.url
        # S-004: warn when EMBER_SERVER_URL is non-loopback over plaintext HTTP
        # with insecure transport explicitly allowed — agent state (potentially
        # containing secrets) will be sent unencrypted to a remote host.
        if (
            not endpoint.is_local
            and endpoint.scheme == "http"
            and endpoint.allow_insecure_transport
        ):
            log.warning(
                "EMBER_SERVER_URL=%r is a non-loopback address over plaintext "
                "http with EMBER_ALLOW_INSECURE_TRANSPORT enabled — agent state "
                "will be sent unencrypted. Use https or a loopback address.",
                url,
            )
    except (InvalidEndpointError, InsecureEndpointError) as exc:
        url = f"<invalid: {exc}>"
    log.info("ember MCP server starting (server_url=%s, autostart=%s)", url, AUTOSTART)
    # stdout is the JSON-RPC wire; any non-protocol output corrupts it.
    mcp.run()


if __name__ == "__main__":
    main()
