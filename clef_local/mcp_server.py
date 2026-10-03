"""MCP stdio server exposing Clef-Flash decision-making to opencode.

Thin client: on each tool call it talks to the warm Clef HTTP server
(``clef_local.server``). If that server is not running and CLEF_AUTOSTART is on,
it starts it detached and waits for readiness. Keeping the model out of this
process is deliberate: opencode's MCP discovery has a short timeout and would
otherwise pay the ~10s model-load cost (and reload per session).

opencode namespaces tools as ``<server>_<tool>``; with the server key ``clef``
this appears as ``clef_decide``.

Run (opencode does this for you):
    .venv/bin/python clef_local/mcp_server.py
Env:
    CLEF_SERVER_URL   default http://127.0.0.1:8765
    CLEF_AUTOSTART    default 1 (0 disables)
    CLEF_START_TIMEOUT default 300 seconds
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Literal

import httpx
from mcp.server import MCPServer
from pydantic import BaseModel, Field

from clef_local import agent_kit

# stdout is the JSON-RPC wire; log to stderr only.
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="[clef-mcp] %(message)s")
log = logging.getLogger("clef-mcp")

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_URL = os.environ.get("CLEF_SERVER_URL", "http://127.0.0.1:8765").rstrip("/")
AUTOSTART = os.environ.get("CLEF_AUTOSTART", "1").lower() not in ("0", "false", "no", "")
START_TIMEOUT = float(os.environ.get("CLEF_START_TIMEOUT", "300"))

mcp = MCPServer("clef", instructions=agent_kit.instructions())


@mcp.resource(
    agent_kit.GUIDE_URI,
    name="clef-decide-guide",
    description="Full playbook for the decide tool: schemas, thresholds, and recipes.",
    mime_type="text/markdown",
)
def guide() -> str:
    return agent_kit.skill()


class Question(BaseModel):
    """A single typed question for the decision model."""

    type: Literal["noul", "choice", "score"] = Field(
        description="noul = yes/no, choice = named options, score = ordered options",
    )
    instructions: str | None = Field(
        default=None,
        description="What to decide. Optional; the question ID is used if omitted.",
    )
    criteria: dict[str, str] | list[str] | None = Field(
        default=None,
        description=(
            "For choice: mapping of option id -> description. "
            "For score: ordered list of option descriptions (index 0 is lowest). "
            "For noul: optional {'true':..., 'false':...} descriptions."
        ),
    )


class DecideInput(BaseModel):
    state: Any = Field(
        description="The situation to decide on: a string or any JSON object/array.",
    )
    questions: dict[str, Question] = Field(
        description="Mapping of question ID to a typed question.",
    )
    model: str = Field(default="clef-flash", description="Model label to echo back.")


def _server_ready() -> bool:
    try:
        resp = httpx.get(f"{SERVER_URL}/health", timeout=2.0)
        return resp.status_code == 200 and resp.json().get("engine") is not None
    except Exception:
        return False


def _start_server() -> int:
    """Launch the warm HTTP server detached; return its PID.

    The child is told to listen on the host/port encoded in ``SERVER_URL`` so
    autostart works for non-default ports. Its PID is recorded in
    ``CLEF_AUTOSTART_PIDFILE`` (default ``logs/server.pid``) so callers/tests can
    stop exactly the process they spawned (never the whole host's servers).
    """
    from urllib.parse import urlparse

    parsed = urlparse(SERVER_URL)
    child_env = dict(os.environ)
    child_env["CLEF_HOST"] = parsed.hostname or "127.0.0.1"
    child_env["CLEF_PORT"] = str(parsed.port or 8765)

    log_file = Path(os.environ.get("CLEF_SERVER_LOG", str(REPO_ROOT / "logs" / "server.log")))
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log.info(
        "Clef server not running; launching it on %s:%s (log: %s)",
        child_env["CLEF_HOST"],
        child_env["CLEF_PORT"],
        log_file,
    )
    with open(log_file, "ab") as handle:
        proc = subprocess.Popen(
            [sys.executable, "-m", "clef_local.server"],
            cwd=str(REPO_ROOT),
            env=child_env,
            stdout=handle,
            stderr=handle,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    pidfile = Path(os.environ.get("CLEF_AUTOSTART_PIDFILE", str(REPO_ROOT / "logs" / "server.pid")))
    try:
        pidfile.parent.mkdir(parents=True, exist_ok=True)
        pidfile.write_text(str(proc.pid))
    except OSError:
        log.warning("could not write pidfile %s", pidfile)
    return proc.pid


def _ensure_server() -> None:
    if _server_ready():
        return
    if not AUTOSTART:
        raise RuntimeError(
            f"Clef server not reachable at {SERVER_URL} and CLEF_AUTOSTART=0. "
            "Start it with: .venv/bin/python -m clef_local.server"
        )
    _start_server()
    deadline = time.time() + START_TIMEOUT
    while time.time() < deadline:
        if _server_ready():
            log.info("Clef server is ready")
            return
        time.sleep(2.0)
    raise RuntimeError(
        f"Clef server did not become ready within {START_TIMEOUT:.0f}s. "
        "Check logs/server.log"
    )


@mcp.tool()
def decide(input: DecideInput) -> dict[str, Any]:
    """Ask the local Clef-Flash decision model to classify a state.

    Use this for bounded, high-speed decisions: routing, triage, urgency,
    yes/no checks, or scoring. The model sees only `state`, so include every
    piece of evidence the decision depends on. Returns per-question answers.
    For 'choice' the answer has the picked choice, confidence, and full
    probabilities; for 'score' an expected score over the ordered criteria;
    for 'noul' the probability the proposition is true.
    """
    _ensure_server()
    payload = {
        "model": input.model,
        "state": input.state,
        "questions": {
            key: question.model_dump(exclude_none=True)
            for key, question in input.questions.items()
        },
    }
    resp = httpx.post(f"{SERVER_URL}/v1/systemone", json=payload, timeout=300.0)
    if resp.status_code >= 400:
        raise RuntimeError(f"Clef server error {resp.status_code}: {resp.text}")
    return resp.json()


def main() -> None:
    log.info("Clef MCP server starting (server_url=%s, autostart=%s)", SERVER_URL, AUTOSTART)
    # stdout is the JSON-RPC wire; any non-protocol output corrupts it.
    mcp.run()


if __name__ == "__main__":
    main()
