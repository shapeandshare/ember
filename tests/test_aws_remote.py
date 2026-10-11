"""Unit tests for ember_aws.remote.Remote (T034, T041a)."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from ember_aws.names import DeploymentName
from ember_aws.remote import Remote

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _names(name: str = "default") -> DeploymentName:
    return DeploymentName(name=name)


def _capture_runner() -> tuple[list[Any], MagicMock]:
    """Return (calls, mock_runner) where calls accumulates every argv passed."""
    calls: list[Any] = []

    def runner(argv: list[str], **kwargs: Any) -> None:
        calls.append((argv, kwargs))

    mock = MagicMock(side_effect=runner)
    return calls, mock


# ---------------------------------------------------------------------------
# ssh
# ---------------------------------------------------------------------------


def test_ssh_builds_correct_argv() -> None:
    """ssh() passes ["tailscale","ssh","root@ember-<name>"] to the runner."""
    calls, runner = _capture_runner()
    remote = Remote(_names("default"), runner=runner)

    remote.ssh()

    assert len(calls) == 1
    argv, _kwargs = calls[0]
    assert argv == ["tailscale", "ssh", "root@ember-default"]


def test_ssh_never_uses_shell() -> None:
    """ssh() must never pass shell=True to the runner."""
    calls, runner = _capture_runner()
    remote = Remote(_names("default"), runner=runner)

    remote.ssh()

    _, kwargs = calls[0]
    assert kwargs.get("shell") is not True


def test_ssh_uses_custom_name() -> None:
    """ssh() uses the deployment name from DeploymentName.hostname."""
    calls, runner = _capture_runner()
    remote = Remote(_names("team-a1"), runner=runner)

    remote.ssh()

    argv, _ = calls[0]
    assert argv == ["tailscale", "ssh", "root@ember-team-a1"]


# ---------------------------------------------------------------------------
# logs — unit mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("unit_key", "expected_unit"),
    [
        ("ember", "ember"),
        ("converge", "ember-converge"),
        ("idle", "ember-idle"),
        ("tailscale", "ember-tailscale"),
    ],
)
def test_logs_unit_mapping(unit_key: str, expected_unit: str) -> None:
    """Each --unit key maps to its systemd unit name."""
    calls, runner = _capture_runner()
    remote = Remote(_names("default"), runner=runner)

    remote.logs(unit=unit_key, follow=False)

    argv, _ = calls[0]
    assert "-u" in argv
    idx = argv.index("-u")
    assert argv[idx + 1] == expected_unit


# ---------------------------------------------------------------------------
# logs — full argv
# ---------------------------------------------------------------------------


def test_logs_follow_builds_full_argv() -> None:
    """logs(unit='ember', follow=True) → exact argv from the contract."""
    calls, runner = _capture_runner()
    remote = Remote(_names("default"), runner=runner)

    remote.logs(unit="ember", follow=True)

    argv, _ = calls[0]
    assert argv == [
        "tailscale",
        "ssh",
        "root@ember-default",
        "journalctl",
        "-u",
        "ember",
        "-f",
    ]


def test_logs_no_follow_omits_f_flag() -> None:
    """logs(unit='ember', follow=False) omits the -f flag."""
    calls, runner = _capture_runner()
    remote = Remote(_names("default"), runner=runner)

    remote.logs(unit="ember", follow=False)

    argv, _ = calls[0]
    assert argv == [
        "tailscale",
        "ssh",
        "root@ember-default",
        "journalctl",
        "-u",
        "ember",
    ]
    assert "-f" not in argv


def test_logs_converge_follow() -> None:
    """logs(unit='converge', follow=True) uses ember-converge unit."""
    calls, runner = _capture_runner()
    remote = Remote(_names("default"), runner=runner)

    remote.logs(unit="converge", follow=True)

    argv, _ = calls[0]
    assert argv == [
        "tailscale",
        "ssh",
        "root@ember-default",
        "journalctl",
        "-u",
        "ember-converge",
        "-f",
    ]


def test_logs_never_uses_shell() -> None:
    """logs() must never pass shell=True to the runner."""
    calls, runner = _capture_runner()
    remote = Remote(_names("default"), runner=runner)

    remote.logs(unit="ember", follow=False)

    _, kwargs = calls[0]
    assert kwargs.get("shell") is not True


# ---------------------------------------------------------------------------
# logs — invalid unit rejected
# ---------------------------------------------------------------------------


def test_logs_invalid_unit_raises() -> None:
    """logs() raises ValueError for an unrecognised unit key."""
    _, runner = _capture_runner()
    remote = Remote(_names("default"), runner=runner)

    with pytest.raises(ValueError, match="unknown unit"):
        remote.logs(unit="bogus", follow=False)


def test_logs_invalid_unit_does_not_call_runner() -> None:
    """logs() must not invoke the runner when the unit is invalid."""
    calls, runner = _capture_runner()
    remote = Remote(_names("default"), runner=runner)

    with pytest.raises(ValueError, match="unknown unit"):
        remote.logs(unit="not-a-unit", follow=False)

    assert calls == []


# ---------------------------------------------------------------------------
# Default runner is subprocess.run
# ---------------------------------------------------------------------------


def test_default_runner_is_subprocess_run() -> None:
    """Remote() without an explicit runner defaults to subprocess.run."""
    remote = Remote(_names("default"))
    assert remote._runner is subprocess.run


# ---------------------------------------------------------------------------
# T041a: verify — on-instance and operator-side argv
# ---------------------------------------------------------------------------

_MODEL_S3_URI = "s3://ember-model-cache-123456789012-us-east-1/models/flash/17f0b0a"
_EMBER_VERSION = "0.12.0"
_TAILNET = "example.ts.net"
_SERVER_URL = f"https://ember-default.{_TAILNET}"
_TOKEN = "tok-abc123"


def _uri_hash(uri: str) -> str:
    return hashlib.sha256(uri.encode()).hexdigest()[:16]


def _model_cache_dir(uri: str) -> str:
    return f"/home/ember/.cache/ember/hosted-models/{_uri_hash(uri)}"


def test_verify_on_instance_argv_git_clone() -> None:
    """verify() passes git clone --depth 1 --branch v<version> to tailscale ssh."""
    calls, runner = _capture_runner()
    remote = Remote(_names("default"), runner=runner)

    remote.verify(
        ember_version=_EMBER_VERSION,
        model_s3_uri=_MODEL_S3_URI,
        server_url=_SERVER_URL,
        token=_TOKEN,
    )

    on_instance_calls = [
        argv for argv, _ in calls if "tailscale" in argv[0] and "ember@" in argv[2]
    ]
    assert on_instance_calls, "expected at least one tailscale ssh ember@ call"
    combined = " ".join(on_instance_calls[0])
    assert f"--branch v{_EMBER_VERSION}" in combined
    assert "git clone" in combined
    assert "https://github.com/shapeandshare/ember" in combined


def test_verify_on_instance_command_is_rerunnable() -> None:
    """verify() recreates the checkout, so a second run cannot fail on clone."""
    calls, runner = _capture_runner()
    remote = Remote(_names("default"), runner=runner)

    remote.verify(
        ember_version=_EMBER_VERSION,
        model_s3_uri=_MODEL_S3_URI,
        server_url=_SERVER_URL,
        token=_TOKEN,
    )

    on_instance_calls = [
        argv for argv, _ in calls if "tailscale" in argv[0] and "ember@" in argv[2]
    ]
    assert on_instance_calls
    combined = " ".join(on_instance_calls[0])
    assert "rm -rf /opt/ember-src" in combined
    assert combined.index("rm -rf /opt/ember-src") < combined.index("git clone")


def test_verify_on_instance_links_hosted_cache_for_tests() -> None:
    """verify() links the hosted cache where the checkout's tests look for it."""
    calls, runner = _capture_runner()
    remote = Remote(_names("default"), runner=runner)

    remote.verify(
        ember_version=_EMBER_VERSION,
        model_s3_uri=_MODEL_S3_URI,
        server_url=_SERVER_URL,
        token=_TOKEN,
    )

    on_instance_calls = [
        argv for argv, _ in calls if "tailscale" in argv[0] and "ember@" in argv[2]
    ]
    assert on_instance_calls
    combined = " ".join(on_instance_calls[0])
    cache_dir = _model_cache_dir(_MODEL_S3_URI)
    assert f"ln -sfn {cache_dir} .models/clef-flash" in combined


def test_verify_on_instance_argv_make_test_strict() -> None:
    """verify() includes make test-strict with EMBER_DEVICE=cuda."""
    calls, runner = _capture_runner()
    remote = Remote(_names("default"), runner=runner)

    remote.verify(
        ember_version=_EMBER_VERSION,
        model_s3_uri=_MODEL_S3_URI,
        server_url=_SERVER_URL,
        token=_TOKEN,
    )

    on_instance_calls = [
        argv for argv, _ in calls if "tailscale" in argv[0] and "ember@" in argv[2]
    ]
    assert on_instance_calls
    combined = " ".join(on_instance_calls[0])
    assert "make test-strict" in combined
    assert "EMBER_DEVICE=cuda" in combined
    cache_dir = _model_cache_dir(_MODEL_S3_URI)
    assert f"EMBER_MODEL_DIR={cache_dir}" in combined


def test_verify_on_instance_argv_eval_context_cuda() -> None:
    """verify() includes ember eval context --device cuda in the on-instance command."""
    calls, runner = _capture_runner()
    remote = Remote(_names("default"), runner=runner)

    remote.verify(
        ember_version=_EMBER_VERSION,
        model_s3_uri=_MODEL_S3_URI,
        server_url=_SERVER_URL,
        token=_TOKEN,
    )

    on_instance_calls = [
        argv for argv, _ in calls if "tailscale" in argv[0] and "ember@" in argv[2]
    ]
    assert on_instance_calls
    combined = " ".join(on_instance_calls[0])
    assert "ember eval context --device cuda" in combined
    assert "--models flash" in combined


def test_verify_on_instance_uses_ember_user() -> None:
    """verify() SSHes as ember@ember-<name>, not root@."""
    calls, runner = _capture_runner()
    remote = Remote(_names("default"), runner=runner)

    remote.verify(
        ember_version=_EMBER_VERSION,
        model_s3_uri=_MODEL_S3_URI,
        server_url=_SERVER_URL,
        token=_TOKEN,
    )

    on_instance_calls = [
        argv for argv, _ in calls if "tailscale" in argv[0] and "ember@" in argv[2]
    ]
    assert on_instance_calls
    assert on_instance_calls[0][2] == "ember@ember-default"


def test_verify_operator_eval_run_uses_child_env() -> None:
    """verify() passes EMBER_SERVER_URL and EMBER_AUTH_TOKEN only in the child env."""
    calls, runner = _capture_runner()
    remote = Remote(_names("default"), runner=runner)

    remote.verify(
        ember_version=_EMBER_VERSION,
        model_s3_uri=_MODEL_S3_URI,
        server_url=_SERVER_URL,
        token=_TOKEN,
    )

    eval_run_calls = [
        (argv, kwargs)
        for argv, kwargs in calls
        if len(argv) >= 2 and "ember" in argv[0] and "eval" in argv
    ]
    assert eval_run_calls, "expected at least one ember eval run call"
    _, kwargs = eval_run_calls[0]
    env = kwargs.get("env") or {}
    assert env.get("EMBER_SERVER_URL") == _SERVER_URL
    assert env.get("EMBER_AUTH_TOKEN") == _TOKEN


def test_verify_operator_eval_run_argv() -> None:
    """verify() calls ember eval run with the correct argv."""
    calls, runner = _capture_runner()
    remote = Remote(_names("default"), runner=runner)

    remote.verify(
        ember_version=_EMBER_VERSION,
        model_s3_uri=_MODEL_S3_URI,
        server_url=_SERVER_URL,
        token=_TOKEN,
    )

    eval_run_calls = [
        argv
        for argv, _ in calls
        if len(argv) >= 3 and "ember" in argv[0] and "eval" in argv and "run" in argv
    ]
    assert eval_run_calls, "expected ember eval run call"


def test_verify_operator_eval_report_compare(tmp_path: Path) -> None:
    """verify() calls ember eval report --compare against the newest MPS bundle."""
    bundle = tmp_path / "run-001"
    bundle.mkdir()
    (bundle / "results.json").write_text("{}")

    calls, runner = _capture_runner()
    remote = Remote(_names("default"), runner=runner)

    remote.verify(
        ember_version=_EMBER_VERSION,
        model_s3_uri=_MODEL_S3_URI,
        server_url=_SERVER_URL,
        token=_TOKEN,
        benchmark_dir=tmp_path,
    )

    report_calls = [
        argv
        for argv, _ in calls
        if len(argv) >= 3
        and "ember" in argv[0]
        and "eval" in argv
        and "report" in argv
        and "--compare" in argv
    ]
    assert report_calls, "expected ember eval report --compare call"


def test_verify_never_uses_shell() -> None:
    """verify() must never pass shell=True to the runner."""
    calls, runner = _capture_runner()
    remote = Remote(_names("default"), runner=runner)

    remote.verify(
        ember_version=_EMBER_VERSION,
        model_s3_uri=_MODEL_S3_URI,
        server_url=_SERVER_URL,
        token=_TOKEN,
    )

    for _, kwargs in calls:
        assert kwargs.get("shell") is not True
