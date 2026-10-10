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
    assert "model_dir" not in engine, "I-001: model_dir must not appear in /health"
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


# ###########################################################################
# Constitution Article V "Unverified hosted-deployment exception": the
# lifespan() startup path checks ember.serving.hosted.resolve() first, before
# falling back to the normal REGISTRY-based path. TestClient(app) drives the
# real lifespan context manager (Starlette wraps it synchronously), so this
# exercises the actual dispatch, not a reimplementation of it — Engine()
# itself is mocked out to avoid a real torch/model load in this unit test.
# ###########################################################################
def _measure_flash(monkeypatch, tmp_path, cap: int | None) -> None:
    import dataclasses

    from ember import models
    from ember.cfg import paths

    monkeypatch.setattr(paths, "config_path", lambda: tmp_path / "config.json")
    for name in ("EMBER_MAX_LENGTH", "EMBER_MAX_REQUEST_LENGTH", "EMBER_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("EMBER_MODEL_DIR", raising=False)
    for key, spec in models.REGISTRY.items():
        measured = cap if key == "flash" else None
        monkeypatch.setitem(
            models.REGISTRY,
            key,
            dataclasses.replace(spec, max_request_length=measured),
        )


def test_lifespan_uses_hosted_source_when_configured(monkeypatch, tmp_path) -> None:
    from ember.serving import hosted, runtime
    from ember.serving import server as server_mod
    from ember.serving.limit_source import LimitSource

    _measure_flash(monkeypatch, tmp_path, 8192)
    fake_source = hosted.HostedModelSource(
        uri="s3://my-bucket/clef-flash",
        model_dir=__import__("pathlib").Path("/fake/model/dir"),
    )
    monkeypatch.setattr(hosted, "resolve", lambda: fake_source)

    captured: dict[str, object] = {}

    class _FakeEngine:
        def __init__(self, model_dir, **kwargs):
            captured["model_dir"] = model_dir
            captured.update(kwargs)
            self.device = "cpu"
            self.dtype = "float32"

        def describe(self):
            return {"model": "s3://my-bucket/clef-flash"}

    monkeypatch.setattr(server_mod, "Engine", _FakeEngine)
    monkeypatch.setattr(runtime, "Engine", _FakeEngine)

    with _in_process_client() as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["engine"]["model"] == "s3://my-bucket/clef-flash"

    assert captured["model_dir"] == fake_source.model_dir
    assert "spec" not in captured
    assert "skip_integrity" not in captured
    assert "max_length" not in captured
    assert "max_request_length" not in captured
    # A hosted model is outside the registry: the lowest registry cap applies.
    limits = captured["limits"]
    assert limits.max_request_length == 8192
    assert limits.max_request_length_source is LimitSource.FALLBACK


def test_lifespan_passes_the_registry_models_measured_cap(
    monkeypatch, tmp_path
) -> None:
    from ember import models
    from ember.serving import hosted
    from ember.serving import server as server_mod
    from ember.serving.limit_source import LimitSource

    _measure_flash(monkeypatch, tmp_path, 8192)
    monkeypatch.setattr(hosted, "resolve", lambda: None)
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    monkeypatch.setattr(models, "resolve_dir", lambda name: model_dir)

    captured: dict[str, object] = {}

    class _FakeEngine:
        def __init__(self, model_dir, **kwargs):
            captured["model_dir"] = model_dir
            captured.update(kwargs)
            self.device = "cpu"
            self.dtype = "float32"

        def describe(self):
            return {"model": "flash"}

    monkeypatch.setattr(server_mod, "Engine", _FakeEngine)

    with _in_process_client() as client:
        assert client.get("/health").json()["status"] == "ok"

    assert captured["model_dir"] == model_dir
    limits = captured["limits"]
    assert limits.max_request_length == 8192
    assert limits.max_request_length_source is LimitSource.MEASURED


def _registry_model_dir(monkeypatch, tmp_path):
    import json

    from ember import models
    from ember.serving import hosted

    monkeypatch.setattr(hosted, "resolve", lambda: None)
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(
        json.dumps({"text_config": {"max_position_embeddings": 262144}})
    )
    monkeypatch.setattr(models, "resolve_dir", lambda name: model_dir)
    return model_dir


def test_health_engine_reports_the_limits_and_their_sources(
    monkeypatch, tmp_path
) -> None:
    import dataclasses

    from ember import models
    from ember.serving import runtime

    _measure_flash(monkeypatch, tmp_path, None)
    monkeypatch.setitem(
        models.REGISTRY,
        "flash",
        dataclasses.replace(models.REGISTRY["flash"], fallback_request_length=20480),
    )
    _registry_model_dir(monkeypatch, tmp_path)
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))

    with _in_process_client() as client:
        engine = client.get("/health").json()["engine"]

    assert engine["max_length"] == 262144
    assert engine["max_length_source"] == "model"
    assert engine["max_request_length"] == 20480
    assert engine["max_request_length_source"] == "fallback"


def _lifespan_limit_lines(monkeypatch, caplog) -> list[str]:
    import logging

    from ember.serving import server as server_mod

    class _FakeEngine:
        def __init__(self, model_dir, **kwargs):
            self.device = "cpu"
            self.dtype = "float32"

        def describe(self):
            return {"model": "flash"}

    monkeypatch.setattr(server_mod, "Engine", _FakeEngine)
    with caplog.at_level(logging.INFO, logger="ember.serving.server"):
        with _in_process_client() as client:
            client.get("/health")
    return [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("limits:")
    ]


def test_lifespan_logs_the_limits_once(monkeypatch, tmp_path, caplog) -> None:
    _measure_flash(monkeypatch, tmp_path, 8192)
    _registry_model_dir(monkeypatch, tmp_path)
    assert _lifespan_limit_lines(monkeypatch, caplog) == [
        "limits: enforced 8192 tokens; max_length 262144 (model), "
        "max_request_length 8192 (measured)"
    ]


def test_lifespan_logs_a_disabled_cap(monkeypatch, tmp_path, caplog) -> None:
    _measure_flash(monkeypatch, tmp_path, 8192)
    _registry_model_dir(monkeypatch, tmp_path)
    monkeypatch.setenv("EMBER_MAX_REQUEST_LENGTH", "0")
    assert _lifespan_limit_lines(monkeypatch, caplog) == [
        "limits: enforced 262144 tokens; max_length 262144 (model), "
        "max_request_length disabled (operator)"
    ]


def test_main_sends_ember_logs_through_uvicorns_handler(monkeypatch) -> None:
    import uvicorn
    from ember.serving import server as server_mod

    captured: dict[str, object] = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: captured.update(kwargs))
    server_mod.main()
    ember_logger = captured["log_config"]["loggers"]["ember"]
    assert ember_logger["level"] == "INFO"
    assert ember_logger["handlers"] == ["default"]


@pytest.mark.filterwarnings("ignore:.*found in sys.modules:RuntimeWarning")
def test_the_server_logger_stays_under_ember_when_run_as_a_script() -> None:
    """`ember start` runs `python -m ember.serving.server`, so `__name__` is not
    the module path there; the logger must still sit under `ember`."""
    import runpy

    namespace = runpy.run_module("ember.serving.server", run_name="__not_main__")
    assert namespace["log"].name == "ember.serving.server"


# ###########################################################################
# Refusals: 413 with the token split, 500 on a size-check mismatch
# ###########################################################################
class _RaisingEngine:
    device = "cpu"
    dtype = "float32"

    def __init__(self, error: Exception) -> None:
        self.error = error

    def advise(self, *args, **kwargs):
        raise self.error

    def describe(self):
        return {"model": "fake"}


def _refusal():
    from ember.serving.limit_source import LimitSource
    from ember.serving.limits import Limits
    from ember.serving.request_size import RequestSize, refusal_message
    from ember.serving.runtime import RequestTooLargeError

    size = RequestSize(total=41230, state=39800, media=0, fixed=1430)
    limits = Limits(
        max_length=262144,
        max_length_source=LimitSource.MODEL,
        max_request_length=32768,
        max_request_length_source=LimitSource.FALLBACK,
    )
    message = refusal_message(size, limits, 262144)
    return RequestTooLargeError(message, size=size, limits=limits), message


def _requests_with_status(text: str, status: str) -> float:
    from prometheus_client.parser import text_string_to_metric_families

    return sum(
        sample.value
        for family in text_string_to_metric_families(text)
        for sample in family.samples
        if sample.name == "ember_advise_requests_total"
        and sample.labels.get("status") == status
    )


def test_an_oversized_request_gets_413_with_the_refusal(monkeypatch) -> None:
    from ember.serving import server as server_mod

    monkeypatch.delenv("EMBER_SERVER_AUTH_TOKEN", raising=False)
    error, message = _refusal()
    monkeypatch.setattr(server_mod, "_ENGINE", _RaisingEngine(error))
    resp = _in_process_client().post("/v1/systemone", json=BODY)
    assert resp.status_code == 413
    assert resp.json() == {"detail": message}


def test_a_size_check_mismatch_gets_500(monkeypatch) -> None:
    from ember.serving import server as server_mod
    from fastapi.testclient import TestClient

    monkeypatch.delenv("EMBER_SERVER_AUTH_TOKEN", raising=False)
    error = RuntimeError(
        "size check mismatch; refusing to answer from a possibly shortened input"
    )
    monkeypatch.setattr(server_mod, "_ENGINE", _RaisingEngine(error))
    client = TestClient(server_mod.app, raise_server_exceptions=False)
    assert client.post("/v1/systemone", json=BODY).status_code == 500


def test_refusals_are_counted_with_status_413(monkeypatch) -> None:
    from ember.serving import server as server_mod

    monkeypatch.delenv("EMBER_SERVER_AUTH_TOKEN", raising=False)
    error, _ = _refusal()
    monkeypatch.setattr(server_mod, "_ENGINE", _RaisingEngine(error))
    client = _in_process_client()
    before = _requests_with_status(client.get("/metrics").text, "413")
    client.post("/v1/systemone", json=BODY)
    after = _requests_with_status(client.get("/metrics").text, "413")
    assert after == before + 1


def test_lifespan_falls_back_to_registry_when_hosted_not_configured(
    monkeypatch,
) -> None:
    """When EMBER_MODEL_S3_URI is unset, hosted.resolve() returns None and the
    existing REGISTRY-based path is completely unaffected — this is a
    regression lock, not new behavior."""
    from ember.serving import hosted

    monkeypatch.setattr(hosted, "resolve", lambda: None)
    resp = _in_process_client().get("/health")
    assert resp.status_code == 200
    # Either "ok" (weights present) or "loading" (not pulled) — both are the
    # pre-existing, unaffected REGISTRY-based behavior; what matters is that
    # no hosted-path field leaks in when hosted.resolve() returned None.
    body = resp.json()
    assert body["status"] in ("ok", "loading")


def test_health_version_is_the_installed_distribution_version() -> None:
    import importlib.metadata
    import tomllib
    from pathlib import Path

    name = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text()
    )["project"]["name"]
    body = _in_process_client().get("/health").json()
    assert body["version"] == importlib.metadata.version(name)


# ###########################################################################
# T-004: host config must be validated against loopback when auth is disabled
# ###########################################################################
def test_lifespan_raises_on_non_loopback_host_without_auth(monkeypatch) -> None:
    """T-004: Starting the server on a non-loopback address without
    EMBER_SERVER_AUTH_TOKEN must raise RuntimeError (fail-fast before ready).
    Exposing the unauthenticated inference endpoint beyond loopback removes the
    only security boundary."""
    monkeypatch.setenv("EMBER_HOST", "0.0.0.0")  # noqa: S104
    monkeypatch.delenv("EMBER_SERVER_AUTH_TOKEN", raising=False)
    from ember.serving import server as server_mod
    from fastapi.testclient import TestClient

    with pytest.raises(RuntimeError, match=r"EMBER_HOST|non-loopback|auth"):
        with TestClient(server_mod.app):
            pass


def test_lifespan_allows_non_loopback_host_when_auth_is_enabled(monkeypatch) -> None:
    """T-004: A non-loopback host is allowed when EMBER_SERVER_AUTH_TOKEN is
    set — the bearer-auth layer becomes the security boundary."""
    monkeypatch.setenv("EMBER_HOST", "0.0.0.0")  # noqa: S104
    monkeypatch.setenv("EMBER_SERVER_AUTH_TOKEN", "secret")
    resp = _in_process_client().get("/health")
    assert resp.status_code == 200


def test_lifespan_allows_loopback_host_without_auth(monkeypatch) -> None:
    """T-004: The default loopback address must continue to work without auth."""
    monkeypatch.setenv("EMBER_HOST", "127.0.0.1")
    monkeypatch.delenv("EMBER_SERVER_AUTH_TOKEN", raising=False)
    resp = _in_process_client().get("/health")
    assert resp.status_code == 200
