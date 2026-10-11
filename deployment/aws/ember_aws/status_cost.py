"""StatusCost: cost and uptime helpers for StatusReader."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .defaults import DEFAULT_REGION


def compute_cost(
    instance_data: dict[str, Any],
    clients: Any,
    sizing: Any,
) -> tuple[float | None, float | None, float | None]:
    """Return ``(uptime_seconds, hourly_usd, cost_since_start_usd)``.

    Parameters
    ----------
    instance_data : dict[str, Any]
        EC2 instance dict from ``describe_instances``.
    clients : Any
        An :class:`~ember_aws.aws_clients.AwsClients` instance (or a mock).
    sizing : Any
        A :class:`~ember_aws.sizing_table.SizingTable` instance (or a mock).

    Returns
    -------
    tuple[float | None, float | None, float | None]
        ``(uptime_s, hourly_usd, cost_usd)``; any element may be ``None``
        when the required data is unavailable.
    """
    launch_time: datetime | None = instance_data.get("LaunchTime")
    if launch_time is None:
        return None, None, None

    # Ensure timezone-aware.
    if launch_time.tzinfo is None:
        launch_time = launch_time.replace(tzinfo=UTC)

    now = datetime.now(tz=UTC)
    uptime_s = (now - launch_time).total_seconds()
    uptime_h = uptime_s / 3600.0

    # Determine hourly rate.
    instance_type = instance_data.get("InstanceType", "")
    az = (instance_data.get("Placement") or {}).get("AvailabilityZone", "")
    region = az[:-1] if az else DEFAULT_REGION  # strip trailing AZ letter

    hourly = get_hourly_rate(instance_data, instance_type, az, region, clients, sizing)
    if hourly is None:
        return uptime_s, None, None

    cost = round(hourly * uptime_h, 2)
    return uptime_s, hourly, cost


def get_hourly_rate(
    instance_data: dict[str, Any],
    instance_type: str,
    az: str,
    region: str,
    clients: Any,
    sizing: Any,
) -> float | None:
    """Return the hourly rate: spot price if spot, else sizing table.

    Parameters
    ----------
    instance_data : dict[str, Any]
        EC2 instance dict.
    instance_type : str
        EC2 instance type (e.g. ``"g6e.xlarge"``).
    az : str
        Availability zone (e.g. ``"us-east-1a"``).
    region : str
        AWS region derived from ``az`` (e.g. ``"us-east-1"``).
    clients : Any
        AWS clients bundle.
    sizing : Any
        Sizing table.

    Returns
    -------
    float | None
        Hourly USD rate, or ``None`` when unavailable.
    """
    lifecycle = instance_data.get("InstanceLifecycle", "")
    market_options = instance_data.get("InstanceMarketOptions") or {}
    is_spot = lifecycle == "spot" or market_options.get("MarketType") == "spot"

    if is_spot:
        spot = get_spot_price(instance_type, az, clients)
        if spot is not None:
            return spot

    return hourly_from_sizing(instance_type, region, sizing)


def get_spot_price(instance_type: str, az: str, clients: Any) -> float | None:
    """Fetch the current spot price from ``describe_spot_price_history``.

    Parameters
    ----------
    instance_type : str
        EC2 instance type.
    az : str
        Availability zone.
    clients : Any
        AWS clients bundle.

    Returns
    -------
    float | None
        Spot price in USD, or ``None`` on any error.
    """
    try:
        resp = clients.ec2.describe_spot_price_history(
            InstanceTypes=[instance_type],
            AvailabilityZone=az,
            ProductDescriptions=["Linux/UNIX"],
            MaxResults=1,
        )
        history = resp.get("SpotPriceHistory", [])
        if history:
            return float(history[0]["SpotPrice"])
        return None
    except Exception:
        return None


def hourly_from_sizing(instance_type: str, region: str, sizing: Any) -> float | None:
    """Return the on-demand hourly rate from the sizing table, or None.

    Parameters
    ----------
    instance_type : str
        EC2 instance type.
    region : str
        AWS region code.
    sizing : Any
        Sizing table.

    Returns
    -------
    float | None
        Hourly USD rate, or ``None`` when not found.
    """
    try:
        model = _guess_model(instance_type, sizing)
        entry = sizing.resolve(model, instance_type)
        hourly_map: dict[str, float] = entry.hourly_usd
        return hourly_map.get(region) or next(iter(hourly_map.values()), None)
    except Exception:
        return _hourly_from_sizing_scan(instance_type, region, sizing)


def _hourly_from_sizing_scan(
    instance_type: str, region: str, sizing: Any
) -> float | None:
    """Scan all sizing entries for the instance type, or return None."""
    try:
        for entry in sizing.entries:
            if entry.instance_type == instance_type:
                hourly_map: dict[str, float] = entry.hourly_usd
                return hourly_map.get(region) or next(iter(hourly_map.values()), None)
        return None
    except Exception:
        return None


def _guess_model(instance_type: str, sizing: Any) -> str:
    """Guess the model name from the instance type (best-effort)."""
    try:
        for entry in sizing.entries:
            if entry.instance_type == instance_type:
                return str(entry.model)
        return "flash"
    except Exception:
        return "flash"
