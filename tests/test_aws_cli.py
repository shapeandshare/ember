"""Tests for __main__.py argparse wiring and exit-code mapping (T031)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Fake factory / lifecycle / model_cache
# ---------------------------------------------------------------------------


class FakeLifecycle:
    """Fake Lifecycle for CLI wiring tests."""

    def __init__(self) -> None:
        self.deploy_called: list[Any] = []
        self.token_called: list[Any] = []
        self.deploy_raises: BaseException | None = None
        self.token_raises: BaseException | None = None
        self.token_value: str = "fake-token"

    def deploy(self, deployment: Any) -> None:
        """Record the call and optionally raise."""
        self.deploy_called.append(deployment)
        if self.deploy_raises is not None:
            raise self.deploy_raises

    def token(self, deployment: Any) -> None:
        """Record the call and optionally raise."""
        self.token_called.append(deployment)
        if self.token_raises is not None:
            raise self.token_raises
        print(self.token_value)


class FakeModelCache:
    """Fake ModelCache for CLI wiring tests."""

    def __init__(self) -> None:
        self.add_called: list[Any] = []
        self.list_called: int = 0
        self.remove_called: list[Any] = []
        self.destroy_called: list[Any] = []
        self.add_raises: BaseException | None = None
        self.list_raises: BaseException | None = None
        self.remove_raises: BaseException | None = None
        self.destroy_raises: BaseException | None = None
        self.list_result: list[Any] = []

    def add(
        self, model: str, bucket: str | None = None, prefix: str = "models/"
    ) -> None:
        self.add_called.append((model, bucket, prefix))
        if self.add_raises is not None:
            raise self.add_raises

    def list(self, bucket: str | None = None, prefix: str = "models/") -> list[Any]:
        self.list_called += 1
        if self.list_raises is not None:
            raise self.list_raises
        return self.list_result

    def remove(
        self,
        model: str,
        revision: str,
        bucket: str | None = None,
        prefix: str = "models/",
    ) -> None:
        self.remove_called.append((model, revision))
        if self.remove_raises is not None:
            raise self.remove_raises

    def destroy(self, confirm: str, bucket: str | None = None) -> None:
        self.destroy_called.append(confirm)
        if self.destroy_raises is not None:
            raise self.destroy_raises


class FakePreflight:
    """Fake Preflight for CLI wiring tests."""

    def __init__(self) -> None:
        self.run_called: list[Any] = []
        self.run_raises: BaseException | None = None
        self.results: list[Any] = []

    def run(self, deployment: Any) -> list[Any]:
        self.run_called.append(deployment)
        if self.run_raises is not None:
            raise self.run_raises
        return self.results


def _make_factory(
    lifecycle: FakeLifecycle | None = None,
    model_cache: FakeModelCache | None = None,
    preflight: FakePreflight | None = None,
) -> Any:
    """Return a factory callable that injects fakes.

    The factory returns a 5-tuple matching the extended factory contract:
    ``(lifecycle_control, status_reader, remote, lifecycle, model_cache)``.
    The ``preflight`` fake is stored on the lifecycle fake so handlers can
    reach it via ``_lc._preflight``.
    """
    from unittest.mock import MagicMock

    lc = lifecycle or FakeLifecycle()
    mc = model_cache or FakeModelCache()
    pf = preflight or FakePreflight()
    # Attach preflight to lifecycle so handle_preflight can find it.
    lc._preflight = pf  # type: ignore[attr-defined]

    def factory(
        clients: Any, tailscale: Any, name: Any = None
    ) -> tuple[Any, Any, Any, Any, Any]:
        return MagicMock(), MagicMock(), MagicMock(), lc, mc

    return factory, lc, mc, pf


# ---------------------------------------------------------------------------
# Import the build() seam
# ---------------------------------------------------------------------------


def _build(argv: list[str], factory: Any) -> int:
    """Call __main__.build(argv, factory) and return the exit code."""
    from ember_aws.__main__ import build

    return build(argv, factory)


# ---------------------------------------------------------------------------
# preflight subcommand
# ---------------------------------------------------------------------------


class TestPreflightCLI:
    """CLI wiring for the preflight subcommand."""

    def test_preflight_ok_exits_0(self, monkeypatch: Any) -> None:
        """preflight with all checks passing exits 0."""
        factory, _lc, _mc, pf = _make_factory()
        pf.results = []  # no failures

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                [
                    "preflight",
                    "--name",
                    "default",
                    "--region",
                    "us-east-1",
                    "--model",
                    "flash",
                ],
                factory,
            )

        assert code == 0

    def test_preflight_failure_exits_1(self, monkeypatch: Any) -> None:
        """preflight with a blocking failure exits 1."""
        from ember_aws.check_result import CheckResult
        from ember_aws.preflight_check import PreflightCheck

        factory, _lc, _mc, pf = _make_factory()
        pf.results = [
            CheckResult(
                check=PreflightCheck.AWS_IDENTITY,
                ok=False,
                problem="no credentials",
                fix="aws sso login",
                blocking=True,
            )
        ]

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                [
                    "preflight",
                    "--name",
                    "default",
                    "--region",
                    "us-east-1",
                    "--model",
                    "flash",
                ],
                factory,
            )

        assert code == 1

    def test_preflight_prints_failure_line(self, monkeypatch: Any, capsys: Any) -> None:
        """preflight prints '✗ <check>: <problem> — fix: <action>' for failures."""
        from ember_aws.check_result import CheckResult
        from ember_aws.preflight_check import PreflightCheck

        factory, _lc, _mc, pf = _make_factory()
        pf.results = [
            CheckResult(
                check=PreflightCheck.AWS_IDENTITY,
                ok=False,
                problem="no credentials",
                fix="aws sso login",
                blocking=True,
            )
        ]

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            _build(
                [
                    "preflight",
                    "--name",
                    "default",
                    "--region",
                    "us-east-1",
                    "--model",
                    "flash",
                ],
                factory,
            )

        captured = capsys.readouterr()
        assert "✗" in captured.out
        assert "aws-identity" in captured.out
        assert "no credentials" in captured.out
        assert "aws sso login" in captured.out


# ---------------------------------------------------------------------------
# cache subcommand
# ---------------------------------------------------------------------------


class TestCacheCLI:
    """CLI wiring for the cache subcommand."""

    def test_cache_add_exits_0(self, monkeypatch: Any) -> None:
        """cache add exits 0 on success."""
        factory, _lc, mc, _pf = _make_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                ["cache", "add", "--model", "flash", "--region", "us-east-1"], factory
            )

        assert code == 0
        assert len(mc.add_called) == 1

    def test_cache_add_passes_model(self, monkeypatch: Any) -> None:
        """cache add passes the --model flag to ModelCache.add."""
        factory, _lc, mc, _pf = _make_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            _build(
                ["cache", "add", "--model", "flash", "--region", "us-east-1"], factory
            )

        assert mc.add_called[0][0] == "flash"

    def test_cache_add_with_bucket_and_prefix(self, monkeypatch: Any) -> None:
        """cache add passes --bucket and --prefix to ModelCache.add."""
        factory, _lc, mc, _pf = _make_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            _build(
                [
                    "cache",
                    "add",
                    "--model",
                    "flash",
                    "--region",
                    "us-east-1",
                    "--bucket",
                    "my-bucket",
                    "--prefix",
                    "custom/",
                ],
                factory,
            )

        assert mc.add_called[0][1] == "my-bucket"
        assert mc.add_called[0][2] == "custom/"

    def test_cache_list_exits_0(self, monkeypatch: Any) -> None:
        """cache list exits 0."""
        factory, _lc, mc, _pf = _make_factory()
        mc.list_result = [{"model": "flash", "revision": "abc", "status": "complete"}]

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(["cache", "list", "--region", "us-east-1"], factory)

        assert code == 0

    def test_cache_rm_exits_0(self, monkeypatch: Any) -> None:
        """cache rm exits 0 on success."""
        factory, _lc, mc, _pf = _make_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                [
                    "cache",
                    "rm",
                    "--model",
                    "flash",
                    "--revision",
                    "abc123",
                    "--region",
                    "us-east-1",
                ],
                factory,
            )

        assert code == 0
        assert mc.remove_called[0] == ("flash", "abc123")

    def test_cache_rm_exits_3_when_in_use(self, monkeypatch: Any) -> None:
        """cache rm exits 3 when CacheInUseError is raised."""
        from ember_aws.model_cache import CacheInUseError

        factory, _lc, mc, _pf = _make_factory()
        mc.remove_raises = CacheInUseError("deployment uses it")

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                [
                    "cache",
                    "rm",
                    "--model",
                    "flash",
                    "--revision",
                    "abc123",
                    "--region",
                    "us-east-1",
                ],
                factory,
            )

        assert code == 3

    def test_cache_destroy_exits_0(self, monkeypatch: Any) -> None:
        """cache destroy exits 0 on success."""
        factory, _lc, mc, _pf = _make_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                ["cache", "destroy", "--confirm", "my-bucket", "--region", "us-east-1"],
                factory,
            )

        assert code == 0
        assert mc.destroy_called[0] == "my-bucket"

    def test_cache_destroy_exits_3_when_in_use(self, monkeypatch: Any) -> None:
        """cache destroy exits 3 when CacheInUseError is raised."""
        from ember_aws.model_cache import CacheInUseError

        factory, _lc, mc, _pf = _make_factory()
        mc.destroy_raises = CacheInUseError("deployment exists")

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                ["cache", "destroy", "--confirm", "my-bucket", "--region", "us-east-1"],
                factory,
            )

        assert code == 3


# ---------------------------------------------------------------------------
# deploy subcommand
# ---------------------------------------------------------------------------


class TestDeployCLI:
    """CLI wiring for the deploy subcommand."""

    def test_deploy_exits_0_on_success(self, monkeypatch: Any) -> None:
        """deploy exits 0 on success."""
        factory, lc, _mc, _pf = _make_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                [
                    "deploy",
                    "--name",
                    "default",
                    "--region",
                    "us-east-1",
                    "--model",
                    "flash",
                ],
                factory,
            )

        assert code == 0
        assert len(lc.deploy_called) == 1

    def test_deploy_passes_name_and_model(self, monkeypatch: Any) -> None:
        """deploy passes --name and --model to Lifecycle.deploy."""
        factory, lc, _mc, _pf = _make_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            _build(
                [
                    "deploy",
                    "--name",
                    "mydeployment",
                    "--region",
                    "us-east-1",
                    "--model",
                    "flash",
                ],
                factory,
            )

        assert lc.deploy_called[0].name == "mydeployment"
        assert lc.deploy_called[0].model == "flash"

    def test_deploy_exits_1_on_validation_error(self, monkeypatch: Any) -> None:
        """deploy exits 1 when a validation/preflight error is raised."""
        from ember_aws.sizing_table import SizingError

        factory, lc, _mc, _pf = _make_factory()
        lc.deploy_raises = SizingError("unsupported instance type")

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                [
                    "deploy",
                    "--name",
                    "default",
                    "--region",
                    "us-east-1",
                    "--model",
                    "flash",
                ],
                factory,
            )

        assert code == 1

    def test_deploy_exits_2_on_stack_error(self, monkeypatch: Any) -> None:
        """deploy exits 2 when a StackDeployError is raised."""
        from ember_aws.lifecycle import StackDeployError

        factory, lc, _mc, _pf = _make_factory()
        lc.deploy_raises = StackDeployError("stack failed")

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                [
                    "deploy",
                    "--name",
                    "default",
                    "--region",
                    "us-east-1",
                    "--model",
                    "flash",
                ],
                factory,
            )

        assert code == 2

    def test_deploy_defaults_region_to_us_west_2(self, monkeypatch: Any) -> None:
        """deploy defaults --region to us-west-2 when omitted."""
        factory, lc, _mc, _pf = _make_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(["deploy", "--name", "default", "--model", "flash"], factory)

        assert code == 0
        assert lc.deploy_called[0].region == "us-west-2"

    def test_deploy_passes_instance_type(self, monkeypatch: Any) -> None:
        """deploy passes --instance-type to Lifecycle.deploy."""
        factory, lc, _mc, _pf = _make_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            _build(
                [
                    "deploy",
                    "--name",
                    "default",
                    "--region",
                    "us-east-1",
                    "--model",
                    "flash",
                    "--instance-type",
                    "g6e.xlarge",
                ],
                factory,
            )

        assert lc.deploy_called[0].instance_type == "g6e.xlarge"

    def test_deploy_passes_capacity(self, monkeypatch: Any) -> None:
        """deploy passes --capacity to Lifecycle.deploy."""
        factory, lc, _mc, _pf = _make_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            _build(
                [
                    "deploy",
                    "--name",
                    "default",
                    "--region",
                    "us-east-1",
                    "--model",
                    "flash",
                    "--capacity",
                    "spot",
                ],
                factory,
            )

        assert lc.deploy_called[0].capacity.value == "spot"

    def test_deploy_passes_idle_minutes(self, monkeypatch: Any) -> None:
        """deploy passes --idle-minutes to Lifecycle.deploy."""
        factory, lc, _mc, _pf = _make_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            _build(
                [
                    "deploy",
                    "--name",
                    "default",
                    "--region",
                    "us-east-1",
                    "--model",
                    "flash",
                    "--idle-minutes",
                    "30",
                ],
                factory,
            )

        assert lc.deploy_called[0].idle_minutes == 30


# ---------------------------------------------------------------------------
# token subcommand
# ---------------------------------------------------------------------------


class TestTokenCLI:
    """CLI wiring for the token subcommand."""

    def test_token_exits_0(self, monkeypatch: Any) -> None:
        """token exits 0 on success."""
        factory, lc, _mc, _pf = _make_factory()

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                [
                    "token",
                    "--name",
                    "default",
                    "--region",
                    "us-east-1",
                    "--model",
                    "flash",
                ],
                factory,
            )

        assert code == 0
        assert len(lc.token_called) == 1

    def test_token_exits_2_on_aws_error(self, monkeypatch: Any) -> None:
        """token exits 2 when an AWS error is raised."""
        from botocore.exceptions import ClientError

        factory, lc, _mc, _pf = _make_factory()
        lc.token_raises = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "not found"}},
            "GetParameter",
        )

        with (
            patch("ember_aws.__main__._make_clients", return_value=MagicMock()),
            patch("ember_aws.__main__._make_tailscale", return_value=MagicMock()),
        ):
            code = _build(
                [
                    "token",
                    "--name",
                    "default",
                    "--region",
                    "us-east-1",
                    "--model",
                    "flash",
                ],
                factory,
            )

        assert code == 2
