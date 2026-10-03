"""gut-feeling MCP stdio server: the ``advise`` tool plus its agent guidance.

A thin client. Each tool call goes to the warm model server (``gut_feeling.server``).
When that server is down and GUT_FEELING_AUTOSTART is on, it is started through
``process.start`` — the same model resolution, pid file, and log as
``gut-feeling start``. The model never loads in this process, so the MCP handshake
stays instant.

opencode namespaces tools as ``<server>_<tool>``: with the server key ``gut-feeling``
the tool appears as ``gut-feeling_advise`` (Claude Code: ``mcp__gut-feeling__advise``).

Env:
    GUT_FEELING_SERVER_URL     default http://127.0.0.1:8765
    GUT_FEELING_AUTOSTART      default 1 (0 disables)
    GUT_FEELING_START_TIMEOUT  default 300 seconds
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

from gut_feeling import agent_kit, process

# stdout is the JSON-RPC wire; log to stderr only.
logging.basicConfig(
    level=logging.INFO, stream=sys.stderr, format="[gut-feeling-mcp] %(message)s"
)
log = logging.getLogger("gut-feeling-mcp")

SERVER_URL = os.environ.get("GUT_FEELING_SERVER_URL", "http://127.0.0.1:8765").rstrip(
    "/"
)
AUTOSTART = os.environ.get("GUT_FEELING_AUTOSTART", "1").lower() not in (
    "0",
    "false",
    "no",
    "",
)
START_TIMEOUT = float(os.environ.get("GUT_FEELING_START_TIMEOUT", "300"))

mcp = MCPServer("gut-feeling", instructions=agent_kit.instructions())


@mcp.resource(
    agent_kit.GUIDE_URI,
    name="gut-feeling-guide",
    description="Full playbook for the advise tool: schemas, thresholds, and recipes.",
    mime_type="text/markdown",
)
def guide() -> str:
    return agent_kit.skill()


class Question(BaseModel):
    """One typed question for gut-feeling to weigh in on."""

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
            "gut-feeling sees nothing else."
        ),
    )
    questions: dict[str, Question] = Field(
        description="Mapping of question ID to a typed question.",
    )
    model: str = Field(
        default="clef-flash", description="Model label echoed back in the response."
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
            f"gut-feeling server not reachable at {SERVER_URL} and "
            "GUT_FEELING_AUTOSTART=0. Start it with: gut-feeling start"
        )
    host, port = _host_port()
    log.info("gut-feeling server not running; starting it on %s:%s", host, port)
    process.start(host=host, port=port, timeout=START_TIMEOUT)
    log.info("gut-feeling server is ready")


@mcp.tool()
def advise(input: AdviseInput) -> dict[str, Any]:
    """Get gut-feeling's read on a situation, as calibrated probabilities.

    gut-feeling (Cloudflare's Clef-Flash model, running locally) advises; you decide.
    Consult it at bounded decision points: intent, triage, routing, yes/no gates, and
    risk, severity, or effort scores. It sees only `state`, so include every piece of
    evidence the call depends on. For 'choice' the answer has the leading option,
    its confidence, and full probabilities; for 'score' an expected score over the
    ordered criteria; for 'noul' the probability the proposition is true.
    """
    # Only ToolError messages reach the agent; anything else is reported generically.
    try:
        _ensure_server()
    except RuntimeError as exc:
        raise ToolError(str(exc)) from exc
    payload = {
        "model": input.model,
        "state": input.state,
        "questions": {
            key: question.model_dump(exclude_none=True)
            for key, question in input.questions.items()
        },
    }
    try:
        resp = httpx.post(f"{SERVER_URL}/v1/systemone", json=payload, timeout=300.0)
    except httpx.HTTPError as exc:
        raise ToolError(f"gut-feeling server request failed: {exc}") from exc
    if resp.status_code >= 400:
        raise ToolError(f"gut-feeling server error {resp.status_code}: {resp.text}")
    answer: dict[str, Any] = resp.json()
    return answer


def main() -> None:
    log.info(
        "gut-feeling MCP server starting (server_url=%s, autostart=%s)",
        SERVER_URL,
        AUTOSTART,
    )
    # stdout is the JSON-RPC wire; any non-protocol output corrupts it.
    mcp.run()


if __name__ == "__main__":
    main()
