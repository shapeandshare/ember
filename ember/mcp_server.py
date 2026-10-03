"""ember MCP stdio server: the ``advise`` tool plus its agent guidance.

A thin client. Each tool call goes to the warm model server (``ember.server``).
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
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from ember import agent_kit, process

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
    return agent_kit.skill()


class Question(BaseModel):
    """One typed question for ember to weigh in on."""

    type: Literal["noul", "choice", "score"] = Field(
        description="noul = yes/no, choice = named options, score = ordered options",
    )
    instructions: str | None = Field(
        default=None,
        description="What to weigh in on. Optional; defaults to the question ID.",
    )
    criteria: dict[str, str] | list[str] | None = Field(
        default=None,
        description=(
            "For choice: mapping of option id -> description. "
            "For score: ordered list of option descriptions (index 0 is lowest). "
            "For noul: optional {'true':..., 'false':...} descriptions."
        ),
    )


class AdviseInput(BaseModel):
    state: Any = Field(
        description=(
            "The situation to read: a string or any JSON object/array. "
            "ember sees nothing else."
        ),
    )
    questions: dict[str, Question] = Field(
        description="Mapping of question ID to a typed question.",
    )
    model: str = Field(
        default="clef-flash", description="Model label echoed back in the response."
    )
    images: list[str | dict[str, Any]] | None = Field(
        default=None,
        description=(
            "Optional images as data: URIs (data:image/png;base64,...) or "
            "{content_type, base64} objects. No remote URLs or local paths."
        ),
    )
    videos: list[list[str | dict[str, Any]]] | None = Field(
        default=None,
        description="Optional videos, each a list of frame refs in the images format.",
    )
    media_kwargs: dict[str, Any] | None = Field(
        default=None, description="Optional image/video processor arguments."
    )


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
    risk, severity, or effort scores. It sees only `state`, so include every piece of
    evidence the call depends on. Attach images or video frames as base64 data URIs in
    `images`/`videos` when pixels are the evidence. For 'choice' the answer has the
    leading option, its confidence, and full probabilities; for 'score' an expected
    score over the ordered criteria; for 'noul' the probability the proposition is true.
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
    log.info(
        "ember MCP server starting (server_url=%s, autostart=%s)",
        SERVER_URL,
        AUTOSTART,
    )
    # stdout is the JSON-RPC wire; any non-protocol output corrupts it.
    mcp.run()


if __name__ == "__main__":
    main()
