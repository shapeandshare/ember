"""MCP call paths: tool discovery, the `advise` tool over stdio, error handling when the
model server is down or the model is missing, autostart on a configured port, and the
agent guidance served at connect time.

All MCP servers here are spawned over stdio and never touch the opencode CLI.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from ember import models
from ember.agent_kit import api as agent_kit
from ember.cfg.endpoint import Endpoint
from ember.mcp import mcp_server
from ember.mcp.mcp_types import AdviseInput
from mcp.client.stdio import stdio_client
from mcp.server.mcpserver.exceptions import ToolError
from PIL import Image

from mcp import ClientSession
from tests.conftest import free_port, mcp_stdin_params, terminate_pid


def _png_data_uri(color: tuple[int, int, int] = (220, 30, 30)) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


SAMPLE = {
    "input": {
        "state": (
            "The login endpoint returns 401 for all users after the latest deploy."
        ),
        "questions": {
            "urgent": {"type": "noul", "instructions": "Is this urgent?"},
            "team": {
                "type": "choice",
                "instructions": "Which team should handle this?",
                "criteria": {
                    "auth": "Authentication/sessions",
                    "frontend": "UI issues",
                },
            },
        },
    }
}


async def _list_tools(params):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.list_tools()


async def _call_advise(params, arguments=SAMPLE):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool("advise", arguments)


def _payload(result):
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(result.content[0].text)


@pytest.mark.model
def test_mcp_exposes_the_advise_tool(base_url: str) -> None:
    tools = asyncio.run(_list_tools(mcp_stdin_params(base_url)))
    advise = next(tool for tool in tools.tools if tool.name == "advise")
    assert advise.input_schema["properties"].get("input")
    schema = json.dumps(advise.input_schema)
    for field in ("images", "videos", "media_kwargs"):
        assert field in schema, f"advise schema is missing {field}"


@pytest.mark.model
def test_mcp_advise_accepts_an_inline_image(base_url: str) -> None:
    arguments = {
        "input": {
            "state": "Review the attached color swatch.",
            "images": [_png_data_uri()],
            "questions": {
                "red": {
                    "type": "noul",
                    "instructions": "Is the image predominantly red?",
                }
            },
        }
    }
    result = asyncio.run(_call_advise(mcp_stdin_params(base_url), arguments))
    assert result.is_error is False
    answer = _payload(result)["answers"]["red"]
    assert answer["type"] == "noul"
    assert answer["noul"] > 0.5, "the model should read the red swatch as red"


@pytest.mark.model
def test_mcp_advise_returns_typed_answers(base_url: str) -> None:
    result = asyncio.run(_call_advise(mcp_stdin_params(base_url)))
    assert result.is_error is False
    answers = _payload(result)["answers"]
    assert answers["urgent"]["type"] == "noul"
    assert 0.0 <= answers["urgent"]["noul"] <= 1.0
    team = answers["team"]
    assert team["type"] == "choice"
    assert team["choice"] in {"auth", "frontend"}
    assert abs(sum(team["probabilities"].values()) - 1.0) < 0.05


def test_mcp_surfaces_error_when_server_down_and_autostart_off() -> None:
    params = mcp_stdin_params(f"http://127.0.0.1:{free_port()}", autostart="0")
    try:
        result = asyncio.run(_call_advise(params))
    except Exception:
        # A raised protocol error is an acceptable way to report the failure.
        return
    assert result.is_error is True


def test_mcp_autostart_reports_a_missing_model_quickly(tmp_path) -> None:
    params = mcp_stdin_params(
        f"http://127.0.0.1:{free_port()}",
        autostart="1",
        EMBER_MODEL_DIR=str(tmp_path / "missing"),
        EMBER_STATE_DIR=str(tmp_path / "state"),
    )
    started = time.time()
    result = asyncio.run(_call_advise(params))
    assert result.is_error is True
    assert "ember model pull" in result.content[0].text
    assert time.time() - started < 30


@pytest.mark.model
def test_mcp_autostart_launches_server_on_configured_port(tmp_path) -> None:
    # The spawned server resolves the model the same way, so skip like the others.
    if models.resolve_dir(None) is None:
        if os.environ.get("EMBER_REQUIRE_MODEL") == "1":
            pytest.fail("model not pulled (EMBER_REQUIRE_MODEL=1)")
        pytest.skip("model not pulled")
    pidfile = tmp_path / "server.pid"
    params = mcp_stdin_params(
        f"http://127.0.0.1:{free_port()}",
        autostart="1",
        EMBER_STATE_DIR=str(tmp_path),
    )
    try:
        result = asyncio.run(_call_advise(params))
        assert result.is_error is False
        assert pidfile.exists(), "autostart did not record the spawned server PID"
    finally:
        if pidfile.exists():
            terminate_pid(int(pidfile.read_text().strip()))


def test_ensure_server_never_autostarts_for_a_non_loopback_endpoint(
    monkeypatch,
) -> None:
    """US3 T020: spec Clarification 5/FR-007; contracts/hosted-endpoint.md rules 2
    and 6 — a hosted endpoint is just another non-loopback server_url, and
    the existing `_ensure_server` guard (`if not endpoint.is_local: return`) already
    makes autostart/fallback impossible for it. This locks that in directly rather
    than relying on an unreachable real network call to prove the negative."""

    def _fail_if_called(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError(
            "process.is_up must not be consulted for a remote endpoint"
        )

    monkeypatch.setattr(mcp_server.process, "is_up", _fail_if_called)
    remote = Endpoint(
        url="https://hosted.example",
        host="hosted.example",
        scheme="https",
        is_local=False,
        allow_insecure_transport=False,
        request_timeout=5,
    )
    mcp_server._ensure_server(remote)  # must return immediately, no exception


def test_mcp_advertises_instructions_and_guide_resource() -> None:
    """Agents learn the tool from initialize.instructions and the ember://guide
    resource, neither of which needs the model server."""
    params = mcp_stdin_params(f"http://127.0.0.1:{free_port()}", autostart="0")

    async def run():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                resources = await session.list_resources()
                guide = await session.read_resource(agent_kit.GUIDE_URI)
                return init, resources, guide

    init, resources, guide = asyncio.run(run())
    assert init.server_info.name == "ember"
    assert init.instructions == agent_kit.instructions()
    assert agent_kit.GUIDE_URI in {
        str(resource.uri) for resource in resources.resources
    }
    assert guide.contents[0].text == agent_kit.skill()


@pytest.mark.model
def test_mcp_returns_actionable_errors_for_malformed_questions(base_url: str) -> None:
    missing_criteria = {
        "input": {
            "state": "x",
            "questions": {"team": {"type": "choice", "instructions": "Which?"}},
        }
    }
    result = asyncio.run(_call_advise(mcp_stdin_params(base_url), missing_criteria))
    assert result.is_error is True
    assert "criteria must not be empty" in result.content[0].text


# ###########################################################################
# Direct client tests against a stub endpoint (no model required)
# ###########################################################################
class _StubHandler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:
        return

    def _reply(self, code: int, body: str, content_type: str) -> None:
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _record(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw) if raw else {}
        except ValueError:
            payload = {}
        self.stub.requests.append(
            {
                "path": self.path,
                "headers": {k.lower(): v for k, v in self.headers.items()},
                "payload": payload,
            }
        )

    def do_GET(self) -> None:
        self._record()
        if self.path == "/health":
            self._reply(
                200,
                json.dumps(
                    {
                        "status": "ok",
                        "pid": 1,
                        "engine": None,
                        "version": "test",
                        "auth_required": False,
                    }
                ),
                "application/json",
            )
        else:
            self._reply(404, "{}", "application/json")

    def do_POST(self) -> None:
        self._record()
        stub = self.stub
        if stub.raw is not None:
            self._reply(stub.status, stub.raw, stub.content_type)
        elif stub.status >= 400:
            self._reply(stub.status, "nope", "text/plain")
        else:
            self._reply(200, json.dumps(stub.payload), "application/json")


class _Stub:
    def __init__(self, status: int, payload: dict, raw: str | None, content_type: str):
        self.status = status
        self.payload = payload
        self.raw = raw
        self.content_type = content_type
        self.requests: list[dict] = []


@pytest.fixture
def stub_env(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path / "state"))
    for name in (
        "EMBER_SERVER_URL",
        "EMBER_AUTH_TOKEN",
        "EMBER_AUTH_HEADER",
        "EMBER_ALLOW_INSECURE_TRANSPORT",
        "EMBER_REQUEST_TIMEOUT",
        "EMBER_SERVER_AUTH_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def stub_server():
    servers: list[ThreadingHTTPServer] = []

    def make(
        *,
        status: int = 200,
        payload: dict | None = None,
        raw: str | None = None,
        content_type: str = "application/json",
    ):
        stub = _Stub(
            status=status,
            payload=(
                payload
                if payload is not None
                else {"model": "clef-flash", "answers": {}, "usage": {}}
            ),
            raw=raw,
            content_type=content_type,
        )
        handler = type("Handler", (_StubHandler,), {"stub": stub})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}", stub

    yield make
    for server in servers:
        server.shutdown()
        server.server_close()


def _call_direct(monkeypatch, url: str, *, images=None, model="clef-flash"):
    monkeypatch.setenv("EMBER_SERVER_URL", url)
    monkeypatch.setenv("EMBER_AUTOSTART", "0")
    fields = {
        "state": "read this",
        "questions": {"q": {"type": "noul"}},
        "model": model,
    }
    if images is not None:
        fields["images"] = images
    return asyncio.run(mcp_server.advise(AdviseInput(**fields)))


def test_client_sends_bearer_token(stub_env, stub_server, monkeypatch):
    url, stub = stub_server()
    monkeypatch.setenv("EMBER_AUTH_TOKEN", "s3cret")
    _call_direct(monkeypatch, url)
    assert stub.requests[-1]["headers"].get("authorization") == "Bearer s3cret"


def test_client_sends_custom_header(stub_env, stub_server, monkeypatch):
    url, stub = stub_server()
    monkeypatch.setenv("EMBER_AUTH_TOKEN", "s3cret")
    monkeypatch.setenv("EMBER_AUTH_HEADER", "X-API-KEY")
    _call_direct(monkeypatch, url)
    assert stub.requests[-1]["headers"].get("x-api-key") == "s3cret"


def test_auth_failure_hides_secret(stub_env, stub_server, monkeypatch):
    url, _ = stub_server(status=401)
    monkeypatch.setenv("EMBER_AUTH_TOKEN", "supersecret")
    with pytest.raises(ToolError) as excinfo:
        _call_direct(monkeypatch, url)
    assert "authentication failed" in str(excinfo.value)
    assert "supersecret" not in str(excinfo.value)


def test_remote_advise_forwards_media(stub_env, stub_server, monkeypatch):
    url, stub = stub_server()
    _call_direct(monkeypatch, url, images=[_png_data_uri()])
    assert stub.requests[-1]["payload"]["images"]


def test_request_sent_only_to_configured_endpoint(stub_env, stub_server, monkeypatch):
    url, stub = stub_server()
    _call_direct(monkeypatch, url)
    posts = [r for r in stub.requests if r["path"] == "/v1/systemone"]
    assert len(posts) == 1


def test_client_works_with_no_local_weights(stub_env, stub_server, monkeypatch):
    url, _ = stub_server()
    assert _call_direct(monkeypatch, url)["model"] == "clef-flash"


def test_unreachable_endpoint_is_actionable(stub_env, monkeypatch):
    monkeypatch.setattr(mcp_server, "AUTOSTART", False)
    monkeypatch.setenv("EMBER_SERVER_URL", f"http://127.0.0.1:{free_port()}")
    with pytest.raises(ToolError, match="not reachable"):
        asyncio.run(
            mcp_server.advise(AdviseInput(state="x", questions={"q": {"type": "noul"}}))
        )


def test_insecure_transport_is_refused(stub_env, monkeypatch):
    monkeypatch.setenv("EMBER_SERVER_URL", "http://192.0.2.1:8765")
    with pytest.raises(ToolError, match="plaintext"):
        asyncio.run(
            mcp_server.advise(AdviseInput(state="x", questions={"q": {"type": "noul"}}))
        )


def test_incompatible_response_is_actionable(stub_env, stub_server, monkeypatch):
    url, _ = stub_server(raw="not json", content_type="text/html")
    with pytest.raises(ToolError, match="valid ember response"):
        _call_direct(monkeypatch, url)


def test_model_mismatch_is_reported(stub_env, stub_server, monkeypatch):
    url, _ = stub_server(payload={"model": "full", "answers": {}, "usage": {}})
    result = _call_direct(monkeypatch, url, model="clef-flash")
    assert "warning" in result


def test_default_model_label_does_not_warn(stub_env, stub_server, monkeypatch):
    url, _ = stub_server(payload={"model": "flash", "answers": {}, "usage": {}})
    monkeypatch.setenv("EMBER_SERVER_URL", url)
    monkeypatch.setenv("EMBER_AUTOSTART", "0")
    result = asyncio.run(
        mcp_server.advise(AdviseInput(state="x", questions={"q": {"type": "noul"}}))
    )
    assert "warning" not in result


def test_remote_answer_shape_matches_local(stub_env, stub_server, monkeypatch):
    local_shape = {
        "model": "clef-flash",
        "answers": {"q": {"type": "noul", "noul": 0.9}},
        "usage": {"input_tokens": 1, "output_tokens": 0},
        "latency_ms": 12.3,
    }
    url, _ = stub_server(payload=local_shape)
    result = _call_direct(monkeypatch, url)
    assert set(result) >= {"model", "answers", "usage", "latency_ms"}
    assert result["answers"]["q"]["type"] == "noul"
    assert 0.0 <= result["answers"]["q"]["noul"] <= 1.0
    assert result["usage"]["output_tokens"] == 0


def _error_endpoint() -> Endpoint:
    return Endpoint(
        url="https://example.com",
        host="example.com",
        scheme="https",
        is_local=False,
        allow_insecure_transport=False,
        request_timeout=7,
    )


def test_classifier_timeout_names_the_bound():
    message = mcp_server._client_error_message(
        httpx.ConnectTimeout("slow"), _error_endpoint()
    )
    assert "timed out after 7s" in message


def test_classifier_certificate_is_distinct_from_unreachable():
    exc = httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED]")
    exc.__cause__ = ssl.SSLCertVerificationError("certificate verify failed")
    message = mcp_server._client_error_message(exc, _error_endpoint())
    assert "certificate" in message.lower()


def test_classifier_unreachable_error():
    message = mcp_server._client_error_message(
        httpx.ConnectError("connection refused"), _error_endpoint()
    )
    assert "not reachable" in message


# ###########################################################################
# R-002: advise() must log a call summary (question IDs + model) to stderr
# ###########################################################################
# ###########################################################################
# S-004: MCP main() must warn when EMBER_SERVER_URL is non-loopback + insecure
# ###########################################################################
# ###########################################################################
# R-003: MCP log format must include a timestamp (structured logging)
# ###########################################################################
def test_mcp_log_format_includes_timestamp(monkeypatch):
    """R-003: The MCP logger's formatter must include a timestamp so log
    lines are correlatable with server-side events and auditable."""
    import logging

    logger = logging.getLogger("ember-mcp")
    handlers = logger.handlers or logging.root.handlers
    for handler in handlers:
        fmt = handler.formatter
        if fmt is not None:
            pattern = fmt._fmt if hasattr(fmt, "_fmt") else str(fmt)
            if "%(asctime)s" in pattern or "asctime" in pattern:
                return
    pytest.fail(
        "R-003: ember-mcp logger must use a formatter that includes %(asctime)s"
    )


def test_main_logs_warning_when_server_url_is_non_loopback_and_insecure(
    monkeypatch, caplog
):
    """S-004: mcp_server.main() must emit a WARNING when EMBER_SERVER_URL
    resolves to a non-loopback address and EMBER_ALLOW_INSECURE_TRANSPORT is
    enabled — state containing secrets would be sent in plaintext over the
    network without this advisory."""
    import logging

    monkeypatch.setenv("EMBER_SERVER_URL", "http://192.0.2.1:8765")
    monkeypatch.setenv("EMBER_ALLOW_INSECURE_TRANSPORT", "1")
    monkeypatch.setattr(mcp_server.mcp, "run", lambda: None)
    with caplog.at_level(logging.WARNING, logger="ember-mcp"):
        mcp_server.main()
    assert any(
        "insecure" in r.message.lower() or "non-loopback" in r.message.lower()
        for r in caplog.records
        if r.levelno >= logging.WARNING
    ), "S-004: main() must warn about non-loopback insecure transport"


def test_main_no_warning_when_server_url_is_loopback(monkeypatch, caplog):
    """S-004: No warning when EMBER_SERVER_URL is loopback (default case)."""
    import logging

    monkeypatch.setenv("EMBER_SERVER_URL", "http://127.0.0.1:8765")
    monkeypatch.delenv("EMBER_ALLOW_INSECURE_TRANSPORT", raising=False)
    monkeypatch.setattr(mcp_server.mcp, "run", lambda: None)
    with caplog.at_level(logging.WARNING, logger="ember-mcp"):
        mcp_server.main()
    assert not any(
        "insecure" in r.message.lower() or "non-loopback" in r.message.lower()
        for r in caplog.records
        if r.levelno >= logging.WARNING
    ), "S-004: no warning expected for loopback URL"


def test_advise_logs_question_ids_on_success(
    stub_env, stub_server, monkeypatch, caplog
):
    """R-002: Each successful advise call must log question IDs and model label
    so there is a minimal audit trail without persisting state content."""
    import logging

    url, _ = stub_server(
        payload={
            "model": "clef-flash",
            "answers": {"q": {"type": "noul", "noul": 0.9}},
            "usage": {},
        }
    )
    monkeypatch.setenv("EMBER_SERVER_URL", url)
    monkeypatch.setenv("EMBER_AUTOSTART", "0")
    with caplog.at_level(logging.INFO, logger="ember-mcp"):
        asyncio.run(
            mcp_server.advise(AdviseInput(state="x", questions={"q": {"type": "noul"}}))
        )
    combined = caplog.text
    assert "advise" in combined.lower() or "q" in combined, (
        "R-002: advise() must log question IDs or a call summary to stderr"
    )


# ###########################################################################
# I-002: ToolError messages must not include raw server error bodies
# ###########################################################################
def test_server_4xx_error_body_is_sanitized(stub_env, stub_server, monkeypatch):
    """I-002: A 4xx response body must not include raw filesystem paths or
    stack traces — only the actionable message is forwarded to the agent.
    The msg field deliberately contains a path and a traceback marker so the
    test fails if the sanitizer is removed or bypassed."""
    fastapi_422 = json.dumps(
        {
            "detail": [
                {
                    "type": "value_error",
                    "loc": ["body", "state"],
                    "msg": (
                        "Traceback (most recent call last):"
                        " /home/user/ember/serving/runtime.py line 42"
                    ),
                    "url": "https://errors.pydantic.dev/...",
                }
            ]
        }
    )
    url, _ = stub_server(status=422, raw=fastapi_422, content_type="application/json")
    with pytest.raises(ToolError) as exc_info:
        _call_direct(monkeypatch, url)
    error_text = str(exc_info.value)
    assert "422" in error_text
    assert "/home/" not in error_text, "filesystem paths must not leak in ToolError"
    assert "Traceback" not in error_text, "traceback markers must not leak in ToolError"


def test_server_5xx_error_returns_generic_message(stub_env, stub_server, monkeypatch):
    """I-002: A 5xx body with filesystem paths must not be forwarded verbatim."""
    url, _ = stub_server(
        status=500,
        raw="/home/user/ember/ember/serving/runtime.py: RuntimeError at line 42",
        content_type="text/plain",
    )
    with pytest.raises(ToolError) as exc_info:
        _call_direct(monkeypatch, url)
    error_text = str(exc_info.value)
    assert "/home/" not in error_text, "5xx body must not forward filesystem paths"
    assert "500" in error_text


# ###########################################################################
# Over-limit refusals reach the agent intact (contracts/mcp-tool.md)
# ###########################################################################
def _refusals() -> list[str]:
    from ember.serving.limit_source import LimitSource
    from ember.serving.limits import Limits
    from ember.serving.request_size import RequestSize, refusal_message

    def caps(max_length, max_source, cap, cap_source):
        return Limits(
            max_length=max_length,
            max_length_source=max_source,
            max_request_length=cap,
            max_request_length_source=cap_source,
        )

    model, operator = LimitSource.MODEL, LimitSource.OPERATOR
    return [
        refusal_message(
            RequestSize(total=41230, state=39800, media=0, fixed=1430),
            caps(262144, model, 32768, LimitSource.FALLBACK),
            262144,
        ),
        refusal_message(
            RequestSize(total=2600, state=900, media=1200, fixed=500),
            caps(1024, operator, 0, operator),
            262144,
        ),
        refusal_message(
            RequestSize(total=300000, state=298570, media=0, fixed=1430),
            caps(262144, model, 0, operator),
            262144,
        ),
        refusal_message(
            RequestSize(total=3000, state=10, media=0, fixed=2990),
            caps(262144, model, 2048, operator),
            262144,
        ),
    ]


@pytest.mark.parametrize("message", _refusals())
def test_a_refusal_reaches_the_agent_intact(
    message, stub_env, stub_server, monkeypatch
):
    url, _ = stub_server(status=413, raw=json.dumps({"detail": message}))
    with pytest.raises(ToolError) as exc_info:
        _call_direct(monkeypatch, url)
    assert str(exc_info.value) == "ember server error 413: " + message


@pytest.mark.model
def test_mcp_refuses_an_oversized_request_end_to_end(base_url: str) -> None:
    engine = httpx.get(f"{base_url}/health", timeout=10.0).json()["engine"]
    cap, maximum = engine["max_request_length"], engine["max_length"]
    enforced = min(cap, maximum) if cap else maximum
    arguments = {
        "input": {
            "state": "word " * (enforced + 100),
            "questions": {"urgent": {"type": "noul", "instructions": "Is it urgent?"}},
        }
    }
    result = asyncio.run(_call_advise(mcp_stdin_params(base_url), arguments))
    assert result.is_error is True
    text = result.content[0].text
    # Over stdio, mcp prefixes tool errors with "Error executing tool advise: ".
    assert "ember server error 413: request too large:" in text
    assert "Split: state" in text
