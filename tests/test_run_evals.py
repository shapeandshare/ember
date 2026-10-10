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
from evals.eval.provenance import model_spec_info


def test_health_sends_auth_headers_when_configured(monkeypatch: Any) -> None:
    """``_health`` must send the configured auth header to ``/health``.

    A hosted endpoint that requires auth (e.g. ``x-api-key``) returns 403 to
    an unauthenticated ``/health`` request. Without the header, the response
    body carries no ``engine``/``version`` keys and ``_health`` silently
    returns ``{}``, so the run's ``model``/``model_spec``/``engine``/server
    ``version`` provenance is lost even though the request to
    ``/v1/systemone`` itself succeeds.
    """
    monkeypatch.setenv("EMBER_AUTH_TOKEN", "secret-token")
    monkeypatch.setenv("EMBER_AUTH_HEADER", "x-api-key")

    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(request.headers)
        if request.headers.get("x-api-key") != "secret-token":
            return httpx.Response(403, json={"error": "forbidden"})
        return httpx.Response(
            200,
            json={
                "engine": {"model_dir": "clef-flash"},
                "version": "0.10.2",
                "auth_required": False,
            },
        )

    transport = httpx.MockTransport(handler)
    real_get = httpx.get

    def fake_get(
        url: str, *, timeout: float, headers: dict[str, str] | None = None
    ) -> httpx.Response:
        with httpx.Client(transport=transport) as client:
            return client.get(url, timeout=timeout, headers=headers)

    monkeypatch.setattr(httpx, "get", fake_get)
    try:
        health = run_evals._health("https://hosted.example.com")
    finally:
        monkeypatch.setattr(httpx, "get", real_get)

    assert "x-api-key" in captured_headers
    assert health["engine"] == {"model_dir": "clef-flash"}
    assert health["version"] == "0.10.2"


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


@pytest.mark.parametrize(
    ("name", "expected_registry_name"),
    [
        ("clef-flash", "flash"),
        ("Cloudflare__clef-flash", "flash"),
        ("clef", "full"),
        ("Cloudflare__clef", "full"),
        ("not-a-known-model", None),
    ],
)
def test_model_spec_info_matches_hosted_s3_derived_names(
    name: str, expected_registry_name: str | None
) -> None:
    """``model_spec_info`` must recognise a hosted/S3-derived model name.

    A local run's derived name is the registry ``dir_name`` (``clef-flash``).
    A hosted/S3 run's derived name (``_model_name`` in ``run_evals.py``) is
    the S3 path segment before ``artifacts``, which follows the convention
    ``<repo-owner>__<repo-name>`` (``Cloudflare__clef-flash`` for
    ``Cloudflare/clef-flash``). Both must resolve to the same registry entry
    so a leaderboard can group hosted and local runs of the same model
    together.
    """
    spec = model_spec_info(name)
    if expected_registry_name is None:
        assert spec == {}
    else:
        assert spec.get("name") == expected_registry_name


def test_health_has_no_engine_or_version_on_403(monkeypatch: Any) -> None:
    """Without credentials, a 403 response still parses as JSON, but carries
    no ``engine``/``version`` keys; callers must use ``.get(...)``, not
    assume a 2xx shape.
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
        health = run_evals._health("https://hosted.example.com")
    finally:
        monkeypatch.setattr(httpx, "get", real_get)

    assert health.get("engine") is None
    assert health.get("version") is None


def test_health_returns_empty_dict_on_connection_error(monkeypatch: Any) -> None:
    """A transport-level failure (connection refused, timeout) degrades
    ``_health`` to ``{}`` rather than raising.
    """

    def fake_get(
        url: str, *, timeout: float, headers: dict[str, str] | None = None
    ) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    real_get = httpx.get
    monkeypatch.setattr(httpx, "get", fake_get)
    try:
        health = run_evals._health("https://unreachable.example.com")
    finally:
        monkeypatch.setattr(httpx, "get", real_get)

    assert health == {}
