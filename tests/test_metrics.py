"""Prometheus metrics: the /metrics endpoint and advise instrumentation."""

from __future__ import annotations

import httpx
import pytest
from prometheus_client.parser import text_string_to_metric_families

STATE = "Checkout is down for all customers; every request has returned HTTP 500."
QUESTIONS = {"urgent": {"type": "noul", "instructions": "Is this urgent?"}}

METRIC_NAMES = (
    "ember_advise_requests_total",
    "ember_advise_latency_seconds",
    "ember_advise_input_tokens_total",
    "ember_advise_output_tokens_total",
    "ember_model_info",
)


def _samples(text: str, name: str) -> list:
    return [
        sample
        for family in text_string_to_metric_families(text)
        for sample in family.samples
        if sample.name == name
    ]


def _total(text: str, name: str, **labels: str) -> float:
    return sum(
        sample.value
        for sample in _samples(text, name)
        if all(sample.labels.get(key) == value for key, value in labels.items())
    )


def _metrics(base_url: str) -> str:
    return httpx.get(f"{base_url}/metrics", timeout=10.0).text


def test_server_returns_503_when_model_not_loaded(monkeypatch):
    """Article XIV §14.1 — server MUST return 503 (not crash) when model absent.

    The server must start and serve health/metrics even without weights; only
    the advise endpoint returns 503.  ``process.start()`` fails fast *before*
    spawning when weights are absent (tested in test_runtime_unit.py), but
    direct ``python -m ember.serving.server`` must remain responsive.

    Uses lifespan=True so the test exercises the actual startup path.
    """
    # import-placement:allow - deferred; server loads torch at import
    from ember.serving import server
    from fastapi.testclient import TestClient

    monkeypatch.setenv("EMBER_MODEL_DIR", "/nonexistent/no-weights-here")

    with TestClient(server.app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/v1/systemone",
            json={"state": "x", "questions": {"q": {"type": "noul"}}},
        )
        assert resp.status_code == 503
        assert "model" in resp.json()["detail"].lower()

        resp_health = client.get("/health")
        assert resp_health.status_code == 200
        assert resp_health.json()["status"] == "loading"


def test_metrics_endpoint_is_exposed_without_the_model():
    # import-placement:allow - deferred; server loads torch at import
    from ember.serving import server
    from fastapi.testclient import TestClient

    resp = TestClient(server.app).get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    for name in METRIC_NAMES:
        assert name in resp.text, f"{name} missing from /metrics"
    for name in (
        "python_info",
        "python_gc_objects_collected_total",
        "process_cpu_seconds_total",
    ):
        assert name not in resp.text, f"{name} should not be exposed"


def test_model_info_tracks_the_engine_lifecycle(monkeypatch, tmp_path):
    # import-placement:allow - deferred; server loads torch at import
    from ember.serving import server
    from fastapi.testclient import TestClient

    # import-placement:allow - deferred; server loads torch at import
    from prometheus_client import generate_latest

    class FakeEngine:
        device = "cpu"
        dtype = "float32"

        def __init__(
            self, model_dir, device=None, max_length=None, model_name=None, **_kw
        ):
            self.model_dir = model_dir
            self.model_name = model_name or "fake"

    model_dir = tmp_path / "model"
    model_dir.mkdir()
    monkeypatch.setattr(server.models, "resolve_dir", lambda name: model_dir)
    monkeypatch.setattr(server, "Engine", FakeEngine)

    with TestClient(server.app) as client:
        during = client.get("/metrics").text
    assert _total(during, "ember_model_info") == 1.0

    after = generate_latest(server.REGISTRY).decode()
    assert _total(after, "ember_model_info") == 0.0


def test_unloaded_engine_requests_are_counted():
    # import-placement:allow - deferred; server loads torch at import
    from ember.serving import server
    from fastapi.testclient import TestClient

    client = TestClient(server.app)
    resp = client.post(
        "/v1/systemone",
        json={"state": "x", "questions": {"urgent": {"type": "noul"}}},
    )
    assert resp.status_code == 503
    text = client.get("/metrics").text
    assert _total(text, "ember_advise_requests_total", status="503") >= 1


def test_unexpected_errors_are_counted(monkeypatch):
    # import-placement:allow - deferred; server loads torch at import
    from ember.serving import server
    from fastapi.testclient import TestClient

    class ExplodingEngine:
        device = "cpu"
        dtype = "float32"

        def advise(self, *args: object, **kwargs: object) -> dict:
            raise RuntimeError("boom")

    monkeypatch.setattr(server, "_ENGINE", ExplodingEngine())
    client = TestClient(server.app, raise_server_exceptions=False)
    resp = client.post(
        "/v1/systemone",
        json={"state": "x", "questions": {"urgent": {"type": "noul"}}},
    )
    assert resp.status_code == 500
    text = client.get("/metrics").text
    assert _total(text, "ember_advise_requests_total", status="500") >= 1


@pytest.mark.model
def test_advise_updates_metrics(base_url: str) -> None:
    before = _metrics(base_url)
    resp = httpx.post(
        f"{base_url}/v1/systemone",
        json={"model": "clef-flash", "state": STATE, "questions": QUESTIONS},
        timeout=300.0,
    )
    assert resp.status_code == 200
    after = _metrics(base_url)

    ok = _total(after, "ember_advise_requests_total", status="200")
    assert ok >= _total(before, "ember_advise_requests_total", status="200") + 1
    assert _total(after, "ember_advise_latency_seconds_count", status="200") > 0
    assert _total(after, "ember_advise_input_tokens_total") > 0
    assert _total(after, "ember_model_info") == 1.0


@pytest.mark.model
def test_validation_errors_are_counted(base_url: str) -> None:
    before = _metrics(base_url)
    resp = httpx.post(
        f"{base_url}/v1/systemone",
        json={"state": STATE, "questions": {"bogus": {"type": "nonsense"}}},
        timeout=30.0,
    )
    assert resp.status_code == 422
    after = _metrics(base_url)
    counted = _total(after, "ember_advise_requests_total", status="422")
    assert counted >= _total(before, "ember_advise_requests_total", status="422") + 1


@pytest.mark.model
def test_schema_validation_errors_are_counted(base_url: str) -> None:
    """A body FastAPI rejects before the handler is still an advise request."""
    before = _metrics(base_url)
    resp = httpx.post(
        f"{base_url}/v1/systemone",
        json={"state": STATE, "questions": "not-a-mapping"},
        timeout=30.0,
    )
    assert resp.status_code == 422
    after = _metrics(base_url)
    counted = _total(after, "ember_advise_requests_total", status="422")
    assert counted >= _total(before, "ember_advise_requests_total", status="422") + 1
