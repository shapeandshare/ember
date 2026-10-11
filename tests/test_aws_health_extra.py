"""Extra tests for health.py: non-cuda 200, DNS/TLS hint, HTTP error status."""

from __future__ import annotations

from typing import Any

import httpx


class TestWaitHealthyExtra:
    """Additional wait_healthy() coverage for uncovered branches."""

    def test_non_cuda_200_keeps_polling_until_cuda(self) -> None:
        """wait_healthy() keeps polling when 200 but device != cuda."""
        from ember_aws.health import wait_healthy

        call_count = 0

        def _handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "engine": {"device": "cpu"},
                        "version": "0.12.0",
                    },
                )
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "engine": {"device": "cuda"},
                    "version": "0.12.0",
                },
            )

        transport = httpx.MockTransport(_handler)
        result = wait_healthy(
            url="https://ember-default.example.ts.net",
            token="tok",
            timeout_s=60,
            transport=transport,
            poll_interval_s=0,
        )
        assert result["engine"]["device"] == "cuda"
        assert call_count == 3

    def test_non_200_non_503_status_keeps_polling(self) -> None:
        """wait_healthy() keeps polling on unexpected HTTP status codes."""
        from ember_aws.health import wait_healthy

        call_count = 0

        def _handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return httpx.Response(502, text="Bad Gateway")
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "engine": {"device": "cuda"},
                    "version": "0.12.0",
                },
            )

        transport = httpx.MockTransport(_handler)
        result = wait_healthy(
            url="https://ember-default.example.ts.net",
            token="tok",
            timeout_s=60,
            transport=transport,
            poll_interval_s=0,
        )
        assert result["engine"]["device"] == "cuda"

    def test_dns_tls_hint_printed_on_name_resolution_error(self, capsys: Any) -> None:
        """wait_healthy() prints a DNS/TLS hint when a name resolution error occurs."""
        from ember_aws.health import wait_healthy

        call_count = 0

        def _handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "engine": {"device": "cuda"},
                        "version": "0.12.0",
                    },
                )
            raise Exception("Name or service not known")

        transport = httpx.MockTransport(_handler)
        result = wait_healthy(
            url="https://ember-default.example.ts.net",
            token="tok",
            timeout_s=60,
            transport=transport,
            poll_interval_s=0,
        )
        assert result["engine"]["device"] == "cuda"
        captured = capsys.readouterr()
        assert "waiting" in captured.out.lower() or "tls" in captured.out.lower()

    def test_tls_error_prints_hint(self, capsys: Any) -> None:
        """wait_healthy() prints a DNS/TLS hint when a TLS error occurs."""
        from ember_aws.health import wait_healthy

        call_count = 0

        def _handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "engine": {"device": "cuda"},
                        "version": "0.12.0",
                    },
                )
            raise Exception("TLS handshake failed")

        transport = httpx.MockTransport(_handler)
        result = wait_healthy(
            url="https://ember-default.example.ts.net",
            token="tok",
            timeout_s=60,
            transport=transport,
            poll_interval_s=0,
        )
        assert result["engine"]["device"] == "cuda"
        captured = capsys.readouterr()
        assert "waiting" in captured.out.lower() or "tls" in captured.out.lower()

    def test_503_status_text_printed_once_per_change(self, capsys: Any) -> None:
        """wait_healthy() prints the 503 status text only when it changes."""
        from ember_aws.health import wait_healthy

        call_count = 0

        def _handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(
                    503,
                    json={"status": "loading", "engine": {"device": "cpu"}},
                )
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "engine": {"device": "cuda"},
                    "version": "0.12.0",
                },
            )

        transport = httpx.MockTransport(_handler)
        wait_healthy(
            url="https://ember-default.example.ts.net",
            token="tok",
            timeout_s=60,
            transport=transport,
            poll_interval_s=0,
        )
        captured = capsys.readouterr()
        assert captured.out.count("loading") == 1

    def test_health_timeout_error_has_last_response(self) -> None:
        """HealthTimeoutError carries the last_response attribute."""
        from ember_aws.health import HealthTimeoutError

        exc = HealthTimeoutError("timed out", last_response="HTTP 503: loading")
        assert exc.last_response == "HTTP 503: loading"

    def test_health_timeout_alias_works(self) -> None:
        """HealthTimeout is an alias for HealthTimeoutError."""
        from ember_aws.health import HealthTimeout, HealthTimeoutError

        assert HealthTimeout is HealthTimeoutError

    def test_non_cuda_device_status_printed_once(self, capsys: Any) -> None:
        """wait_healthy() prints device=cpu status once when device is not cuda."""
        from ember_aws.health import wait_healthy

        call_count = 0

        def _handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "engine": {"device": "cpu"},
                        "version": "0.12.0",
                    },
                )
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "engine": {"device": "cuda"},
                    "version": "0.12.0",
                },
            )

        transport = httpx.MockTransport(_handler)
        wait_healthy(
            url="https://ember-default.example.ts.net",
            token="tok",
            timeout_s=60,
            transport=transport,
            poll_interval_s=0,
        )
        captured = capsys.readouterr()
        assert captured.out.count("device=cpu") == 1

    def test_safe_json_returns_empty_dict_on_invalid_json(self) -> None:
        """_safe_json() returns {} when the response body is not valid JSON."""
        from ember_aws.health import _safe_json

        resp = httpx.Response(200, text="not json")
        result = _safe_json(resp)
        assert result == {}


class TestProbeHealth:
    """probe_health() reads /health once and never raises."""

    def test_returns_the_body_on_200(self) -> None:
        """A 200 response yields the parsed body (including the pid)."""
        from ember_aws.health import probe_health

        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json={"status": "ok", "pid": 7})
        )

        result = probe_health(
            url="https://ember-default.example.ts.net", token="tok", transport=transport
        )

        assert result == {"status": "ok", "pid": 7}

    def test_returns_none_when_not_200(self) -> None:
        """A non-200 response yields None."""
        from ember_aws.health import probe_health

        transport = httpx.MockTransport(lambda request: httpx.Response(503))

        result = probe_health(
            url="https://ember-default.example.ts.net", token="tok", transport=transport
        )

        assert result is None


class TestWaitHealthyPreviousPid:
    """wait_healthy() ignores a healthy response from the pre-restart process."""

    def test_keeps_polling_until_the_pid_changes(self) -> None:
        """A cuda response from the previous pid cannot end the wait."""
        from ember_aws.health import wait_healthy

        call_count = 0

        def _handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            pid = 1 if call_count < 3 else 2
            return httpx.Response(
                200,
                json={"status": "ok", "pid": pid, "engine": {"device": "cuda"}},
            )

        transport = httpx.MockTransport(_handler)
        result = wait_healthy(
            url="https://ember-default.example.ts.net",
            token="tok",
            timeout_s=60,
            transport=transport,
            poll_interval_s=0,
            previous_pid=1,
        )

        assert result["pid"] == 2
        assert call_count == 3
