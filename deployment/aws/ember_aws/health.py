"""Health polling for the ember model server over Tailscale HTTPS."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

#: Default health poll timeout in seconds.
_DEFAULT_TIMEOUT_S = 1200

#: Default poll interval in seconds.
_DEFAULT_POLL_INTERVAL_S = 10

#: DNS/TLS not-ready hint message (split to stay ≤ 88 chars per line).
_DNS_TLS_HINT = (
    "  waiting: DNS or TLS not ready"
    " — check `make aws-logs UNIT=tailscale`"
    " and confirm 'HTTPS Certificates' is on"
    " in the Tailscale admin console"
)


class HealthTimeoutError(Exception):
    """Raised when the health poll deadline is exceeded.

    Parameters
    ----------
    message : str
        Human-readable description including the last response or error text.
    last_response : str
        The last response body or error text seen before timeout.
    """

    def __init__(self, message: str, last_response: str = "") -> None:
        super().__init__(message)
        self.last_response = last_response


#: Backward-compatible alias kept so existing imports still work.
HealthTimeout = HealthTimeoutError


def wait_healthy(
    url: str,
    token: str,
    timeout_s: int | None = None,
    transport: httpx.BaseTransport | None = None,
    poll_interval_s: float = _DEFAULT_POLL_INTERVAL_S,
) -> dict[str, Any]:
    """Poll ``GET <url>/health`` until the engine reports ``device == "cuda"``.

    Treats HTTP 503 as "loading" (prints the ``status`` text once per change)
    and returns the parsed body when ``engine.device == "cuda"``.

    The timeout defaults to the ``EMBER_AWS_HEALTH_TIMEOUT`` environment
    variable (seconds), falling back to 1200 s.

    Parameters
    ----------
    url : str
        Base URL of the ember server (e.g.
        ``"https://ember-default.example.ts.net"``).
    token : str
        Bearer token for the ``Authorization`` header.
    timeout_s : int | None
        Poll deadline in seconds.  ``None`` reads ``EMBER_AWS_HEALTH_TIMEOUT``
        or uses the 1200 s default.
    transport : httpx.BaseTransport | None
        Optional custom transport (used in tests via ``httpx.MockTransport``).
    poll_interval_s : float
        Seconds to sleep between polls; defaults to 10.

    Returns
    -------
    dict[str, Any]
        The parsed ``/health`` response body when the engine is on CUDA.

    Raises
    ------
    HealthTimeoutError
        If the deadline is exceeded before the engine reports
        ``device == "cuda"``.
    """
    if timeout_s is None:
        env_val = os.environ.get("EMBER_AWS_HEALTH_TIMEOUT")
        timeout_s = int(env_val) if env_val is not None else _DEFAULT_TIMEOUT_S

    deadline = time.monotonic() + timeout_s
    last_status: str = ""
    last_response: str = ""

    client_kwargs: dict[str, Any] = {}
    if transport is not None:
        client_kwargs["transport"] = transport

    while True:
        if time.monotonic() >= deadline:
            raise HealthTimeoutError(
                f"health poll timed out after {timeout_s} s;"
                f" last response: {last_response}",
                last_response=last_response,
            )

        try:
            with httpx.Client(**client_kwargs) as client:
                resp = client.get(
                    f"{url}/health",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=30,
                )
            last_response = resp.text

            if resp.status_code == 503:
                body = _safe_json(resp)
                status_text = body.get("status", "loading")
                if status_text != last_status:
                    print(f"  waiting: {status_text}")
                    last_status = status_text
            elif resp.status_code == 200:
                body = _safe_json(resp)
                device = (body.get("engine") or {}).get("device", "")
                if device == "cuda":
                    return body
                # Not cuda yet — keep polling (e.g. still on cpu during load)
                status_text = f"device={device}"
                if status_text != last_status:
                    print(f"  waiting: {status_text}")
                    last_status = status_text
            else:
                last_response = f"HTTP {resp.status_code}: {resp.text}"

        except Exception as exc:
            last_response = str(exc)
            lower = last_response.lower()
            if "name or service not known" in lower or "tls" in lower:
                print(_DNS_TLS_HINT)

        if time.monotonic() >= deadline:
            raise HealthTimeoutError(
                f"health poll timed out after {timeout_s} s;"
                f" last response: {last_response}",
                last_response=last_response,
            )

        time.sleep(poll_interval_s)


def _safe_json(resp: httpx.Response) -> dict[str, Any]:
    """Parse JSON from a response, returning an empty dict on failure.

    Parameters
    ----------
    resp : httpx.Response
        The HTTP response to parse.

    Returns
    -------
    dict[str, Any]
        Parsed JSON body, or ``{}`` on parse error.
    """
    try:
        result: dict[str, Any] = resp.json()
        return result
    except Exception:
        return {}
