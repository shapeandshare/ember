"""Tests for LifecycleControl: stop, start, destroy, rotate_token (T033/T036)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Shared helpers (reuse the same fake-builder pattern from test_aws_stack_lifecycle.py)
# ---------------------------------------------------------------------------

_TAILNET_SUFFIX = "example.ts.net"
_TAILNET_URL = "https://ember-default.example.ts.net"


def _make_clients(
    *,
    instance_id: str = "i-0001",
    instance_state: str = "running",
    ssm_params: dict[str, str] | None = None,
    stack_exists: bool = True,
) -> Any:
    """Build a fake AwsClients-shaped object for control-plane tests."""
    from botocore.exceptions import ClientError

    clients = MagicMock()

    # EC2 — describe_instances
    clients.ec2.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": instance_id,
                        "State": {"Name": instance_state},
                    }
                ]
            }
        ]
    }
    clients.ec2.stop_instances.return_value = {
        "StoppingInstances": [
            {"InstanceId": instance_id, "CurrentState": {"Name": "stopping"}}
        ]
    }
    clients.ec2.start_instances.return_value = {
        "StartingInstances": [
            {"InstanceId": instance_id, "CurrentState": {"Name": "pending"}}
        ]
    }
    clients.ec2.reboot_instances.return_value = {}
    clients.ec2.get_waiter.return_value = MagicMock()

    # CFN — stack existence
    if stack_exists:
        clients.cfn.describe_stacks.return_value = {
            "Stacks": [
                {
                    "StackName": "ember-default",
                    "StackStatus": "CREATE_COMPLETE",
                    "Outputs": [
                        {"OutputKey": "InstanceId", "OutputValue": instance_id},
                        {
                            "OutputKey": "RoleArn",
                            "OutputValue": "arn:aws:iam::123:role/r",
                        },
                    ],
                }
            ]
        }
    else:
        clients.cfn.describe_stacks.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "does not exist"}},
            "DescribeStacks",
        )
    clients.cfn.delete_stack.return_value = {}
    clients.cfn.get_waiter.return_value = MagicMock()

    # SSM
    _ssm_store: dict[str, str] = dict(ssm_params or {})

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

    def _get_parameters_by_path(**kwargs: Any) -> dict[str, Any]:
        prefix = kwargs.get("Path", "")
        params = [
            {"Name": k, "Value": v}
            for k, v in _ssm_store.items()
            if k.startswith(prefix)
        ]
        return {"Parameters": params}

    def _delete_parameters(**kwargs: Any) -> dict[str, Any]:
        names = kwargs.get("Names", [])
        for n in names:
            _ssm_store.pop(n, None)
        return {"DeletedParameters": names, "InvalidParameters": []}

    clients.ssm.get_parameter.side_effect = _get_parameter
    clients.ssm.put_parameter.side_effect = _put_parameter
    clients.ssm.get_parameters_by_path.side_effect = _get_parameters_by_path
    clients.ssm.delete_parameters.side_effect = _delete_parameters

    return clients


def _make_tailscale(
    *,
    tailnet_suffix: str = _TAILNET_SUFFIX,
    devices: list[dict[str, Any]] | None = None,
) -> Any:
    ts = MagicMock()
    ts.tailnet_dns.return_value = {"magic_dns": True, "suffix": tailnet_suffix}
    ts.mint_join_key.return_value = {"id": "key-abc", "key": "tskey-auth-xxx"}
    ts.devices.return_value = devices if devices is not None else []
    ts.delete_devices.return_value = None
    return ts


def _make_lifecycle_control(
    *,
    instance_id: str = "i-0001",
    instance_state: str = "running",
    ssm_params: dict[str, str] | None = None,
    stack_exists: bool = True,
    tailscale_devices: list[dict[str, Any]] | None = None,
) -> tuple[Any, Any, Any]:
    """Return (LifecycleControl, clients, tailscale) for a test."""
    from ember_aws.lifecycle_control import LifecycleControl

    clients = _make_clients(
        instance_id=instance_id,
        instance_state=instance_state,
        ssm_params=ssm_params,
        stack_exists=stack_exists,
    )
    ts = _make_tailscale(devices=tailscale_devices)
    lc = LifecycleControl(clients=clients, tailscale=ts)
    return lc, clients, ts


# ---------------------------------------------------------------------------
# T033: stop
# ---------------------------------------------------------------------------


class TestStop:
    """stop() on running → stop_instances + wait; on stopped → already stopped."""

    def test_stop_running_calls_stop_instances(self) -> None:
        """stop() on a running instance calls EC2 stop_instances."""
        from ember_aws.deployment import Deployment

        lc, clients, _ = _make_lifecycle_control(instance_state="running")
        deployment = Deployment(name="default", model="flash")
        lc.stop(deployment)

        clients.ec2.stop_instances.assert_called_once()
        call_kwargs = clients.ec2.stop_instances.call_args
        instance_ids = call_kwargs.kwargs.get("InstanceIds") or call_kwargs.args[0]
        assert "i-0001" in instance_ids

    def test_stop_running_waits_for_stopped(self) -> None:
        """stop() on a running instance waits for the stopped state."""
        from ember_aws.deployment import Deployment

        lc, clients, _ = _make_lifecycle_control(instance_state="running")
        deployment = Deployment(name="default", model="flash")
        lc.stop(deployment)

        waiter = clients.ec2.get_waiter.return_value
        waiter.wait.assert_called_once()

    def test_stop_already_stopped_prints_message(self, capsys: Any) -> None:
        """stop() on a stopped instance prints 'already stopped'."""
        from ember_aws.deployment import Deployment

        lc, _clients, _ = _make_lifecycle_control(instance_state="stopped")
        deployment = Deployment(name="default", model="flash")
        lc.stop(deployment)

        captured = capsys.readouterr()
        assert "already stopped" in captured.out

    def test_stop_already_stopped_no_stop_instances_call(self) -> None:
        """stop() on a stopped instance must NOT call stop_instances."""
        from ember_aws.deployment import Deployment

        lc, clients, _ = _make_lifecycle_control(instance_state="stopped")
        deployment = Deployment(name="default", model="flash")
        lc.stop(deployment)

        clients.ec2.stop_instances.assert_not_called()


# ---------------------------------------------------------------------------
# T033: start
# ---------------------------------------------------------------------------


class TestStart:
    """start() mints join key only if device missing; on running prints already running.

    Idempotent: already running → prints message, no EC2 call.
    """

    def test_start_running_prints_already_running(self, capsys: Any) -> None:
        """start() on a running instance prints 'already running: <url>'."""
        from ember_aws.deployment import Deployment

        lc, _clients, _ts = _make_lifecycle_control(instance_state="running")
        deployment = Deployment(name="default", model="flash")

        with patch("ember_aws.lifecycle_control.wait_healthy") as mock_health:
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.start(deployment)

        captured = capsys.readouterr()
        assert "already running" in captured.out
        assert _TAILNET_URL in captured.out

    def test_start_running_no_start_instances_call(self) -> None:
        """start() on a running instance must NOT call start_instances."""
        from ember_aws.deployment import Deployment

        lc, clients, _ts = _make_lifecycle_control(instance_state="running")
        deployment = Deployment(name="default", model="flash")

        with patch("ember_aws.lifecycle_control.wait_healthy") as mock_health:
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.start(deployment)

        clients.ec2.start_instances.assert_not_called()

    def test_start_stopped_calls_start_instances(self) -> None:
        """start() on a stopped instance calls EC2 start_instances."""
        from ember_aws.deployment import Deployment

        lc, clients, _ts = _make_lifecycle_control(
            instance_state="stopped",
            ssm_params={"/ember/default/server-token": "tok"},
        )
        deployment = Deployment(name="default", model="flash")

        with patch("ember_aws.lifecycle_control.wait_healthy") as mock_health:
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.start(deployment)

        clients.ec2.start_instances.assert_called_once()
        call_kwargs = clients.ec2.start_instances.call_args
        instance_ids = call_kwargs.kwargs.get("InstanceIds") or call_kwargs.args[0]
        assert "i-0001" in instance_ids

    def test_start_mints_join_key_when_device_missing(self) -> None:
        """start() mints a fresh join key when the device is absent from the tailnet."""
        from ember_aws.deployment import Deployment

        # No devices on the tailnet
        lc, _clients, ts = _make_lifecycle_control(
            instance_state="stopped",
            ssm_params={"/ember/default/server-token": "tok"},
            tailscale_devices=[],
        )
        deployment = Deployment(name="default", model="flash")

        with patch("ember_aws.lifecycle_control.wait_healthy") as mock_health:
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.start(deployment)

        ts.mint_join_key.assert_called_once()

    def test_start_skips_join_key_when_device_present(self) -> None:
        """start() does NOT mint a join key when device is already on the tailnet."""
        from ember_aws.deployment import Deployment

        # Device already on the tailnet
        devices = [
            {"hostname": "ember-default", "tags": ["tag:ember"], "id": "dev-001"}
        ]
        lc, _clients, ts = _make_lifecycle_control(
            instance_state="stopped",
            ssm_params={"/ember/default/server-token": "tok"},
            tailscale_devices=devices,
        )
        deployment = Deployment(name="default", model="flash")

        with patch("ember_aws.lifecycle_control.wait_healthy") as mock_health:
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.start(deployment)

        ts.mint_join_key.assert_not_called()

    def test_start_waits_for_health(self) -> None:
        """start() calls wait_healthy after starting the instance."""
        from ember_aws.deployment import Deployment

        lc, _clients, _ts = _make_lifecycle_control(
            instance_state="stopped",
            ssm_params={"/ember/default/server-token": "tok"},
        )
        deployment = Deployment(name="default", model="flash")

        with patch("ember_aws.lifecycle_control.wait_healthy") as mock_health:
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.start(deployment)

        mock_health.assert_called_once()
        call_kwargs = mock_health.call_args
        url_arg = call_kwargs.kwargs.get("url") or (
            call_kwargs.args[0] if call_kwargs.args else None
        )
        assert url_arg == _TAILNET_URL


# ---------------------------------------------------------------------------
# T033: destroy
# ---------------------------------------------------------------------------


class TestDestroy:
    """destroy() order: tailnet devices → delete_stack → wait → delete SSM params.

    Guarded: exits 3 without --confirm <name>. Idempotent: nothing deployed → exit 0.
    """

    def test_destroy_without_confirm_exits_3(self) -> None:
        """destroy() without --confirm <name> must exit with code 3."""
        from ember_aws.deployment import Deployment

        lc, _clients, _ts = _make_lifecycle_control()
        deployment = Deployment(name="default", model="flash")

        with pytest.raises(SystemExit) as exc_info:
            lc.destroy(deployment, confirm=None)

        assert exc_info.value.code == 3

    def test_destroy_wrong_confirm_exits_3(self) -> None:
        """destroy() with wrong confirm name must exit with code 3."""
        from ember_aws.deployment import Deployment

        lc, _clients, _ts = _make_lifecycle_control()
        deployment = Deployment(name="default", model="flash")

        with pytest.raises(SystemExit) as exc_info:
            lc.destroy(deployment, confirm="wrong-name")

        assert exc_info.value.code == 3

    def test_destroy_deletes_tailnet_devices_first(self) -> None:
        """destroy() must delete tailnet devices before deleting the stack."""
        from ember_aws.deployment import Deployment

        call_order: list[str] = []
        lc, clients, ts = _make_lifecycle_control(
            ssm_params={"/ember/default/server-token": "tok"}
        )
        deployment = Deployment(name="default", model="flash")

        ts.delete_devices.side_effect = lambda *a, **kw: call_order.append(
            "delete_devices"
        )
        clients.cfn.delete_stack.side_effect = lambda **kw: call_order.append(
            "delete_stack"
        )

        lc.destroy(deployment, confirm="default")

        assert "delete_devices" in call_order
        assert "delete_stack" in call_order
        assert call_order.index("delete_devices") < call_order.index("delete_stack")

    def test_destroy_waits_after_delete_stack(self) -> None:
        """destroy() must wait for stack deletion after calling delete_stack."""
        from ember_aws.deployment import Deployment

        call_order: list[str] = []
        lc, clients, _ts = _make_lifecycle_control(
            ssm_params={"/ember/default/server-token": "tok"}
        )
        deployment = Deployment(name="default", model="flash")

        clients.cfn.delete_stack.side_effect = lambda **kw: call_order.append(
            "delete_stack"
        )
        waiter = clients.cfn.get_waiter.return_value
        waiter.wait.side_effect = lambda **kw: call_order.append("wait")

        lc.destroy(deployment, confirm="default")

        assert "delete_stack" in call_order
        assert "wait" in call_order
        assert call_order.index("delete_stack") < call_order.index("wait")

    def test_destroy_deletes_ssm_params_after_stack(self) -> None:
        """destroy() must delete all /ember/<name>/* SSM params after stack deletion."""
        from ember_aws.deployment import Deployment

        call_order: list[str] = []
        ssm_params = {
            "/ember/default/server-token": "tok",
            "/ember/default/config": "{}",
            "/ember/default/tailscale-join-key": "key",
        }
        lc, clients, _ts = _make_lifecycle_control(ssm_params=ssm_params)
        deployment = Deployment(name="default", model="flash")

        waiter = clients.cfn.get_waiter.return_value
        waiter.wait.side_effect = lambda **kw: call_order.append("wait")

        orig_delete = clients.ssm.delete_parameters.side_effect

        def _track_delete(**kwargs: Any) -> Any:
            call_order.append("delete_params")
            return orig_delete(**kwargs)

        clients.ssm.delete_parameters.side_effect = _track_delete

        lc.destroy(deployment, confirm="default")

        assert "wait" in call_order
        assert "delete_params" in call_order
        assert call_order.index("wait") < call_order.index("delete_params")

    def test_destroy_deletes_all_ssm_params_under_prefix(self) -> None:
        """destroy() must delete every /ember/<name>/* parameter."""
        from ember_aws.deployment import Deployment

        ssm_params = {
            "/ember/default/server-token": "tok",
            "/ember/default/config": "{}",
            "/ember/default/tailscale-join-key": "key",
        }
        lc, clients, _ts = _make_lifecycle_control(ssm_params=ssm_params)
        deployment = Deployment(name="default", model="flash")

        lc.destroy(deployment, confirm="default")

        # get_parameters_by_path must have been called with the prefix
        clients.ssm.get_parameters_by_path.assert_called()
        path_arg = (
            clients.ssm.get_parameters_by_path.call_args.kwargs.get("Path")
            or clients.ssm.get_parameters_by_path.call_args.args[0]
        )
        assert path_arg == "/ember/default/"

        # delete_parameters must have been called with all three names
        clients.ssm.delete_parameters.assert_called()
        deleted_names: list[str] = []
        for c in clients.ssm.delete_parameters.call_args_list:
            names = c.kwargs.get("Names") or (c.args[0] if c.args else [])
            deleted_names.extend(names)
        assert set(deleted_names) == set(ssm_params.keys())

    def test_destroy_never_touches_cache_stack(self) -> None:
        """destroy() must never call delete_stack on the cache stack."""
        from ember_aws.deployment import Deployment

        lc, clients, _ts = _make_lifecycle_control(
            ssm_params={"/ember/default/server-token": "tok"}
        )
        deployment = Deployment(name="default", model="flash")

        lc.destroy(deployment, confirm="default")

        # delete_stack must only target ember-default, never the cache stack
        for c in clients.cfn.delete_stack.call_args_list:
            stack_name = c.kwargs.get("StackName") or (c.args[0] if c.args else "")
            assert "cache" not in stack_name.lower(), (
                f"destroy must never touch the cache stack,"
                f" but called delete_stack({stack_name!r})"
            )

    def test_destroy_when_no_stack_prints_nothing_deployed(self, capsys: Any) -> None:
        """A second destroy (no stack) prints 'nothing deployed' and exits 0."""
        from ember_aws.deployment import Deployment

        lc, _clients, _ts = _make_lifecycle_control(stack_exists=False)
        deployment = Deployment(name="default", model="flash")

        # Should NOT raise SystemExit — exits 0 (or just returns)
        lc.destroy(deployment, confirm="default")

        captured = capsys.readouterr()
        assert "nothing deployed" in captured.out

    def test_destroy_when_no_stack_does_not_call_delete_stack(self) -> None:
        """A second destroy must not call delete_stack when there is no stack."""
        from ember_aws.deployment import Deployment

        lc, clients, _ts = _make_lifecycle_control(stack_exists=False)
        deployment = Deployment(name="default", model="flash")

        lc.destroy(deployment, confirm="default")

        clients.cfn.delete_stack.assert_not_called()


# ---------------------------------------------------------------------------
# T033: rotate_token
# ---------------------------------------------------------------------------


class TestRotateToken:
    """rotate_token() overwrites the token param, reboots, then waits for health."""

    def test_rotate_token_overwrites_token_param(self) -> None:
        """rotate_token() must call SSM put_parameter for the token with Overwrite=True.

        The token param must be overwritten (not created fresh).
        """
        from ember_aws.deployment import Deployment

        old_token = "old-token-value"
        lc, clients, _ts = _make_lifecycle_control(
            ssm_params={"/ember/default/server-token": old_token}
        )
        deployment = Deployment(name="default", model="flash")

        with patch("ember_aws.lifecycle_control.wait_healthy") as mock_health:
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.rotate_token(deployment)

        token_puts = [
            c
            for c in clients.ssm.put_parameter.call_args_list
            if c.kwargs.get("Name") == "/ember/default/server-token"
        ]
        assert len(token_puts) == 1
        assert token_puts[0].kwargs.get("Overwrite") is True

    def test_rotate_token_new_token_differs_from_old(self) -> None:
        """rotate_token() must write a new token value, not the old one."""
        from ember_aws.deployment import Deployment

        old_token = "old-token-value"
        lc, clients, _ts = _make_lifecycle_control(
            ssm_params={"/ember/default/server-token": old_token}
        )
        deployment = Deployment(name="default", model="flash")

        with patch("ember_aws.lifecycle_control.wait_healthy") as mock_health:
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.rotate_token(deployment)

        token_puts = [
            c
            for c in clients.ssm.put_parameter.call_args_list
            if c.kwargs.get("Name") == "/ember/default/server-token"
        ]
        new_value = token_puts[0].kwargs.get("Value")
        assert new_value != old_token

    def test_rotate_token_reboots_instance(self) -> None:
        """rotate_token() must call EC2 reboot_instances."""
        from ember_aws.deployment import Deployment

        lc, clients, _ts = _make_lifecycle_control(
            ssm_params={"/ember/default/server-token": "tok"}
        )
        deployment = Deployment(name="default", model="flash")

        with patch("ember_aws.lifecycle_control.wait_healthy") as mock_health:
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.rotate_token(deployment)

        clients.ec2.reboot_instances.assert_called_once()
        call_kwargs = clients.ec2.reboot_instances.call_args
        instance_ids = call_kwargs.kwargs.get("InstanceIds") or call_kwargs.args[0]
        assert "i-0001" in instance_ids

    def test_rotate_token_overwrites_before_reboot(self) -> None:
        """rotate_token() must overwrite the token param before rebooting."""
        from ember_aws.deployment import Deployment

        call_order: list[str] = []
        lc, clients, _ts = _make_lifecycle_control(
            ssm_params={"/ember/default/server-token": "tok"}
        )
        deployment = Deployment(name="default", model="flash")

        orig_put = clients.ssm.put_parameter.side_effect

        def _track_put(**kwargs: Any) -> Any:
            if kwargs.get("Name") == "/ember/default/server-token":
                call_order.append("put_token")
            return orig_put(**kwargs) if orig_put else {}

        clients.ssm.put_parameter.side_effect = _track_put
        clients.ec2.reboot_instances.side_effect = lambda **kw: call_order.append(
            "reboot"
        )

        with patch("ember_aws.lifecycle_control.wait_healthy") as mock_health:
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.rotate_token(deployment)

        assert "put_token" in call_order
        assert "reboot" in call_order
        assert call_order.index("put_token") < call_order.index("reboot")

    def test_rotate_token_waits_for_health_after_reboot(self) -> None:
        """rotate_token() must call wait_healthy after rebooting."""
        from ember_aws.deployment import Deployment

        call_order: list[str] = []
        lc, clients, _ts = _make_lifecycle_control(
            ssm_params={"/ember/default/server-token": "tok"}
        )
        deployment = Deployment(name="default", model="flash")

        clients.ec2.reboot_instances.side_effect = lambda **kw: call_order.append(
            "reboot"
        )

        def _mock_wait_healthy(**kw: Any) -> dict[str, Any]:
            call_order.append("wait_healthy")
            return {"engine": {"device": "cuda"}, "version": "0.12.0"}

        with patch(
            "ember_aws.lifecycle_control.wait_healthy",
            side_effect=_mock_wait_healthy,
        ):
            lc.rotate_token(deployment)

        assert "reboot" in call_order
        assert "wait_healthy" in call_order
        assert call_order.index("reboot") < call_order.index("wait_healthy")

    def test_rotate_token_new_token_not_in_stdout(self, capsys: Any) -> None:
        """rotate_token() must never print the new token to stdout."""
        from ember_aws.deployment import Deployment

        lc, clients, _ts = _make_lifecycle_control(
            ssm_params={"/ember/default/server-token": "tok"}
        )
        deployment = Deployment(name="default", model="flash")

        with patch("ember_aws.lifecycle_control.wait_healthy") as mock_health:
            mock_health.return_value = {
                "engine": {"device": "cuda"},
                "version": "0.12.0",
            }
            lc.rotate_token(deployment)

        token_puts = [
            c
            for c in clients.ssm.put_parameter.call_args_list
            if c.kwargs.get("Name") == "/ember/default/server-token"
        ]
        new_token = token_puts[0].kwargs.get("Value", "")

        captured = capsys.readouterr()
        assert new_token not in captured.out
        assert new_token not in captured.err
