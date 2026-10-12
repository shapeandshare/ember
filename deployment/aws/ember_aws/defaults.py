"""Default values shared by the ember_aws operator CLI and its models."""

from __future__ import annotations

#: Default AWS region for deployments; override with ``--region`` or ``REGION=``.
DEFAULT_REGION: str = "us-west-2"
