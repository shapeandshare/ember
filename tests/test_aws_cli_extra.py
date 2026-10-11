"""Extra tests for __main__.py, _cli_handlers.py, and _cli_handlers_control.py."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_factory(
    *,
    lcc: Any = None,
    sr: Any = None,
    remote: Any = None,
    lc: Any = None,
    mc: Any = None,
) -> Any:
    """Return a factory callable that returns the given fakes."""
    _lcc = lcc or MagicMock()
    _sr = sr or MagicMock()
    _remote = remote or MagicMock()
    _lc = lc or MagicMock()
    _mc = mc or MagicMock()

    def factory(
        clients: Any, tailscale: Any, name: Any = None
    ) -> tuple[Any, Any, Any, Any, Any]:
        return _lcc, _sr, _remote, _lc, _mc

    return factory


def _make_args(**kwargs: Any) -> Any:
    """Build a fake argparse.Namespace."""
    import argparse

    ns = argparse.Namespace()
    defaults = {
        "name": "default",
        "model": "flash",
        "region": "us-east-1",
        "instance_type": None,
        "ember_version": "",
        "capacity": "on-demand",
        "idle_minutes": 0,
        "json": False,
        "unit": "ember",
        "follow": False,
        "confirm": None,
        "revision": "rev123",
        "bucket": None,
        "prefix": "models/",
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(ns, k, v)
    return ns


# ---------------------------------------------------------------------------
# __main__.build()
# ---------------------------------------------------------------------------


class TestMainBuild:
    """__main__.build() dispatches to the correct handler."""

    def test_build_returns_1_when_no_subcommand(self) -> None:
        """build() returns 1 and prints help when no subcommand is given."""
        from ember_aws.__main__ import build

        result = build([])
        assert result == 1

    def test_build_dispatches_to_handler(self) -> None:
        """build() calls the handler attached to the parsed args."""
        from ember_aws.__main__ import build

        def fake_factory(
            clients: Any, tailscale: Any, name: Any = None
        ) -> tuple[Any, Any, Any, Any, Any]:
            return MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()

        with (
            patch("ember_aws.__main__._make_clients") as mock_clients,
            patch("ember_aws.__main__._make_tailscale") as mock_ts,
            patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct,
        ):
            mock_clients.return_value = MagicMock()
            mock_ts.return_value = MagicMock()
            mock_ct.return_value = (MagicMock(), MagicMock())

            # Use a real subcommand that we can intercept
            lc = MagicMock()
            lc.token.return_value = None
            factory = _make_factory(lc=lc)

            result = build(
                [
                    "token",
                    "--name",
                    "default",
                    "--model",
                    "flash",
                    "--region",
                    "us-east-1",
                ],
                factory=factory,
            )
        # token handler should succeed
        assert result == 0

    def test_main_returns_int(self) -> None:
        """main() returns an integer exit code."""
        from ember_aws.__main__ import build

        result = build([])
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# handle_preflight()
# ---------------------------------------------------------------------------


class TestHandlePreflight:
    """handle_preflight() runs preflight and returns correct exit codes."""

    def test_returns_0_when_all_checks_pass(self) -> None:
        """handle_preflight() returns 0 when preflight has no failures."""
        from ember_aws._cli_handlers import handle_preflight

        lc = MagicMock()
        lc._preflight = MagicMock()
        lc._preflight.run.return_value = []
        factory = _make_factory(lc=lc)

        args = _make_args()

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_preflight(args, factory)

        assert result == 0

    def test_returns_1_when_blocking_failure(self) -> None:
        """handle_preflight() returns 1 when there is a blocking failure."""
        from ember_aws._cli_handlers import handle_preflight
        from ember_aws.check_result import CheckResult
        from ember_aws.preflight_check import PreflightCheck

        lc = MagicMock()
        lc._preflight = MagicMock()
        lc._preflight.run.return_value = [
            CheckResult(
                check=PreflightCheck.AWS_IDENTITY,
                ok=False,
                problem="no credentials",
                fix="aws sso login",
                blocking=True,
            )
        ]
        factory = _make_factory(lc=lc)
        args = _make_args()

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_preflight(args, factory)

        assert result == 1

    def test_prints_non_blocking_warning(self, capsys: Any) -> None:
        """handle_preflight() prints '!' for non-blocking failures."""
        from ember_aws._cli_handlers import handle_preflight
        from ember_aws.check_result import CheckResult
        from ember_aws.preflight_check import PreflightCheck

        lc = MagicMock()
        lc._preflight = MagicMock()
        lc._preflight.run.return_value = [
            CheckResult(
                check=PreflightCheck.TAILSCALE_HTTPS,
                ok=False,
                problem="HTTPS certs not enabled",
                fix="enable in admin console",
                blocking=False,
            )
        ]
        factory = _make_factory(lc=lc)
        args = _make_args()

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_preflight(args, factory)

        assert result == 0
        captured = capsys.readouterr()
        assert "!" in captured.out


# ---------------------------------------------------------------------------
# handle_cache_dispatch()
# ---------------------------------------------------------------------------


class TestHandleCacheDispatch:
    """handle_cache_dispatch() dispatches to sub-handlers."""

    def test_returns_1_when_no_sub_handler(self, capsys: Any) -> None:
        """handle_cache_dispatch() returns 1 when no sub-handler is set."""
        from ember_aws._cli_handlers import handle_cache_dispatch

        args = _make_args()
        # No handler attribute set
        result = handle_cache_dispatch(args, _make_factory())
        assert result == 1

    def test_dispatches_to_sub_handler(self) -> None:
        """handle_cache_dispatch() calls args.handler when set."""
        from ember_aws._cli_handlers import handle_cache_dispatch

        called: list[bool] = []

        def sub_handler(args: Any, factory: Any) -> int:
            called.append(True)
            return 0

        args = _make_args()
        args.handler = sub_handler
        result = handle_cache_dispatch(args, _make_factory())
        assert result == 0
        assert called == [True]


# ---------------------------------------------------------------------------
# handle_cache_add()
# ---------------------------------------------------------------------------


class TestHandleCacheAdd:
    """handle_cache_add() calls mc.add and returns correct exit codes."""

    def test_returns_0_on_success(self) -> None:
        """handle_cache_add() returns 0 when mc.add succeeds."""
        from ember_aws._cli_handlers import handle_cache_add

        mc = MagicMock()
        mc.add.return_value = None
        factory = _make_factory(mc=mc)
        args = _make_args()

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_cache_add(args, factory)

        assert result == 0

    def test_returns_3_on_cache_in_use_error(self) -> None:
        """handle_cache_add() returns 3 when CacheInUseError is raised."""
        from ember_aws._cli_handlers import handle_cache_add
        from ember_aws.model_cache import CacheInUseError

        mc = MagicMock()
        mc.add.side_effect = CacheInUseError("in use")
        factory = _make_factory(mc=mc)
        args = _make_args()

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_cache_add(args, factory)

        assert result == 3

    def test_returns_2_on_generic_exception(self) -> None:
        """handle_cache_add() returns 2 on unexpected exceptions."""
        from ember_aws._cli_handlers import handle_cache_add

        mc = MagicMock()
        mc.add.side_effect = RuntimeError("unexpected")
        factory = _make_factory(mc=mc)
        args = _make_args()

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_cache_add(args, factory)

        assert result == 2


# ---------------------------------------------------------------------------
# handle_cache_list()
# ---------------------------------------------------------------------------


class TestHandleCacheList:
    """handle_cache_list() calls mc.list and prints results."""

    def test_returns_0_and_prints_items(self, capsys: Any) -> None:
        """handle_cache_list() returns 0 and prints each cached model."""
        from ember_aws._cli_handlers import handle_cache_list

        mc = MagicMock()
        mc.list.return_value = [
            {"model": "flash", "revision": "rev123", "status": "complete"}
        ]
        factory = _make_factory(mc=mc)
        args = _make_args()

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_cache_list(args, factory)

        assert result == 0
        captured = capsys.readouterr()
        assert "flash@rev123" in captured.out
        assert "complete" in captured.out

    def test_prints_size_and_deployments_when_present(self, capsys: Any) -> None:
        """handle_cache_list() renders the size and using deployments."""
        from ember_aws._cli_handlers import handle_cache_list

        mc = MagicMock()
        mc.list.return_value = [
            {
                "model": "flash",
                "revision": "rev123",
                "status": "complete",
                "total_bytes": 18 * 2**30,
                "deployments": ["default"],
            }
        ]
        factory = _make_factory(mc=mc)
        args = _make_args()

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_cache_list(args, factory)

        assert result == 0
        captured = capsys.readouterr()
        assert "18.0 GiB" in captured.out
        assert "used by: default" in captured.out

    def test_returns_2_on_exception(self) -> None:
        """handle_cache_list() returns 2 on unexpected exceptions."""
        from ember_aws._cli_handlers import handle_cache_list

        mc = MagicMock()
        mc.list.side_effect = RuntimeError("unexpected")
        factory = _make_factory(mc=mc)
        args = _make_args()

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_cache_list(args, factory)

        assert result == 2


# ---------------------------------------------------------------------------
# handle_cache_rm()
# ---------------------------------------------------------------------------


class TestHandleCacheRm:
    """handle_cache_rm() calls mc.remove and returns correct exit codes."""

    def test_returns_0_on_success(self) -> None:
        """handle_cache_rm() returns 0 when mc.remove succeeds."""
        from ember_aws._cli_handlers import handle_cache_rm

        mc = MagicMock()
        mc.remove.return_value = None
        factory = _make_factory(mc=mc)
        args = _make_args()

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_cache_rm(args, factory)

        assert result == 0

    def test_returns_3_on_cache_in_use_error(self) -> None:
        """handle_cache_rm() returns 3 when CacheInUseError is raised."""
        from ember_aws._cli_handlers import handle_cache_rm
        from ember_aws.model_cache import CacheInUseError

        mc = MagicMock()
        mc.remove.side_effect = CacheInUseError("in use")
        factory = _make_factory(mc=mc)
        args = _make_args()

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_cache_rm(args, factory)

        assert result == 3

    def test_returns_2_on_generic_exception(self) -> None:
        """handle_cache_rm() returns 2 on unexpected exceptions."""
        from ember_aws._cli_handlers import handle_cache_rm

        mc = MagicMock()
        mc.remove.side_effect = RuntimeError("unexpected")
        factory = _make_factory(mc=mc)
        args = _make_args()

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_cache_rm(args, factory)

        assert result == 2

    def test_resolves_the_registry_revision_when_omitted(self) -> None:
        """handle_cache_rm() resolves --revision from the registry when omitted."""
        import ember.models as ember_models

        from ember_aws._cli_handlers import handle_cache_rm

        mc = MagicMock()
        mc.remove.return_value = None
        factory = _make_factory(mc=mc)
        args = _make_args(revision=None)

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_cache_rm(args, factory)

        assert result == 0
        pinned = ember_models.REGISTRY["flash"].revision or "latest"
        mc.remove.assert_called_once_with(
            "flash", pinned, bucket=None, prefix="models/"
        )

    def test_unknown_model_without_revision_exits_1(self) -> None:
        """An unpinned model without --revision is an actionable error."""
        from ember_aws._cli_handlers import handle_cache_rm

        mc = MagicMock()
        factory = _make_factory(mc=mc)
        args = _make_args(model="mystery", revision=None)

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_cache_rm(args, factory)

        assert result == 1
        mc.remove.assert_not_called()


# ---------------------------------------------------------------------------
# handle_cache_destroy()
# ---------------------------------------------------------------------------


class TestHandleCacheDestroy:
    """handle_cache_destroy() calls mc.destroy and returns correct exit codes."""

    def test_returns_0_on_success(self) -> None:
        """handle_cache_destroy() returns 0 when mc.destroy succeeds."""
        from ember_aws._cli_handlers import handle_cache_destroy

        mc = MagicMock()
        mc.destroy.return_value = None
        factory = _make_factory(mc=mc)
        args = _make_args(confirm="my-bucket")

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_cache_destroy(args, factory)

        assert result == 0

    def test_returns_3_on_confirmation_error(self) -> None:
        """handle_cache_destroy() returns 3 when ConfirmationError is raised."""
        from ember_aws._cli_handlers import handle_cache_destroy
        from ember_aws.model_cache import ConfirmationError

        mc = MagicMock()
        mc.destroy.side_effect = ConfirmationError("wrong confirm")
        factory = _make_factory(mc=mc)
        args = _make_args(confirm="wrong")

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_cache_destroy(args, factory)

        assert result == 3

    def test_returns_3_on_cache_in_use_error(self) -> None:
        """handle_cache_destroy() returns 3 when CacheInUseError is raised."""
        from ember_aws._cli_handlers import handle_cache_destroy
        from ember_aws.model_cache import CacheInUseError

        mc = MagicMock()
        mc.destroy.side_effect = CacheInUseError("in use")
        factory = _make_factory(mc=mc)
        args = _make_args(confirm="my-bucket")

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_cache_destroy(args, factory)

        assert result == 3

    def test_returns_2_on_generic_exception(self) -> None:
        """handle_cache_destroy() returns 2 on unexpected exceptions."""
        from ember_aws._cli_handlers import handle_cache_destroy

        mc = MagicMock()
        mc.destroy.side_effect = RuntimeError("unexpected")
        factory = _make_factory(mc=mc)
        args = _make_args(confirm="my-bucket")

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_cache_destroy(args, factory)

        assert result == 2


# ---------------------------------------------------------------------------
# handle_deploy()
# ---------------------------------------------------------------------------


class TestHandleDeploy:
    """handle_deploy() calls lc.deploy and returns correct exit codes."""

    def test_returns_0_on_success(self) -> None:
        """handle_deploy() returns 0 when lc.deploy succeeds."""
        from ember_aws._cli_handlers import handle_deploy

        lc = MagicMock()
        lc.deploy.return_value = None
        factory = _make_factory(lc=lc)
        args = _make_args()

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_deploy(args, factory)

        assert result == 0

    def test_returns_exit_code_from_system_exit(self) -> None:
        """handle_deploy() returns the SystemExit code."""
        from ember_aws._cli_handlers import handle_deploy

        lc = MagicMock()
        lc.deploy.side_effect = SystemExit(1)
        factory = _make_factory(lc=lc)
        args = _make_args()

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_deploy(args, factory)

        assert result == 1

    def test_returns_1_on_sizing_error(self) -> None:
        """handle_deploy() returns 1 when SizingError is raised."""
        from ember_aws._cli_handlers import handle_deploy
        from ember_aws.sizing_table import SizingError

        lc = MagicMock()
        lc.deploy.side_effect = SizingError("unsupported")
        factory = _make_factory(lc=lc)
        args = _make_args()

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_deploy(args, factory)

        assert result == 1

    def test_returns_2_on_stack_deploy_error(self) -> None:
        """handle_deploy() returns 2 when StackDeployError is raised."""
        from ember_aws._cli_handlers import handle_deploy
        from ember_aws.lifecycle import StackDeployError

        lc = MagicMock()
        lc.deploy.side_effect = StackDeployError("stack failed")
        factory = _make_factory(lc=lc)
        args = _make_args()

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_deploy(args, factory)

        assert result == 2

    def test_returns_2_on_generic_exception(self) -> None:
        """handle_deploy() returns 2 on unexpected exceptions."""
        from ember_aws._cli_handlers import handle_deploy

        lc = MagicMock()
        lc.deploy.side_effect = RuntimeError("unexpected")
        factory = _make_factory(lc=lc)
        args = _make_args()

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_deploy(args, factory)

        assert result == 2

    def test_passes_instance_type_when_set(self) -> None:
        """handle_deploy() passes instance_type to Deployment when set."""
        from ember_aws._cli_handlers import handle_deploy

        lc = MagicMock()
        lc.deploy.return_value = None
        factory = _make_factory(lc=lc)
        args = _make_args(instance_type="g5.2xlarge")

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_deploy(args, factory)

        assert result == 0
        call_args = lc.deploy.call_args
        deployment = (
            call_args.args[0] if call_args.args else call_args.kwargs.get("deployment")
        )
        assert deployment.instance_type == "g5.2xlarge"

    def test_passes_ember_version_when_set(self) -> None:
        """handle_deploy() passes ember_version to Deployment when set."""
        from ember_aws._cli_handlers import handle_deploy

        lc = MagicMock()
        lc.deploy.return_value = None
        factory = _make_factory(lc=lc)
        args = _make_args(ember_version="0.12.0")

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_deploy(args, factory)

        assert result == 0
        call_args = lc.deploy.call_args
        deployment = (
            call_args.args[0] if call_args.args else call_args.kwargs.get("deployment")
        )
        assert deployment.ember_version == "0.12.0"


# ---------------------------------------------------------------------------
# handle_token()
# ---------------------------------------------------------------------------


class TestHandleToken:
    """handle_token() calls lc.token and returns correct exit codes."""

    def test_returns_0_on_success(self) -> None:
        """handle_token() returns 0 when lc.token succeeds."""
        from ember_aws._cli_handlers import handle_token

        lc = MagicMock()
        lc.token.return_value = None
        factory = _make_factory(lc=lc)
        args = _make_args()

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_token(args, factory)

        assert result == 0

    def test_returns_2_on_exception(self) -> None:
        """handle_token() returns 2 on unexpected exceptions."""
        from ember_aws._cli_handlers import handle_token

        lc = MagicMock()
        lc.token.side_effect = RuntimeError("unexpected")
        factory = _make_factory(lc=lc)
        args = _make_args()

        with patch("ember_aws._cli_handlers._make_clients_and_tailscale") as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_token(args, factory)

        assert result == 2


# ---------------------------------------------------------------------------
# handle_status()
# ---------------------------------------------------------------------------


class TestHandleStatus:
    """handle_status() calls sr.read and prints status."""

    def test_returns_0_and_prints_state(self, capsys: Any) -> None:
        """handle_status() returns 0 and prints the deployment state."""
        from ember_aws._cli_handlers_control import handle_status
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.deployment_status import DeploymentStatus

        sr = MagicMock()
        status = DeploymentStatus(state=DeploymentState.RUNNING)
        sr.read.return_value = status
        factory = _make_factory(sr=sr)
        args = _make_args()

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_status(args, factory)

        assert result == 0
        captured = capsys.readouterr()
        assert "running" in captured.out

    def test_returns_json_when_json_flag_set(self, capsys: Any) -> None:
        """handle_status() returns JSON output when --json is set."""
        from ember_aws._cli_handlers_control import handle_status
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.deployment_status import DeploymentStatus

        sr = MagicMock()
        status = DeploymentStatus(state=DeploymentState.RUNNING)
        sr.read.return_value = status
        factory = _make_factory(sr=sr)
        args = _make_args(json=True)

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_status(args, factory)

        assert result == 0
        captured = capsys.readouterr()
        import json

        data = json.loads(captured.out)
        assert "state" in data

    def test_returns_2_on_exception(self) -> None:
        """handle_status() returns 2 when sr.read raises."""
        from ember_aws._cli_handlers_control import handle_status

        sr = MagicMock()
        sr.read.side_effect = RuntimeError("unexpected")
        factory = _make_factory(sr=sr)
        args = _make_args()

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_status(args, factory)

        assert result == 2

    def test_prints_optional_fields_when_present(self, capsys: Any) -> None:
        """handle_status() prints optional fields when they are set."""
        from ember_aws._cli_handlers_control import handle_status
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.deployment_status import DeploymentStatus
        from ember_aws.stop_reason import StopReason

        sr = MagicMock()
        status = DeploymentStatus(
            state=DeploymentState.RUNNING,
            instance_type="g6e.xlarge",
            capacity="on-demand",
            az="us-east-1a",
            url="https://ember-default.example.ts.net",
            stop_reason=StopReason.IDLE,
            idle_minutes=60,
            uptime=3600.0,
            cost_since_start_usd=1.86,
            health={"engine": {"device": "cuda"}},
        )
        sr.read.return_value = status
        factory = _make_factory(sr=sr)
        args = _make_args()

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_status(args, factory)

        assert result == 0
        captured = capsys.readouterr()
        assert "g6e.xlarge" in captured.out
        assert "on-demand" in captured.out
        assert "us-east-1a" in captured.out
        assert "ember-default.example.ts.net" in captured.out
        assert "idle" in captured.out
        assert "60" in captured.out
        assert "3600" in captured.out
        assert "1.86" in captured.out
        assert "cuda" in captured.out

    def test_prints_health_error_when_present(self, capsys: Any) -> None:
        """handle_status() prints health error when health dict has 'error' key."""
        from ember_aws._cli_handlers_control import handle_status
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.deployment_status import DeploymentStatus

        sr = MagicMock()
        status = DeploymentStatus(
            state=DeploymentState.RUNNING,
            health={"error": "connection refused"},
        )
        sr.read.return_value = status
        factory = _make_factory(sr=sr)
        args = _make_args()

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_status(args, factory)

        assert result == 0
        captured = capsys.readouterr()
        assert "error" in captured.out
        assert "connection refused" in captured.out


# ---------------------------------------------------------------------------
# handle_stop()
# ---------------------------------------------------------------------------


class TestHandleStop:
    """handle_stop() calls lcc.stop and returns correct exit codes."""

    def test_returns_0_on_success(self) -> None:
        """handle_stop() returns 0 when lcc.stop succeeds."""
        from ember_aws._cli_handlers_control import handle_stop

        lcc = MagicMock()
        lcc.stop.return_value = None
        factory = _make_factory(lcc=lcc)
        args = _make_args()

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_stop(args, factory)

        assert result == 0

    def test_returns_2_on_exception(self) -> None:
        """handle_stop() returns 2 on unexpected exceptions."""
        from ember_aws._cli_handlers_control import handle_stop

        lcc = MagicMock()
        lcc.stop.side_effect = RuntimeError("unexpected")
        factory = _make_factory(lcc=lcc)
        args = _make_args()

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_stop(args, factory)

        assert result == 2


# ---------------------------------------------------------------------------
# handle_start()
# ---------------------------------------------------------------------------


class TestHandleStart:
    """handle_start() calls lcc.start and returns correct exit codes."""

    def test_returns_0_on_success(self) -> None:
        """handle_start() returns 0 when lcc.start succeeds."""
        from ember_aws._cli_handlers_control import handle_start

        lcc = MagicMock()
        lcc.start.return_value = None
        factory = _make_factory(lcc=lcc)
        args = _make_args()

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_start(args, factory)

        assert result == 0

    def test_returns_2_on_exception(self) -> None:
        """handle_start() returns 2 on unexpected exceptions."""
        from ember_aws._cli_handlers_control import handle_start

        lcc = MagicMock()
        lcc.start.side_effect = RuntimeError("unexpected")
        factory = _make_factory(lcc=lcc)
        args = _make_args()

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_start(args, factory)

        assert result == 2


# ---------------------------------------------------------------------------
# handle_logs()
# ---------------------------------------------------------------------------


class TestHandleLogs:
    """handle_logs() calls remote.logs and returns correct exit codes."""

    def test_returns_0_on_success(self) -> None:
        """handle_logs() returns 0 when remote.logs succeeds."""
        from ember_aws._cli_handlers_control import handle_logs

        remote = MagicMock()
        remote.logs.return_value = None
        factory = _make_factory(remote=remote)
        args = _make_args()

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_logs(args, factory)

        assert result == 0

    def test_returns_1_on_value_error(self) -> None:
        """handle_logs() returns 1 when remote.logs raises ValueError."""
        from ember_aws._cli_handlers_control import handle_logs

        remote = MagicMock()
        remote.logs.side_effect = ValueError("invalid unit")
        factory = _make_factory(remote=remote)
        args = _make_args()

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_logs(args, factory)

        assert result == 1

    def test_returns_2_on_generic_exception(self) -> None:
        """handle_logs() returns 2 on unexpected exceptions."""
        from ember_aws._cli_handlers_control import handle_logs

        remote = MagicMock()
        remote.logs.side_effect = RuntimeError("unexpected")
        factory = _make_factory(remote=remote)
        args = _make_args()

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_logs(args, factory)

        assert result == 2


@pytest.mark.parametrize("handler_name", ["handle_logs", "handle_ssh"])
def test_remote_handlers_pass_the_parsed_deployment_name(
    handler_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """handle_logs/handle_ssh give the factory the parsed deployment name."""
    import argparse

    from ember_aws import _cli_handlers_control

    seen_names: list[Any] = []

    def factory(clients: Any, tailscale: Any, name: Any = None) -> Any:
        seen_names.append(name)
        return MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()

    args = argparse.Namespace(name="team-a", unit="ember", follow=False)
    monkeypatch.setattr(
        _cli_handlers_control,
        "_make_clients_and_tailscale",
        lambda region: (MagicMock(), MagicMock()),
    )

    handler = getattr(_cli_handlers_control, handler_name)
    result = handler(args, factory)

    assert result == 0
    assert seen_names == ["team-a"]


def test_default_factory_binds_remote_to_the_deployment_name() -> None:
    """The real factory builds the Remote for the named deployment."""
    from ember_aws.__main__ import _default_factory

    _, _, remote, _, _ = _default_factory(MagicMock(), MagicMock(), "team-a")

    assert remote._names.name == "team-a"


# ---------------------------------------------------------------------------
# handle_ssh()
# ---------------------------------------------------------------------------


class TestHandleSsh:
    """handle_ssh() calls remote.ssh and returns correct exit codes."""

    def test_returns_0_on_success(self) -> None:
        """handle_ssh() returns 0 when remote.ssh succeeds."""
        from ember_aws._cli_handlers_control import handle_ssh

        remote = MagicMock()
        remote.ssh.return_value = None
        factory = _make_factory(remote=remote)
        args = _make_args()

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_ssh(args, factory)

        assert result == 0

    def test_returns_2_on_exception(self) -> None:
        """handle_ssh() returns 2 on unexpected exceptions."""
        from ember_aws._cli_handlers_control import handle_ssh

        remote = MagicMock()
        remote.ssh.side_effect = RuntimeError("unexpected")
        factory = _make_factory(remote=remote)
        args = _make_args()

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_ssh(args, factory)

        assert result == 2


# ---------------------------------------------------------------------------
# handle_rotate_token()
# ---------------------------------------------------------------------------


class TestHandleRotateToken:
    """handle_rotate_token() calls lcc.rotate_token and returns correct exit codes."""

    def test_returns_0_on_success(self) -> None:
        """handle_rotate_token() returns 0 when lcc.rotate_token succeeds."""
        from ember_aws._cli_handlers_control import handle_rotate_token

        lcc = MagicMock()
        lcc.rotate_token.return_value = None
        factory = _make_factory(lcc=lcc)
        args = _make_args()

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_rotate_token(args, factory)

        assert result == 0

    def test_returns_2_on_exception(self) -> None:
        """handle_rotate_token() returns 2 on unexpected exceptions."""
        from ember_aws._cli_handlers_control import handle_rotate_token

        lcc = MagicMock()
        lcc.rotate_token.side_effect = RuntimeError("unexpected")
        factory = _make_factory(lcc=lcc)
        args = _make_args()

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_rotate_token(args, factory)

        assert result == 2


# ---------------------------------------------------------------------------
# handle_destroy()
# ---------------------------------------------------------------------------


class TestHandleDestroy:
    """handle_destroy() calls lcc.destroy and returns correct exit codes."""

    def test_returns_0_on_success(self) -> None:
        """handle_destroy() returns 0 when lcc.destroy succeeds."""
        from ember_aws._cli_handlers_control import handle_destroy

        lcc = MagicMock()
        lcc.destroy.return_value = None
        factory = _make_factory(lcc=lcc)
        args = _make_args(confirm="default")

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_destroy(args, factory)

        assert result == 0

    def test_returns_exit_code_from_system_exit(self) -> None:
        """handle_destroy() returns the SystemExit code."""
        from ember_aws._cli_handlers_control import handle_destroy

        lcc = MagicMock()
        lcc.destroy.side_effect = SystemExit(3)
        factory = _make_factory(lcc=lcc)
        args = _make_args(confirm="wrong")

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_destroy(args, factory)

        assert result == 3

    def test_returns_2_on_generic_exception(self) -> None:
        """handle_destroy() returns 2 on unexpected exceptions."""
        from ember_aws._cli_handlers_control import handle_destroy

        lcc = MagicMock()
        lcc.destroy.side_effect = RuntimeError("unexpected")
        factory = _make_factory(lcc=lcc)
        args = _make_args(confirm="default")

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_destroy(args, factory)

        assert result == 2


# ---------------------------------------------------------------------------
# handle_replace()
# ---------------------------------------------------------------------------


class TestHandleReplace:
    """handle_replace() calls lc.replace and returns correct exit codes."""

    def test_returns_0_on_success(self) -> None:
        """handle_replace() returns 0 when lc.replace succeeds."""
        from ember_aws._cli_handlers_control import handle_replace

        lc = MagicMock()
        lc.replace.return_value = None
        factory = _make_factory(lc=lc)
        args = _make_args()

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_replace(args, factory)

        assert result == 0

    def test_returns_exit_code_from_system_exit(self) -> None:
        """handle_replace() returns the SystemExit code."""
        from ember_aws._cli_handlers_control import handle_replace

        lc = MagicMock()
        lc.replace.side_effect = SystemExit(1)
        factory = _make_factory(lc=lc)
        args = _make_args()

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_replace(args, factory)

        assert result == 1

    def test_returns_2_on_generic_exception(self) -> None:
        """handle_replace() returns 2 on unexpected exceptions."""
        from ember_aws._cli_handlers_control import handle_replace

        lc = MagicMock()
        lc.replace.side_effect = RuntimeError("unexpected")
        factory = _make_factory(lc=lc)
        args = _make_args()

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (MagicMock(), MagicMock())
            result = handle_replace(args, factory)

        assert result == 2


# ---------------------------------------------------------------------------
# handle_verify()
# ---------------------------------------------------------------------------


class TestHandleVerify:
    """handle_verify() reads SSM config and calls remote.verify."""

    def test_returns_2_when_parameter_not_found(self) -> None:
        """handle_verify() returns 2 with actionable message when SSM param is
        missing."""
        from botocore.exceptions import ClientError

        from ember_aws._cli_handlers_control import handle_verify

        clients = MagicMock()
        clients.ssm.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "not found"}},
            "GetParameter",
        )
        factory = _make_factory()

        args = _make_args()

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (clients, MagicMock())
            result = handle_verify(args, factory)

        assert result == 2

    def test_returns_2_on_generic_exception(self) -> None:
        """handle_verify() returns 2 on unexpected exceptions."""
        from ember_aws._cli_handlers_control import handle_verify

        clients = MagicMock()
        clients.ssm.get_parameter.side_effect = RuntimeError("unexpected")
        factory = _make_factory()
        args = _make_args()

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale"
        ) as mock_ct:
            mock_ct.return_value = (clients, MagicMock())
            result = handle_verify(args, factory)

        assert result == 2


# ---------------------------------------------------------------------------
# _is_parameter_not_found()
# ---------------------------------------------------------------------------


class TestIsParameterNotFound:
    """_is_parameter_not_found() correctly identifies ParameterNotFound errors."""

    def test_returns_true_for_parameter_not_found(self) -> None:
        """Returns True for a ParameterNotFound ClientError."""
        from botocore.exceptions import ClientError

        from ember_aws._cli_handlers_control import _is_parameter_not_found

        exc = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "not found"}},
            "GetParameter",
        )
        assert _is_parameter_not_found(exc) is True

    def test_returns_false_for_other_client_error(self) -> None:
        """Returns False for a non-ParameterNotFound ClientError."""
        from botocore.exceptions import ClientError

        from ember_aws._cli_handlers_control import _is_parameter_not_found

        exc = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "access denied"}},
            "GetParameter",
        )
        assert _is_parameter_not_found(exc) is False

    def test_returns_false_for_non_client_error(self) -> None:
        """Returns False for non-ClientError exceptions."""
        from ember_aws._cli_handlers_control import _is_parameter_not_found

        assert _is_parameter_not_found(ValueError("not a client error")) is False
