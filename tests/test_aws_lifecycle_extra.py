"""Extra tests for lifecycle.py: replace, _resolve_bucket, _read_current_generation."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers (reuse pattern from test_aws_stack_lifecycle.py)
# ---------------------------------------------------------------------------


def _make_clients(
    *,
    ssm_params: dict[str, str] | None = None,
) -> Any:
    clients = MagicMock()
    _ssm_store: dict[str, str] = dict(ssm_params or {})

    from botocore.exceptions import ClientError

    def _get_parameter(**kwargs: Any) -> dict[str, Any]:
        name = kwargs.get("Name", "")
        if name in _ssm_store:
            return {"Parameter": {"Name": name, "Value": _ssm_store[name]}}
        raise ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "not found"}},
            "GetParameter",
        )

    def _put_parameter(**kwargs: Any) -> dict[str, Any]:
        _ssm_store[kwargs["Name"]] = kwargs["Value"]
        return {}

    clients.ssm.get_parameter.side_effect = _get_parameter
    clients.ssm.put_parameter.side_effect = _put_parameter

    clients.cfn.describe_stacks.return_value = {
        "Stacks": [
            {
                "StackName": "ember-default",
                "StackStatus": "CREATE_COMPLETE",
                "Outputs": [
                    {"OutputKey": "InstanceId", "OutputValue": "i-0001"},
                    {"OutputKey": "RoleArn", "OutputValue": "arn:aws:iam::123:role/r"},
                ],
            }
        ]
    }
    clients.cfn.create_stack.return_value = {}
    clients.cfn.get_waiter.return_value = MagicMock()
    clients.cfn.describe_stack_events.return_value = {"StackEvents": []}

    clients.ec2.describe_vpcs.return_value = {
        "Vpcs": [{"VpcId": "vpc-default", "IsDefault": True}]
    }
    clients.ec2.describe_instance_type_offerings.return_value = {
        "InstanceTypeOfferings": [
            {
                "InstanceType": "g6e.xlarge",
                "Location": "us-east-1a",
                "LocationType": "availability-zone",
            }
        ]
    }
    clients.ec2.describe_subnets.return_value = {
        "Subnets": [
            {
                "SubnetId": "subnet-aaa",
                "VpcId": "vpc-default",
                "AvailabilityZone": "us-east-1a",
            }
        ]
    }
    return clients


def _make_tailscale() -> Any:
    ts = MagicMock()
    ts.tailnet_dns.return_value = {"magic_dns": True, "suffix": "example.ts.net"}
    ts.mint_join_key.return_value = {"id": "key-abc", "key": "tskey-auth-xxx"}
    ts.devices.return_value = []
    ts.delete_devices.return_value = None
    return ts


def _make_model_cache(*, cache_status: str = "complete") -> Any:
    mc = MagicMock()
    mc.status.return_value = cache_status
    mc.add.return_value = None
    mc._stack_bucket.return_value = "ember-model-cache-123456789-us-east-1"
    mc.ensure_bucket.return_value = "ember-model-cache-123456789-us-east-1"
    return mc


def _make_preflight(*, ok: bool = True) -> Any:
    pf = MagicMock()
    pf.run.return_value = []
    return pf


def _make_lifecycle(
    clients: Any,
    ts: Any,
    mc: Any,
    pf: Any,
) -> Any:
    from ember_aws.lifecycle import Lifecycle

    return Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)


# ---------------------------------------------------------------------------
# replace()
# ---------------------------------------------------------------------------


class TestLifecycleReplace:
    """Lifecycle.replace() delegates to LifecycleUpdate.replace."""

    def test_replace_calls_lifecycle_update_replace(self) -> None:
        """replace() delegates to LifecycleUpdate.replace."""
        from ember_aws.deployment import Deployment

        clients = _make_clients()
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()
        lc = _make_lifecycle(clients, ts, mc, pf)

        deployment = Deployment(name="default", model="flash")

        with patch("ember_aws.lifecycle.LifecycleUpdate") as mock_updater_cls:
            mock_updater = MagicMock()
            mock_updater_cls.return_value = mock_updater
            lc.replace(deployment)

        mock_updater.replace.assert_called_once_with(deployment, mc)

    def test_replace_passes_model_cache_to_updater(self) -> None:
        """replace() passes the model_cache to LifecycleUpdate.replace."""
        from ember_aws.deployment import Deployment

        clients = _make_clients()
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()
        lc = _make_lifecycle(clients, ts, mc, pf)

        deployment = Deployment(name="default", model="flash")

        captured_mc: list[Any] = []

        with patch("ember_aws.lifecycle.LifecycleUpdate") as mock_updater_cls:
            mock_updater = MagicMock()

            def _capture_replace(dep: Any, model_cache: Any) -> None:
                captured_mc.append(model_cache)

            mock_updater.replace.side_effect = _capture_replace
            mock_updater_cls.return_value = mock_updater
            lc.replace(deployment)

        assert captured_mc[0] is mc


# ---------------------------------------------------------------------------
# _resolve_bucket()
# ---------------------------------------------------------------------------


class TestLifecycleResolveBucket:
    """Lifecycle._resolve_bucket() returns the S3 bucket name."""

    def test_resolve_bucket_uses_stack_bucket_when_available(self) -> None:
        """_resolve_bucket() returns the bucket from _stack_bucket()."""
        from ember_aws.lifecycle import Lifecycle
        from ember_aws.names import DeploymentName

        clients = _make_clients()
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        names = DeploymentName(name="default")
        bucket = lc._resolve_bucket(names)
        assert bucket == "ember-model-cache-123456789-us-east-1"

    def test_resolve_bucket_falls_back_to_ensure_bucket(self) -> None:
        """_resolve_bucket() falls back to ensure_bucket() when _stack_bucket
        returns None."""
        from ember_aws.lifecycle import Lifecycle
        from ember_aws.names import DeploymentName

        clients = _make_clients()
        ts = _make_tailscale()
        mc = MagicMock()
        mc._stack_bucket.return_value = None
        mc.ensure_bucket.return_value = "fallback-bucket"
        pf = _make_preflight()
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        names = DeploymentName(name="default")
        bucket = lc._resolve_bucket(names)
        assert bucket == "fallback-bucket"

    def test_resolve_bucket_returns_placeholder_when_both_fail(self) -> None:
        """_resolve_bucket() returns a placeholder when both methods fail."""
        from ember_aws.lifecycle import Lifecycle
        from ember_aws.names import DeploymentName

        clients = _make_clients()
        ts = _make_tailscale()
        mc = MagicMock()
        mc._stack_bucket.return_value = None
        mc.ensure_bucket.return_value = None
        pf = _make_preflight()
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        names = DeploymentName(name="default")
        bucket = lc._resolve_bucket(names)
        assert bucket == "ember-model-cache-bucket"

    def test_resolve_bucket_when_no_stack_bucket_attr(self) -> None:
        """_resolve_bucket() uses ensure_bucket when _stack_bucket attr is absent."""
        from ember_aws.lifecycle import Lifecycle
        from ember_aws.names import DeploymentName

        clients = _make_clients()
        ts = _make_tailscale()
        # mc without _stack_bucket attribute
        mc = MagicMock(spec=["ensure_bucket", "status", "add"])
        mc.ensure_bucket.return_value = "ensure-bucket-name"
        pf = _make_preflight()
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        names = DeploymentName(name="default")
        bucket = lc._resolve_bucket(names)
        assert bucket == "ensure-bucket-name"


# ---------------------------------------------------------------------------
# _read_current_generation()
# ---------------------------------------------------------------------------


class TestLifecycleReadCurrentGeneration:
    """Lifecycle._read_current_generation() reads the config generation from SSM."""

    def test_returns_zero_when_param_not_found(self) -> None:
        """_read_current_generation() returns 0 when the SSM parameter does not
        exist."""
        from ember_aws.lifecycle import Lifecycle
        from ember_aws.names import DeploymentName

        clients = _make_clients(ssm_params={})
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        names = DeploymentName(name="default")
        gen = lc._read_current_generation(names)
        assert gen == 0

    def test_returns_generation_from_existing_config(self) -> None:
        """_read_current_generation() returns the generation from the SSM config."""
        import json

        from ember_aws.lifecycle import Lifecycle
        from ember_aws.names import DeploymentName

        config_data = {
            "ember_version": "0.12.0",
            "model_s3_uri": "s3://bucket/models/flash/rev",
            "generation": 5,
        }
        names_obj = DeploymentName(name="default")
        clients = _make_clients(
            ssm_params={names_obj.config_param: json.dumps(config_data)}
        )
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        gen = lc._read_current_generation(names_obj)
        assert gen == 5

    def test_returns_zero_when_config_has_no_generation(self) -> None:
        """_read_current_generation() returns 0 when generation key is absent."""
        import json

        from ember_aws.lifecycle import Lifecycle
        from ember_aws.names import DeploymentName

        config_data = {"ember_version": "0.12.0"}
        names_obj = DeploymentName(name="default")
        clients = _make_clients(
            ssm_params={names_obj.config_param: json.dumps(config_data)}
        )
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        gen = lc._read_current_generation(names_obj)
        assert gen == 0

    def test_returns_zero_when_config_is_invalid_json(self) -> None:
        """_read_current_generation() returns 0 when the config is not valid JSON."""
        from ember_aws.lifecycle import Lifecycle
        from ember_aws.names import DeploymentName

        names_obj = DeploymentName(name="default")
        clients = _make_clients(
            ssm_params={names_obj.config_param: "not-json"}
        )
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        gen = lc._read_current_generation(names_obj)
        assert gen == 0

    def test_reraises_non_parameter_not_found_errors(self) -> None:
        """_read_current_generation() re-raises non-ParameterNotFound ClientErrors."""
        import pytest
        from botocore.exceptions import ClientError

        from ember_aws.lifecycle import Lifecycle
        from ember_aws.names import DeploymentName

        clients = _make_clients()
        clients.ssm.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "GetParameter",
        )
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        names_obj = DeploymentName(name="default")
        with pytest.raises(ClientError):
            lc._read_current_generation(names_obj)
