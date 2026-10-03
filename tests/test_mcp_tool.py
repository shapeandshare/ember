"""MCP call paths: tool discovery, the `advise` tool over stdio, error handling when the
model server is down or the model is missing, autostart on a configured port, and the
agent guidance served at connect time.

All MCP servers here are spawned over stdio and never touch the opencode CLI.
"""

from __future__ import annotations

import asyncio
import json
import time

import pytest
from ember import agent_kit
from mcp import ClientSession
from mcp.client.stdio import stdio_client

from tests.conftest import free_port, mcp_stdin_params, terminate_pid

SAMPLE = {
    "input": {
        "state": (
            "The login endpoint returns 401 for all users after the latest deploy."
        ),
        "questions": {
            "urgent": {"type": "noul", "instructions": "Is this urgent?"},
            "team": {
                "type": "choice",
                "instructions": "Which team should handle this?",
                "criteria": {
                    "auth": "Authentication/sessions",
                    "frontend": "UI issues",
                },
            },
        },
    }
}


async def _list_tools(params):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.list_tools()


async def _call_advise(params, arguments=SAMPLE):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool("advise", arguments)


def _payload(result):
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(result.content[0].text)


@pytest.mark.model
def test_mcp_exposes_the_advise_tool(base_url: str) -> None:
    tools = asyncio.run(_list_tools(mcp_stdin_params(base_url)))
    advise = next(tool for tool in tools.tools if tool.name == "advise")
    assert advise.input_schema["properties"].get("input")


@pytest.mark.model
def test_mcp_advise_returns_typed_answers(base_url: str) -> None:
    result = asyncio.run(_call_advise(mcp_stdin_params(base_url)))
    assert result.is_error is False
    answers = _payload(result)["answers"]
    assert answers["urgent"]["type"] == "noul"
    assert 0.0 <= answers["urgent"]["noul"] <= 1.0
    team = answers["team"]
    assert team["type"] == "choice"
    assert team["choice"] in {"auth", "frontend"}
    assert abs(sum(team["probabilities"].values()) - 1.0) < 0.05


def test_mcp_surfaces_error_when_server_down_and_autostart_off() -> None:
    params = mcp_stdin_params(f"http://127.0.0.1:{free_port()}", autostart="0")
    try:
        result = asyncio.run(_call_advise(params))
    except Exception:
        # A raised protocol error is an acceptable way to report the failure.
        return
    assert result.is_error is True


def test_mcp_autostart_reports_a_missing_model_quickly(tmp_path) -> None:
    params = mcp_stdin_params(
        f"http://127.0.0.1:{free_port()}",
        autostart="1",
        EMBER_MODEL_DIR=str(tmp_path / "missing"),
        EMBER_STATE_DIR=str(tmp_path / "state"),
    )
    started = time.time()
    result = asyncio.run(_call_advise(params))
    assert result.is_error is True
    assert "ember model pull" in result.content[0].text
    assert time.time() - started < 30


@pytest.mark.model
def test_mcp_autostart_launches_server_on_configured_port(tmp_path) -> None:
    pidfile = tmp_path / "server.pid"
    params = mcp_stdin_params(
        f"http://127.0.0.1:{free_port()}",
        autostart="1",
        EMBER_STATE_DIR=str(tmp_path),
    )
    try:
        result = asyncio.run(_call_advise(params))
        assert result.is_error is False
        assert pidfile.exists(), "autostart did not record the spawned server PID"
    finally:
        if pidfile.exists():
            terminate_pid(int(pidfile.read_text().strip()))


def test_mcp_advertises_instructions_and_guide_resource() -> None:
    """Agents learn the tool from initialize.instructions and the ember://guide
    resource, neither of which needs the model server."""
    params = mcp_stdin_params(f"http://127.0.0.1:{free_port()}", autostart="0")

    async def run():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                resources = await session.list_resources()
                guide = await session.read_resource(agent_kit.GUIDE_URI)
                return init, resources, guide

    init, resources, guide = asyncio.run(run())
    assert init.server_info.name == "ember"
    assert init.instructions == agent_kit.instructions()
    assert agent_kit.GUIDE_URI in {
        str(resource.uri) for resource in resources.resources
    }
    assert guide.contents[0].text == agent_kit.skill()


@pytest.mark.model
def test_mcp_returns_actionable_errors_for_malformed_questions(base_url: str) -> None:
    missing_criteria = {
        "input": {
            "state": "x",
            "questions": {"team": {"type": "choice", "instructions": "Which?"}},
        }
    }
    result = asyncio.run(_call_advise(mcp_stdin_params(base_url), missing_criteria))
    assert result.is_error is True
    assert "criteria must not be empty" in result.content[0].text
