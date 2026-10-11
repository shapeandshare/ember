"""Tests for Lifecycle update path and replace() (T043, US3).

Reuses helpers from test_aws_stack_lifecycle.py.

Behaviours under test:
- version-only change → config generation up, empty change set = no stack update,
  reboot_instances called, wait health; token unchanged; no tailnet device deletion.
- instance_type change → change set with InstanceType (stop/start by CFN),
  tailnet devices NOT deleted.
- no change at all → no put_parameter, no reboot, prints "up to date: <url>".
- change set resource change with Replacement True → delete tailnet devices and
  mint new join key BEFORE execute_change_set.
- replace() → re-resolve DLAMI ID, force replacement, delete devices + mint key
  first, wait for health.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers (mirrors test_aws_stack_lifecycle.py)
# ---------------------------------------------------------------------------

_TAILNET_SUFFIX = "example.ts.net"
_TAILNET_URL = "https://ember-default.example.ts.net"
_DLAMI_SSM_PATH = (
    "/aws/service/deeplearning/ami/x86_64"
    "/base-oss-nvidia-driver-gpu-ubuntu-24.04/latest/ami-id"
)


def _make_clients(
    *,
    stack_exists: bool = True,
    stack_status: str = "UPDATE_COMPLETE",
    stack_outputs: list[dict[str, Any]] | None = None,
    stack_params: dict[str, str] | None = None,
    ssm_params: dict[str, str] | None = None,
    ami_id: str = "ami-0abc1234",
    subnet_id: str = "subnet-aaa",
    vpc_id: str = "vpc-bbb",
    instance_state: str = "running",
) -> Any:
    """Build a fake AwsClients-shaped object for update tests."""
    clients = MagicMock()

    # CFN
    if stack_exists:
        clients.cfn.describe_stacks.return_value = {
            "Stacks": [
                {
                    "StackName": "ember-default",
                    "StackStatus": stack_status,
                    "Parameters": [
                        {"ParameterKey": k, "ParameterValue": v}
                        for k, v in (stack_params or {}).items()
                    ],
                    "Outputs": stack_outputs
                    or [
                        {"OutputKey": "InstanceId", "OutputValue": "i-0001"},
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

    clients.cfn.create_stack.return_value = {
        "StackId": "arn:aws:cfn:us-east-1:123:stack/ember-default/x"
    }
    clients.cfn.get_waiter.return_value = MagicMock()
    clients.cfn.describe_stack_events.return_value = {"StackEvents": []}

    # SSM
    _ssm_store: dict[str, str] = dict(ssm_params or {})

    def _get_parameter(**kwargs: Any) -> dict[str, Any]:
        name = kwargs.get("Name", "")
        if name == _DLAMI_SSM_PATH:
            return {"Parameter": {"Name": name, "Value": ami_id}}
        if name in _ssm_store:
            return {"Parameter": {"Name": name, "Value": _ssm_store[name]}}
        from botocore.exceptions import ClientError

        raise ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "not found"}},
            "GetParameter",
        )

    def _put_parameter(**kwargs: Any) -> dict[str, Any]:
        _ssm_store[kwargs["Name"]] = kwargs["Value"]
        return {}

    clients.ssm.get_parameter.side_effect = _get_parameter
    clients.ssm.put_parameter.side_effect = _put_parameter

    # EC2
    clients.ec2.describe_instance_type_offerings.return_value = {
        "InstanceTypeOfferings": [
            {
                "InstanceType": "g6e.xlarge",
                "Location": "us-east-1a",
                "LocationType": "availability-zone",
            },
        ]
    }
    clients.ec2.describe_subnets.return_value = {
        "Subnets": [
            {"SubnetId": subnet_id, "VpcId": vpc_id, "AvailabilityZone": "us-east-1a"}
        ]
    }
    clients.ec2.describe_vpcs.return_value = {
        "Vpcs": [{"VpcId": vpc_id, "IsDefault": True}]
    }
    clients.ec2.describe_instances.return_value = {
        "Reservations": [
            {"Instances": [{"State": {"Name": instance_state}, "InstanceId": "i-0001"}]}
        ]
    }

    return clients


def _make_tailscale(
    *,
    tailnet_suffix: str = _TAILNET_SUFFIX,
    magic_dns: bool = True,
    join_key_id: str = "key-abc",
    join_key_value: str = "tskey-auth-xxx",
) -> Any:
    ts = MagicMock()
    ts.tailnet_dns.return_value = {"magic_dns": magic_dns, "suffix": tailnet_suffix}
    ts.mint_join_key.return_value = {"id": join_key_id, "key": join_key_value}
    ts.devices.return_value = []
    ts.delete_devices.return_value = None
    return ts


def _make_model_cache(*, cache_status: str = "complete") -> Any:
    mc = MagicMock()
    mc.status.return_value = cache_status
    mc.add.return_value = None
    mc.ensure_bucket.return_value = "ember-model-cache-123456789-us-east-1"
    mc._stack_bucket.return_value = "ember-model-cache-123456789-us-east-1"
    return mc


def _make_preflight(*, ok: bool = True) -> Any:
    pf = MagicMock()
    if ok:
        pf.run.return_value = []
    else:
        from ember_aws.check_result import CheckResult
        from ember_aws.preflight_check import PreflightCheck

        pf.run.return_value = [
            CheckResult(
                check=PreflightCheck.AWS_IDENTITY,
                ok=False,
                problem="no credentials",
                fix="aws sso login",
                blocking=True,
            )
        ]
    return pf


_FLASH_REVISION = "17f0b0ad64efb65d273590632833508766b2aae6"
_FLASH_S3_URI = (
    f"s3://ember-model-cache-123456789-us-east-1/models/flash/{_FLASH_REVISION}"
)


def _make_existing_config(
    *,
    ember_version: str = "0.12.0",
    model_s3_uri: str = _FLASH_S3_URI,
    max_request_length: int = 24576,
    idle_minutes: int = 0,
    generation: int = 1,
) -> str:
    """Return a JSON config string as stored in SSM."""
    return json.dumps(
        {
            "ember_version": ember_version,
            "model_s3_uri": model_s3_uri,
            "max_request_length": max_request_length,
            "idle_minutes": idle_minutes,
            "generation": generation,
        }
    )


def _make_lifecycle(
    clients: Any,
    tailscale: Any,
    model_cache: Any | None = None,
    preflight: Any | None = None,
) -> Any:
    """Build a Lifecycle with sensible defaults."""
    from ember_aws.lifecycle import Lifecycle

    mc = model_cache or _make_model_cache()
    pf = preflight or _make_preflight()
    return Lifecycle(clients=clients, tailscale=tailscale, model_cache=mc, preflight=pf)


# ---------------------------------------------------------------------------
# T043: version-only change
# ---------------------------------------------------------------------------


class TestUpdateVersionOnly:
    """Version-only change: generation up, no stack update, reboot, wait."""

    def test_version_change_increments_generation(self, capsys: Any) -> None:
        """A version-only change must increment the config generation."""
        existing_config = _make_existing_config(ember_version="0.12.0", generation=1)
        clients = _make_clients(
            ssm_params={
                "/ember/default/config": existing_config,
                "/ember/default/server-token": "tok",
            }
        )
        ts = _make_tailscale()
        lc = _make_lifecycle(clients, ts)

        from ember_aws.deployment import Deployment

        deployment = Deployment(name="default", model="flash", ember_version="0.13.0")

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle_update.Stack") as mock_update_stack_cls,
            patch("ember_aws.lifecycle_update.wait_healthy") as mock_health,
        ):
            mock_stack = MagicMock()
            mock_stack.exists.return_value = True
            mock_stack.update.return_value = False  # empty change set
            mock_stack.update_has_replacement.return_value = False
            mock_stack.outputs.return_value = {"InstanceId": "i-0001"}
            mock_stack.pick_subnet.return_value = ("subnet-aaa", "vpc-bbb")
            mock_stack.resolve_image_id.return_value = "ami-0abc1234"
            mock_stack_cls.return_value = mock_stack
            mock_update_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.13.0",
            }

            lc.deploy(deployment)

        # The config param must have been put with generation=2
        put_calls = clients.ssm.put_parameter.call_args_list
        config_puts = [c for c in put_calls if "/ember/default/config" in str(c)]
        assert len(config_puts) >= 1, "config param must be put"
        last_config_value = config_puts[-1].kwargs.get(
            "Value", config_puts[-1].args[1] if len(config_puts[-1].args) > 1 else ""
        )
        config_data = json.loads(last_config_value)
        assert config_data["generation"] == 2, (
            f"generation must be 2, got {config_data['generation']}"
        )

    def test_version_change_no_stack_update_when_empty_changeset(
        self, capsys: Any
    ) -> None:
        """Empty change set → no stack update (update returns False)."""
        existing_config = _make_existing_config(ember_version="0.12.0", generation=1)
        clients = _make_clients(
            ssm_params={
                "/ember/default/config": existing_config,
                "/ember/default/server-token": "tok",
            }
        )
        ts = _make_tailscale()
        lc = _make_lifecycle(clients, ts)

        from ember_aws.deployment import Deployment

        deployment = Deployment(name="default", model="flash", ember_version="0.13.0")

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle_update.Stack") as mock_update_stack_cls,
            patch("ember_aws.lifecycle_update.wait_healthy") as mock_health,
        ):
            mock_stack = MagicMock()
            mock_stack.exists.return_value = True
            mock_stack.update.return_value = False  # empty change set
            mock_stack.update_has_replacement.return_value = False
            mock_stack.outputs.return_value = {"InstanceId": "i-0001"}
            mock_stack.pick_subnet.return_value = ("subnet-aaa", "vpc-bbb")
            mock_stack.resolve_image_id.return_value = "ami-0abc1234"
            mock_stack_cls.return_value = mock_stack
            mock_update_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.13.0",
            }

            lc.deploy(deployment)

        # stack.wait("update") must NOT be called (no stack update)
        wait_calls = [c for c in mock_stack.wait.call_args_list if "update" in str(c)]
        assert len(wait_calls) == 0, (
            "stack.wait('update') must not be called for empty change set"
        )

    def test_version_change_reboots_instance(self, capsys: Any) -> None:
        """A version-only change must call reboot_instances."""
        existing_config = _make_existing_config(ember_version="0.12.0", generation=1)
        clients = _make_clients(
            ssm_params={
                "/ember/default/config": existing_config,
                "/ember/default/server-token": "tok",
            }
        )
        ts = _make_tailscale()
        lc = _make_lifecycle(clients, ts)

        from ember_aws.deployment import Deployment

        deployment = Deployment(name="default", model="flash", ember_version="0.13.0")

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle_update.Stack") as mock_update_stack_cls,
            patch("ember_aws.lifecycle_update.wait_healthy") as mock_health,
        ):
            mock_stack = MagicMock()
            mock_stack.exists.return_value = True
            mock_stack.update.return_value = False
            mock_stack.update_has_replacement.return_value = False
            mock_stack.outputs.return_value = {"InstanceId": "i-0001"}
            mock_stack.pick_subnet.return_value = ("subnet-aaa", "vpc-bbb")
            mock_stack.resolve_image_id.return_value = "ami-0abc1234"
            mock_stack_cls.return_value = mock_stack
            mock_update_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.13.0",
            }

            lc.deploy(deployment)

        clients.ec2.reboot_instances.assert_called_once()

    def test_version_change_waits_health(self, capsys: Any) -> None:
        """A version-only change must wait for health after reboot."""
        existing_config = _make_existing_config(ember_version="0.12.0", generation=1)
        clients = _make_clients(
            ssm_params={
                "/ember/default/config": existing_config,
                "/ember/default/server-token": "tok",
            }
        )
        ts = _make_tailscale()
        lc = _make_lifecycle(clients, ts)

        from ember_aws.deployment import Deployment

        deployment = Deployment(name="default", model="flash", ember_version="0.13.0")

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle_update.Stack") as mock_update_stack_cls,
            patch("ember_aws.lifecycle_update.wait_healthy") as mock_health,
        ):
            mock_stack = MagicMock()
            mock_stack.exists.return_value = True
            mock_stack.update.return_value = False
            mock_stack.update_has_replacement.return_value = False
            mock_stack.outputs.return_value = {"InstanceId": "i-0001"}
            mock_stack.pick_subnet.return_value = ("subnet-aaa", "vpc-bbb")
            mock_stack.resolve_image_id.return_value = "ami-0abc1234"
            mock_stack_cls.return_value = mock_stack
            mock_update_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.13.0",
            }

            lc.deploy(deployment)

        mock_health.assert_called_once()

    def test_version_change_token_unchanged(self, capsys: Any) -> None:
        """A version-only change must NOT overwrite the token."""
        existing_token = "existing-secret-token"
        existing_config = _make_existing_config(ember_version="0.12.0", generation=1)
        clients = _make_clients(
            ssm_params={
                "/ember/default/config": existing_config,
                "/ember/default/server-token": existing_token,
            }
        )
        ts = _make_tailscale()
        lc = _make_lifecycle(clients, ts)

        from ember_aws.deployment import Deployment

        deployment = Deployment(name="default", model="flash", ember_version="0.13.0")

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle_update.Stack") as mock_update_stack_cls,
            patch("ember_aws.lifecycle_update.wait_healthy") as mock_health,
        ):
            mock_stack = MagicMock()
            mock_stack.exists.return_value = True
            mock_stack.update.return_value = False
            mock_stack.update_has_replacement.return_value = False
            mock_stack.outputs.return_value = {"InstanceId": "i-0001"}
            mock_stack.pick_subnet.return_value = ("subnet-aaa", "vpc-bbb")
            mock_stack.resolve_image_id.return_value = "ami-0abc1234"
            mock_stack_cls.return_value = mock_stack
            mock_update_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.13.0",
            }

            lc.deploy(deployment)

        token_put_calls = [
            c
            for c in clients.ssm.put_parameter.call_args_list
            if "/ember/default/server-token" in str(c)
        ]
        assert len(token_put_calls) == 0, (
            "token must not be overwritten on a version-only update"
        )

    def test_version_change_no_tailnet_device_deletion(self, capsys: Any) -> None:
        """A version-only change must NOT delete tailnet devices."""
        existing_config = _make_existing_config(ember_version="0.12.0", generation=1)
        clients = _make_clients(
            ssm_params={
                "/ember/default/config": existing_config,
                "/ember/default/server-token": "tok",
            }
        )
        ts = _make_tailscale()
        lc = _make_lifecycle(clients, ts)

        from ember_aws.deployment import Deployment

        deployment = Deployment(name="default", model="flash", ember_version="0.13.0")

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle_update.Stack") as mock_update_stack_cls,
            patch("ember_aws.lifecycle_update.wait_healthy") as mock_health,
        ):
            mock_stack = MagicMock()
            mock_stack.exists.return_value = True
            mock_stack.update.return_value = False
            mock_stack.update_has_replacement.return_value = False
            mock_stack.outputs.return_value = {"InstanceId": "i-0001"}
            mock_stack.pick_subnet.return_value = ("subnet-aaa", "vpc-bbb")
            mock_stack.resolve_image_id.return_value = "ami-0abc1234"
            mock_stack_cls.return_value = mock_stack
            mock_update_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.13.0",
            }

            lc.deploy(deployment)

        ts.delete_devices.assert_not_called()


# ---------------------------------------------------------------------------
# T043: instance_type change
# ---------------------------------------------------------------------------


class TestUpdateInstanceType:
    """instance_type change → change set with InstanceType, no device deletion."""

    def test_instance_type_change_calls_stack_update(self, capsys: Any) -> None:
        """An instance_type change must call stack.update (change set path)."""
        existing_config = _make_existing_config(generation=1)
        clients = _make_clients(
            ssm_params={
                "/ember/default/config": existing_config,
                "/ember/default/server-token": "tok",
            }
        )
        ts = _make_tailscale()
        lc = _make_lifecycle(clients, ts)

        from ember_aws.deployment import Deployment

        deployment = Deployment(
            name="default", model="flash", instance_type="g5.2xlarge"
        )

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle_update.Stack") as mock_update_stack_cls,
            patch("ember_aws.lifecycle_update.wait_healthy") as mock_health,
        ):
            mock_stack = MagicMock()
            mock_stack.exists.return_value = True
            mock_stack.update.return_value = True  # change set applied
            mock_stack.update_has_replacement.return_value = False
            mock_stack.outputs.return_value = {"InstanceId": "i-0001"}
            mock_stack.pick_subnet.return_value = ("subnet-aaa", "vpc-bbb")
            mock_stack.resolve_image_id.return_value = "ami-0abc1234"
            mock_stack_cls.return_value = mock_stack
            mock_update_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }

            lc.deploy(deployment)

        mock_stack.update.assert_called_once()

    def test_change_set_includes_the_model_prefix(self, capsys: Any) -> None:
        """The stack params carry ModelPrefix, so the IAM policy follows the model."""
        existing_config = _make_existing_config(generation=1)
        clients = _make_clients(
            ssm_params={
                "/ember/default/config": existing_config,
                "/ember/default/server-token": "tok",
            }
        )
        ts = _make_tailscale()
        lc = _make_lifecycle(clients, ts)

        import ember.models as ember_models

        from ember_aws.deployment import Deployment

        deployment = Deployment(
            name="default", model="flash", instance_type="g5.2xlarge"
        )
        revision = ember_models.REGISTRY["flash"].revision or "latest"

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle_update.Stack") as mock_update_stack_cls,
            patch("ember_aws.lifecycle_update.wait_healthy") as mock_health,
        ):
            mock_stack = MagicMock()
            mock_stack.exists.return_value = True
            mock_stack.update.return_value = True
            mock_stack.update_has_replacement.return_value = False
            mock_stack.outputs.return_value = {"InstanceId": "i-0001"}
            mock_stack.pick_subnet.return_value = ("subnet-aaa", "vpc-bbb")
            mock_stack.resolve_image_id.return_value = "ami-0abc1234"
            mock_stack_cls.return_value = mock_stack
            mock_update_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }

            lc.deploy(deployment)

        params = mock_stack.update.call_args.args[0]
        assert params["ModelPrefix"] == f"models/flash/{revision}/"

    def test_instance_type_change_no_device_deletion(self, capsys: Any) -> None:
        """An instance_type change must NOT delete tailnet devices."""
        existing_config = _make_existing_config(generation=1)
        clients = _make_clients(
            ssm_params={
                "/ember/default/config": existing_config,
                "/ember/default/server-token": "tok",
            }
        )
        ts = _make_tailscale()
        lc = _make_lifecycle(clients, ts)

        from ember_aws.deployment import Deployment

        deployment = Deployment(
            name="default", model="flash", instance_type="g5.2xlarge"
        )

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle_update.Stack") as mock_update_stack_cls,
            patch("ember_aws.lifecycle_update.wait_healthy") as mock_health,
        ):
            mock_stack = MagicMock()
            mock_stack.exists.return_value = True
            mock_stack.update.return_value = True
            mock_stack.update_has_replacement.return_value = False
            mock_stack.outputs.return_value = {"InstanceId": "i-0001"}
            mock_stack.pick_subnet.return_value = ("subnet-aaa", "vpc-bbb")
            mock_stack.resolve_image_id.return_value = "ami-0abc1234"
            mock_stack_cls.return_value = mock_stack
            mock_update_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }

            lc.deploy(deployment)

        ts.delete_devices.assert_not_called()


# ---------------------------------------------------------------------------
# T043: no change at all
# ---------------------------------------------------------------------------


class TestUpdateNoChange:
    """No change at all → no put_parameter, no reboot, prints 'up to date: <url>'."""

    def test_no_change_prints_up_to_date(self, capsys: Any) -> None:
        """When nothing changed, prints 'up to date: <url>'."""
        existing_config = _make_existing_config(
            ember_version="0.12.0",
            model_s3_uri=_FLASH_S3_URI,
            max_request_length=24576,
            idle_minutes=0,
            generation=1,
        )
        clients = _make_clients(
            ssm_params={
                "/ember/default/config": existing_config,
                "/ember/default/server-token": "tok",
            }
        )
        ts = _make_tailscale()
        lc = _make_lifecycle(clients, ts)

        from ember_aws.deployment import Deployment

        # Same version as stored
        deployment = Deployment(name="default", model="flash", ember_version="0.12.0")

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle_update.Stack") as mock_update_stack_cls,
            patch("ember_aws.lifecycle_update.wait_healthy") as mock_health,
        ):
            mock_stack = MagicMock()
            mock_stack.exists.return_value = True
            mock_stack.update.return_value = False
            mock_stack.update_has_replacement.return_value = False
            mock_stack.outputs.return_value = {"InstanceId": "i-0001"}
            mock_stack.pick_subnet.return_value = ("subnet-aaa", "vpc-bbb")
            mock_stack.resolve_image_id.return_value = "ami-0abc1234"
            mock_stack_cls.return_value = mock_stack
            mock_update_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }

            lc.deploy(deployment)

        captured = capsys.readouterr()
        assert "up to date" in captured.out, (
            f"Expected 'up to date' in output, got: {captured.out!r}"
        )
        assert _TAILNET_URL in captured.out, (
            f"Expected URL {_TAILNET_URL!r} in output, got: {captured.out!r}"
        )

    def test_no_change_no_put_parameter(self, capsys: Any) -> None:
        """When nothing changed, no SSM put_parameter must be called."""
        existing_config = _make_existing_config(
            ember_version="0.12.0",
            model_s3_uri=_FLASH_S3_URI,
            max_request_length=24576,
            idle_minutes=0,
            generation=1,
        )
        clients = _make_clients(
            ssm_params={
                "/ember/default/config": existing_config,
                "/ember/default/server-token": "tok",
            }
        )
        ts = _make_tailscale()
        lc = _make_lifecycle(clients, ts)

        from ember_aws.deployment import Deployment

        deployment = Deployment(name="default", model="flash", ember_version="0.12.0")

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle_update.Stack") as mock_update_stack_cls,
            patch("ember_aws.lifecycle_update.wait_healthy") as mock_health,
        ):
            mock_stack = MagicMock()
            mock_stack.exists.return_value = True
            mock_stack.update.return_value = False
            mock_stack.update_has_replacement.return_value = False
            mock_stack.outputs.return_value = {"InstanceId": "i-0001"}
            mock_stack.pick_subnet.return_value = ("subnet-aaa", "vpc-bbb")
            mock_stack.resolve_image_id.return_value = "ami-0abc1234"
            mock_stack_cls.return_value = mock_stack
            mock_update_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }

            lc.deploy(deployment)

        clients.ssm.put_parameter.assert_not_called()

    def test_no_change_no_reboot(self, capsys: Any) -> None:
        """When nothing changed, reboot_instances must NOT be called."""
        existing_config = _make_existing_config(
            ember_version="0.12.0",
            model_s3_uri=_FLASH_S3_URI,
            max_request_length=24576,
            idle_minutes=0,
            generation=1,
        )
        clients = _make_clients(
            ssm_params={
                "/ember/default/config": existing_config,
                "/ember/default/server-token": "tok",
            }
        )
        ts = _make_tailscale()
        lc = _make_lifecycle(clients, ts)

        from ember_aws.deployment import Deployment

        deployment = Deployment(name="default", model="flash", ember_version="0.12.0")

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle_update.Stack") as mock_update_stack_cls,
            patch("ember_aws.lifecycle_update.wait_healthy") as mock_health,
        ):
            mock_stack = MagicMock()
            mock_stack.exists.return_value = True
            mock_stack.update.return_value = False
            mock_stack.outputs.return_value = {"InstanceId": "i-0001"}
            mock_stack.pick_subnet.return_value = ("subnet-aaa", "vpc-bbb")
            mock_stack.resolve_image_id.return_value = "ami-0abc1234"
            mock_stack_cls.return_value = mock_stack
            mock_update_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }

            lc.deploy(deployment)

        clients.ec2.reboot_instances.assert_not_called()


# ---------------------------------------------------------------------------
# T043: change set with Replacement=True
# ---------------------------------------------------------------------------


class TestUpdateReplacement:
    """Replacement=True: delete devices and mint a key BEFORE execute."""

    def test_replacement_deletes_devices_before_execute(self, capsys: Any) -> None:
        """With Replacement=True, delete_devices runs before execute_change_set."""
        existing_config = _make_existing_config(generation=1)
        clients = _make_clients(
            ssm_params={
                "/ember/default/config": existing_config,
                "/ember/default/server-token": "tok",
            }
        )
        ts = _make_tailscale()
        lc = _make_lifecycle(clients, ts)

        from ember_aws.deployment import Deployment

        deployment = Deployment(
            name="default", model="flash", instance_type="g5.2xlarge"
        )

        call_order: list[str] = []

        ts.delete_devices.side_effect = lambda *a, **kw: call_order.append(
            "delete_devices"
        )
        ts.mint_join_key.side_effect = lambda *a, **kw: (
            call_order.append("mint_join_key")
            or {"id": "key-abc", "key": "tskey-auth-xxx"}
        )

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle_update.Stack") as mock_update_stack_cls,
            patch("ember_aws.lifecycle_update.wait_healthy") as mock_health,
        ):
            mock_stack = MagicMock()
            mock_stack.exists.return_value = True
            # update returns True AND signals replacement
            mock_stack.update.return_value = True
            mock_stack.update_has_replacement.return_value = True
            mock_stack.outputs.return_value = {"InstanceId": "i-0001"}
            mock_stack.pick_subnet.return_value = ("subnet-aaa", "vpc-bbb")
            mock_stack.resolve_image_id.return_value = "ami-0abc1234"

            def _track_execute(*args: Any, **kwargs: Any) -> None:
                call_order.append("execute_change_set")

            mock_stack.execute_change_set.side_effect = _track_execute
            mock_stack_cls.return_value = mock_stack
            mock_update_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }

            lc.deploy(deployment)

        assert "delete_devices" in call_order, "delete_devices must be called"
        assert "mint_join_key" in call_order, "mint_join_key must be called"
        assert "execute_change_set" in call_order, "execute_change_set must be called"
        assert call_order.index("delete_devices") < call_order.index(
            "execute_change_set"
        ), "delete_devices must happen before execute_change_set"
        assert call_order.index("mint_join_key") < call_order.index(
            "execute_change_set"
        ), "mint_join_key must happen before execute_change_set"


# ---------------------------------------------------------------------------
# T043: replace()
# ---------------------------------------------------------------------------


class TestReplace:
    """replace(): new AMI, forced replacement, devices+key first, wait."""

    def test_replace_resolves_new_ami(self, capsys: Any) -> None:
        """replace() must call resolve_image_id to get a fresh DLAMI."""
        existing_config = _make_existing_config(generation=1)
        clients = _make_clients(
            ssm_params={
                "/ember/default/config": existing_config,
                "/ember/default/server-token": "tok",
            }
        )
        ts = _make_tailscale()
        lc = _make_lifecycle(clients, ts)

        from ember_aws.deployment import Deployment

        deployment = Deployment(name="default", model="flash")

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle_update.Stack") as mock_update_stack_cls,
            patch("ember_aws.lifecycle_update.wait_healthy") as mock_health,
        ):
            mock_stack = MagicMock()
            mock_stack.exists.return_value = True
            mock_stack.update.return_value = True
            mock_stack.update_has_replacement.return_value = True
            mock_stack.outputs.return_value = {"InstanceId": "i-0001"}
            mock_stack.pick_subnet.return_value = ("subnet-aaa", "vpc-bbb")
            mock_stack.resolve_image_id.return_value = "ami-new-1234"
            mock_stack_cls.return_value = mock_stack
            mock_update_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }

            lc.replace(deployment)

        mock_stack.resolve_image_id.assert_called()

    def test_replace_preserves_the_deployed_state(self, capsys: Any) -> None:
        """replace() keeps the deployed instance type, version, idle, and model."""
        existing_config = _make_existing_config(
            ember_version="0.11.0", idle_minutes=30, generation=3
        )
        clients = _make_clients(
            ssm_params={
                "/ember/default/config": existing_config,
                "/ember/default/server-token": "tok",
            },
            stack_params={"InstanceType": "g5.2xlarge", "Capacity": "spot"},
        )
        ts = _make_tailscale()
        lc = _make_lifecycle(clients, ts)

        from ember_aws.deployment import Deployment

        deployment = Deployment(name="default", model="flash")

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle_update.Stack") as mock_update_stack_cls,
            patch("ember_aws.lifecycle_update.wait_healthy") as mock_health,
        ):
            mock_stack = MagicMock()
            mock_stack.resolve_image_id.return_value = "ami-new-1234"
            mock_stack.prepare_change_set.return_value = "cs-1"
            mock_stack_cls.return_value = mock_stack
            mock_update_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.11.0",
            }

            lc.replace(deployment)

        written = json.loads(
            clients.ssm.get_parameter(Name="/ember/default/config")["Parameter"][
                "Value"
            ]
        )
        assert written["ember_version"] == "0.11.0"
        assert written["idle_minutes"] == 30
        assert written["model_s3_uri"] == _FLASH_S3_URI
        params = mock_stack.prepare_change_set.call_args.args[0]
        assert params["InstanceType"] == "g5.2xlarge"

    def test_replace_deletes_devices_before_update(self, capsys: Any) -> None:
        """replace() must delete tailnet devices before executing the change set."""
        existing_config = _make_existing_config(generation=1)
        clients = _make_clients(
            ssm_params={
                "/ember/default/config": existing_config,
                "/ember/default/server-token": "tok",
            }
        )
        ts = _make_tailscale()
        lc = _make_lifecycle(clients, ts)

        from ember_aws.deployment import Deployment

        deployment = Deployment(name="default", model="flash")

        call_order: list[str] = []
        ts.delete_devices.side_effect = lambda *a, **kw: call_order.append(
            "delete_devices"
        )
        ts.mint_join_key.side_effect = lambda *a, **kw: (
            call_order.append("mint_join_key")
            or {"id": "key-abc", "key": "tskey-auth-xxx"}
        )

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle_update.Stack") as mock_update_stack_cls,
            patch("ember_aws.lifecycle_update.wait_healthy") as mock_health,
        ):
            mock_stack = MagicMock()
            mock_stack.exists.return_value = True
            mock_stack.update.return_value = True
            mock_stack.update_has_replacement.return_value = True
            mock_stack.outputs.return_value = {"InstanceId": "i-0001"}
            mock_stack.pick_subnet.return_value = ("subnet-aaa", "vpc-bbb")
            mock_stack.resolve_image_id.return_value = "ami-new-1234"

            def _track_execute(*args: Any, **kwargs: Any) -> None:
                call_order.append("execute_change_set")

            mock_stack.execute_change_set.side_effect = _track_execute
            mock_stack_cls.return_value = mock_stack
            mock_update_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }

            lc.replace(deployment)

        assert "delete_devices" in call_order
        assert "mint_join_key" in call_order
        assert "execute_change_set" in call_order
        assert call_order.index("delete_devices") < call_order.index(
            "execute_change_set"
        )
        assert call_order.index("mint_join_key") < call_order.index(
            "execute_change_set"
        )

    def test_replace_waits_health(self, capsys: Any) -> None:
        """replace() must wait for health after the change set executes."""
        existing_config = _make_existing_config(generation=1)
        clients = _make_clients(
            ssm_params={
                "/ember/default/config": existing_config,
                "/ember/default/server-token": "tok",
            }
        )
        ts = _make_tailscale()
        lc = _make_lifecycle(clients, ts)

        from ember_aws.deployment import Deployment

        deployment = Deployment(name="default", model="flash")

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle_update.Stack") as mock_update_stack_cls,
            patch("ember_aws.lifecycle_update.wait_healthy") as mock_health,
        ):
            mock_stack = MagicMock()
            mock_stack.exists.return_value = True
            mock_stack.update.return_value = True
            mock_stack.update_has_replacement.return_value = True
            mock_stack.outputs.return_value = {"InstanceId": "i-0001"}
            mock_stack.pick_subnet.return_value = ("subnet-aaa", "vpc-bbb")
            mock_stack.resolve_image_id.return_value = "ami-new-1234"
            mock_stack_cls.return_value = mock_stack
            mock_update_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }

            lc.replace(deployment)

        mock_health.assert_called_once()
