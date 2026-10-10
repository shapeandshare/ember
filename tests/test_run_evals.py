"""Unit tests for the benchmark runner's engine-info and advise calls.

Covers the auth-header contract on ``/health`` and ``/v1/systemone``: a hosted
endpoint protected by ``EMBER_AUTH_TOKEN`` must receive the same credential on
both calls, or the run's recorded ``engine``/``model`` provenance silently
goes empty.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from evals.eval import run_evals


def test_engine_sends_auth_headers_when_configured(monkeypatch: Any) -> None:
    """``_engine`` must send the configured auth header to ``/health``.

    A hosted endpoint that requires auth (e.g. ``x-api-key``) returns 403 to
    an unauthenticated ``/health`` request. Without the header, the response
    body carries no ``engine`` key and ``_engine`` silently returns ``{}``,
    so the run's ``model``/``model_spec``/``engine`` provenance is lost even
    though the request to ``/v1/systemone`` itself succeeds.
    """
    monkeypatch.setenv("EMBER_AUTH_TOKEN", "secret-token")
    monkeypatch.setenv("EMBER_AUTH_HEADER", "x-api-key")

    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(request.headers)
        if request.headers.get("x-api-key") != "secret-token":
            return httpx.Response(403, json={"error": "forbidden"})
        return httpx.Response(200, json={"engine": {"model_dir": "clef-flash"}})

    transport = httpx.MockTransport(handler)
    real_get = httpx.get

    def fake_get(
        url: str, *, timeout: float, headers: dict[str, str] | None = None
    ) -> httpx.Response:
        with httpx.Client(transport=transport) as client:
            return client.get(url, timeout=timeout, headers=headers)

    monkeypatch.setattr(httpx, "get", fake_get)
    try:
        engine = run_evals._engine("https://hosted.example.com")
    finally:
        monkeypatch.setattr(httpx, "get", real_get)

    assert "x-api-key" in captured_headers
    assert engine == {"model_dir": "clef-flash"}


@pytest.mark.parametrize(
    ("engine", "expected"),
    [
        ({"model": "clef-flash"}, "clef-flash"),
        (
            {
                "model": (
                    "s3://obp-0ttxc8-metaflow/metaflow/model-pipelines-dev/"
                    "Cloudflare__clef-flash/artifacts/model_file"
                )
            },
            "Cloudflare__clef-flash",
        ),
        ({}, "unknown"),
    ],
)
def test_model_name_handles_local_and_s3_engine_values(
    engine: dict[str, Any], expected: str
) -> None:
    """``_model_name`` reads the ``model`` field ember's ``/health`` reports.

    A local server's ``model`` is already a short name (the registry dir
    name). A hosted/S3 deployment's ``model`` is the full
    ``s3://bucket/.../<model>/artifacts/<file>`` URI (``Engine.model_name``
    is set to ``hosted_source.uri`` — see ``ember/serving/server.py``); the
    meaningful identifier is the path segment just before ``artifacts``, not
    the trailing filename that ``Path(...).name`` would pick up.
    """
    assert run_evals._model_name(engine) == expected


def test_engine_returns_empty_dict_on_403(monkeypatch: Any) -> None:
    """Without credentials, a 403 response still parses as JSON with no
    ``engine`` key, and ``_engine`` degrades to ``{}`` rather than raising.
    """
    monkeypatch.delenv("EMBER_AUTH_TOKEN", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "forbidden"})

    transport = httpx.MockTransport(handler)
    real_get = httpx.get

    def fake_get(
        url: str, *, timeout: float, headers: dict[str, str] | None = None
    ) -> httpx.Response:
        with httpx.Client(transport=transport) as client:
            return client.get(url, timeout=timeout, headers=headers)

    monkeypatch.setattr(httpx, "get", fake_get)
    try:
        engine = run_evals._engine("https://hosted.example.com")
    finally:
        monkeypatch.setattr(httpx, "get", real_get)

    assert engine == {}
