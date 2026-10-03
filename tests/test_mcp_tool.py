"""MCP call paths: tool discovery, the `decide` tool over stdio, error handling when
the model server is down, and autostart on a configured (non-default) port.

All MCP servers here are spawned over stdio and never touch the opencode CLI.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from mcp import ClientSession
from mcp.client.stdio import stdio_client

from tests.conftest import free_port, mcp_stdin_params, terminate_pid

from clef_local import agent_kit

SAMPLE = {
    "input": {
        "state": "The login endpoint returns 401 for all users after the latest deploy.",
        "questions": {
            "urgent": {"type": "noul", "instructions": "Is this urgent?"},
            "team": {
                "type": "choice",
                "instructions": "Which team should handle this?",
                "criteria": {"auth": "Authentication/sessions", "frontend": "UI issues"},
            },
        },
    }
}


async def _list_tools(params):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.list_tools()


async def _call_decide(params, arguments=SAMPLE):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool("decide", arguments)


def _payload(result):
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(result.content[0].text)


@pytest.mark.model
def test_mcp_exposes_decide_tool(base_url: str) -> None:
    tools = asyncio.run(_list_tools(mcp_stdin_params(base_url)))
    names = {tool.name for tool in tools.tools}
    assert "decide" in names
    decide = next(tool for tool in tools.tools if tool.name == "decide")
    assert decide.input_schema["properties"].get("input")


@pytest.mark.model
def test_mcp_decide_returns_typed_answers(base_url: str) -> None:
    result = asyncio.run(_call_decide(mcp_stdin_params(base_url)))
    assert result.is_error is False
    body = _payload(result)
    answers = body["answers"]
    assert answers["urgent"]["type"] == "noul"
    assert 0.0 <= answers["urgent"]["noul"] <= 1.0
    team = answers["team"]
    assert team["type"] == "choice"
    assert team["choice"] in {"auth", "frontend"}
    assert abs(sum(team["probabilities"].values()) - 1.0) < 0.05


def test_mcp_surfaces_error_when_server_down_and_autostart_off() -> None:
    params = mcp_stdin_params(f"http://127.0.0.1:{free_port()}", autostart="0")
    try:
        result = asyncio.run(_call_decide(params))
    except Exception:
        # A raised protocol error is an acceptable way to report the failure.
        return
    assert result.is_error is True


@pytest.mark.model
def test_mcp_autostart_launches_server_on_configured_port(tmp_path) -> None:
    port = free_port()
    pidfile = tmp_path / "server.pid"
    params = mcp_stdin_params(
        f"http://127.0.0.1:{port}",
        autostart="1",
        CLEF_AUTOSTART_PIDFILE=str(pidfile),
        CLEF_SERVER_LOG=str(tmp_path / "server.log"),
    )
    try:
        result = asyncio.run(_call_decide(params))
        assert result.is_error is False
        assert pidfile.exists(), "autostart did not record the spawned server PID"
    finally:
        if pidfile.exists():
            terminate_pid(int(pidfile.read_text().strip()))


def test_mcp_advertises_instructions_and_guide_resource() -> None:
    """Agents learn the tool from initialize.instructions and the clef://guide resource,
    neither of which needs the model server."""
    params = mcp_stdin_params(f"http://127.0.0.1:{free_port()}", autostart="0")

    async def run():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                resources = await session.list_resources()
                guide = await session.read_resource(agent_kit.GUIDE_URI)
                return init, resources, guide

    init, resources, guide = asyncio.run(run())
    assert init.instructions == agent_kit.instructions()
    assert agent_kit.GUIDE_URI in {str(resource.uri) for resource in resources.resources}
    assert guide.contents[0].text == agent_kit.skill()
