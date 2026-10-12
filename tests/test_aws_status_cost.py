"""Tests for status_cost.py: compute_cost, get_hourly_rate, get_spot_price,
hourly_from_sizing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sizing(
    *,
    instance_type: str = "g6e.xlarge",
    model: str = "flash",
    hourly_usd: dict[str, float] | None = None,
) -> Any:
    """Build a fake SizingTable-shaped object."""
    entry = MagicMock()
    entry.instance_type = instance_type
    entry.model = model
    entry.hourly_usd = hourly_usd or {"us-east-1": 1.861}

    sizing = MagicMock()
    sizing.entries = [entry]
    sizing.resolve.return_value = entry
    return sizing


def _make_clients(*, spot_price: str | None = None) -> Any:
    clients = MagicMock()
    if spot_price is not None:
        clients.ec2.describe_spot_price_history.return_value = {
            "SpotPriceHistory": [{"SpotPrice": spot_price}]
        }
    else:
        clients.ec2.describe_spot_price_history.return_value = {"SpotPriceHistory": []}
    return clients


def _instance_data(
    *,
    instance_type: str = "g6e.xlarge",
    az: str = "us-east-1a",
    launch_offset_s: float = 3600.0,
    lifecycle: str = "",
    market_type: str = "",
) -> dict[str, Any]:
    launch_time = datetime.now(tz=UTC) - timedelta(seconds=launch_offset_s)
    data: dict[str, Any] = {
        "InstanceType": instance_type,
        "LaunchTime": launch_time,
        "Placement": {"AvailabilityZone": az},
    }
    if lifecycle:
        data["InstanceLifecycle"] = lifecycle
    if market_type:
        data["InstanceMarketOptions"] = {"MarketType": market_type}
    return data


# ---------------------------------------------------------------------------
# compute_cost()
# ---------------------------------------------------------------------------


class TestComputeCost:
    """compute_cost() returns (uptime_s, hourly_usd, cost_usd)."""

    def test_returns_none_triple_when_no_launch_time(self) -> None:
        """compute_cost() returns (None, None, None) when LaunchTime is absent."""
        from ember_aws.status_cost import compute_cost

        clients = _make_clients()
        sizing = _make_sizing()
        result = compute_cost({}, clients, sizing)
        assert result == (None, None, None)

    def test_returns_uptime_and_cost_for_on_demand(self) -> None:
        """compute_cost() returns correct uptime and cost for on-demand instance."""
        from ember_aws.status_cost import compute_cost

        clients = _make_clients()
        sizing = _make_sizing(hourly_usd={"us-east-1": 2.0})
        data = _instance_data(launch_offset_s=3600.0)

        uptime_s, hourly, cost = compute_cost(data, clients, sizing)
        assert uptime_s is not None
        assert abs(uptime_s - 3600.0) < 5.0  # within 5 seconds
        assert hourly == 2.0
        assert cost is not None
        assert abs(cost - 2.0) < 0.1  # ~1 hour at $2/h

    def test_returns_none_cost_when_hourly_unavailable(self) -> None:
        """compute_cost() returns (uptime_s, None, None) when hourly rate is unknown."""
        from ember_aws.status_cost import compute_cost

        clients = _make_clients()
        sizing = MagicMock()
        sizing.entries = []
        sizing.resolve.side_effect = Exception("not found")

        data = _instance_data()
        uptime_s, hourly, cost = compute_cost(data, clients, sizing)
        assert uptime_s is not None
        assert hourly is None
        assert cost is None

    def test_handles_naive_launch_time(self) -> None:
        """compute_cost() handles a naive (timezone-unaware) LaunchTime."""
        from ember_aws.status_cost import compute_cost

        clients = _make_clients()
        sizing = _make_sizing(hourly_usd={"us-east-1": 1.0})
        # Naive datetime (no tzinfo)
        naive_launch = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
        data = {
            "InstanceType": "g6e.xlarge",
            "LaunchTime": naive_launch,
            "Placement": {"AvailabilityZone": "us-east-1a"},
        }
        uptime_s, hourly, _cost = compute_cost(data, clients, sizing)
        assert uptime_s is not None
        assert hourly == 1.0


# ---------------------------------------------------------------------------
# get_hourly_rate()
# ---------------------------------------------------------------------------


class TestGetHourlyRate:
    """get_hourly_rate() returns spot price for spot instances, sizing table
    otherwise."""

    def test_returns_spot_price_for_spot_lifecycle(self) -> None:
        """get_hourly_rate() returns the spot price when InstanceLifecycle='spot'."""
        from ember_aws.status_cost import get_hourly_rate

        clients = _make_clients(spot_price="0.50")
        sizing = _make_sizing()
        data = _instance_data(lifecycle="spot")

        rate = get_hourly_rate(
            data, "g6e.xlarge", "us-east-1a", "us-east-1", clients, sizing
        )
        assert rate == 0.50

    def test_returns_spot_price_for_spot_market_type(self) -> None:
        """get_hourly_rate() returns spot price when MarketType='spot'."""
        from ember_aws.status_cost import get_hourly_rate

        clients = _make_clients(spot_price="0.75")
        sizing = _make_sizing()
        data = _instance_data(market_type="spot")

        rate = get_hourly_rate(
            data, "g6e.xlarge", "us-east-1a", "us-east-1", clients, sizing
        )
        assert rate == 0.75

    def test_falls_back_to_sizing_when_spot_price_unavailable(self) -> None:
        """get_hourly_rate() falls back to sizing table when spot price is
        unavailable."""
        from ember_aws.status_cost import get_hourly_rate

        clients = _make_clients(spot_price=None)
        sizing = _make_sizing(hourly_usd={"us-east-1": 1.861})
        data = _instance_data(lifecycle="spot")

        rate = get_hourly_rate(
            data, "g6e.xlarge", "us-east-1a", "us-east-1", clients, sizing
        )
        assert rate == 1.861

    def test_returns_sizing_rate_for_on_demand(self) -> None:
        """get_hourly_rate() returns sizing table rate for on-demand instances."""
        from ember_aws.status_cost import get_hourly_rate

        clients = _make_clients()
        sizing = _make_sizing(hourly_usd={"us-east-1": 1.861})
        data = _instance_data()

        rate = get_hourly_rate(
            data, "g6e.xlarge", "us-east-1a", "us-east-1", clients, sizing
        )
        assert rate == 1.861


# ---------------------------------------------------------------------------
# get_spot_price()
# ---------------------------------------------------------------------------


class TestGetSpotPrice:
    """get_spot_price() fetches the current spot price."""

    def test_returns_float_when_history_available(self) -> None:
        """get_spot_price() returns the spot price as a float."""
        from ember_aws.status_cost import get_spot_price

        clients = _make_clients(spot_price="1.234")
        result = get_spot_price("g6e.xlarge", "us-east-1a", clients)
        assert result == 1.234

    def test_returns_none_when_no_history(self) -> None:
        """get_spot_price() returns None when no spot price history is available."""
        from ember_aws.status_cost import get_spot_price

        clients = _make_clients(spot_price=None)
        result = get_spot_price("g6e.xlarge", "us-east-1a", clients)
        assert result is None

    def test_returns_none_on_exception(self) -> None:
        """get_spot_price() returns None when the EC2 call raises an exception."""
        from ember_aws.status_cost import get_spot_price

        clients = MagicMock()
        clients.ec2.describe_spot_price_history.side_effect = Exception("AccessDenied")
        result = get_spot_price("g6e.xlarge", "us-east-1a", clients)
        assert result is None


# ---------------------------------------------------------------------------
# hourly_from_sizing()
# ---------------------------------------------------------------------------


class TestHourlyFromSizing:
    """hourly_from_sizing() looks up the on-demand rate from the sizing table."""

    def test_returns_rate_for_known_instance_type(self) -> None:
        """hourly_from_sizing() returns the rate for a known instance type."""
        from ember_aws.status_cost import hourly_from_sizing

        sizing = _make_sizing(
            instance_type="g6e.xlarge", hourly_usd={"us-east-1": 1.861}
        )
        result = hourly_from_sizing("g6e.xlarge", "us-east-1", sizing)
        assert result == 1.861

    def test_returns_first_rate_when_region_not_in_map(self) -> None:
        """hourly_from_sizing() returns the first rate when the region is not
        in the map."""
        from ember_aws.status_cost import hourly_from_sizing

        sizing = _make_sizing(
            instance_type="g6e.xlarge", hourly_usd={"us-east-1": 1.861}
        )
        result = hourly_from_sizing("g6e.xlarge", "eu-west-1", sizing)
        assert result == 1.861  # falls back to first value

    def test_returns_none_when_sizing_raises(self) -> None:
        """hourly_from_sizing() returns None when the sizing table raises."""
        from ember_aws.status_cost import hourly_from_sizing

        sizing = MagicMock()
        sizing.entries = []
        sizing.resolve.side_effect = Exception("SizingError")
        result = hourly_from_sizing("unknown-type", "us-east-1", sizing)
        assert result is None

    def test_scans_entries_when_resolve_fails(self) -> None:
        """hourly_from_sizing() scans entries when resolve() raises."""
        from ember_aws.status_cost import hourly_from_sizing

        entry = MagicMock()
        entry.instance_type = "g6e.xlarge"
        entry.model = "flash"
        entry.hourly_usd = {"us-east-1": 1.861}

        sizing = MagicMock()
        sizing.entries = [entry]
        sizing.resolve.side_effect = Exception("not found")

        result = hourly_from_sizing("g6e.xlarge", "us-east-1", sizing)
        assert result == 1.861

    def test_returns_none_when_no_entries_match(self) -> None:
        """hourly_from_sizing() returns None when no entry matches the instance type."""
        from ember_aws.status_cost import hourly_from_sizing

        entry = MagicMock()
        entry.instance_type = "g5.2xlarge"
        entry.hourly_usd = {"us-east-1": 1.212}

        sizing = MagicMock()
        sizing.entries = [entry]
        sizing.resolve.side_effect = Exception("not found")

        result = hourly_from_sizing("g6e.xlarge", "us-east-1", sizing)
        assert result is None


# ---------------------------------------------------------------------------
# _guess_model()
# ---------------------------------------------------------------------------


class TestGuessModel:
    """_guess_model() returns the model name for a given instance type."""

    def test_returns_model_for_known_instance_type(self) -> None:
        """_guess_model() returns the model name when the instance type is found."""
        from ember_aws.status_cost import _guess_model

        entry = MagicMock()
        entry.instance_type = "g6e.xlarge"
        entry.model = "flash"

        sizing = MagicMock()
        sizing.entries = [entry]

        result = _guess_model("g6e.xlarge", sizing)
        assert result == "flash"

    def test_returns_flash_when_not_found(self) -> None:
        """_guess_model() returns 'flash' when the instance type is not in entries."""
        from ember_aws.status_cost import _guess_model

        sizing = MagicMock()
        sizing.entries = []

        result = _guess_model("unknown-type", sizing)
        assert result == "flash"

    def test_returns_flash_on_exception(self) -> None:
        """_guess_model() returns 'flash' when the sizing table raises."""
        from ember_aws.status_cost import _guess_model

        sizing = MagicMock()
        sizing.entries = MagicMock(side_effect=Exception("error"))

        result = _guess_model("g6e.xlarge", sizing)
        assert result == "flash"
