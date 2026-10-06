"""HTTP API call paths: GET /health, POST /v1/systemone across all question types,
and request-validation errors. Uses the session-scoped isolated server.
"""

from __future__ import annotations

import base64
import io

import httpx
import pytest
from PIL import Image

STATE = (
    "Checkout is down for all customers; every request has returned HTTP 500 "
    "for the last hour."
)

QUESTIONS = {
    "urgent": {"type": "noul", "instructions": "Is this support request urgent?"},
    "team": {
        "type": "choice",
        "instructions": "Which team should handle this request?",
        "criteria": {
            "billing": "Payments, invoices, and refunds",
            "technical": "Outages, errors, and configuration",
            "sales": "Plans and upgrades",
        },
    },
    "severity": {
        "type": "score",
        "instructions": "How severe is the customer impact?",
        "criteria": ["No impact", "Minor", "Major", "Critical"],
    },
}


def _png_data_uri(color: tuple[int, int, int] = (220, 30, 30)) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def _ask(
    base_url: str,
    *,
    state=STATE,
    questions=QUESTIONS,
    images=None,
    videos=None,
    media_kwargs=None,
) -> httpx.Response:
    body: dict = {"model": "clef-flash", "state": state, "questions": questions}
    if images is not None:
        body["images"] = images
    if videos is not None:
        body["videos"] = videos
    if media_kwargs is not None:
        body["media_kwargs"] = media_kwargs
    return httpx.post(f"{base_url}/v1/systemone", json=body, timeout=300.0)


@pytest.mark.model
def test_health_reports_accelerator_and_dtype(base_url: str) -> None:
    resp = httpx.get(f"{base_url}/health", timeout=10.0)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["pid"] > 0
    engine = body["engine"]
    assert engine["device"] in ("mps", "cpu")
    assert engine["dtype"] in ("float16", "float32")
    assert engine["model_dir"].endswith("clef-flash")
    assert engine["model"] == "flash"
    assert body["version"]
    assert body["auth_required"] is False


@pytest.mark.model
def test_systemone_covers_all_supported_question_types(base_url: str) -> None:
    resp = _ask(base_url)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    answers = body["answers"]

    # noul -> probability of true
    assert answers["urgent"]["type"] == "noul"
    assert 0.0 <= answers["urgent"]["noul"] <= 1.0

    # choice -> picked option + full distribution
    team = answers["team"]
    assert team["type"] == "choice"
    assert team["choice"] in QUESTIONS["team"]["criteria"]
    assert set(team["probabilities"]) == set(QUESTIONS["team"]["criteria"])
    assert abs(max(team["probabilities"].values()) - team["confidence"]) < 1e-3

    # score -> expected score over ordered criteria + legend
    severity = answers["severity"]
    assert severity["type"] == "score"
    assert 0.0 <= severity["score"] <= 3.0
    assert set(severity["legend"]) == {"0", "1", "2", "3"}

    # envelope
    assert body["usage"]["output_tokens"] == 0
    assert body["usage"]["input_tokens"] > 0
    assert body["latency_ms"] > 0


@pytest.mark.model
def test_probabilities_are_normalized(base_url: str) -> None:
    resp = _ask(base_url)
    for qid, answer in resp.json()["answers"].items():
        if "probabilities" in answer:
            assert abs(sum(answer["probabilities"].values()) - 1.0) < 0.05, qid


@pytest.mark.model
def test_invalid_question_type_rejected(base_url: str) -> None:
    resp = _ask(
        base_url, questions={"bogus": {"type": "nonsense", "instructions": "?"}}
    )
    assert resp.status_code == 422


@pytest.mark.model
def test_choice_without_criteria_rejected(base_url: str) -> None:
    resp = _ask(
        base_url, questions={"team": {"type": "choice", "instructions": "Which?"}}
    )
    assert resp.status_code == 422


@pytest.mark.model
def test_missing_state_rejected(base_url: str) -> None:
    resp = httpx.post(
        f"{base_url}/v1/systemone", json={"questions": QUESTIONS}, timeout=30.0
    )
    assert resp.status_code == 422


@pytest.mark.model
def test_missing_questions_rejected(base_url: str) -> None:
    resp = httpx.post(f"{base_url}/v1/systemone", json={"state": STATE}, timeout=30.0)
    assert resp.status_code == 422


@pytest.mark.model
def test_systemone_accepts_an_inline_image(base_url: str) -> None:
    questions = {
        "red": {"type": "noul", "instructions": "Is the image predominantly red?"}
    }
    resp = _ask(
        base_url,
        state="Review the attached color swatch.",
        questions=questions,
        images=[_png_data_uri()],
    )
    assert resp.status_code == 200, resp.text
    answer = resp.json()["answers"]["red"]
    assert answer["type"] == "noul"
    assert answer["noul"] > 0.5, "the model should read the red swatch as red"


@pytest.mark.model
def test_invalid_media_ref_rejected(base_url: str) -> None:
    resp = _ask(base_url, images=["/etc/passwd"])
    assert resp.status_code == 422


@pytest.mark.model
def test_disallowed_data_uri_content_type_rejected(base_url: str) -> None:
    svg = "data:image/svg+xml;base64," + base64.b64encode(b"<svg/>").decode()
    resp = _ask(base_url, images=[svg])
    assert resp.status_code == 422


@pytest.mark.model
def test_reserved_media_kwargs_key_rejected(base_url: str) -> None:
    resp = _ask(base_url, media_kwargs={"text": "override"})
    assert resp.status_code == 422


# ###########################################################################
# /health contract + optional server auth (in-process; no model required)
# ###########################################################################
BODY = {"model": "clef-flash", "state": "x", "questions": {"q": {"type": "noul"}}}


def _in_process_client():
    from ember.serving import server as server_mod
    from fastapi.testclient import TestClient

    return TestClient(server_mod.app)


def test_health_advertises_contract_fields() -> None:
    resp = _in_process_client().get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert {"status", "pid", "engine", "version", "auth_required"} <= set(body)
    assert body["auth_required"] is False


def test_health_reports_auth_required_when_token_set(monkeypatch) -> None:
    monkeypatch.setenv("EMBER_SERVER_AUTH_TOKEN", "secret")
    assert _in_process_client().get("/health").json()["auth_required"] is True


def test_health_and_metrics_need_no_token_when_auth_enabled(monkeypatch) -> None:
    monkeypatch.setenv("EMBER_SERVER_AUTH_TOKEN", "secret")
    client = _in_process_client()
    assert client.get("/health").status_code == 200
    assert client.get("/metrics").status_code == 200


def test_protected_route_rejects_missing_token(monkeypatch) -> None:
    monkeypatch.setenv("EMBER_SERVER_AUTH_TOKEN", "secret")
    resp = _in_process_client().post("/v1/systemone", json=BODY)
    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate") == "Bearer"


def test_protected_route_rejects_wrong_token(monkeypatch) -> None:
    monkeypatch.setenv("EMBER_SERVER_AUTH_TOKEN", "secret")
    resp = _in_process_client().post(
        "/v1/systemone", json=BODY, headers={"Authorization": "Bearer nope"}
    )
    assert resp.status_code == 401


def test_missing_and_wrong_token_are_indistinguishable(monkeypatch) -> None:
    monkeypatch.setenv("EMBER_SERVER_AUTH_TOKEN", "secret")
    client = _in_process_client()
    missing = client.post("/v1/systemone", json=BODY)
    wrong = client.post(
        "/v1/systemone", json=BODY, headers={"Authorization": "Bearer nope"}
    )
    assert missing.status_code == wrong.status_code == 401
    assert missing.json() == wrong.json()


def test_protected_route_accepts_valid_token_past_auth(monkeypatch) -> None:
    monkeypatch.setenv("EMBER_SERVER_AUTH_TOKEN", "secret")
    resp = _in_process_client().post(
        "/v1/systemone", json=BODY, headers={"Authorization": "Bearer secret"}
    )
    assert resp.status_code != 401


def test_auth_disabled_requires_no_token(monkeypatch) -> None:
    monkeypatch.delenv("EMBER_SERVER_AUTH_TOKEN", raising=False)
    resp = _in_process_client().post("/v1/systemone", json=BODY)
    assert resp.status_code != 401
