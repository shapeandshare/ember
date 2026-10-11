"""Tests for TailscaleClient (T017)."""

from __future__ import annotations

import json

import httpx
import pytest

from ember_aws.tailscale_client import TailscaleClient, TailscaleError


class _MockTransport(httpx.MockTransport):
    """Thin wrapper that records requests for assertion."""

    def __init__(self, handler: object) -> None:
        self._handler = handler
        self.requests: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._handler(request)  # type: ignore[operator]


def _make_transport(
    responses: dict[str, httpx.Response],
) -> _MockTransport:
    """Build a mock transport from a path → response mapping."""

    def handler(request: httpx.Request) -> httpx.Response:
        key = f"{request.method} {request.url.path}"
        if key in responses:
            return responses[key]
        return httpx.Response(404, json={"message": f"no mock for {key}"})

    return _MockTransport(handler)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def token_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={"access_token": "tok-abc123", "token_type": "Bearer", "expires_in": 3600},
    )


@pytest.fixture
def mint_key_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "key-xyz",
            "key": "tskey-auth-abc",
            "expires": "2026-10-12T00:00:00Z",
        },
    )


@pytest.fixture
def devices_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "devices": [
                {
                    "id": "dev-1",
                    "hostname": "ember-default",
                    "tags": ["tag:ember"],
                },
                {
                    "id": "dev-2",
                    "hostname": "ember-other",
                    "tags": ["tag:ember"],
                },
                {
                    "id": "dev-3",
                    "hostname": "ember-default",
                    "tags": ["tag:other"],
                },
            ]
        },
    )


@pytest.fixture
def dns_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "magicDNS": True,
            "domains": [{"suffix": "example.ts.net"}],
        },
    )


# ---------------------------------------------------------------------------
# Token exchange
# ---------------------------------------------------------------------------


def test_token_exchange_posts_correct_fields(
    token_response: httpx.Response,
) -> None:
    """token() posts client_id, client_secret, grant_type, and scope."""
    transport = _make_transport({"POST /api/v2/oauth/token": token_response})
    client = TailscaleClient(
        client_id="cid",
        client_secret="csec",  # type: ignore[arg-type]
        transport=transport,
    )
    tok = client.token()
    assert tok == "tok-abc123"

    req = transport.requests[0]
    body = dict(pair.split("=") for pair in req.content.decode().split("&"))
    assert body["client_id"] == "cid"
    assert body["client_secret"] == "csec"
    assert body["grant_type"] == "client_credentials"
    assert "auth_keys" in body["scope"]
    assert "devices%3Acore" in body["scope"] or "devices:core" in body["scope"]


def test_token_secret_not_in_str() -> None:
    """The secret must not appear in str() of the client."""
    client = TailscaleClient(
        client_id="cid",
        client_secret="super-secret-value",  # type: ignore[arg-type]
    )
    assert "super-secret-value" not in str(client)
    assert "super-secret-value" not in repr(client)


# ---------------------------------------------------------------------------
# mint_join_key
# ---------------------------------------------------------------------------


def test_mint_join_key_posts_correct_body(
    token_response: httpx.Response,
    mint_key_response: httpx.Response,
) -> None:
    """mint_join_key posts the expected capabilities and expirySeconds."""
    transport = _make_transport(
        {
            "POST /api/v2/oauth/token": token_response,
            "POST /api/v2/tailnet/-/keys": mint_key_response,
        }
    )
    client = TailscaleClient(
        client_id="cid",
        client_secret="csec",  # type: ignore[arg-type]
        transport=transport,
    )
    result = client.mint_join_key("tag:ember")
    assert result["id"] == "key-xyz"

    # Find the keys request
    keys_req = next(
        r for r in transport.requests if r.url.path == "/api/v2/tailnet/-/keys"
    )
    body = json.loads(keys_req.content)
    caps = body["capabilities"]["devices"]["create"]
    assert caps["reusable"] is False
    assert caps["ephemeral"] is False
    assert caps["preauthorized"] is True
    assert "tag:ember" in caps["tags"]
    assert body["expirySeconds"] == 3600


def test_mint_join_key_custom_expiry(
    token_response: httpx.Response,
    mint_key_response: httpx.Response,
) -> None:
    """mint_join_key respects a custom expiry_s."""
    transport = _make_transport(
        {
            "POST /api/v2/oauth/token": token_response,
            "POST /api/v2/tailnet/-/keys": mint_key_response,
        }
    )
    client = TailscaleClient(
        client_id="cid",
        client_secret="csec",  # type: ignore[arg-type]
        transport=transport,
    )
    client.mint_join_key("tag:ember", expiry_s=7200)
    keys_req = next(
        r for r in transport.requests if r.url.path == "/api/v2/tailnet/-/keys"
    )
    body = json.loads(keys_req.content)
    assert body["expirySeconds"] == 7200


# ---------------------------------------------------------------------------
# delete_devices
# ---------------------------------------------------------------------------


def test_delete_devices_filters_by_hostname_and_tag(
    token_response: httpx.Response,
    devices_response: httpx.Response,
) -> None:
    """delete_devices deletes only devices matching hostname AND tag."""
    deleted_ids: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/v2/oauth/token":
            return token_response
        if request.method == "GET" and request.url.path == "/api/v2/tailnet/-/devices":
            return devices_response
        if request.method == "DELETE" and request.url.path.startswith(
            "/api/v2/device/"
        ):
            dev_id = request.url.path.split("/")[-1]
            deleted_ids.append(dev_id)
            return httpx.Response(200)
        return httpx.Response(404)

    transport = _MockTransport(handler)
    client = TailscaleClient(
        client_id="cid",
        client_secret="csec",  # type: ignore[arg-type]
        transport=transport,
    )
    client.delete_devices("ember-default", "tag:ember")

    # Only dev-1 matches hostname=ember-default AND tag=tag:ember
    # dev-2 has different hostname; dev-3 has different tag
    assert deleted_ids == ["dev-1"]


# ---------------------------------------------------------------------------
# tailnet_dns
# ---------------------------------------------------------------------------


def test_tailnet_dns_returns_magicdns_and_suffix(
    token_response: httpx.Response,
    dns_response: httpx.Response,
) -> None:
    """tailnet_dns() returns the MagicDNS flag and the .ts.net suffix."""
    transport = _make_transport(
        {
            "POST /api/v2/oauth/token": token_response,
            "GET /api/v2/tailnet/-/dns/preferences": dns_response,
        }
    )
    client = TailscaleClient(
        client_id="cid",
        client_secret="csec",  # type: ignore[arg-type]
        transport=transport,
    )
    result = client.tailnet_dns()
    assert result["magic_dns"] is True
    assert result["suffix"] == "example.ts.net"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_tailscale_error_on_api_failure() -> None:
    """API errors raise TailscaleError carrying the message."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"message": "invalid credentials"},
        )

    transport = _MockTransport(handler)
    client = TailscaleClient(
        client_id="cid",
        client_secret="csec",  # type: ignore[arg-type]
        transport=transport,
    )
    with pytest.raises(TailscaleError) as exc_info:
        client.token()
    assert "invalid credentials" in str(exc_info.value)


def test_tailscale_error_secret_not_in_str() -> None:
    """TailscaleError must not expose the secret in its str()."""
    err = TailscaleError("some api error")
    assert "super-secret" not in str(err)


# ---------------------------------------------------------------------------
# from_env
# ---------------------------------------------------------------------------


def test_from_env_reads_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """from_env() reads TS_OAUTH_CLIENT_ID and TS_OAUTH_CLIENT_SECRET."""
    monkeypatch.setenv("TS_OAUTH_CLIENT_ID", "env-cid")
    monkeypatch.setenv("TS_OAUTH_CLIENT_SECRET", "env-csec")
    client = TailscaleClient.from_env()
    assert client.client_id == "env-cid"
    # Secret must not be exposed
    assert "env-csec" not in str(client)


def test_from_env_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """from_env() raises when env vars are absent."""
    monkeypatch.delenv("TS_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("TS_OAUTH_CLIENT_SECRET", raising=False)
    with pytest.raises((KeyError, ValueError, TailscaleError)):
        TailscaleClient.from_env()
