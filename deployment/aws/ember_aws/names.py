"""Deployment name validation and derived SSM/stack/tag names."""

from __future__ import annotations

import re

from pydantic import BaseModel, field_validator

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,30}[a-z0-9]$")


class DeploymentName(BaseModel):
    """A validated deployment name with derived resource identifiers.

    The name must match ``^[a-z][a-z0-9-]{1,30}[a-z0-9]$``: lowercase
    alphanumeric, hyphens allowed in the middle, 3-32 characters total.

    Parameters
    ----------
    name : str
        The deployment name (e.g. ``"default"`` or ``"team-a1"``).
    """

    name: str

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if not _NAME_RE.match(v):
            raise ValueError(
                f"deployment name {v!r} must match ^[a-z][a-z0-9-]{{1,30}}[a-z0-9]$"
            )
        return v

    @property
    def stack_name(self) -> str:
        """CloudFormation stack name: ``ember-<name>``."""
        return f"ember-{self.name}"

    @property
    def hostname(self) -> str:
        """Tailscale hostname: ``ember-<name>``."""
        return f"ember-{self.name}"

    @property
    def ssm_prefix(self) -> str:
        """SSM parameter path prefix: ``/ember/<name>/``."""
        return f"/ember/{self.name}/"

    @property
    def config_param(self) -> str:
        """SSM parameter path for the instance config JSON."""
        return f"/ember/{self.name}/config"

    @property
    def token_param(self) -> str:
        """SSM parameter path for the server auth token (SecureString)."""
        return f"/ember/{self.name}/server-token"

    @property
    def join_key_param(self) -> str:
        """SSM parameter path for the Tailscale join key (SecureString)."""
        return f"/ember/{self.name}/tailscale-join-key"

    @property
    def tag(self) -> str:
        """AWS resource tag value: ``ember:deployment=<name>``."""
        return f"ember:deployment={self.name}"
