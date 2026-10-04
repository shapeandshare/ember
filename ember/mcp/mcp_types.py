"""Pydantic input types for the ``advise`` MCP tool.

Defines the wire schema that the MCP server validates before forwarding a
call to the model server.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


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
    """Input schema for the ``advise`` tool (wrapped in an ``input`` field)."""

    state: Any = Field(
        description=(
            "The situation to read: a string or any JSON object/array. "
            "Attach images/videos separately when the evidence is visual."
        ),
    )
    questions: dict[str, Question] = Field(
        description="Mapping of question ID to a typed question.",
    )
    model: str = Field(
        default="clef-flash",
        description=(
            "Informational label only. The response always reflects the model "
            "the server loaded at startup; this field is not used for routing."
        ),
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
