"""Doctor subcommand handler: platform, dependency, model, server, and agent checks."""

from __future__ import annotations

import argparse
import collections.abc
import platform
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .. import models as models_mod
from ..cfg import config, paths
from ..cfg import endpoint as endpoint_mod
from ..serving import hosted, limits, process
from .endpoint import endpoint_status, resolve_endpoint
from .registration import registration_lines


def _doctor_check_platform(
    check: collections.abc.Callable[[str, bool, str], bool],
    info: collections.abc.Callable[[str, str], None],
) -> bool:
    """Emit the platform and Python version doctor lines.

    Parameters
    ----------
    check : Callable[[str, bool, str], bool]
        Emit a pass/fail line and return its result.
    info : Callable[[str, str], None]
        Emit an informational line.

    Returns
    -------
    bool
        ``True`` when every emitted check passed.
    """
    ok = True
    if paths.is_apple_silicon():
        ok = check("platform", True, "Apple Silicon macOS") and ok
    else:
        info(
            "platform",
            f"{sys.platform}/{platform.machine()} — unsupported; "
            "model server requires Apple Silicon macOS",
        )
    tested_python = sys.version_info[:2] == (3, 12)
    ok = (
        check(
            "python",
            tested_python,
            platform.python_version()
            if tested_python
            else f"{platform.python_version()} is untested; "
            "reinstall with `uv tool install --python 3.12 ...`",
        )
        and ok
    )
    return ok


def _doctor_check_deps(
    check: collections.abc.Callable[[str, bool, str], bool],
) -> bool:
    """Emit torch and transformers availability doctor lines.

    Parameters
    ----------
    check : Callable[[str, bool, str], bool]
        Emit a pass/fail line and return its result.

    Returns
    -------
    bool
        ``True`` when every emitted check passed.
    """
    ok = True
    try:
        # import-placement:allow - doctor availability probe; may not be installed
        import torch

        mps = torch.backends.mps.is_available()
        ok = (
            check(
                "torch",
                True,
                f"{torch.__version__} (mps={'yes' if mps else 'no, CPU fallback'})",
            )
            and ok
        )
    except ImportError as exc:
        ok = check("torch", False, str(exc)) and ok
    try:
        # import-placement:allow - doctor availability probe; may not be installed
        import transformers

        ok = check("transformers", True, transformers.__version__) and ok
    except ImportError as exc:
        ok = check("transformers", False, str(exc)) and ok
    return ok


def _doctor_check_models(
    check: collections.abc.Callable[[str, bool, str], bool],
    info: collections.abc.Callable[[str, str], None],
) -> bool:
    """Emit model availability doctor lines for the selected and optional models.

    When ``EMBER_MODEL_S3_URI`` is configured (constitution Article V,
    "Model Loading"), that operator-supplied location is checked first,
    instead of the normal ``REGISTRY``-based report (there is no ``REGISTRY``
    entry for this path).

    Parameters
    ----------
    check : Callable[[str, bool, str], bool]
        Emit a pass/fail line and return its result.
    info : Callable[[str, str], None]
        Emit an informational line.

    Returns
    -------
    bool
        ``True`` when the selected model check passed.
    """
    hosted_source = hosted.resolve()
    if hosted_source is not None:
        return check(
            f"model {hosted_source.uri}",
            hosted_source.model_dir.is_dir(),
            str(hosted_source.model_dir),
        )
    selected = config.resolve("model")
    model_dir = models_mod.resolve_dir(selected)
    ok = check(
        f"model {selected}",
        model_dir is not None,
        str(model_dir)
        if model_dir
        else f"not pulled; run: ember model pull {selected}",
    )
    for row in models_mod.list_models():
        if row["name"] != selected:
            info(
                f"model {row['name']} ({row['params']})",
                row["path"] or "not pulled (optional)",
            )
    return ok


def _doctor_model_location() -> tuple[Path | None, str | None]:
    """Return the selected model's directory and registry key.

    Returns
    -------
    tuple[Path | None, str | None]
        A configured hosted source's directory and ``None`` (it is outside the
        registry); otherwise ``models.resolve_dir`` (``None`` when not pulled)
        and ``models.registry_key`` for the selected model.
    """
    hosted_source = hosted.resolve()
    if hosted_source is not None:
        return hosted_source.model_dir, None
    selected = config.resolve("model")
    return models_mod.resolve_dir(selected), models_mod.registry_key(selected)


def _live_limits(engine: Any) -> limits.Limits | None:
    """Read the limits a server reports in its ``/health`` ``engine``, if any."""
    if not isinstance(engine, dict) or "max_request_length" not in engine:
        return None
    try:
        return limits.Limits.model_validate(
            {field: engine.get(field) for field in limits.Limits.model_fields}
        )
    except ValidationError:
        return None


def _doctor_limits(
    info: collections.abc.Callable[[str, str], None],
    status: dict[str, Any],
    model_dir: Path | None,
    registry_key: str | None,
) -> None:
    """Emit the limits line: live from the endpoint, configured, or unknown.

    Parameters
    ----------
    info : Callable[[str, str], None]
        Emit an informational line.
    status : dict[str, Any]
        ``endpoint_status`` output for the configured endpoint.
    model_dir : Path | None
        The selected model's directory, or ``None`` when not pulled.
    registry_key : str | None
        The selected model's registry key, or ``None`` outside the registry.
    """
    if status["reachable"]:
        engine = status.get("engine")
        live = _live_limits(engine)
        if engine is None:
            info("limits", "unknown; the server has not loaded a model yet")
        elif live is None:
            info("limits", "unknown; the server does not report limits (older ember)")
        else:
            origin = "local server" if status["kind"] == "local" else status["url"]
            info("limits", f"{live.summary()}; live from {origin}")
    elif status["kind"] == "local":
        configured = limits.from_config(model_dir, registry_key)
        info("limits", f"{configured.summary()}; configured, server not running")
    else:
        info("limits", "unknown; remote endpoint unreachable")


def cmd_doctor(args: argparse.Namespace) -> int:
    """Check platform, dependencies, model, and server (``ember doctor``).

    Ends with one pair of lines per coding-agent harness: its binary on
    ``PATH`` and where ember is registered for it. Registration is
    informational and never fails the check.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments; uses ``--server-url`` for endpoint reporting.

    Returns
    -------
    int
        ``0`` if every check passed, ``1`` otherwise.
    """

    def check(label: str, good: bool, detail: str) -> bool:
        print(f"[{'ok' if good else 'FAIL'}] {label}: {detail}")
        return good

    def info(label: str, detail: str) -> None:
        print(f"[info] {label}: {detail}")

    ok = _doctor_check_platform(check, info)
    ok = _doctor_check_deps(check) and ok
    ok = _doctor_check_models(check, info) and ok

    host, port = config.resolve("host"), int(config.resolve("port"))
    running = process.health(host, port) is not None
    info(
        "server",
        f"running at {host}:{port}"
        if running
        else "stopped; starts on first use or with `ember start`",
    )
    info(
        "server remote",
        "enabled (binds a non-loopback host)"
        if not endpoint_mod.is_loopback_host(str(host))
        else "disabled (loopback by default)",
    )
    info(
        "server auth",
        "required" if config.resolve("server_auth_token") else "disabled",
    )
    try:
        status = endpoint_status(resolve_endpoint(args))
    except (
        endpoint_mod.InvalidEndpointError,
        endpoint_mod.InsecureEndpointError,
    ) as exc:
        info("endpoint", f"invalid: {exc}")
    else:
        state = "reachable" if status["reachable"] else "unreachable"
        info("endpoint", f"{status['kind']} {status['url']} ({state})")
        _doctor_limits(info, status, *_doctor_model_location())
    for label, detail in registration_lines(Path.cwd()):
        info(label, detail)
    return 0 if ok else 1
