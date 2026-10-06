"""Unit tests for the client inference endpoint helper (remote inference)."""

from __future__ import annotations

import pytest
from ember.cfg import config
from ember.cfg import endpoint as ep


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
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


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "127.0.0.2", "::1"])
def test_loopback_hosts_are_local(host: str) -> None:
    assert ep.is_loopback_host(host) is True


@pytest.mark.parametrize("host", ["::ffff:127.0.0.1"])
def test_ipv4_mapped_ipv6_loopback_is_local(host: str) -> None:
    assert ep.is_loopback_host(host) is True


@pytest.mark.parametrize("host", ["192.0.2.1", "0.0.0.0", "example.com", None, ""])  # noqa: S104
def test_non_loopback_hosts_are_not_local(host) -> None:
    assert ep.is_loopback_host(host) is False


def test_resolve_defaults_to_loopback(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path / "state"))
    resolved = ep.Endpoint.resolve()
    assert resolved.is_local is True
    assert resolved.url == "http://127.0.0.1:8765"
    assert resolved.request_timeout == 300


def test_resolve_rejects_non_http_scheme(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("EMBER_SERVER_URL", "ftp://example.com")
    with pytest.raises(ep.InvalidEndpointError):
        ep.Endpoint.resolve()


def test_resolve_rejects_plaintext_remote_by_default(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("EMBER_SERVER_URL", "http://192.0.2.1:8765")
    with pytest.raises(ep.InsecureEndpointError):
        ep.Endpoint.resolve()


def test_resolve_allows_plaintext_remote_with_override(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("EMBER_SERVER_URL", "http://192.0.2.1:8765")
    monkeypatch.setenv("EMBER_ALLOW_INSECURE_TRANSPORT", "true")
    resolved = ep.Endpoint.resolve()
    assert resolved.is_local is False


def test_resolve_allows_https_remote(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("EMBER_SERVER_URL", "https://example.com")
    resolved = ep.Endpoint.resolve()
    assert resolved.is_local is False
    assert resolved.scheme == "https"


def test_url_override_beats_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("EMBER_SERVER_URL", "https://example.com")
    resolved = ep.Endpoint.resolve(url="http://127.0.0.1:9999")
    assert resolved.url == "http://127.0.0.1:9999"


def test_request_timeout_env_override(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("EMBER_REQUEST_TIMEOUT", "5")
    assert ep.Endpoint.resolve().request_timeout == 5


def test_build_auth_headers_default_is_bearer(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("EMBER_AUTH_TOKEN", "s3cret")
    assert ep.build_auth_headers() == {"Authorization": "Bearer s3cret"}


def test_build_auth_headers_custom_header(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("EMBER_AUTH_TOKEN", "s3cret")
    monkeypatch.setenv("EMBER_AUTH_HEADER", "X-API-KEY")
    assert ep.build_auth_headers() == {"X-API-KEY": "s3cret"}


def test_build_auth_headers_empty_when_no_token(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EMBER_STATE_DIR", str(tmp_path / "state"))
    assert ep.build_auth_headers() == {}


def test_config_file_env_precedence(monkeypatch, tmp_path) -> None:
    state = tmp_path / "state"
    monkeypatch.setenv("EMBER_STATE_DIR", str(state))
    state.mkdir(parents=True, exist_ok=True)
    config.save({"server_url": "https://config.example.com"})
    assert ep.Endpoint.resolve().url == "https://config.example.com"
    monkeypatch.setenv("EMBER_SERVER_URL", "https://env.example.com")
    assert ep.Endpoint.resolve().url == "https://env.example.com"
