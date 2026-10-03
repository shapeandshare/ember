"""Prometheus metrics: the /metrics endpoint and advise instrumentation."""

from __future__ import annotations

import httpx
import pytest
from prometheus_client.parser import text_string_to_metric_families

STATE = "Checkout is down for all customers; every request has returned HTTP 500."
QUESTIONS = {"urgent": {"type": "noul", "instructions": "Is this urgent?"}}

METRIC_NAMES = (
    "ember_advise_requests_total",
    "ember_advise_latency_seconds_count",
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


def test_metrics_endpoint_is_exposed_without_the_model():
    from ember import server
    from fastapi.testclient import TestClient

    resp = TestClient(server.app).get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    for name in METRIC_NAMES:
        assert name in resp.text, f"{name} missing from /metrics"


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
    assert _total(after, "ember_advise_latency_seconds_count") > 0
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
