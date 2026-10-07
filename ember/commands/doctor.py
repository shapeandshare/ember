"""Doctor subcommand handler: platform, dependency, model, and server checks."""

from __future__ import annotations

import argparse
import collections.abc
import platform
import shutil
import sys

from .. import models as models_mod
from ..cfg import config, paths
from ..cfg import endpoint as endpoint_mod
from ..serving import process
from .endpoint import endpoint_status, resolve_endpoint


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


def cmd_doctor(args: argparse.Namespace) -> int:
    """Check platform, dependencies, model, and server (``ember doctor``).

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
    info("opencode", shutil.which("opencode") or "not on PATH")
    return 0 if ok else 1
