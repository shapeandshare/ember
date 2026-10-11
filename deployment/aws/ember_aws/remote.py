"""Remote operations on a deployed ember instance via Tailscale SSH."""

from __future__ import annotations

import hashlib
import shutil
import subprocess  # nosec B404
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .names import DeploymentName

#: Maps the CLI ``--unit`` key to the systemd unit name on the instance.
#: Derived from ``deployment/aws/instance/*.service`` (SyslogIdentifier fields).
_UNIT_MAP: dict[str, str] = {
    "ember": "ember",
    "converge": "ember-converge",
    "idle": "ember-idle",
    "tailscale": "ember-tailscale",
}

#: Type alias for the injected runner (matches subprocess.run's signature subset).
_Runner = Callable[..., Any]

#: ember GitHub repository URL.
_EMBER_REPO = "https://github.com/shapeandshare/ember"

#: Clone destination on the instance (owned by the ember SSH user).
_INSTANCE_CLONE_DIR = "/home/ember/ember-src"

#: ember user home directory on the instance.
_EMBER_HOME = "/home/ember"


def _model_cache_dir(model_s3_uri: str) -> str:
    """Return the model cache directory path on the instance for a given S3 URI.

    Mirrors the logic in ``deployment/aws/instance/converge.sh``:
    ``${HOME}/.cache/ember/hosted-models/<first-16-chars-of-sha256(uri)>``.

    Parameters
    ----------
    model_s3_uri : str
        The ``s3://bucket/prefix`` URI stored in the instance config.

    Returns
    -------
    str
        Absolute path to the model cache directory on the instance.
    """
    uri_hash = hashlib.sha256(model_s3_uri.encode()).hexdigest()[:16]
    return f"{_EMBER_HOME}/.cache/ember/hosted-models/{uri_hash}"


def _result_names(results_dir: Path) -> set[str]:
    """Return the names of the ``*_results.json`` files in ``results_dir``.

    Parameters
    ----------
    results_dir : Path
        The results directory to scan.

    Returns
    -------
    set[str]
        File names present, empty when the directory is absent.
    """
    if not results_dir.is_dir():
        return set()
    return {p.name for p in results_dir.glob("*_results.json")}


def _newest_unseen_results(results_dir: Path, before: set[str]) -> Path | None:
    """Return the newest results file not present before the run, or ``None``.

    Parameters
    ----------
    results_dir : Path
        The results directory to scan.
    before : set[str]
        Result file names that existed before ``ember eval run``.

    Returns
    -------
    Path | None
        The run's own results file, or ``None`` when none appeared.
    """
    if not results_dir.is_dir():
        return None
    candidates = sorted(
        (p for p in results_dir.glob("*_results.json") if p.name not in before),
        key=lambda p: p.stat().st_mtime,
    )
    return candidates[-1] if candidates else None


def _newest_mps_bundle(benchmark_dir: Path) -> Path | None:
    """Return the newest ``results.json`` under ``benchmark_dir``, or ``None``.

    Parameters
    ----------
    benchmark_dir : Path
        The ``benchmark/`` directory to search.

    Returns
    -------
    Path | None
        Path to the newest ``results.json``, or ``None`` when the directory is
        absent or empty.
    """
    if not benchmark_dir.is_dir():
        return None
    candidates = sorted(
        benchmark_dir.glob("*/results.json"),
        key=lambda p: p.parent.name,
        reverse=True,
    )
    return candidates[0] if candidates else None


class Remote:
    """Run operator commands on the instance over Tailscale SSH.

    All commands are forwarded to an injected ``runner`` (default:
    ``subprocess.run``) so tests can capture the argv without touching
    Tailscale or AWS.  ``shell=True`` is never used.

    Parameters
    ----------
    names : DeploymentName
        Validated deployment name; ``names.hostname`` supplies the SSH target.
    runner : Callable, optional
        Callable with the same signature as ``subprocess.run``.  Defaults to
        ``subprocess.run``.  Tests inject a mock here.
    """

    def __init__(
        self,
        names: DeploymentName,
        runner: _Runner = subprocess.run,
    ) -> None:
        self._names = names
        self._runner = runner

    def logs(self, unit: str, follow: bool) -> None:
        """Stream or dump journald logs from the instance.

        Runs ``tailscale ssh root@<hostname> journalctl -u <unit> [-f]``
        through the injected runner.

        Parameters
        ----------
        unit : str
            One of ``ember``, ``converge``, ``idle``, or ``tailscale``.
            Each maps to its systemd unit name on the instance.
        follow : bool
            When ``True``, appends ``-f`` to follow the journal live.

        Raises
        ------
        ValueError
            If ``unit`` is not one of the recognised keys.
        """
        if unit not in _UNIT_MAP:
            known = ", ".join(sorted(_UNIT_MAP))
            raise ValueError(f"unknown unit {unit!r}; valid choices are: {known}")

        systemd_unit = _UNIT_MAP[unit]
        argv: list[str] = [
            "tailscale",
            "ssh",
            f"root@{self._names.hostname}",
            "journalctl",
            "-u",
            systemd_unit,
        ]
        if follow:
            argv.append("-f")

        self._runner(argv, shell=False, check=True)

    def ssh(self) -> None:
        """Open an interactive SSH session on the instance.

        Runs ``tailscale ssh root@<hostname>`` through the injected runner.
        """
        argv: list[str] = [
            "tailscale",
            "ssh",
            f"root@{self._names.hostname}",
        ]
        self._runner(argv, shell=False, check=True)

    def verify(
        self,
        *,
        ember_version: str,
        model_s3_uri: str,
        server_url: str,
        token: str,
        benchmark_dir: Path | None = None,
        results_dir: Path | None = None,
    ) -> None:
        """Run the CUDA verification gate (T041).

        Two phases:

        1. **On the instance** (via ``tailscale ssh ember@<hostname>``):
           recreate the checkout of the pinned ember release (so the gate is
           rerunnable), link the hosted model cache into the checkout's
           ``.models/clef-flash`` (where the model-backed tests and the
           context probe look for it), run ``make test-strict`` with
           ``EMBER_DEVICE=cuda``, then run
           ``ember eval context --device cuda --models flash`` (flash is the
           only AWS-supported model).

        2. **On the operator side**: run ``ember eval run`` with
           ``EMBER_SERVER_URL`` and ``EMBER_AUTH_TOKEN`` set only in the
           child environment, then ``ember eval report --compare`` against
           the newest MPS bundle in ``benchmark/``.

        Parameters
        ----------
        ember_version : str
            The pinned ``ember-advise`` version (``X.Y.Z``) to clone and test.
        model_s3_uri : str
            The ``s3://bucket/prefix`` URI of the model on the instance.
        server_url : str
            The Tailscale HTTPS URL of the deployed ember server.
        token : str
            The server auth token (``EMBER_AUTH_TOKEN``).
        benchmark_dir : Path | None, optional
            Directory containing tracked MPS benchmark bundles.  Defaults to
            ``<repo-root>/benchmark/``.
        results_dir : Path | None, optional
            Directory ``ember eval run`` writes ``*_results.json`` into.
            Defaults to ``<repo-root>/results/``.
        """
        cache_dir = _model_cache_dir(model_s3_uri)
        on_instance_cmd = (
            f"rm -rf {_INSTANCE_CLONE_DIR} && "
            f"git clone --depth 1 --branch v{ember_version} {_EMBER_REPO} "
            f"{_INSTANCE_CLONE_DIR} && "
            f"cd {_INSTANCE_CLONE_DIR} && "
            f"uv sync --locked && "
            f"mkdir -p .models && "
            f"ln -sfn {cache_dir} .models/clef-flash && "
            f"EMBER_MODEL_DIR={cache_dir} EMBER_DEVICE=cuda make test-strict && "
            f".venv/bin/ember eval context --device cuda --models flash"
        )
        self._runner(
            [
                "tailscale",
                "ssh",
                f"ember@{self._names.hostname}",
                on_instance_cmd,
            ],
            shell=False,
            check=True,
        )

        ember_bin = shutil.which("ember") or sys.executable
        child_env = {"EMBER_SERVER_URL": server_url, "EMBER_AUTH_TOKEN": token}
        if results_dir is None:
            results_dir = Path(__file__).resolve().parents[3] / "results"
        before = _result_names(results_dir)
        self._runner(
            [ember_bin, "eval", "run"],
            shell=False,
            check=True,
            env=child_env,
        )

        if benchmark_dir is None:
            benchmark_dir = Path(__file__).resolve().parents[3] / "benchmark"
        newest = _newest_mps_bundle(benchmark_dir)
        cuda_result = _newest_unseen_results(results_dir, before)
        if newest is not None and cuda_result is not None:
            self._runner(
                [
                    ember_bin,
                    "eval",
                    "report",
                    "--compare",
                    str(newest),
                    str(cuda_result),
                ],
                shell=False,
                check=True,
            )
        else:
            print(
                "  verify: skipping the report comparison"
                " (need the newest MPS bundle and the CUDA run's results)"
            )
