"""ember MCP stdio server: the ``advise`` tool plus its agent guidance.

A thin client. Each tool call goes to the warm model server (``ember.serving.server``).
When that server is down and EMBER_AUTOSTART is on, it is started through
``process.start`` — the same model resolution, pid file, and log as
``ember start``. The model never loads in this process, so the MCP handshake
stays instant.

opencode namespaces tools as ``<server>_<tool>``: with the server key ``ember``
the tool appears as ``ember_advise`` (Claude Code: ``mcp__ember__advise``).

Env:
    EMBER_SERVER_URL     default http://127.0.0.1:8765
    EMBER_AUTOSTART      default 1 (0 disables)
    EMBER_START_TIMEOUT  default 300 seconds
"""

from __future__ import annotations

import ipaddress
import logging
import os
import sys
from typing import Any
from urllib.parse import urlparse

import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from ..agent_kit import api as agent_kit
from ..serving import process
from .mcp_types import AdviseInput

# stdout is the JSON-RPC wire; log to stderr only.
logging.basicConfig(
    level=logging.INFO, stream=sys.stderr, format="[ember-mcp] %(message)s"
)
log = logging.getLogger("ember-mcp")

SERVER_URL = os.environ.get("EMBER_SERVER_URL", "http://127.0.0.1:8765").rstrip("/")


def validate_server_url(url: str) -> None:
    """Enforce the loopback-only trust boundary for the ember model server URL.

    ember is a local-first tool; the model server must only be reachable on the
    loopback interface. Accepting a non-loopback URL would allow an attacker who
    can set ``EMBER_SERVER_URL`` to redirect all ``advise`` calls — including the
    full ``state`` payload — to an attacker-controlled server.

    Accepted hosts: ``localhost``, ``127.0.0.0/8`` (the full loopback block),
    and ``::1`` (IPv6 loopback).

    Parameters
    ----------
    url : str
        The server URL to validate (e.g. ``http://127.0.0.1:8765``).

    Raises
    ------
    ValueError
        If the URL's hostname does not resolve to a loopback address.
        The message names the offending host, explains the loopback-only
        design, and points to ``SECURITY.md`` for context.
    """
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if host in ("localhost",):
        return
    try:
        addr = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError(
            f"EMBER_SERVER_URL host {host!r} is not a loopback address. "
            "ember only connects to loopback targets (localhost, 127.0.0.0/8, ::1) "
            "to keep agent state payloads local. "
            "See SECURITY.md for the loopback-only design rationale."
        ) from exc
    if not addr.is_loopback:
        raise ValueError(
            f"EMBER_SERVER_URL host {host!r} is not a loopback address. "
            "ember only connects to loopback targets (localhost, 127.0.0.0/8, ::1) "
            "to keep agent state payloads local. "
            "See SECURITY.md for the loopback-only design rationale."
        )


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


def _host_port() -> tuple[str, int]:
    parsed = urlparse(SERVER_URL)
    return parsed.hostname or "127.0.0.1", parsed.port or 8765


def _server_ready() -> bool:
    return process.is_up(*_host_port())


def _ensure_server() -> None:
    if _server_ready():
        return
    if not AUTOSTART:
        raise RuntimeError(
            f"ember server not reachable at {SERVER_URL} and "
            "EMBER_AUTOSTART=0. Start it with: ember start"
        )
    host, port = _host_port()
    log.info("ember server not running; starting it on %s:%s", host, port)
    process.start(host=host, port=port, timeout=START_TIMEOUT)
    log.info("ember server is ready")


@mcp.tool()
def advise(input: AdviseInput) -> dict[str, Any]:
    """Get ember's read on a situation, as calibrated probabilities.

    ember (a local decision model) advises; you decide.
    Consult it at bounded decision points: intent, triage, routing, yes/no gates, and
    risk, severity, or effort scores. It sees only what you pass, so include every
    piece of evidence the call depends on and attach images or video frames as base64
    `data:` URIs in `images`/`videos` when pixels are the evidence. For 'choice' the
    answer has the leading option, its confidence, and full probabilities; for 'score'
    an expected score over the ordered criteria; for 'noul' the probability the
    proposition is true.
    """
    # Only ToolError messages reach the agent; anything else is reported generically.
    try:
        _ensure_server()
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
        resp = httpx.post(f"{SERVER_URL}/v1/systemone", json=payload, timeout=300.0)
    except httpx.HTTPError as exc:
        raise ToolError(f"ember server request failed: {exc}") from exc
    if resp.status_code >= 400:
        raise ToolError(f"ember server error {resp.status_code}: {resp.text}")
    answer: dict[str, Any] = resp.json()
    return answer


def main() -> None:
    """Run the MCP stdio server; blocks until the client disconnects."""
    try:
        validate_server_url(SERVER_URL)
    except ValueError as exc:
        log.exception("startup aborted: %s", exc)
        sys.exit(1)
    log.info(
        "ember MCP server starting (server_url=%s, autostart=%s)",
        SERVER_URL,
        AUTOSTART,
    )
    # stdout is the JSON-RPC wire; any non-protocol output corrupts it.
    mcp.run()


if __name__ == "__main__":
    main()
