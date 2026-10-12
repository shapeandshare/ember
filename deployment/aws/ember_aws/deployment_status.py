"""DeploymentStatus: the output model for the ``status`` command."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from .deployment_state import DeploymentState
from .stop_reason import StopReason


class DeploymentStatus(BaseModel):
    """Snapshot of a named ember deployment's current state.

    All fields except ``state`` are optional; absent or unreachable parts
    are represented as ``None``.  ``idle_minutes`` is the string ``"off"``
    when the idle timer is disabled (configured value 0), or an ``int``
    when it is active.

    Parameters
    ----------
    state : DeploymentState
        Lifecycle state derived from the CFN stack status and EC2 instance
        state.
    stop_reason : StopReason | None
        Why the instance stopped, or ``None`` when running or unknown.
    instance_id : str | None
        EC2 instance ID (e.g. ``"i-0abc1234"``).
    instance_type : str | None
        EC2 instance type (e.g. ``"g6e.xlarge"``).
    capacity : str | None
        ``"on-demand"`` or ``"spot"``.
    az : str | None
        Availability zone (e.g. ``"us-east-1a"``).
    tailnet_name : str | None
        Tailscale tailnet DNS suffix (e.g. ``"example.ts.net"``).
    url : str | None
        Full HTTPS URL of the ember server on the tailnet.
    health : dict[str, Any] | None
        Parsed ``/health`` response body, or ``{"error": "<text>"}`` when
        the endpoint is unreachable.
    uptime : float | None
        Seconds since ``LaunchTime``.
    hourly_usd : float | None
        On-demand or spot hourly price for the instance type and region.
    cost_since_start_usd : float | None
        Estimated cost since ``LaunchTime`` (``hourly x hours``), rounded
        to the nearest cent.
    idle_minutes : int | str | None
        Minutes of inactivity before auto-stop.  ``"off"`` when 0,
        an ``int`` when active, ``None`` when unknown.
    """

    state: DeploymentState
    stop_reason: StopReason | None = None
    instance_id: str | None = None
    instance_type: str | None = None
    capacity: str | None = None
    az: str | None = None
    tailnet_name: str | None = None
    url: str | None = None
    health: dict[str, Any] | None = None
    uptime: float | None = None
    hourly_usd: float | None = None
    cost_since_start_usd: float | None = None
    idle_minutes: int | str | None = None
