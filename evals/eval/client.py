"""HTTP client helpers for the benchmark harness (split out of ``run_evals.py``).

The server URL is resolved like the MCP client's endpoint, the deployment label
is a generic description that never carries the URL, and ``advise`` posts one
item to ``/v1/systemone``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from ember.cfg.endpoint import (
    Endpoint,
    InsecureEndpointError,
    InvalidEndpointError,
    build_auth_headers,
    is_loopback_host,
)

DEFAULT_SERVER = "http://127.0.0.1:8765"
TIMEOUT = 120.0


def resolve_server(flag: str | None) -> str:
    """Resolve the server URL: an explicit flag, else the configured endpoint.

    Parameters
    ----------
    flag : str | None
        The ``--server`` value, or ``None`` when unset.

    Returns
    -------
    str
        The flag when given; otherwise the endpoint resolved through
        ``Endpoint.resolve`` (env > config file > default), falling back to the
        loopback default when the configured endpoint is invalid or insecure.
    """
    if flag:
        return flag
    try:
        return Endpoint.resolve().url
    except (InvalidEndpointError, InsecureEndpointError):
        return DEFAULT_SERVER


_DEVICE_LABELS = {
    "mps": "Apple Silicon, MPS",
    "cuda": "GPU, CUDA",
    "cpu": "CPU",
}


def deployment_label(explicit: str | None, server: str, device: str | None) -> str:
    """Return a generic deployment description, never the raw server URL.

    Parameters
    ----------
    explicit : str | None
        An operator-supplied label (``--deployment-label`` /
        ``EMBER_DEPLOYMENT_LABEL``), e.g. ``"Remote hosted — NVIDIA A10G,
        24 GB VRAM, g5.4xlarge"``. ember has no way to query the specific
        GPU model or instance size from ``/health`` — only an operator
        running the benchmark knows that, so this is the only path to
        reporting it.
    server : str
        The model server's base URL. Used only to classify local vs. remote
        (``ember.cfg.endpoint.is_loopback_host``); the URL itself is never
        returned, so it never appears in published run provenance.
    device : str | None
        The engine's reported device (``"mps"``, ``"cuda"``, ``"cpu"``), or
        ``None``/unknown.

    Returns
    -------
    str
        ``explicit`` when given. Otherwise ``"Local (...)"`` or
        ``"Remote hosted (...)"`` plus a human label for ``device``
        (``_DEVICE_LABELS``), or no parenthetical when the device is
        unrecognised.
    """
    if explicit:
        return explicit
    location = (
        "Local" if is_loopback_host(urlparse(server).hostname) else "Remote hosted"
    )
    device_label = _DEVICE_LABELS.get(device or "")
    return f"{location} ({device_label})" if device_label else location


def model_name(engine: dict[str, Any]) -> str:
    """Return a short, filesystem-safe model identifier from an engine dict.

    Parameters
    ----------
    engine : dict[str, Any]
        The ``engine`` object from ``GET /health`` (``Engine.describe()``).

    Returns
    -------
    str
        For a local server, ``engine["model"]`` is already the registry's
        short name (``Engine.model_name`` defaults to ``model_dir.name``) and
        is returned as-is. For a hosted/S3 deployment, ``engine["model"]`` is
        the full ``s3://bucket/.../<model>/artifacts/<file>`` URI
        (``model_name=hosted_source.uri`` in ``ember/serving/server.py``);
        this returns the path segment just before ``artifacts``, the
        meaningful model identifier, rather than the trailing filename.
        ``"unknown"`` when ``model`` is missing.
    """
    raw = str(engine.get("model", "unknown"))
    if raw.startswith("s3://"):
        parts = [p for p in raw.split("/") if p]
        if "artifacts" in parts:
            return parts[parts.index("artifacts") - 1]
        return parts[-1] if parts else "unknown"
    return Path(raw).name


def health(server: str) -> dict[str, Any]:
    """Return ``GET /health``'s body, authenticated, or ``{}`` on failure.

    Parameters
    ----------
    server : str
        The model server's base URL.

    Returns
    -------
    dict[str, Any]
        The parsed ``/health`` body (``status``, ``pid``, ``engine``,
        ``version``, ``auth_required``), or ``{}`` if the request fails or
        the response is not valid JSON. Sends ``build_auth_headers()`` so a
        gateway-authenticated hosted deployment (one that gates ``/health``
        behind the same credential as ``/v1/systemone``) is actually reached;
        without it, a non-2xx response carries no ``engine``/``version`` keys
        and this degrades to ``{}`` silently.
    """
    try:
        response = httpx.get(
            f"{server}/health", timeout=5.0, headers=build_auth_headers()
        )
        body = response.json()
    except (httpx.HTTPError, ValueError):
        return {}
    return body if isinstance(body, dict) else {}


def advise(server: str, item: dict[str, Any]) -> dict[str, Any]:
    """Post one item to ``/v1/systemone`` and return the parsed body."""
    payload: dict[str, Any] = {
        "model": "clef-flash",
        "state": item["state"],
        "questions": item["questions"],
    }
    for key in ("images", "videos", "media_kwargs"):
        if item.get(key) is not None:
            payload[key] = item[key]
    response = httpx.post(
        f"{server}/v1/systemone",
        json=payload,
        timeout=TIMEOUT,
        headers=build_auth_headers(),
    )
    response.raise_for_status()
    body: dict[str, Any] = response.json()
    return body
