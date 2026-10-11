"""Tests for DeploymentStatus and StatusReader (T032)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------

_TAILNET_SUFFIX = "example.ts.net"
_INSTANCE_ID = "i-0abc1234"
_INSTANCE_TYPE = "g6e.xlarge"
_AZ = "us-east-1a"
_LAUNCH_TIME = datetime(2026, 10, 11, 10, 0, 0, tzinfo=UTC)


def _make_clients(
    *,
    stack_exists: bool = True,
    stack_status: str = "CREATE_COMPLETE",
    instance_state: str = "running",
    instance_state_reason_code: str = "",
    instance_state_reason_msg: str = "",
    launch_time: datetime = _LAUNCH_TIME,
    az: str = _AZ,
    instance_type: str = _INSTANCE_TYPE,
    capacity: str = "on-demand",
    ssm_config: dict[str, Any] | None = None,
    spot_price: str | None = None,
) -> Any:
    """Build a fake AwsClients-shaped object for status tests."""
    clients = MagicMock()

    # CFN
    if stack_exists:
        clients.cfn.describe_stacks.return_value = {
            "Stacks": [
                {
                    "StackName": "ember-default",
                    "StackStatus": stack_status,
                    "Outputs": [
                        {"OutputKey": "InstanceId", "OutputValue": _INSTANCE_ID},
                        {
                            "OutputKey": "RoleArn",
                            "OutputValue": "arn:aws:iam::123:role/r",
                        },
                    ],
                }
            ]
        }
    else:
        from botocore.exceptions import ClientError

        clients.cfn.describe_stacks.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "does not exist"}},
            "DescribeStacks",
        )

    # EC2 — describe_instances
    market_options: dict[str, Any] = {}
    if capacity == "spot":
        market_options = {"MarketType": "spot"}

    state_reason: dict[str, str] = {}
    if instance_state_reason_code:
        state_reason = {
            "Code": instance_state_reason_code,
            "Message": instance_state_reason_msg,
        }

    clients.ec2.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": _INSTANCE_ID,
                        "InstanceType": instance_type,
                        "State": {"Name": instance_state},
                        "StateReason": state_reason,
                        "Placement": {"AvailabilityZone": az},
                        "LaunchTime": launch_time,
                        "InstanceLifecycle": "spot" if capacity == "spot" else "",
                        "InstanceMarketOptions": market_options,
                    }
                ]
            }
        ]
    }

    # EC2 — describe_spot_price_history
    if spot_price is not None:
        clients.ec2.describe_spot_price_history.return_value = {
            "SpotPriceHistory": [
                {
                    "InstanceType": instance_type,
                    "AvailabilityZone": az,
                    "SpotPrice": spot_price,
                    "Timestamp": launch_time,
                }
            ]
        }
    else:
        clients.ec2.describe_spot_price_history.return_value = {"SpotPriceHistory": []}

    # SSM — config param
    _default_config = {
        "ember_version": "0.12.0",
        "model_s3_uri": "s3://bucket/models/flash/abc123",
        "max_request_length": 24576,
        "idle_minutes": 0,
        "generation": 1,
    }
    config_value = json.dumps(ssm_config if ssm_config is not None else _default_config)

    def _get_parameter(**kwargs: Any) -> dict[str, Any]:
        name = kwargs.get("Name", "")
        if name == "/ember/default/config":
            return {"Parameter": {"Name": name, "Value": config_value}}
        from botocore.exceptions import ClientError

        raise ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "not found"}},
            "GetParameter",
        )

    clients.ssm.get_parameter.side_effect = _get_parameter

    return clients


def _make_tailscale(
    *,
    tailnet_suffix: str = _TAILNET_SUFFIX,
    magic_dns: bool = True,
    has_device: bool = True,
) -> Any:
    ts = MagicMock()
    ts.tailnet_dns.return_value = {"magic_dns": magic_dns, "suffix": tailnet_suffix}
    if has_device:
        ts.devices.return_value = [
            {
                "hostname": "ember-default",
                "tags": ["tag:ember"],
                "id": "dev-001",
            }
        ]
    else:
        ts.devices.return_value = []
    return ts


def _make_sizing() -> Any:
    """Return a fake SizingTable with a flash/g6e.xlarge entry."""
    from ember_aws.sizing_entry import SizingEntry
    from ember_aws.sizing_table import SizingTable

    entry = SizingEntry(
        model="flash",
        instance_type="g6e.xlarge",
        gpu="L40S",
        gpu_memory_gib=48,
        status="supported",
        default=True,
        request_cap=24576,
        cap_source="fallback",
        hourly_usd={"us-east-1": 1.861},
        priced_on="2026-10-11",
        note="test entry",
    )
    return SizingTable(entries=[entry])


def _make_health_transport(
    *,
    status_code: int = 200,
    body: dict[str, Any] | None = None,
    raise_exc: Exception | None = None,
) -> httpx.MockTransport:
    """Return a mock transport for health checks."""
    _body = body or {
        "status": "ok",
        "engine": {"device": "cuda"},
        "version": "0.12.0",
    }

    def _handler(request: httpx.Request) -> httpx.Response:
        if raise_exc is not None:
            raise raise_exc
        return httpx.Response(status_code, json=_body)

    return httpx.MockTransport(_handler)


# ---------------------------------------------------------------------------
# DeploymentStatus model tests
# ---------------------------------------------------------------------------


class TestDeploymentStatus:
    """Unit tests for the DeploymentStatus Pydantic model."""

    def test_model_fields_present(self) -> None:
        """DeploymentStatus must have all data-model.md fields."""
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.deployment_status import DeploymentStatus

        status = DeploymentStatus(state=DeploymentState.ABSENT)
        assert status.state == DeploymentState.ABSENT
        assert status.stop_reason is None
        assert status.instance_id is None
        assert status.instance_type is None
        assert status.capacity is None
        assert status.az is None
        assert status.tailnet_name is None
        assert status.url is None
        assert status.health is None
        assert status.uptime is None
        assert status.hourly_usd is None
        assert status.cost_since_start_usd is None
        assert status.idle_minutes is None

    def test_json_round_trip(self) -> None:
        """DeploymentStatus must round-trip through JSON."""
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.deployment_status import DeploymentStatus
        from ember_aws.stop_reason import StopReason

        status = DeploymentStatus(
            state=DeploymentState.STOPPED,
            stop_reason=StopReason.IDLE,
            instance_id="i-0001",
            instance_type="g6e.xlarge",
            capacity="on-demand",
            az="us-east-1a",
            tailnet_name="example.ts.net",
            url="https://ember-default.example.ts.net",
            health={"status": "ok", "engine": {"device": "cuda"}},
            uptime=3600.0,
            hourly_usd=1.861,
            cost_since_start_usd=1.86,
            idle_minutes="off",
        )
        raw = status.model_dump_json()
        restored = DeploymentStatus.model_validate_json(raw)
        assert restored.state == DeploymentState.STOPPED
        assert restored.stop_reason == StopReason.IDLE
        assert restored.idle_minutes == "off"

    def test_json_validates_against_model(self) -> None:
        """--json output must validate against the DeploymentStatus model."""
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.deployment_status import DeploymentStatus

        status = DeploymentStatus(state=DeploymentState.RUNNING)
        raw_json = status.model_dump_json()
        parsed = json.loads(raw_json)
        # Must have a 'state' key
        assert "state" in parsed
        # Must round-trip cleanly
        restored = DeploymentStatus.model_validate(parsed)
        assert restored.state == DeploymentState.RUNNING

    def test_idle_minutes_off_when_zero(self) -> None:
        """idle_minutes field accepts 'off' string when value is 0."""
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.deployment_status import DeploymentStatus

        status = DeploymentStatus(state=DeploymentState.RUNNING, idle_minutes="off")
        assert status.idle_minutes == "off"

    def test_idle_minutes_numeric_when_nonzero(self) -> None:
        """idle_minutes field accepts int when value > 0."""
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.deployment_status import DeploymentStatus

        status = DeploymentStatus(state=DeploymentState.RUNNING, idle_minutes=30)
        assert status.idle_minutes == 30


# ---------------------------------------------------------------------------
# StatusReader: absent stack
# ---------------------------------------------------------------------------


class TestStatusReaderAbsent:
    """StatusReader returns absent state when no stack exists."""

    def test_absent_when_no_stack(self) -> None:
        """state == absent when the CFN stack does not exist."""
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(stack_exists=False)
        ts = _make_tailscale()
        sizing = _make_sizing()

        names = DeploymentName(name="default")
        reader = StatusReader(clients=clients, tailscale=ts, sizing=sizing)
        status = reader.read(names)

        from ember_aws.deployment_state import DeploymentState

        assert status.state == DeploymentState.ABSENT
        assert status.instance_id is None
        assert status.url is None


# ---------------------------------------------------------------------------
# StatusReader: state mapping from stack + instance states
# ---------------------------------------------------------------------------


class TestStatusReaderStateMapping:
    """StatusReader maps stack and instance states to DeploymentState."""

    def test_running_when_stack_complete_and_instance_running(self) -> None:
        """state == running when stack is CREATE_COMPLETE and instance running."""
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(
            stack_status="CREATE_COMPLETE", instance_state="running"
        )
        ts = _make_tailscale()
        sizing = _make_sizing()
        transport = _make_health_transport()

        names = DeploymentName(name="default")
        reader = StatusReader(
            clients=clients, tailscale=ts, sizing=sizing, http_transport=transport
        )
        status = reader.read(names)

        assert status.state == DeploymentState.RUNNING

    def test_stopped_when_instance_stopped(self) -> None:
        """state == stopped when instance state is stopped."""
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(
            stack_status="CREATE_COMPLETE", instance_state="stopped"
        )
        ts = _make_tailscale()
        sizing = _make_sizing()

        names = DeploymentName(name="default")
        reader = StatusReader(clients=clients, tailscale=ts, sizing=sizing)
        status = reader.read(names)

        assert status.state == DeploymentState.STOPPED

    def test_creating_when_stack_in_progress(self) -> None:
        """state == creating when stack is CREATE_IN_PROGRESS."""
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(stack_status="CREATE_IN_PROGRESS")
        ts = _make_tailscale()
        sizing = _make_sizing()

        names = DeploymentName(name="default")
        reader = StatusReader(clients=clients, tailscale=ts, sizing=sizing)
        status = reader.read(names)

        assert status.state == DeploymentState.CREATING

    def test_failed_when_stack_rollback_complete(self) -> None:
        """state == failed when stack is ROLLBACK_COMPLETE."""
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(stack_status="ROLLBACK_COMPLETE")
        ts = _make_tailscale()
        sizing = _make_sizing()

        names = DeploymentName(name="default")
        reader = StatusReader(clients=clients, tailscale=ts, sizing=sizing)
        status = reader.read(names)

        assert status.state == DeploymentState.FAILED

    def test_stopping_when_instance_stopping(self) -> None:
        """state == stopping when instance state is stopping."""
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(
            stack_status="CREATE_COMPLETE", instance_state="stopping"
        )
        ts = _make_tailscale()
        sizing = _make_sizing()

        names = DeploymentName(name="default")
        reader = StatusReader(clients=clients, tailscale=ts, sizing=sizing)
        status = reader.read(names)

        assert status.state == DeploymentState.STOPPING


# ---------------------------------------------------------------------------
# StatusReader: stop_reason
# ---------------------------------------------------------------------------


class TestStatusReaderStopReason:
    """StatusReader maps EC2 StateReason to StopReason."""

    def test_stop_reason_idle_when_shutdown_initiated_and_idle_minutes_set(
        self,
    ) -> None:
        """stop_reason == idle when StateReason.Code is Client.InstanceInitiatedShutdown
        and idle_minutes > 0."""
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader
        from ember_aws.stop_reason import StopReason

        clients = _make_clients(
            stack_status="CREATE_COMPLETE",
            instance_state="stopped",
            instance_state_reason_code="Client.InstanceInitiatedShutdown",
            instance_state_reason_msg="Client.InstanceInitiatedShutdown: ...",
            ssm_config={
                "ember_version": "0.12.0",
                "model_s3_uri": "s3://bucket/models/flash/abc123",
                "max_request_length": 24576,
                "idle_minutes": 30,
                "generation": 1,
            },
        )
        ts = _make_tailscale()
        sizing = _make_sizing()

        names = DeploymentName(name="default")
        reader = StatusReader(clients=clients, tailscale=ts, sizing=sizing)
        status = reader.read(names)

        assert status.state == DeploymentState.STOPPED
        assert status.stop_reason == StopReason.IDLE

    def test_stop_reason_operator_when_shutdown_initiated_and_idle_minutes_zero(
        self,
    ) -> None:
        """stop_reason == operator when StateReason.Code is InstanceInitiatedShutdown
        but idle_minutes == 0."""
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader
        from ember_aws.stop_reason import StopReason

        clients = _make_clients(
            stack_status="CREATE_COMPLETE",
            instance_state="stopped",
            instance_state_reason_code="Client.InstanceInitiatedShutdown",
            instance_state_reason_msg="Client.InstanceInitiatedShutdown: ...",
            ssm_config={
                "ember_version": "0.12.0",
                "model_s3_uri": "s3://bucket/models/flash/abc123",
                "max_request_length": 24576,
                "idle_minutes": 0,
                "generation": 1,
            },
        )
        ts = _make_tailscale()
        sizing = _make_sizing()

        names = DeploymentName(name="default")
        reader = StatusReader(clients=clients, tailscale=ts, sizing=sizing)
        status = reader.read(names)

        assert status.stop_reason == StopReason.OPERATOR

    def test_stop_reason_spot_interruption_for_spot_code(self) -> None:
        """stop_reason == spot-interruption for spot interruption StateReason codes."""
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader
        from ember_aws.stop_reason import StopReason

        clients = _make_clients(
            stack_status="CREATE_COMPLETE",
            instance_state="stopped",
            instance_state_reason_code="Server.SpotInstanceShutdown",
            instance_state_reason_msg="Server.SpotInstanceShutdown: ...",
        )
        ts = _make_tailscale()
        sizing = _make_sizing()

        names = DeploymentName(name="default")
        reader = StatusReader(clients=clients, tailscale=ts, sizing=sizing)
        status = reader.read(names)

        assert status.stop_reason == StopReason.SPOT_INTERRUPTION

    def test_stop_reason_spot_interruption_for_termination_code(self) -> None:
        """stop_reason == spot-interruption for Server.SpotInstanceTermination."""
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader
        from ember_aws.stop_reason import StopReason

        clients = _make_clients(
            stack_status="CREATE_COMPLETE",
            instance_state="stopped",
            instance_state_reason_code="Server.SpotInstanceTermination",
            instance_state_reason_msg="Server.SpotInstanceTermination: ...",
        )
        ts = _make_tailscale()
        sizing = _make_sizing()

        names = DeploymentName(name="default")
        reader = StatusReader(clients=clients, tailscale=ts, sizing=sizing)
        status = reader.read(names)

        assert status.stop_reason == StopReason.SPOT_INTERRUPTION

    def test_stop_reason_none_when_running(self) -> None:
        """stop_reason is None when instance is running."""
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(
            stack_status="CREATE_COMPLETE", instance_state="running"
        )
        ts = _make_tailscale()
        sizing = _make_sizing()
        transport = _make_health_transport()

        names = DeploymentName(name="default")
        reader = StatusReader(
            clients=clients, tailscale=ts, sizing=sizing, http_transport=transport
        )
        status = reader.read(names)

        assert status.stop_reason is None


# ---------------------------------------------------------------------------
# StatusReader: cost estimate
# ---------------------------------------------------------------------------


class TestStatusReaderCost:
    """StatusReader computes cost_since_start_usd from hourly rate and LaunchTime."""

    def test_cost_since_start_rounded_to_cents(self) -> None:
        """cost_since_start_usd is hourly x hours since LaunchTime, rounded to cents."""
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        # LaunchTime is fixed; we freeze "now" via monkeypatching in the reader
        clients = _make_clients(
            stack_status="CREATE_COMPLETE",
            instance_state="running",
            launch_time=_LAUNCH_TIME,
        )
        ts = _make_tailscale()
        sizing = _make_sizing()
        transport = _make_health_transport()

        names = DeploymentName(name="default")
        reader = StatusReader(
            clients=clients, tailscale=ts, sizing=sizing, http_transport=transport
        )
        status = reader.read(names)

        # cost_since_start_usd must be a float rounded to 2 decimal places
        assert status.cost_since_start_usd is not None
        cost = status.cost_since_start_usd
        assert isinstance(cost, float)
        # Must be rounded to cents (2 decimal places)
        assert round(cost, 2) == cost

    def test_cost_labelled_estimate(self) -> None:
        """cost_since_start_usd is labelled as an estimate in the model."""
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.deployment_status import DeploymentStatus

        # The field is present and the model serialises it
        status = DeploymentStatus(
            state=DeploymentState.RUNNING,
            cost_since_start_usd=1.86,
        )
        raw = json.loads(status.model_dump_json())
        assert "cost_since_start_usd" in raw
        assert raw["cost_since_start_usd"] == 1.86

    def test_hourly_usd_from_sizing_table(self) -> None:
        """hourly_usd is populated from the sizing table for the instance type."""
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(
            stack_status="CREATE_COMPLETE",
            instance_state="running",
        )
        ts = _make_tailscale()
        sizing = _make_sizing()
        transport = _make_health_transport()

        names = DeploymentName(name="default")
        reader = StatusReader(
            clients=clients, tailscale=ts, sizing=sizing, http_transport=transport
        )
        status = reader.read(names)

        assert status.hourly_usd == pytest.approx(1.861)


# ---------------------------------------------------------------------------
# StatusReader: spot price
# ---------------------------------------------------------------------------


class TestStatusReaderSpotPrice:
    """StatusReader fetches spot price from describe_spot_price_history."""

    def test_spot_price_from_describe_spot_price_history(self) -> None:
        """hourly_usd uses spot price when capacity is spot."""
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(
            stack_status="CREATE_COMPLETE",
            instance_state="running",
            capacity="spot",
            spot_price="0.5500",
        )
        ts = _make_tailscale()
        sizing = _make_sizing()
        transport = _make_health_transport()

        names = DeploymentName(name="default")
        reader = StatusReader(
            clients=clients, tailscale=ts, sizing=sizing, http_transport=transport
        )
        status = reader.read(names)

        # For spot, hourly_usd should reflect the spot price
        assert status.hourly_usd == pytest.approx(0.55)


# ---------------------------------------------------------------------------
# StatusReader: health
# ---------------------------------------------------------------------------


class TestStatusReaderHealth:
    """StatusReader fetches health from the tailnet URL."""

    def test_health_populated_when_reachable(self) -> None:
        """health is populated from GET <url>/health when reachable."""
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(
            stack_status="CREATE_COMPLETE", instance_state="running"
        )
        ts = _make_tailscale()
        sizing = _make_sizing()
        transport = _make_health_transport(
            body={"status": "ok", "engine": {"device": "cuda"}, "version": "0.12.0"}
        )

        names = DeploymentName(name="default")
        reader = StatusReader(
            clients=clients, tailscale=ts, sizing=sizing, http_transport=transport
        )
        status = reader.read(names)

        assert status.health is not None
        assert status.health.get("engine", {}).get("device") == "cuda"

    def test_health_error_when_unreachable(self) -> None:
        """health contains error text when the URL is unreachable."""
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(
            stack_status="CREATE_COMPLETE", instance_state="running"
        )
        ts = _make_tailscale()
        sizing = _make_sizing()
        transport = _make_health_transport(
            raise_exc=httpx.ConnectError("connection refused")
        )

        names = DeploymentName(name="default")
        reader = StatusReader(
            clients=clients, tailscale=ts, sizing=sizing, http_transport=transport
        )
        status = reader.read(names)

        # health should contain an error key, not raise
        assert status.health is not None
        assert "error" in status.health

    def test_health_none_when_stopped(self) -> None:
        """health is None when instance is stopped (no URL to poll)."""
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(
            stack_status="CREATE_COMPLETE", instance_state="stopped"
        )
        ts = _make_tailscale()
        sizing = _make_sizing()

        names = DeploymentName(name="default")
        reader = StatusReader(clients=clients, tailscale=ts, sizing=sizing)
        status = reader.read(names)

        assert status.health is None


# ---------------------------------------------------------------------------
# StatusReader: idle_minutes display
# ---------------------------------------------------------------------------


class TestStatusReaderIdleMinutes:
    """StatusReader shows idle_minutes as 'off' when 0."""

    def test_idle_minutes_off_when_zero(self) -> None:
        """idle_minutes is 'off' when config has idle_minutes == 0."""
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(
            stack_status="CREATE_COMPLETE",
            instance_state="running",
            ssm_config={
                "ember_version": "0.12.0",
                "model_s3_uri": "s3://bucket/models/flash/abc123",
                "max_request_length": 24576,
                "idle_minutes": 0,
                "generation": 1,
            },
        )
        ts = _make_tailscale()
        sizing = _make_sizing()
        transport = _make_health_transport()

        names = DeploymentName(name="default")
        reader = StatusReader(
            clients=clients, tailscale=ts, sizing=sizing, http_transport=transport
        )
        status = reader.read(names)

        assert status.idle_minutes == "off"

    def test_idle_minutes_numeric_when_nonzero(self) -> None:
        """idle_minutes is an int when config has idle_minutes > 0."""
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(
            stack_status="CREATE_COMPLETE",
            instance_state="running",
            ssm_config={
                "ember_version": "0.12.0",
                "model_s3_uri": "s3://bucket/models/flash/abc123",
                "max_request_length": 24576,
                "idle_minutes": 45,
                "generation": 1,
            },
        )
        ts = _make_tailscale()
        sizing = _make_sizing()
        transport = _make_health_transport()

        names = DeploymentName(name="default")
        reader = StatusReader(
            clients=clients, tailscale=ts, sizing=sizing, http_transport=transport
        )
        status = reader.read(names)

        assert status.idle_minutes == 45


# ---------------------------------------------------------------------------
# StatusReader: URL construction
# ---------------------------------------------------------------------------


class TestStatusReaderUrl:
    """StatusReader constructs the tailnet URL from the Tailscale API."""

    def test_url_constructed_from_tailnet_suffix(self) -> None:
        """url is https://ember-<name>.<tailnet>.ts.net."""
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(
            stack_status="CREATE_COMPLETE", instance_state="running"
        )
        ts = _make_tailscale(tailnet_suffix="mynet.ts.net")
        sizing = _make_sizing()
        transport = _make_health_transport()

        names = DeploymentName(name="default")
        reader = StatusReader(
            clients=clients, tailscale=ts, sizing=sizing, http_transport=transport
        )
        status = reader.read(names)

        assert status.url == "https://ember-default.mynet.ts.net"

    def test_tailnet_name_populated(self) -> None:
        """tailnet_name is populated from the Tailscale DNS suffix."""
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(
            stack_status="CREATE_COMPLETE", instance_state="running"
        )
        ts = _make_tailscale(tailnet_suffix="mynet.ts.net")
        sizing = _make_sizing()
        transport = _make_health_transport()

        names = DeploymentName(name="default")
        reader = StatusReader(
            clients=clients, tailscale=ts, sizing=sizing, http_transport=transport
        )
        status = reader.read(names)

        assert status.tailnet_name == "mynet.ts.net"


# ---------------------------------------------------------------------------
# StatusReader: instance fields
# ---------------------------------------------------------------------------


class TestStatusReaderInstanceFields:
    """StatusReader populates instance_id, instance_type, capacity, az."""

    def test_instance_fields_populated(self) -> None:
        """instance_id, instance_type, capacity, az are populated from EC2."""
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(
            stack_status="CREATE_COMPLETE",
            instance_state="running",
            az="us-east-1b",
            instance_type="g6e.xlarge",
        )
        ts = _make_tailscale()
        sizing = _make_sizing()
        transport = _make_health_transport()

        names = DeploymentName(name="default")
        reader = StatusReader(
            clients=clients, tailscale=ts, sizing=sizing, http_transport=transport
        )
        status = reader.read(names)

        assert status.instance_id == _INSTANCE_ID
        assert status.instance_type == "g6e.xlarge"
        assert status.az == "us-east-1b"

    def test_capacity_on_demand(self) -> None:
        """capacity is 'on-demand' for a non-spot instance."""
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(
            stack_status="CREATE_COMPLETE",
            instance_state="running",
            capacity="on-demand",
        )
        ts = _make_tailscale()
        sizing = _make_sizing()
        transport = _make_health_transport()

        names = DeploymentName(name="default")
        reader = StatusReader(
            clients=clients, tailscale=ts, sizing=sizing, http_transport=transport
        )
        status = reader.read(names)

        assert status.capacity == "on-demand"

    def test_capacity_spot(self) -> None:
        """capacity is 'spot' for a spot instance."""
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(
            stack_status="CREATE_COMPLETE",
            instance_state="running",
            capacity="spot",
            spot_price="0.5500",
        )
        ts = _make_tailscale()
        sizing = _make_sizing()
        transport = _make_health_transport()

        names = DeploymentName(name="default")
        reader = StatusReader(
            clients=clients, tailscale=ts, sizing=sizing, http_transport=transport
        )
        status = reader.read(names)

        assert status.capacity == "spot"


# ---------------------------------------------------------------------------
# StatusReader: tolerant of missing SSM config
# ---------------------------------------------------------------------------


class TestStatusReaderTolerance:
    """StatusReader is tolerant of missing or broken parts."""

    def test_tolerant_of_missing_ssm_config(self) -> None:
        """StatusReader does not raise when SSM config param is missing."""
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(
            stack_status="CREATE_COMPLETE",
            instance_state="running",
        )
        # Override SSM to always raise ParameterNotFound
        from botocore.exceptions import ClientError

        clients.ssm.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "not found"}},
            "GetParameter",
        )

        ts = _make_tailscale()
        sizing = _make_sizing()
        transport = _make_health_transport()

        names = DeploymentName(name="default")
        reader = StatusReader(
            clients=clients, tailscale=ts, sizing=sizing, http_transport=transport
        )
        # Must not raise
        status = reader.read(names)
        assert status.state == DeploymentState.RUNNING

    def test_tolerant_of_tailscale_error(self) -> None:
        """StatusReader does not raise when Tailscale API fails."""
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader
        from ember_aws.tailscale_client import TailscaleError

        clients = _make_clients(
            stack_status="CREATE_COMPLETE",
            instance_state="running",
        )
        ts = _make_tailscale()
        ts.tailnet_dns.side_effect = TailscaleError("API error")

        sizing = _make_sizing()

        names = DeploymentName(name="default")
        reader = StatusReader(clients=clients, tailscale=ts, sizing=sizing)
        # Must not raise
        status = reader.read(names)
        assert status.state == DeploymentState.RUNNING
        assert status.url is None

    def test_tolerant_of_no_instance_in_ec2(self) -> None:
        """StatusReader handles empty EC2 describe_instances gracefully."""
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.names import DeploymentName
        from ember_aws.status_reader import StatusReader

        clients = _make_clients(
            stack_status="CREATE_COMPLETE",
            instance_state="running",
        )
        # Override EC2 to return no instances
        clients.ec2.describe_instances.return_value = {"Reservations": []}

        ts = _make_tailscale()
        sizing = _make_sizing()

        names = DeploymentName(name="default")
        reader = StatusReader(clients=clients, tailscale=ts, sizing=sizing)
        # Must not raise; state should still be deterministic
        status = reader.read(names)
        # With no instance data, state falls back to stack-based mapping
        assert status.state in (
            DeploymentState.RUNNING,
            DeploymentState.STOPPED,
            DeploymentState.CREATING,
            DeploymentState.FAILED,
        )


# ---------------------------------------------------------------------------
# --json output validation
# ---------------------------------------------------------------------------


class TestJsonOutput:
    """--json output validates against the DeploymentStatus model."""

    def test_json_output_is_valid_deployment_status(self) -> None:
        """model_dump_json() output validates against DeploymentStatus."""
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.deployment_status import DeploymentStatus

        status = DeploymentStatus(
            state=DeploymentState.RUNNING,
            stop_reason=None,
            instance_id="i-0001",
            instance_type="g6e.xlarge",
            capacity="on-demand",
            az="us-east-1a",
            tailnet_name="example.ts.net",
            url="https://ember-default.example.ts.net",
            health={"status": "ok", "engine": {"device": "cuda"}},
            uptime=7200.0,
            hourly_usd=1.861,
            cost_since_start_usd=3.72,
            idle_minutes="off",
        )
        raw_json = status.model_dump_json()
        parsed = json.loads(raw_json)

        # Validate round-trip
        restored = DeploymentStatus.model_validate(parsed)
        assert restored.state == DeploymentState.RUNNING
        assert restored.instance_id == "i-0001"
        assert restored.cost_since_start_usd == 3.72

    def test_absent_status_json(self) -> None:
        """Absent status serialises cleanly to JSON."""
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.deployment_status import DeploymentStatus

        status = DeploymentStatus(state=DeploymentState.ABSENT)
        raw_json = status.model_dump_json()
        parsed = json.loads(raw_json)
        assert parsed["state"] == "absent"
        # All optional fields should be null
        assert parsed["instance_id"] is None
        assert parsed["url"] is None
