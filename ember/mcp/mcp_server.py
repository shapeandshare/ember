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

    ember (Cloudflare's Clef-Flash model, running locally) advises; you decide.
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
    log.info(
        "ember MCP server starting (server_url=%s, autostart=%s)",
        SERVER_URL,
        AUTOSTART,
    )
    # stdout is the JSON-RPC wire; any non-protocol output corrupts it.
    mcp.run()


if __name__ == "__main__":
    main()
