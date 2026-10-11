"""Tests for Stack lifecycle and Lifecycle.deploy() (T020)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------

_TAILNET_SUFFIX = "example.ts.net"
_TAILNET_URL = "https://ember-default.example.ts.net"
_DLAMI_SSM_PATH = (
    "/aws/service/deeplearning/ami/x86_64"
    "/base-oss-nvidia-driver-gpu-ubuntu-24.04/latest/ami-id"
)


def _make_clients(
    *,
    stack_exists: bool = False,
    stack_status: str = "CREATE_COMPLETE",
    stack_events: list[dict[str, Any]] | None = None,
    stack_outputs: list[dict[str, Any]] | None = None,
    ssm_params: dict[str, str] | None = None,
    ami_id: str = "ami-0abc1234",
    subnet_id: str = "subnet-aaa",
    vpc_id: str = "vpc-bbb",
) -> Any:
    """Build a fake AwsClients-shaped object."""
    clients = MagicMock()

    # CFN
    if stack_exists:
        clients.cfn.describe_stacks.return_value = {
            "Stacks": [
                {
                    "StackName": "ember-default",
                    "StackStatus": stack_status,
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

    if stack_events:
        clients.cfn.describe_stack_events.return_value = {"StackEvents": stack_events}
    else:
        clients.cfn.describe_stack_events.return_value = {"StackEvents": []}

    # SSM
    _ssm_store: dict[str, str] = dict(ssm_params or {})

    def _get_parameter(**kwargs: Any) -> dict[str, Any]:
        name = kwargs.get("Name", "")
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

    # EC2 — SSM AMI lookup
    clients.ssm = clients.ssm  # already set above
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

    def _ssm_get_param(**kwargs: Any) -> dict[str, Any]:
        name = kwargs.get("Name", "")
        if name == _DLAMI_SSM_PATH:
            return {"Parameter": {"Name": name, "Value": ami_id}}
        return _get_parameter(**kwargs)

    clients.ssm.get_parameter.side_effect = _ssm_get_param

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


def _make_mock_stack() -> Any:
    """Create a fully configured mock Stack instance."""
    mock_stack = MagicMock()
    mock_stack.exists.return_value = False
    mock_stack.pick_subnet.return_value = ("subnet-aaa", "vpc-bbb")
    mock_stack.resolve_image_id.return_value = "ami-0abc1234"
    mock_stack.outputs.return_value = {
        "InstanceId": "i-0001",
        "RoleArn": "arn:aws:iam::123:role/r",
    }
    mock_stack.wait.return_value = None
    mock_stack.first_failure_reason.return_value = None
    return mock_stack


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


# ---------------------------------------------------------------------------
# T020: deploy order
# ---------------------------------------------------------------------------


class TestDeployOrder:
    """Verify the exact deploy sequence from T020."""

    def test_deploy_calls_preflight_first(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        """Preflight must be the first call in deploy."""
        from ember_aws.deployment import Deployment
        from ember_aws.lifecycle import Lifecycle
        from ember_aws.names import DeploymentName

        call_order: list[str] = []

        clients = _make_clients()
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = MagicMock()
        pf.run.side_effect = lambda d: call_order.append("preflight") or []

        mc.status.side_effect = lambda *a, **kw: (
            call_order.append("cache_status") or "complete"
        )

        deployment = Deployment(name="default", model="flash")
        _ = DeploymentName(name="default")  # validates the name

        lc = Lifecycle(
            clients=clients,
            tailscale=ts,
            model_cache=mc,
            preflight=pf,
        )

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle.wait_healthy") as mock_health,
        ):
            mock_stack = MagicMock()
            mock_stack.exists.return_value = False
            mock_stack.pick_subnet.return_value = ("subnet-aaa", "vpc-bbb")
            mock_stack.resolve_image_id.return_value = "ami-0abc1234"
            mock_stack.outputs.return_value = {
                "InstanceId": "i-0001",
                "RoleArn": "arn:aws:iam::123:role/r",
            }
            mock_stack.wait.return_value = None
            mock_stack.first_failure_reason.return_value = None
            mock_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }

            lc.deploy(deployment)

        assert call_order[0] == "preflight"
        assert call_order[1] == "cache_status"

    def test_deploy_adds_cache_when_absent(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        """If cache status is absent, ModelCache.add must be called."""
        from ember_aws.deployment import Deployment
        from ember_aws.lifecycle import Lifecycle

        clients = _make_clients()
        ts = _make_tailscale()
        mc = _make_model_cache(cache_status="absent")
        pf = _make_preflight()

        deployment = Deployment(name="default", model="flash")
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle.wait_healthy") as mock_health,
        ):
            mock_stack_cls.return_value = _make_mock_stack()
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.deploy(deployment)

        mc.add.assert_called_once()

    def test_deploy_adds_cache_when_partial(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        """A partial cache is resumed (add is called)."""
        from ember_aws.deployment import Deployment
        from ember_aws.lifecycle import Lifecycle

        clients = _make_clients()
        ts = _make_tailscale()
        mc = _make_model_cache(cache_status="partial")
        pf = _make_preflight()

        deployment = Deployment(name="default", model="flash")
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle.wait_healthy") as mock_health,
        ):
            mock_stack_cls.return_value = _make_mock_stack()
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.deploy(deployment)

        mc.add.assert_called_once()

    def test_deploy_skips_add_when_complete(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        """When cache is complete, ModelCache.add must NOT be called."""
        from ember_aws.deployment import Deployment
        from ember_aws.lifecycle import Lifecycle

        clients = _make_clients()
        ts = _make_tailscale()
        mc = _make_model_cache(cache_status="complete")
        pf = _make_preflight()

        deployment = Deployment(name="default", model="flash")
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle.wait_healthy") as mock_health,
        ):
            mock_stack_cls.return_value = _make_mock_stack()
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.deploy(deployment)

        mc.add.assert_not_called()

    def test_deploy_puts_config_param(self, tmp_path: Any, monkeypatch: Any) -> None:
        """SSM put_parameter for config must be called before create_stack."""
        from ember_aws.deployment import Deployment
        from ember_aws.lifecycle import Lifecycle

        call_order: list[str] = []
        clients = _make_clients()
        orig_put = clients.ssm.put_parameter.side_effect

        def _track_put(**kwargs: Any) -> Any:
            call_order.append(f"ssm_put:{kwargs['Name']}")
            if orig_put:
                return orig_put(**kwargs)
            return {}

        clients.ssm.put_parameter.side_effect = _track_put

        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()

        deployment = Deployment(name="default", model="flash")
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle.wait_healthy") as mock_health,
        ):
            mock_stack = _make_mock_stack()

            def _track_create(**kwargs: Any) -> Any:
                call_order.append("create_stack")
                return {}

            mock_stack.create.side_effect = _track_create
            mock_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.deploy(deployment)

        config_put_idx = next(
            (
                i
                for i, c in enumerate(call_order)
                if "ssm_put:/ember/default/config" in c
            ),
            None,
        )
        create_idx = next(
            (i for i, c in enumerate(call_order) if c == "create_stack"),
            None,
        )
        assert config_put_idx is not None, "config param was never put"
        assert create_idx is not None, "create_stack was never called"
        assert config_put_idx < create_idx, "config must be put before create_stack"

    def test_deploy_token_only_if_absent(self, tmp_path: Any, monkeypatch: Any) -> None:
        """Token is written only when the SSM parameter does not exist yet."""
        from ember_aws.deployment import Deployment
        from ember_aws.lifecycle import Lifecycle

        clients_no_token = _make_clients()
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()

        deployment = Deployment(name="default", model="flash")
        lc = Lifecycle(
            clients=clients_no_token, tailscale=ts, model_cache=mc, preflight=pf
        )

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle.wait_healthy") as mock_health,
        ):
            mock_stack_cls.return_value = _make_mock_stack()
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.deploy(deployment)

        token_calls = [
            c
            for c in clients_no_token.ssm.put_parameter.call_args_list
            if c.kwargs.get("Name") == "/ember/default/server-token"
            or (c.args and c.args[0] == "/ember/default/server-token")
        ]
        assert len(token_calls) >= 1, "token param should be written when absent"

    def test_deploy_token_not_overwritten_when_present(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        """Token is NOT written when the SSM parameter already exists."""
        from ember_aws.deployment import Deployment
        from ember_aws.lifecycle import Lifecycle

        existing_token = "existing-token-value"
        clients_with_token = _make_clients(
            ssm_params={"/ember/default/server-token": existing_token}
        )
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()

        deployment = Deployment(name="default", model="flash")
        lc = Lifecycle(
            clients=clients_with_token, tailscale=ts, model_cache=mc, preflight=pf
        )

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle.wait_healthy") as mock_health,
        ):
            mock_stack_cls.return_value = _make_mock_stack()
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.deploy(deployment)

        token_put_calls = [
            c
            for c in clients_with_token.ssm.put_parameter.call_args_list
            if "/ember/default/server-token" in str(c)
        ]
        assert len(token_put_calls) == 0, (
            "token must not be overwritten when already present"
        )

    def test_deploy_deletes_tailnet_devices_before_join_key(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        """delete_devices must be called before mint_join_key."""
        from ember_aws.deployment import Deployment
        from ember_aws.lifecycle import Lifecycle

        call_order: list[str] = []
        clients = _make_clients()
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()

        ts.delete_devices.side_effect = lambda *a, **kw: call_order.append(
            "delete_devices"
        )
        ts.mint_join_key.side_effect = lambda *a, **kw: (
            call_order.append("mint_join_key")
            or {"id": "key-abc", "key": "tskey-auth-xxx"}
        )

        deployment = Deployment(name="default", model="flash")
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle.wait_healthy") as mock_health,
        ):
            mock_stack_cls.return_value = _make_mock_stack()
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.deploy(deployment)

        assert "delete_devices" in call_order
        assert "mint_join_key" in call_order
        assert call_order.index("delete_devices") < call_order.index("mint_join_key")

    def test_deploy_join_key_put_before_create_stack(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        """Join key SSM put must happen before create_stack."""
        from ember_aws.deployment import Deployment
        from ember_aws.lifecycle import Lifecycle

        call_order: list[str] = []
        clients = _make_clients()
        orig_put = clients.ssm.put_parameter.side_effect

        def _track_put(**kwargs: Any) -> Any:
            call_order.append(f"ssm_put:{kwargs['Name']}")
            if orig_put:
                return orig_put(**kwargs)
            return {}

        clients.ssm.put_parameter.side_effect = _track_put

        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()

        deployment = Deployment(name="default", model="flash")
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle.wait_healthy") as mock_health,
        ):
            mock_stack = _make_mock_stack()

            def _track_create(**kwargs: Any) -> Any:
                call_order.append("create_stack")
                return {}

            mock_stack.create.side_effect = _track_create
            mock_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.deploy(deployment)

        join_key_idx = next(
            (i for i, c in enumerate(call_order) if "tailscale-join-key" in c),
            None,
        )
        create_idx = next(
            (i for i, c in enumerate(call_order) if c == "create_stack"),
            None,
        )
        assert join_key_idx is not None, "join key was never put"
        assert create_idx is not None, "create_stack was never called"
        assert join_key_idx < create_idx, "join key must be put before create_stack"

    def test_deploy_success_output_matches_contract(
        self, tmp_path: Any, monkeypatch: Any, capsys: Any
    ) -> None:
        """Success output must match the contracts/cli.md block."""
        from ember_aws.deployment import Deployment
        from ember_aws.lifecycle import Lifecycle

        clients = _make_clients()
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()

        deployment = Deployment(name="default", model="flash", ember_version="0.12.0")
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle.wait_healthy") as mock_health,
        ):
            mock_stack_cls.return_value = _make_mock_stack()
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.deploy(deployment)

        captured = capsys.readouterr()
        out = captured.out
        assert 'ember deployment "default" is healthy' in out
        assert "g6e.xlarge" in out
        assert "cuda" in out
        assert "0.12.0" in out
        assert "https://ember-default.example.ts.net" in out
        assert "EMBER_AUTH_TOKEN" in out
        assert "ember init --opencode" in out

    def test_deploy_success_output_never_contains_token(
        self, tmp_path: Any, monkeypatch: Any, capsys: Any
    ) -> None:
        """The server token must never appear in deploy output."""
        from ember_aws.deployment import Deployment
        from ember_aws.lifecycle import Lifecycle

        secret_token = "super-secret-token-xyz"
        clients = _make_clients(
            ssm_params={"/ember/default/server-token": secret_token}
        )
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()

        deployment = Deployment(name="default", model="flash")
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle.wait_healthy") as mock_health,
        ):
            mock_stack_cls.return_value = _make_mock_stack()
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.deploy(deployment)

        captured = capsys.readouterr()
        assert secret_token not in captured.out
        assert secret_token not in captured.err

    def test_deploy_stack_failure_exits_2(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        """A stack CREATE_FAILED event must cause SystemExit(2)."""
        from ember_aws.deployment import Deployment
        from ember_aws.lifecycle import Lifecycle, StackDeployError

        clients = _make_clients()
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()

        deployment = Deployment(name="default", model="flash")
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle.wait_healthy"),
        ):
            mock_stack = _make_mock_stack()
            mock_stack.wait.side_effect = StackDeployError(
                "Resource failed: out of capacity"
            )
            mock_stack.first_failure_reason.return_value = "out of capacity"
            mock_stack_cls.return_value = mock_stack

            with pytest.raises(SystemExit) as exc_info:
                lc.deploy(deployment)

        assert exc_info.value.code == 2

    def test_deploy_tight_sizing_warns(
        self, tmp_path: Any, monkeypatch: Any, capsys: Any
    ) -> None:
        """A tight sizing entry must print a warning but not exit."""
        from ember_aws.deployment import Deployment
        from ember_aws.lifecycle import Lifecycle

        clients = _make_clients()
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()

        # g5.2xlarge is tight for flash
        deployment = Deployment(
            name="default", model="flash", instance_type="g5.2xlarge"
        )
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle.wait_healthy") as mock_health,
        ):
            mock_stack_cls.return_value = _make_mock_stack()
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.deploy(deployment)

        captured = capsys.readouterr()
        assert "tight" in captured.out.lower() or "tight" in captured.err.lower()

    def test_deploy_unsupported_sizing_exits_1(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        """An unsupported instance type must cause SystemExit(1)."""
        from ember_aws.deployment import Deployment
        from ember_aws.lifecycle import Lifecycle

        clients = _make_clients()
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()

        # g4dn.xlarge is unsupported for flash
        deployment = Deployment(
            name="default", model="flash", instance_type="g4dn.xlarge"
        )
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        with pytest.raises(SystemExit) as exc_info:
            lc.deploy(deployment)

        assert exc_info.value.code == 1

    def test_deploy_health_poll_uses_cuda_check(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        """wait_healthy must be called with the tailnet URL and token."""
        from ember_aws.deployment import Deployment
        from ember_aws.lifecycle import Lifecycle

        clients = _make_clients()
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()

        deployment = Deployment(name="default", model="flash")
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle.wait_healthy") as mock_health,
        ):
            mock_stack_cls.return_value = _make_mock_stack()
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.deploy(deployment)

        mock_health.assert_called_once()
        call_kwargs = mock_health.call_args
        url_arg = (
            call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("url")
        )
        assert url_arg == "https://ember-default.example.ts.net"


# ---------------------------------------------------------------------------
# T020: token() method
# ---------------------------------------------------------------------------


class TestLifecycleToken:
    """Verify Lifecycle.token() prints only the token."""

    def test_token_prints_only_token(self, capsys: Any) -> None:
        """token() must print exactly the token value (no extra text)."""
        from ember_aws.deployment import Deployment
        from ember_aws.lifecycle import Lifecycle

        secret = "my-secret-token-abc"
        clients = _make_clients(ssm_params={"/ember/default/server-token": secret})
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()

        deployment = Deployment(name="default", model="flash")
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        lc.token(deployment)

        captured = capsys.readouterr()
        assert captured.out.strip() == secret

    def test_token_not_in_stderr(self, capsys: Any) -> None:
        """token() must not log the token to stderr."""
        from ember_aws.deployment import Deployment
        from ember_aws.lifecycle import Lifecycle

        secret = "my-secret-token-abc"
        clients = _make_clients(ssm_params={"/ember/default/server-token": secret})
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()

        deployment = Deployment(name="default", model="flash")
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        lc.token(deployment)

        captured = capsys.readouterr()
        assert secret not in captured.err


# ---------------------------------------------------------------------------
# Stack unit tests (T027)
# ---------------------------------------------------------------------------


class TestStack:
    """Unit tests for Stack."""

    def test_stack_exists_false_when_absent(self) -> None:
        """Stack.exists() returns False when the stack does not exist."""
        from botocore.exceptions import ClientError

        from ember_aws.names import DeploymentName
        from ember_aws.stack import Stack

        clients = MagicMock()
        clients.cfn.describe_stacks.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "does not exist"}},
            "DescribeStacks",
        )

        names = DeploymentName(name="default")
        stack = Stack(clients=clients, names=names)
        assert stack.exists() is False

    def test_stack_exists_true_when_present(self) -> None:
        """Stack.exists() returns True when the stack exists."""
        from ember_aws.names import DeploymentName
        from ember_aws.stack import Stack

        clients = MagicMock()
        clients.cfn.describe_stacks.return_value = {
            "Stacks": [{"StackName": "ember-default", "StackStatus": "CREATE_COMPLETE"}]
        }

        names = DeploymentName(name="default")
        stack = Stack(clients=clients, names=names)
        assert stack.exists() is True

    def test_stack_outputs_returns_dict(self) -> None:
        """Stack.outputs() returns a dict of OutputKey → OutputValue."""
        from ember_aws.names import DeploymentName
        from ember_aws.stack import Stack

        clients = MagicMock()
        clients.cfn.describe_stacks.return_value = {
            "Stacks": [
                {
                    "StackName": "ember-default",
                    "StackStatus": "CREATE_COMPLETE",
                    "Outputs": [
                        {"OutputKey": "InstanceId", "OutputValue": "i-0001"},
                        {
                            "OutputKey": "RoleArn",
                            "OutputValue": "arn:aws:iam::123:role/r",
                        },
                    ],
                }
            ]
        }

        names = DeploymentName(name="default")
        stack = Stack(clients=clients, names=names)
        outputs = stack.outputs()
        assert outputs["InstanceId"] == "i-0001"
        assert outputs["RoleArn"] == "arn:aws:iam::123:role/r"

    def test_stack_first_failure_reason_returns_root_cause(self) -> None:
        """first_failure_reason() returns the earliest failure's reason.

        describe_stack_events returns events newest-first, so the cascade
        victim ("Resource creation cancelled") arrives before the root cause.
        """
        from ember_aws.names import DeploymentName
        from ember_aws.stack import Stack

        clients = MagicMock()
        clients.cfn.describe_stack_events.return_value = {
            "StackEvents": [
                {
                    "ResourceStatus": "CREATE_FAILED",
                    "ResourceStatusReason": "Resource creation cancelled",
                    "LogicalResourceId": "InstanceRole",
                },
                {
                    "ResourceStatus": "CREATE_FAILED",
                    "ResourceStatusReason": "GroupDescription is invalid",
                    "LogicalResourceId": "SecurityGroup",
                },
            ]
        }

        names = DeploymentName(name="default")
        stack = Stack(clients=clients, names=names)
        reason = stack.first_failure_reason()
        assert reason == "GroupDescription is invalid"

    def test_stack_first_failure_reason_none_when_no_failures(self) -> None:
        """first_failure_reason() returns None when no CREATE_FAILED events."""
        from ember_aws.names import DeploymentName
        from ember_aws.stack import Stack

        clients = MagicMock()
        clients.cfn.describe_stack_events.return_value = {"StackEvents": []}

        names = DeploymentName(name="default")
        stack = Stack(clients=clients, names=names)
        assert stack.first_failure_reason() is None

    def test_resolve_image_id_reads_ssm(self) -> None:
        """resolve_image_id() reads the DLAMI SSM parameter."""
        from ember_aws.names import DeploymentName
        from ember_aws.stack import Stack

        clients = MagicMock()
        clients.ssm.get_parameter.return_value = {
            "Parameter": {"Value": "ami-0abc1234"}
        }

        names = DeploymentName(name="default")
        stack = Stack(clients=clients, names=names)
        ami = stack.resolve_image_id("us-east-1")
        assert ami == "ami-0abc1234"

    def test_pick_subnet_returns_first_default_vpc_subnet(self) -> None:
        """pick_subnet() returns the first subnet in the default VPC."""
        from ember_aws.names import DeploymentName
        from ember_aws.stack import Stack

        clients = MagicMock()
        clients.ec2.describe_vpcs.return_value = {
            "Vpcs": [{"VpcId": "vpc-default", "IsDefault": True}]
        }
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
                {
                    "SubnetId": "subnet-aaa",
                    "VpcId": "vpc-default",
                    "AvailabilityZone": "us-east-1a",
                },
            ]
        }

        names = DeploymentName(name="default")
        stack = Stack(clients=clients, names=names)
        subnet_id, vpc_id = stack.pick_subnet("g6e.xlarge")
        assert subnet_id == "subnet-aaa"
        assert vpc_id == "vpc-default"


# ---------------------------------------------------------------------------
# Health tests (T028)
# ---------------------------------------------------------------------------


class TestWaitHealthy:
    """Unit tests for wait_healthy()."""

    def test_returns_body_when_cuda(self) -> None:
        """wait_healthy returns the parsed body when engine.device == cuda."""
        import httpx

        from ember_aws.health import wait_healthy

        response_body = json.dumps(
            {"status": "ok", "engine": {"device": "cuda"}, "version": "0.12.0"}
        )

        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=response_body)

        transport = httpx.MockTransport(_handler)
        result = wait_healthy(
            url="https://ember-default.example.ts.net",
            token="tok",
            timeout_s=10,
            transport=transport,
        )
        assert result["engine"]["device"] == "cuda"

    def test_treats_503_as_loading(self, capsys: Any) -> None:
        """wait_healthy treats 503 as loading and keeps polling."""
        import httpx

        from ember_aws.health import wait_healthy

        call_count = 0

        def _handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(
                    503, json={"status": "loading", "engine": {"device": "cpu"}}
                )
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "engine": {"device": "cuda"},
                    "version": "0.12.0",
                },
            )

        transport = httpx.MockTransport(_handler)
        result = wait_healthy(
            url="https://ember-default.example.ts.net",
            token="tok",
            timeout_s=60,
            transport=transport,
            poll_interval_s=0,
        )
        assert result["engine"]["device"] == "cuda"
        assert call_count == 3

    def test_raises_health_timeout_on_timeout(self) -> None:
        """wait_healthy raises HealthTimeout when the deadline is exceeded."""
        import httpx

        from ember_aws.health import HealthTimeout, wait_healthy

        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                503, json={"status": "loading", "engine": {"device": "cpu"}}
            )

        transport = httpx.MockTransport(_handler)
        with pytest.raises(HealthTimeout):
            wait_healthy(
                url="https://ember-default.example.ts.net",
                token="tok",
                timeout_s=0,
                transport=transport,
                poll_interval_s=0,
            )

    def test_timeout_from_env(self, monkeypatch: Any) -> None:
        """EMBER_AWS_HEALTH_TIMEOUT env var sets the timeout."""
        import httpx

        from ember_aws.health import HealthTimeout, wait_healthy

        monkeypatch.setenv("EMBER_AWS_HEALTH_TIMEOUT", "0")

        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                503, json={"status": "loading", "engine": {"device": "cpu"}}
            )

        transport = httpx.MockTransport(_handler)
        with pytest.raises(HealthTimeout):
            wait_healthy(
                url="https://ember-default.example.ts.net",
                token="tok",
                transport=transport,
                poll_interval_s=0,
            )

    def test_requires_cuda_device(self) -> None:
        """wait_healthy raises HealthTimeout if engine.device is never cuda."""
        import httpx

        from ember_aws.health import HealthTimeout, wait_healthy

        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"status": "ok", "engine": {"device": "cpu"}, "version": "0.12.0"},
            )

        transport = httpx.MockTransport(_handler)
        with pytest.raises(HealthTimeout):
            wait_healthy(
                url="https://ember-default.example.ts.net",
                token="tok",
                timeout_s=0,
                transport=transport,
                poll_interval_s=0,
            )


# ---------------------------------------------------------------------------
# T048: spot capacity in deploy and spot→on-demand replacement
# ---------------------------------------------------------------------------


class TestDeploySpotCapacity:
    """T048: spot passes Capacity=spot; spot to on-demand replaces."""

    def test_deploy_spot_passes_capacity_spot(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        """deploy with capacity=spot must pass Capacity=spot to create_stack."""
        from ember_aws.capacity import Capacity
        from ember_aws.deployment import Deployment
        from ember_aws.lifecycle import Lifecycle

        clients = _make_clients()
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()

        deployment = Deployment(name="default", model="flash", capacity=Capacity.SPOT)
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        captured_params: dict[str, str] = {}

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle.wait_healthy") as mock_health,
        ):
            mock_stack = _make_mock_stack()

            def _capture_create(**kwargs: Any) -> Any:
                captured_params.update(kwargs.get("params", {}))
                return {}

            mock_stack.create.side_effect = _capture_create
            mock_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.deploy(deployment)

        assert captured_params.get("Capacity") == "spot", (
            "deploy with capacity=spot must pass Capacity=spot to create_stack"
        )

    def test_deploy_on_demand_passes_capacity_on_demand(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        """deploy with on-demand passes Capacity=on-demand to create_stack."""
        from ember_aws.capacity import Capacity
        from ember_aws.deployment import Deployment
        from ember_aws.lifecycle import Lifecycle

        clients = _make_clients()
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()

        deployment = Deployment(
            name="default", model="flash", capacity=Capacity.ON_DEMAND
        )
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        captured_params: dict[str, str] = {}

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle.wait_healthy") as mock_health,
        ):
            mock_stack = _make_mock_stack()

            def _capture_create(**kwargs: Any) -> Any:
                captured_params.update(kwargs.get("params", {}))
                return {}

            mock_stack.create.side_effect = _capture_create
            mock_stack_cls.return_value = mock_stack
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.deploy(deployment)

        assert captured_params.get("Capacity") == "on-demand", (
            "deploy with capacity=on-demand must pass Capacity=on-demand"
        )

    def test_spot_to_on_demand_is_replacement(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        """Spot to on-demand is a replacement (devices deleted first)."""
        from ember_aws.capacity import Capacity
        from ember_aws.deployment import Deployment
        from ember_aws.lifecycle import Lifecycle

        clients = _make_clients(
            stack_exists=True,
            ssm_params={"/ember/default/server-token": "tok-abc"},
        )
        ts = _make_tailscale()
        mc = _make_model_cache()
        pf = _make_preflight()

        deployment = Deployment(
            name="default", model="flash", capacity=Capacity.ON_DEMAND
        )
        lc = Lifecycle(clients=clients, tailscale=ts, model_cache=mc, preflight=pf)

        delete_devices_called = False

        def _track_delete(*args: Any, **kwargs: Any) -> None:
            nonlocal delete_devices_called
            delete_devices_called = True

        ts.delete_devices.side_effect = _track_delete

        with (
            patch("ember_aws.lifecycle.Stack") as mock_stack_cls,
            patch("ember_aws.lifecycle_update.Stack") as mock_update_stack_cls,
            patch("ember_aws.lifecycle_update.wait_healthy") as mock_health,
        ):
            mock_stack = _make_mock_stack()
            mock_stack.exists.return_value = True
            mock_stack_cls.return_value = mock_stack

            mock_update_stack = _make_mock_stack()
            mock_update_stack.exists.return_value = True
            mock_update_stack.update_has_replacement.return_value = True
            mock_update_stack.prepare_change_set.return_value = "cs-001"
            mock_update_stack.execute_change_set.return_value = None
            mock_update_stack.wait.return_value = None
            mock_update_stack_cls.return_value = mock_update_stack

            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.deploy(deployment)

        assert delete_devices_called, (
            "spot to on-demand change must delete tailnet devices (replacement path)"
        )
