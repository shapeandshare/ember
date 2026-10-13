"""Stack: CloudFormation stack operations for an ember deployment."""

from __future__ import annotations

import contextlib
from typing import Any

from .names import DeploymentName

#: SSM parameter path for the DLAMI AMI ID.
_DLAMI_SSM_PATH = (
    "/aws/service/deeplearning/ami/x86_64"
    "/base-oss-nvidia-driver-gpu-ubuntu-24.04/latest/ami-id"
)


def _cfn_params(params: dict[str, str]) -> list[dict[str, str]]:
    """Convert parameter pairs to CloudFormation format, skipping internal keys."""
    return [
        {"ParameterKey": k, "ParameterValue": v}
        for k, v in params.items()
        if not k.startswith("_")
    ]


class Stack:
    """CloudFormation stack operations for a named ember deployment.

    Wraps create, wait, outputs, and failure-reason queries for the
    ``ember-<name>`` stack.  ``resolve_image_id`` and ``pick_subnets`` are
    called only on create or replace.

    Parameters
    ----------
    clients : Any
        An :class:`~ember_aws.aws_clients.AwsClients` instance (or a mock).
    names : DeploymentName
        Validated deployment name with derived stack and SSM paths.
    """

    def __init__(self, clients: Any, names: DeploymentName) -> None:
        self._clients = clients
        self._names = names

    # ------------------------------------------------------------------
    # Existence / status
    # ------------------------------------------------------------------

    def exists(self) -> bool:
        """Return True if the stack exists in any non-deleted state.

        Returns
        -------
        bool
            ``True`` when the stack is present.
        """
        from botocore.exceptions import ClientError  # import-placement:allow

        try:
            self._clients.cfn.describe_stacks(StackName=self._names.stack_name)
            return True
        except ClientError as exc:
            code = (exc.response.get("Error") or {}).get("Code", "")
            if "ValidationError" in code or "does not exist" in str(exc):
                return False
            raise

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(self, params: dict[str, str], tags: list[dict[str, str]]) -> None:
        """Create the CloudFormation stack.

        Parameters
        ----------
        params : dict[str, str]
            CloudFormation parameter key → value pairs.
        tags : list[dict[str, str]]
            List of ``{"Key": ..., "Value": ...}`` tag dicts.
        """
        cfn_params = _cfn_params(params)
        self._clients.cfn.create_stack(
            StackName=self._names.stack_name,
            TemplateBody=self._template_body(params),
            Parameters=cfn_params,
            Capabilities=["CAPABILITY_NAMED_IAM"],
            Tags=tags,
        )

    def _template_body(self, params: dict[str, str]) -> str:
        """Return the rendered template body with user data inlined.

        Parameters
        ----------
        params : dict[str, str]
            Stack parameters (used to extract user-data context).

        Returns
        -------
        str
            The full CloudFormation template body.
        """
        return params.get("_template_body", "")

    # ------------------------------------------------------------------
    # Wait
    # ------------------------------------------------------------------

    def wait(self, op: str = "create") -> None:
        """Wait for a stack operation to complete.

        Parameters
        ----------
        op : str
            One of ``"create"``, ``"update"``, or ``"delete"``.

        Raises
        ------
        StackWaitError
            If the waiter raises (stack rolled back or failed).
        """
        waiter_name = f"stack_{op}_complete"
        waiter = self._clients.cfn.get_waiter(waiter_name)
        try:
            waiter.wait(StackName=self._names.stack_name)
        except Exception as exc:
            raise StackWaitError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Outputs
    # ------------------------------------------------------------------

    def outputs(self) -> dict[str, str]:
        """Return the stack's output key → value mapping.

        Returns
        -------
        dict[str, str]
            Stack outputs, e.g. ``{"InstanceId": "i-0001", "RoleArn": "..."}``.
        """
        resp = self._clients.cfn.describe_stacks(StackName=self._names.stack_name)
        stacks = resp.get("Stacks", [])
        if not stacks:
            return {}
        raw_outputs: list[dict[str, str]] = stacks[0].get("Outputs", [])
        return {o["OutputKey"]: o["OutputValue"] for o in raw_outputs}

    # ------------------------------------------------------------------
    # Failure reason
    # ------------------------------------------------------------------

    def first_failure_reason(self) -> str | None:
        """Return the reason from the earliest (root-cause) CREATE_FAILED event.

        Events arrive newest-first, so the earliest failure is the root cause.

        Returns
        -------
        str | None
            The root-cause ``ResourceStatusReason``, or ``None``.
        """
        resp = self._clients.cfn.describe_stack_events(StackName=self._names.stack_name)
        for event in reversed(resp.get("StackEvents", [])):
            if event.get("ResourceStatus") == "CREATE_FAILED":
                return str(event.get("ResourceStatusReason", "unknown reason"))
        return None

    # ------------------------------------------------------------------
    # AMI resolution
    # ------------------------------------------------------------------

    def resolve_image_id(self, region: str) -> str:
        """Read the latest DLAMI AMI ID from the AWS SSM public parameter.

        Parameters
        ----------
        region : str
            AWS region (e.g. ``"us-east-1"``).

        Returns
        -------
        str
            The AMI ID (e.g. ``"ami-0abc1234"``).
        """
        resp = self._clients.ssm.get_parameter(Name=_DLAMI_SSM_PATH)
        ami_id: str = resp["Parameter"]["Value"]
        return ami_id

    # ------------------------------------------------------------------
    # Subnet selection
    # ------------------------------------------------------------------

    def pick_subnets(self, instance_type: str) -> list[tuple[str, str]]:
        """Pick default-VPC subnets in AZs that offer the instance type.

        Parameters
        ----------
        instance_type : str
            EC2 instance type (e.g. ``"g6e.xlarge"``).

        Returns
        -------
        list[tuple[str, str]]
            ``(subnet_id, vpc_id)`` candidates in offering AZs, in API order;
            deploy retries the next candidate when an AZ lacks capacity.

        Raises
        ------
        ValueError
            If no default VPC or no matching subnet is found.
        """
        # Find the default VPC.
        vpcs_resp = self._clients.ec2.describe_vpcs(
            Filters=[{"Name": "isDefault", "Values": ["true"]}]
        )
        vpcs = vpcs_resp.get("Vpcs", [])
        if not vpcs:
            raise ValueError("no default VPC found in this region")
        vpc_id: str = vpcs[0]["VpcId"]

        # Find AZs that offer the instance type.
        offerings_resp = self._clients.ec2.describe_instance_type_offerings(
            LocationType="availability-zone",
            Filters=[{"Name": "instance-type", "Values": [instance_type]}],
        )
        az_set = {
            o["Location"] for o in offerings_resp.get("InstanceTypeOfferings", [])
        }

        candidates = [
            (str(subnet["SubnetId"]), vpc_id)
            for subnet in self._clients.ec2.describe_subnets(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            ).get("Subnets", [])
            if subnet.get("AvailabilityZone") in az_set
        ]
        if not candidates:
            raise ValueError(f"no subnet offers instance type {instance_type!r}")
        return candidates

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(self) -> None:
        """Delete the CloudFormation stack."""
        self._clients.cfn.delete_stack(StackName=self._names.stack_name)

    # ------------------------------------------------------------------
    # Update (change set)
    # ------------------------------------------------------------------

    def update(self, params: dict[str, str]) -> bool:
        """Update the stack via a change set.

        Parameters
        ----------
        params : dict[str, str]
            New parameter key → value pairs.

        Returns
        -------
        bool
            ``True`` if changes were applied; ``False`` if the change set was
            empty (stack already up to date).
        """
        import uuid  # import-placement:allow

        change_set_name = f"ember-update-{uuid.uuid4().hex[:8]}"
        cfn_params = _cfn_params(params)
        try:
            self._clients.cfn.create_change_set(
                StackName=self._names.stack_name,
                ChangeSetName=change_set_name,
                TemplateBody=self._template_body(params),
                Parameters=cfn_params,
                Capabilities=["CAPABILITY_NAMED_IAM"],
            )
            waiter = self._clients.cfn.get_waiter("change_set_create_complete")
            waiter.wait(
                StackName=self._names.stack_name,
                ChangeSetName=change_set_name,
            )
            self._clients.cfn.execute_change_set(
                StackName=self._names.stack_name,
                ChangeSetName=change_set_name,
            )
            return True
        except Exception as exc:
            if "empty" in str(exc).lower() or "no changes" in str(exc).lower():
                return False
            raise

    def prepare_change_set(self, params: dict[str, str]) -> str | None:
        """Create a change set and wait for it, returning its name.

        Returns ``None`` when the change set is empty (no changes).

        Parameters
        ----------
        params : dict[str, str]
            New parameter key → value pairs.

        Returns
        -------
        str | None
            The change set name, or ``None`` if the change set is empty.
        """
        import uuid  # import-placement:allow

        change_set_name = f"ember-update-{uuid.uuid4().hex[:8]}"
        cfn_params = _cfn_params(params)
        try:
            self._clients.cfn.create_change_set(
                StackName=self._names.stack_name,
                ChangeSetName=change_set_name,
                TemplateBody=self._template_body(params),
                Parameters=cfn_params,
                Capabilities=["CAPABILITY_NAMED_IAM"],
            )
            waiter = self._clients.cfn.get_waiter("change_set_create_complete")
            waiter.wait(
                StackName=self._names.stack_name,
                ChangeSetName=change_set_name,
            )
            return change_set_name
        except Exception as exc:
            reason = self._change_set_status_reason(change_set_name) or str(exc)
            lowered = reason.lower()
            if (
                "empty" in lowered
                or "no changes" in lowered
                or "didn't contain changes" in lowered
            ):
                with contextlib.suppress(Exception):
                    self._clients.cfn.delete_change_set(
                        StackName=self._names.stack_name,
                        ChangeSetName=change_set_name,
                    )
                return None
            raise

    def _change_set_status_reason(self, change_set_name: str) -> str:
        """Return a change set's ``StatusReason``, or ``""`` when unavailable."""
        try:
            resp = self._clients.cfn.describe_change_set(
                StackName=self._names.stack_name,
                ChangeSetName=change_set_name,
            )
        except Exception:
            return ""
        return str(resp.get("StatusReason", ""))

    def change_set_has_replacement(self, change_set_name: str) -> bool:
        """Return True if any resource change in the change set requires replacement.

        Parameters
        ----------
        change_set_name : str
            The name of the change set to inspect.

        Returns
        -------
        bool
            ``True`` when at least one resource change has ``Replacement`` set
            to ``"True"`` or ``"Conditional"``.
        """
        resp = self._clients.cfn.describe_change_set(
            StackName=self._names.stack_name,
            ChangeSetName=change_set_name,
        )
        for change in resp.get("Changes", []):
            resource_change = change.get("ResourceChange", {})
            replacement = resource_change.get("Replacement", "False")
            if replacement in ("True", "Conditional"):
                return True
        return False

    def execute_change_set(self, change_set_name: str) -> None:
        """Execute a previously prepared change set.

        Parameters
        ----------
        change_set_name : str
            The name of the change set to execute.
        """
        self._clients.cfn.execute_change_set(
            StackName=self._names.stack_name,
            ChangeSetName=change_set_name,
        )

    def update_has_replacement(self, params: dict[str, str]) -> bool:
        """Prepare a change set and check whether it requires instance replacement.

        This is a convenience wrapper used by the update path to decide whether
        to delete tailnet devices before executing.  It does NOT execute the
        change set; call ``prepare_change_set`` + ``execute_change_set`` for
        the full flow.

        Parameters
        ----------
        params : dict[str, str]
            New parameter key → value pairs.

        Returns
        -------
        bool
            ``True`` when the change set has at least one replacement resource.
        """
        change_set_name = self.prepare_change_set(params)
        if change_set_name is None:
            return False
        return self.change_set_has_replacement(change_set_name)


class StackWaitError(Exception):
    """Raised when a CloudFormation stack waiter fails.

    Parameters
    ----------
    message : str
        Human-readable description of the failure.
    """
