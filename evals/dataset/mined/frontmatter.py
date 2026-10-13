"""Note frontmatter and body extraction, following the vault audit's pattern."""

from __future__ import annotations

import re
from datetime import datetime

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


class NoteFrontmatter(BaseModel):
    """The governed frontmatter a minable vault note carries.

    Parameters
    ----------
    title : str
        The note's human title.
    type : str
        The note's type value (the ``type/*`` axis).
    tags : list[str]
        The note's controlled tags.
    created, updated : str | datetime
        The authoring and update timestamps as recorded (YAML may parse them).
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    title: str
    type: str
    tags: list[str]
    created: str | datetime
    updated: str | datetime


def parse(text: str) -> NoteFrontmatter:
    """Parse a note's frontmatter.

    Parameters
    ----------
    text : str
        The note's full markdown text.

    Returns
    -------
    NoteFrontmatter
        The validated frontmatter.

    Raises
    ------
    ValueError
        When the note has no frontmatter or it is malformed.
    """
    match = FRONTMATTER_RE.match(text)
    if match is None:
        raise ValueError("note has no YAML frontmatter")
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise ValueError(f"malformed frontmatter: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("frontmatter is not a mapping")
    try:
        return NoteFrontmatter.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"invalid frontmatter: {exc}") from exc


def body_of(text: str) -> str:
    """Return the note body, the text after the frontmatter header.

    Parameters
    ----------
    text : str
        The note's full markdown text.

    Returns
    -------
    str
        Everything after the closing ``---`` line.

    Raises
    ------
    ValueError
        When the note has no frontmatter.
    """
    match = FRONTMATTER_RE.match(text)
    if match is None:
        raise ValueError("note has no YAML frontmatter")
    return text[match.end() :]
