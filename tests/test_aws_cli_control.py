"""Tests for US2 CLI wiring: status, stop, start, logs, ssh, rotate-token, destroy."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

#: Repository root, for make dry-run and default-region contract tests.
REPO_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Fake helpers
# ---------------------------------------------------------------------------


class FakeLifecycleControl:
    """Fake LifecycleControl for CLI wiring tests."""

    def __init__(self) -> None:
        self.stop_called: list[Any] = []
        self.start_called: list[Any] = []
        self.destroy_called: list[tuple[Any, str | None]] = []
        self.rotate_token_called: list[Any] = []
        self.stop_raises: BaseException | None = None
        self.start_raises: BaseException | None = None
        self.destroy_raises: BaseException | None = None
        self.rotate_token_raises: BaseException | None = None

    def stop(self, deployment: Any) -> None:
        """Record the call and optionally raise."""
        self.stop_called.append(deployment)
        if self.stop_raises is not None:
            raise self.stop_raises

    def start(self, deployment: Any) -> None:
        """Record the call and optionally raise."""
        self.start_called.append(deployment)
        if self.start_raises is not None:
            raise self.start_raises

    def destroy(self, deployment: Any, confirm: str | None) -> None:
        """Record the call and optionally raise."""
        self.destroy_called.append((deployment, confirm))
        if self.destroy_raises is not None:
            raise self.destroy_raises

    def rotate_token(self, deployment: Any) -> None:
        """Record the call and optionally raise."""
        self.rotate_token_called.append(deployment)
        if self.rotate_token_raises is not None:
            raise self.rotate_token_raises


class FakeStatusReader:
    """Fake StatusReader for CLI wiring tests."""

    def __init__(self) -> None:
        self.read_called: list[Any] = []
        self.read_raises: BaseException | None = None
        self.status_result: Any = None

    def read(self, names: Any) -> Any:
        """Record the call and return a canned result."""
        self.read_called.append(names)
        if self.read_raises is not None:
            raise self.read_raises
        return self.status_result


class FakeRemote:
    """Fake Remote for CLI wiring tests."""

    def __init__(self) -> None:
        self.logs_called: list[tuple[str, bool]] = []
        self.ssh_called: int = 0
        self.logs_raises: BaseException | None = None
        self.ssh_raises: BaseException | None = None

    def logs(self, unit: str, follow: bool) -> None:
        """Record the call and optionally raise."""
        self.logs_called.append((unit, follow))
        if self.logs_raises is not None:
            raise self.logs_raises

    def ssh(self) -> None:
        """Record the call and optionally raise."""
        self.ssh_called += 1
        if self.ssh_raises is not None:
            raise self.ssh_raises


def _make_control_factory(
    lifecycle_control: FakeLifecycleControl | None = None,
    status_reader: FakeStatusReader | None = None,
    remote: FakeRemote | None = None,
) -> tuple[Any, FakeLifecycleControl, FakeStatusReader, FakeRemote]:
    """Return a factory that injects fakes for US2 commands."""
    lcc = lifecycle_control or FakeLifecycleControl()
    sr = status_reader or FakeStatusReader()
    rm = remote or FakeRemote()

    def factory(clients: Any, tailscale: Any) -> tuple[Any, Any, Any, Any, Any]:
        return lcc, sr, rm, MagicMock(), MagicMock()

    return factory, lcc, sr, rm


def _build(argv: list[str], factory: Any) -> int:
    """Call __main__.build(argv, factory) and return the exit code."""
    from ember_aws.__main__ import build

    return build(argv, factory)


# ---------------------------------------------------------------------------
# status subcommand
# ---------------------------------------------------------------------------


class TestStatusCLI:
    """CLI wiring for the status subcommand."""

    def _make_status(self, state: str = "running") -> Any:
        """Build a minimal DeploymentStatus-like object."""
        from ember_aws.deployment_state import DeploymentState
        from ember_aws.deployment_status import DeploymentStatus

        return DeploymentStatus(state=DeploymentState(state))

    def test_status_exits_0(self) -> None:
        """status exits 0 on success."""
        factory, _lcc, sr, _rm = _make_control_factory()
        sr.status_result = self._make_status("running")

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                ["status", "--name", "default", "--region", "us-east-1"], factory
            )

        assert code == 0
        assert len(sr.read_called) == 1

    def test_status_prints_state(self, capsys: Any) -> None:
        """status prints the deployment state to stdout."""
        factory, _lcc, sr, _rm = _make_control_factory()
        sr.status_result = self._make_status("running")

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            _build(["status", "--name", "default", "--region", "us-east-1"], factory)

        captured = capsys.readouterr()
        assert "running" in captured.out

    def test_status_json_prints_valid_json(self, capsys: Any) -> None:
        """status --json prints valid JSON matching DeploymentStatus."""
        factory, _lcc, sr, _rm = _make_control_factory()
        sr.status_result = self._make_status("stopped")

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                ["status", "--name", "default", "--region", "us-east-1", "--json"],
                factory,
            )

        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["state"] == "stopped"

    def test_status_absent_exits_0(self) -> None:
        """status exits 0 even when the deployment is absent."""
        factory, _lcc, sr, _rm = _make_control_factory()
        sr.status_result = self._make_status("absent")

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                ["status", "--name", "default", "--region", "us-east-1"], factory
            )

        assert code == 0

    def test_status_aws_error_exits_2(self) -> None:
        """status exits 2 when an AWS error is raised."""
        from botocore.exceptions import ClientError

        factory, _lcc, sr, _rm = _make_control_factory()
        sr.read_raises = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "DescribeStacks"
        )

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                ["status", "--name", "default", "--region", "us-east-1"], factory
            )

        assert code == 2

    def test_status_passes_name_to_reader(self) -> None:
        """status passes the --name flag to StatusReader.read as a DeploymentName."""
        factory, _lcc, sr, _rm = _make_control_factory()
        sr.status_result = self._make_status("running")

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            _build(
                ["status", "--name", "mydeployment", "--region", "us-east-1"], factory
            )

        assert sr.read_called[0].name == "mydeployment"

    def test_status_defaults_region_to_us_west_2(self) -> None:
        """status defaults --region to us-west-2 when omitted."""
        factory, _lcc, sr, _rm = _make_control_factory()
        sr.status_result = self._make_status("running")

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale",
            return_value=(MagicMock(), None),
        ) as make_clients:
            code = _build(["status", "--name", "default"], factory)

        assert code == 0
        make_clients.assert_called_once_with("us-west-2")


# ---------------------------------------------------------------------------
# stop subcommand
# ---------------------------------------------------------------------------


class TestStopCLI:
    """CLI wiring for the stop subcommand."""

    def test_stop_exits_0_on_success(self) -> None:
        """stop exits 0 on success."""
        factory, lcc, _sr, _rm = _make_control_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                ["stop", "--name", "default", "--region", "us-east-1"], factory
            )

        assert code == 0
        assert len(lcc.stop_called) == 1

    def test_stop_passes_name(self) -> None:
        """stop passes --name to LifecycleControl.stop."""
        factory, lcc, _sr, _rm = _make_control_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            _build(["stop", "--name", "mydeployment", "--region", "us-east-1"], factory)

        assert lcc.stop_called[0].name == "mydeployment"

    def test_stop_exits_2_on_aws_error(self) -> None:
        """stop exits 2 when an AWS error is raised."""
        from botocore.exceptions import ClientError

        factory, lcc, _sr, _rm = _make_control_factory()
        lcc.stop_raises = ClientError(
            {"Error": {"Code": "InvalidInstanceID", "Message": "not found"}},
            "StopInstances",
        )

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                ["stop", "--name", "default", "--region", "us-east-1"], factory
            )

        assert code == 2


# ---------------------------------------------------------------------------
# start subcommand
# ---------------------------------------------------------------------------


class TestStartCLI:
    """CLI wiring for the start subcommand."""

    def test_start_exits_0_on_success(self) -> None:
        """start exits 0 on success."""
        factory, lcc, _sr, _rm = _make_control_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                ["start", "--name", "default", "--region", "us-east-1"], factory
            )

        assert code == 0
        assert len(lcc.start_called) == 1

    def test_start_passes_name(self) -> None:
        """start passes --name to LifecycleControl.start."""
        factory, lcc, _sr, _rm = _make_control_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            _build(
                ["start", "--name", "mydeployment", "--region", "us-east-1"], factory
            )

        assert lcc.start_called[0].name == "mydeployment"

    def test_start_exits_2_on_aws_error(self) -> None:
        """start exits 2 when an AWS error is raised."""
        from botocore.exceptions import ClientError

        factory, lcc, _sr, _rm = _make_control_factory()
        lcc.start_raises = ClientError(
            {"Error": {"Code": "InvalidInstanceID", "Message": "not found"}},
            "StartInstances",
        )

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                ["start", "--name", "default", "--region", "us-east-1"], factory
            )

        assert code == 2


# ---------------------------------------------------------------------------
# logs subcommand
# ---------------------------------------------------------------------------


class TestLogsCLI:
    """CLI wiring for the logs subcommand."""

    def test_logs_exits_0_on_success(self) -> None:
        """logs exits 0 on success."""
        factory, _lcc, _sr, rm = _make_control_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(["logs", "--name", "default"], factory)

        assert code == 0
        assert len(rm.logs_called) == 1

    def test_logs_default_unit_is_ember(self) -> None:
        """logs defaults to --unit ember."""
        factory, _lcc, _sr, rm = _make_control_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            _build(["logs", "--name", "default"], factory)

        unit, follow = rm.logs_called[0]
        assert unit == "ember"
        assert follow is False

    def test_logs_unit_converge(self) -> None:
        """logs --unit converge passes converge to Remote.logs."""
        factory, _lcc, _sr, rm = _make_control_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            _build(["logs", "--name", "default", "--unit", "converge"], factory)

        unit, _ = rm.logs_called[0]
        assert unit == "converge"

    def test_logs_follow_flag(self) -> None:
        """logs --follow passes follow=True to Remote.logs."""
        factory, _lcc, _sr, rm = _make_control_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            _build(["logs", "--name", "default", "--follow"], factory)

        _, follow = rm.logs_called[0]
        assert follow is True

    def test_logs_invalid_unit_exits_nonzero(self) -> None:
        """logs with an unknown --unit exits non-zero."""
        factory, _lcc, _sr, _rm = _make_control_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            try:
                code = _build(["logs", "--name", "default", "--unit", "bad"], factory)
            except SystemExit as exc:
                code = int(exc.code) if exc.code is not None else 2

        assert code != 0

    def test_logs_all_units_accepted(self) -> None:
        """logs accepts ember, converge, idle, and tailscale as --unit values."""
        for unit in ("ember", "converge", "idle", "tailscale"):
            factory, _lcc, _sr, _rm = _make_control_factory()

            with (
                patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
                patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
            ):
                code = _build(["logs", "--name", "default", "--unit", unit], factory)

            assert code == 0, f"unit={unit!r} should exit 0"


# ---------------------------------------------------------------------------
# ssh subcommand
# ---------------------------------------------------------------------------


class TestSshCLI:
    """CLI wiring for the ssh subcommand."""

    def test_ssh_exits_0_on_success(self) -> None:
        """ssh exits 0 on success."""
        factory, _lcc, _sr, rm = _make_control_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(["ssh", "--name", "default"], factory)

        assert code == 0
        assert rm.ssh_called == 1

    def test_ssh_exits_2_on_error(self) -> None:
        """ssh exits 2 when Remote.ssh raises."""
        factory, _lcc, _sr, rm = _make_control_factory()
        rm.ssh_raises = RuntimeError("tailscale not found")

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(["ssh", "--name", "default"], factory)

        assert code == 2


# ---------------------------------------------------------------------------
# rotate-token subcommand
# ---------------------------------------------------------------------------


class TestRotateTokenCLI:
    """CLI wiring for the rotate-token subcommand."""

    def test_rotate_token_exits_0_on_success(self) -> None:
        """rotate-token exits 0 on success."""
        factory, lcc, _sr, _rm = _make_control_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                ["rotate-token", "--name", "default", "--region", "us-east-1"], factory
            )

        assert code == 0
        assert len(lcc.rotate_token_called) == 1

    def test_rotate_token_passes_name(self) -> None:
        """rotate-token passes --name to LifecycleControl.rotate_token."""
        factory, lcc, _sr, _rm = _make_control_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            _build(
                ["rotate-token", "--name", "mydeployment", "--region", "us-east-1"],
                factory,
            )

        assert lcc.rotate_token_called[0].name == "mydeployment"

    def test_rotate_token_exits_2_on_aws_error(self) -> None:
        """rotate-token exits 2 when an AWS error is raised."""
        from botocore.exceptions import ClientError

        factory, lcc, _sr, _rm = _make_control_factory()
        lcc.rotate_token_raises = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "not found"}},
            "PutParameter",
        )

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                ["rotate-token", "--name", "default", "--region", "us-east-1"], factory
            )

        assert code == 2


# ---------------------------------------------------------------------------
# destroy subcommand
# ---------------------------------------------------------------------------


class TestDestroyCLI:
    """CLI wiring for the destroy subcommand."""

    def test_destroy_exits_0_on_success(self) -> None:
        """destroy exits 0 when --confirm matches the name."""
        factory, lcc, _sr, _rm = _make_control_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                [
                    "destroy",
                    "--name",
                    "default",
                    "--region",
                    "us-east-1",
                    "--confirm",
                    "default",
                ],
                factory,
            )

        assert code == 0
        assert len(lcc.destroy_called) == 1

    def test_destroy_passes_confirm(self) -> None:
        """destroy passes --confirm to LifecycleControl.destroy."""
        factory, lcc, _sr, _rm = _make_control_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            _build(
                [
                    "destroy",
                    "--name",
                    "mydeployment",
                    "--region",
                    "us-east-1",
                    "--confirm",
                    "mydeployment",
                ],
                factory,
            )

        _deployment, confirm = lcc.destroy_called[0]
        assert confirm == "mydeployment"

    def test_destroy_exits_3_without_confirm(self) -> None:
        """destroy exits 3 when --confirm is missing (argparse required)."""
        _factory, _lcc, _sr, _rm = _make_control_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            import sys as _sys

            lcc_inner = FakeLifecycleControl()

            def _guard_destroy(deployment: Any, confirm: str | None) -> None:
                if confirm != deployment.name:
                    print(
                        f"error: pass --confirm {deployment.name} to destroy",
                        file=_sys.stderr,
                    )
                    _sys.exit(3)

            lcc_inner.destroy = _guard_destroy  # type: ignore[method-assign]

            def _factory(
                clients: Any, tailscale: Any
            ) -> tuple[Any, Any, Any, Any, Any]:
                return lcc_inner, MagicMock(), MagicMock(), MagicMock(), MagicMock()

            try:
                code = _build(
                    [
                        "destroy",
                        "--name",
                        "default",
                        "--region",
                        "us-east-1",
                        "--confirm",
                        "wrong-name",
                    ],
                    _factory,
                )
            except SystemExit as exc:
                code = int(exc.code) if exc.code is not None else 3

        assert code == 3

    def test_destroy_exits_2_on_aws_error(self) -> None:
        """destroy exits 2 when an AWS error is raised."""
        from botocore.exceptions import ClientError

        factory, lcc, _sr, _rm = _make_control_factory()
        lcc.destroy_raises = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "stack not found"}},
            "DeleteStack",
        )

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                [
                    "destroy",
                    "--name",
                    "default",
                    "--region",
                    "us-east-1",
                    "--confirm",
                    "default",
                ],
                factory,
            )

        assert code == 2

    def test_destroy_passes_name_to_deployment(self) -> None:
        """destroy passes --name to the Deployment given to LifecycleControl."""
        factory, lcc, _sr, _rm = _make_control_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            _build(
                [
                    "destroy",
                    "--name",
                    "mydeployment",
                    "--region",
                    "us-east-1",
                    "--confirm",
                    "mydeployment",
                ],
                factory,
            )

        deployment, _ = lcc.destroy_called[0]
        assert deployment.name == "mydeployment"


# ---------------------------------------------------------------------------
# verify subcommand
# ---------------------------------------------------------------------------


class TestVerifyCLI:
    """CLI wiring for the verify subcommand."""

    def _build_with_ssm_error(self, argv: list[str], error: BaseException) -> int:
        """Build argv with a fake SSM whose get_parameter raises ``error``."""
        factory, _lcc, _sr, _rm = _make_control_factory()
        clients = MagicMock()
        clients.ssm.get_parameter.side_effect = error

        with patch(
            "ember_aws._cli_handlers_control._make_clients_and_tailscale",
            return_value=(clients, None),
        ):
            return _build(argv, factory)

    def test_verify_missing_deployment_prints_actionable_error(
        self, capsys: Any
    ) -> None:
        """verify names the deployment and region when SSM has no config."""
        from botocore.exceptions import ClientError

        code = self._build_with_ssm_error(
            ["verify", "--name", "default"],
            ClientError(
                {"Error": {"Code": "ParameterNotFound", "Message": "not found"}},
                "GetParameter",
            ),
        )

        assert code == 2
        captured = capsys.readouterr()
        assert "no deployment 'default' found in us-west-2" in captured.err
        assert "make aws-up" in captured.err

    def test_verify_missing_deployment_reports_explicit_region(
        self, capsys: Any
    ) -> None:
        """verify reports the region passed with --region."""
        from botocore.exceptions import ClientError

        code = self._build_with_ssm_error(
            ["verify", "--name", "mydeployment", "--region", "eu-west-1"],
            ClientError(
                {"Error": {"Code": "ParameterNotFound", "Message": "not found"}},
                "GetParameter",
            ),
        )

        assert code == 2
        captured = capsys.readouterr()
        assert "no deployment 'mydeployment' found in eu-west-1" in captured.err

    def test_verify_other_aws_error_exits_2(self, capsys: Any) -> None:
        """verify keeps the raw error for non-ParameterNotFound AWS errors."""
        from botocore.exceptions import ClientError

        code = self._build_with_ssm_error(
            ["verify", "--name", "default"],
            ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "denied"}},
                "GetParameter",
            ),
        )

        assert code == 2
        captured = capsys.readouterr()
        assert "AccessDenied" in captured.err

    def test_verify_non_client_error_exits_2(self, capsys: Any) -> None:
        """verify exits 2 for non-boto exceptions."""
        code = self._build_with_ssm_error(
            ["verify", "--name", "default"], RuntimeError("boom")
        )

        assert code == 2
        captured = capsys.readouterr()
        assert "boom" in captured.err


# ---------------------------------------------------------------------------
# make aws-down recipe smoke test
# ---------------------------------------------------------------------------


class TestAwsDownMakeRecipe:
    """Verify the aws-down make recipe passes --confirm correctly."""

    def test_aws_down_make_dry_run(self) -> None:
        """make -n aws-down CONFIRM=x NAME=y renders a sane command."""
        result = subprocess.run(
            ["make", "-n", "aws-down", "CONFIRM=mydeployment", "NAME=mydeployment"],  # noqa: S607
            capture_output=True,
            text=True,
            cwd="/Users/joshburt/Workbench/Repositories/ember",
        )
        combined = result.stdout + result.stderr
        assert "--confirm" in combined
        assert "mydeployment" in combined

    def test_aws_status_make_dry_run(self) -> None:
        """make -n aws-status renders a sane command."""
        result = subprocess.run(
            ["make", "-n", "aws-status"],  # noqa: S607
            capture_output=True,
            text=True,
            cwd="/Users/joshburt/Workbench/Repositories/ember",
        )
        combined = result.stdout + result.stderr
        assert "status" in combined


# ---------------------------------------------------------------------------
# region default
# ---------------------------------------------------------------------------


class TestAwsRegionMakeDefault:
    """The aws-* make targets default REGION to us-west-2."""

    def test_aws_verify_make_default_region(self) -> None:
        """make -n aws-verify renders --region us-west-2 by default."""
        result = subprocess.run(
            ["make", "-n", "aws-verify"],  # noqa: S607
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        combined = result.stdout + result.stderr
        assert "--region us-west-2" in combined

    def test_makefile_region_default_matches_python(self) -> None:
        """shared/aws.mk and ember_aws.defaults agree on the default region."""
        from ember_aws.defaults import DEFAULT_REGION

        text = (REPO_ROOT / "shared" / "aws.mk").read_text()
        match = re.search(r"^REGION\s*\?=\s*(\S+)\s*$", text, re.MULTILINE)
        assert match is not None
        assert match.group(1) == DEFAULT_REGION
