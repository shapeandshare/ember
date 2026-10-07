"""The four agent-eval conditions: how much of the ember kit a session gets."""

from __future__ import annotations

from enum import StrEnum


class Condition(StrEnum):
    """One agent-eval condition, from no ember to the full onboarding kit.

    Members are ordered from least to most of the kit: ``NONE`` gives the
    agent nothing, ``MCP`` adds the MCP server and its instructions, ``SKILL``
    adds the installable skill, and ``FULL`` adds the AGENTS.md policy
    snippet on top. The string value is the condition id used in sandbox
    paths, run configs, and the rendered report.
    """

    NONE = "none"
    MCP = "mcp"
    SKILL = "skill"
    FULL = "full"
