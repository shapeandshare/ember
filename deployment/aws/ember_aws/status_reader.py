"""StatusReader: reads the current state of a named ember deployment."""

from __future__ import annotations

import json
from typing import Any

import httpx

from .deployment_state import DeploymentState
from .deployment_status import DeploymentStatus
from .names import DeploymentName
from .status_cost import compute_cost
from .stop_reason import StopReason

#: EC2 StateReason codes that indicate a spot interruption.
_SPOT_CODES = frozenset(
    {
        "Server.SpotInstanceShutdown",
        "Server.SpotInstanceTermination",
    }
)

#: CFN stack status → DeploymentState mapping (instance state takes priority
#: when the stack is in a terminal "complete" state).
_STACK_STATE_MAP: dict[str, DeploymentState] = {
    "CREATE_IN_PROGRESS": DeploymentState.CREATING,
    "CREATE_COMPLETE": DeploymentState.RUNNING,
    "CREATE_FAILED": DeploymentState.FAILED,
    "ROLLBACK_IN_PROGRESS": DeploymentState.FAILED,
    "ROLLBACK_COMPLETE": DeploymentState.FAILED,
    "ROLLBACK_FAILED": DeploymentState.FAILED,
    "UPDATE_IN_PROGRESS": DeploymentState.UPDATING,
    "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS": DeploymentState.UPDATING,
    "UPDATE_COMPLETE": DeploymentState.RUNNING,
    "UPDATE_ROLLBACK_IN_PROGRESS": DeploymentState.FAILED,
    "UPDATE_ROLLBACK_COMPLETE": DeploymentState.FAILED,
    "UPDATE_ROLLBACK_FAILED": DeploymentState.FAILED,
    "DELETE_IN_PROGRESS": DeploymentState.DESTROYING,
    "DELETE_COMPLETE": DeploymentState.ABSENT,
    "DELETE_FAILED": DeploymentState.FAILED,
    "REVIEW_IN_PROGRESS": DeploymentState.CREATING,
    "IMPORT_IN_PROGRESS": DeploymentState.UPDATING,
    "IMPORT_COMPLETE": DeploymentState.RUNNING,
    "IMPORT_ROLLBACK_IN_PROGRESS": DeploymentState.FAILED,
    "IMPORT_ROLLBACK_COMPLETE": DeploymentState.FAILED,
    "IMPORT_ROLLBACK_FAILED": DeploymentState.FAILED,
}

#: EC2 instance state → DeploymentState (used when stack is in a terminal state).
_INSTANCE_STATE_MAP: dict[str, DeploymentState] = {
    "pending": DeploymentState.CREATING,
    "running": DeploymentState.RUNNING,
    "stopping": DeploymentState.STOPPING,
    "stopped": DeploymentState.STOPPED,
    "shutting-down": DeploymentState.DESTROYING,
    "terminated": DeploymentState.ABSENT,
}

#: Stack statuses that are "terminal" — instance state drives the final state.
_TERMINAL_STACK_STATUSES = frozenset(
    {
        "CREATE_COMPLETE",
        "UPDATE_COMPLETE",
        "IMPORT_COMPLETE",
    }
)


class StatusReader:
    """Reads the current state of a named ember deployment.

    Tolerant of any missing part: no stack → ``absent``; stopped instance →
    ``stopped``; health unreachable → ``health.error``.

    Parameters
    ----------
    clients : Any
        An :class:`~ember_aws.aws_clients.AwsClients` instance (or a mock).
    tailscale : Any
        A :class:`~ember_aws.tailscale_client.TailscaleClient` instance (or a mock).
    sizing : Any
        A :class:`~ember_aws.sizing_table.SizingTable` instance (or a mock).
    http_transport : httpx.BaseTransport | None
        Optional custom HTTP transport for health checks (used in tests).
    """

    def __init__(
        self,
        clients: Any,
        tailscale: Any,
        sizing: Any,
        http_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._clients = clients
        self._tailscale = tailscale
        self._sizing = sizing
        self._http_transport = http_transport

    def read(self, names: DeploymentName) -> DeploymentStatus:
        """Read the current deployment status.

        Parameters
        ----------
        names : DeploymentName
            Validated deployment name with derived resource identifiers.

        Returns
        -------
        DeploymentStatus
            A snapshot of the deployment's current state.  Never raises;
            missing or unreachable parts are represented as ``None`` or
            error dicts.
        """
        stack_info = self._get_stack_info(names)
        if stack_info is None:
            return DeploymentStatus(state=DeploymentState.ABSENT)

        stack_status = stack_info.get("StackStatus", "")
        instance_id = self._extract_instance_id(stack_info)
        instance_data = self._get_instance_data(instance_id) if instance_id else None

        state = self._derive_state(stack_status, instance_data)
        stop_reason = self._derive_stop_reason(instance_data, names)
        url, tailnet_name = self._get_tailnet_url(names)
        health = self._get_health(state, url)
        config = self._get_instance_config(names)

        uptime, hourly_usd, cost = (
            compute_cost(instance_data, self._clients, self._sizing)
            if instance_data
            else (None, None, None)
        )

        idle_minutes = self._idle_minutes_display(config)
        capacity = self._derive_capacity(instance_data)

        az = None
        instance_type = None
        if instance_data:
            az = (instance_data.get("Placement") or {}).get("AvailabilityZone")
            instance_type = instance_data.get("InstanceType")

        return DeploymentStatus(
            state=state,
            stop_reason=stop_reason,
            instance_id=instance_id,
            instance_type=instance_type,
            capacity=capacity,
            az=az,
            tailnet_name=tailnet_name,
            url=url,
            health=health,
            uptime=uptime,
            hourly_usd=hourly_usd,
            cost_since_start_usd=cost,
            idle_minutes=idle_minutes,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_stack_info(self, names: DeploymentName) -> dict[str, Any] | None:
        """Return the first stack dict, or None if the stack does not exist."""
        from botocore.exceptions import ClientError  # import-placement:allow

        try:
            resp = self._clients.cfn.describe_stacks(StackName=names.stack_name)
            stacks = resp.get("Stacks", [])
            if not stacks:
                return None
            result: dict[str, Any] = stacks[0]
            return result
        except ClientError as exc:
            code = (exc.response.get("Error") or {}).get("Code", "")
            if "ValidationError" in code or "does not exist" in str(exc):
                return None
            raise

    def _extract_instance_id(self, stack_info: dict[str, Any]) -> str | None:
        """Extract the InstanceId from stack outputs."""
        for output in stack_info.get("Outputs", []):
            if output.get("OutputKey") == "InstanceId":
                val: str = output["OutputValue"]
                return val
        return None

    def _get_instance_data(self, instance_id: str) -> dict[str, Any] | None:
        """Return the EC2 instance dict, or None if not found."""
        try:
            resp = self._clients.ec2.describe_instances(InstanceIds=[instance_id])
            for reservation in resp.get("Reservations", []):
                instances = reservation.get("Instances", [])
                if instances:
                    result: dict[str, Any] = instances[0]
                    return result
            return None
        except Exception:
            return None

    def _derive_state(
        self,
        stack_status: str,
        instance_data: dict[str, Any] | None,
    ) -> DeploymentState:
        """Map stack status and instance state to a DeploymentState."""
        if stack_status in _TERMINAL_STACK_STATUSES and instance_data:
            ec2_state = (instance_data.get("State") or {}).get("Name", "")
            if ec2_state in _INSTANCE_STATE_MAP:
                return _INSTANCE_STATE_MAP[ec2_state]
        return _STACK_STATE_MAP.get(stack_status, DeploymentState.FAILED)

    def _derive_stop_reason(
        self,
        instance_data: dict[str, Any] | None,
        names: DeploymentName,
    ) -> StopReason | None:
        """Derive the stop reason from EC2 StateReason and instance config."""
        if not instance_data:
            return None
        ec2_state = (instance_data.get("State") or {}).get("Name", "")
        if ec2_state != "stopped":
            return None
        state_reason = instance_data.get("StateReason") or {}
        code = state_reason.get("Code", "")
        if code in _SPOT_CODES:
            return StopReason.SPOT_INTERRUPTION
        if code == "Client.InstanceInitiatedShutdown":
            config = self._get_instance_config(names)
            idle_minutes = (config or {}).get("idle_minutes", 0)
            if idle_minutes and int(idle_minutes) > 0:
                return StopReason.IDLE
            return StopReason.OPERATOR
        if code:
            return StopReason.UNKNOWN
        return None

    def _get_tailnet_url(self, names: DeploymentName) -> tuple[str | None, str | None]:
        """Return (url, tailnet_name) from the Tailscale API, or (None, None)."""
        try:
            dns = self._tailscale.tailnet_dns()
            suffix = dns.get("suffix", "")
            if not suffix:
                return None, None
            url = f"https://{names.hostname}.{suffix}"
            return url, suffix
        except Exception:
            return None, None

    def _get_health(
        self, state: DeploymentState, url: str | None
    ) -> dict[str, Any] | None:
        """Fetch /health from the tailnet URL, or return an error dict."""
        if state != DeploymentState.RUNNING or not url:
            return None
        client_kwargs: dict[str, Any] = {}
        if self._http_transport is not None:
            client_kwargs["transport"] = self._http_transport
        try:
            with httpx.Client(**client_kwargs) as client:
                resp = client.get(f"{url}/health", timeout=10)
            if resp.status_code == 200:
                body: dict[str, Any] = resp.json()
                return body
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except Exception as exc:
            return {"error": str(exc)}

    def _get_instance_config(self, names: DeploymentName) -> dict[str, Any] | None:
        """Read and parse the SSM config parameter, or return None."""
        from botocore.exceptions import ClientError  # import-placement:allow

        try:
            resp = self._clients.ssm.get_parameter(Name=names.config_param)
            raw = resp["Parameter"]["Value"]
            result: dict[str, Any] = json.loads(raw)
            return result
        except ClientError:
            return None
        except Exception:
            return None

    def _idle_minutes_display(self, config: dict[str, Any] | None) -> int | str | None:
        """Return 'off' when idle_minutes == 0, else the int value."""
        if config is None:
            return None
        raw = config.get("idle_minutes")
        if raw is None:
            return None
        val = int(raw)
        return "off" if val == 0 else val

    def _derive_capacity(self, instance_data: dict[str, Any] | None) -> str | None:
        """Return 'spot' or 'on-demand' from instance data."""
        if not instance_data:
            return None
        lifecycle = instance_data.get("InstanceLifecycle", "")
        market_options = instance_data.get("InstanceMarketOptions") or {}
        if lifecycle == "spot" or market_options.get("MarketType") == "spot":
            return "spot"
        return "on-demand"
