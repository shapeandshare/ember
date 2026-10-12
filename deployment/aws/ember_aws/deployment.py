"""Deployment: the desired state the operator provides for an AWS GPU deployment."""

from __future__ import annotations

import re
import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, field_validator

from .capacity import Capacity
from .defaults import DEFAULT_REGION

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


@lru_cache(maxsize=1)
def _pyproject_version() -> str:
    """Read the project version from pyproject.toml at the repo root."""
    root = Path(__file__).resolve().parents[3]
    pyproject = root / "pyproject.toml"
    with pyproject.open("rb") as f:
        data = tomllib.load(f)
    version: str = data["project"]["version"]
    return version


class Deployment(BaseModel):
    """The desired state the operator provides for a named AWS GPU deployment.

    Parameters
    ----------
    name : str
        Deployment name matching ``^[a-z][a-z0-9-]{1,30}[a-z0-9]$``.
    model : str
        Registry key (e.g. ``"flash"``).
    region : str
        AWS region; defaults to ``"us-west-2"``.
    instance_type : str | None
        EC2 instance type; ``None`` resolves to the sizing table default.
    capacity : Capacity
        ``on-demand`` or ``spot``; defaults to ``on-demand``.
    idle_minutes : int
        Minutes of inactivity before auto-stop; 0 = off (default).
    ember_version : str
        Pinned ``ember-advise`` version (``X.Y.Z``); defaults to the
        checkout's ``pyproject.toml`` version.
    subnet_id : str | None
        Subnet to launch in; ``None`` picks the first default-VPC subnet.
    tailscale_tag : str
        Tailscale ACL tag; defaults to ``"tag:ember"``.
    """

    name: str
    model: str
    region: str = DEFAULT_REGION
    instance_type: str | None = None
    capacity: Capacity = Capacity.ON_DEMAND
    idle_minutes: int = 0
    ember_version: str = ""
    subnet_id: str | None = None
    tailscale_tag: str = "tag:ember"

    def model_post_init(self, __context: object) -> None:
        """Set ember_version default after construction."""
        if not self.ember_version:
            object.__setattr__(self, "ember_version", _pyproject_version())

    @field_validator("idle_minutes")
    @classmethod
    def _validate_idle_minutes(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"idle_minutes must be >= 0, got {v}")
        return v

    @field_validator("ember_version")
    @classmethod
    def _validate_ember_version(cls, v: str) -> str:
        if v and not _VERSION_RE.match(v):
            raise ValueError(f"ember_version {v!r} must match X.Y.Z (e.g. '0.12.0')")
        return v
