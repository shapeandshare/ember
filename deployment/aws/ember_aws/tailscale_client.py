"""TailscaleClient: Tailscale API client for operator-side operations."""

from __future__ import annotations

import os
from typing import Any

import httpx
from pydantic import SecretStr

_BASE_URL = "https://api.tailscale.com"


class TailscaleError(Exception):
    """Raised when the Tailscale API returns an error.

    Parameters
    ----------
    message : str
        The ``message`` field from the Tailscale API error body.
    """


class TailscaleClient:
    """Tailscale API client for operator-side deployment operations.

    Exchanges an OAuth client credential for a short-lived bearer token,
    then mints and deletes auth keys and manages tailnet devices.

    Parameters
    ----------
    client_id : str
        Tailscale OAuth client ID (``TS_OAUTH_CLIENT_ID``).
    client_secret : SecretStr
        Tailscale OAuth client secret (``TS_OAUTH_CLIENT_SECRET``).
        Stored as a ``SecretStr`` so it never appears in ``repr`` or logs.
    transport : httpx.BaseTransport | None
        Optional custom transport (used in tests via ``httpx.MockTransport``).
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str | SecretStr,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.client_id = client_id
        self._client_secret: SecretStr = (
            client_secret
            if isinstance(client_secret, SecretStr)
            else SecretStr(client_secret)
        )
        self._transport = transport
        self._cached_token: str | None = None

    def __repr__(self) -> str:
        """Return a repr that never exposes the secret."""
        return f"TailscaleClient(client_id={self.client_id!r})"

    def __str__(self) -> str:
        """Return a str that never exposes the secret."""
        return f"TailscaleClient(client_id={self.client_id!r})"

    @classmethod
    def from_env(cls) -> TailscaleClient:
        """Build a client from environment variables.

        Reads ``TS_OAUTH_CLIENT_ID`` and ``TS_OAUTH_CLIENT_SECRET``.

        Returns
        -------
        TailscaleClient
            A client configured from the environment.

        Raises
        ------
        TailscaleError
            If either environment variable is missing.
        """
        client_id = os.environ.get("TS_OAUTH_CLIENT_ID")
        client_secret = os.environ.get("TS_OAUTH_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise TailscaleError(
                "TS_OAUTH_CLIENT_ID and TS_OAUTH_CLIENT_SECRET must be set"
            )
        return cls(client_id=client_id, client_secret=client_secret)

    def _http_client(self) -> httpx.Client:
        """Return an httpx client, optionally with a custom transport."""
        if self._transport is not None:
            return httpx.Client(transport=self._transport, base_url=_BASE_URL)
        return httpx.Client(base_url=_BASE_URL)

    def _raise_for_error(self, response: httpx.Response) -> None:
        """Raise TailscaleError if the response indicates failure.

        Parameters
        ----------
        response : httpx.Response
            The HTTP response to check.

        Raises
        ------
        TailscaleError
            If the response status is not 2xx.
        """
        if response.is_error:
            try:
                body = response.json()
                message = body.get("message", response.text)
            except Exception:
                message = response.text
            raise TailscaleError(message)

    def token(self) -> str:
        """Exchange the OAuth client credential for a bearer token.

        Posts to ``/api/v2/oauth/token`` with ``grant_type=client_credentials``
        and scopes ``auth_keys devices:core``.

        Returns
        -------
        str
            The access token string.

        Raises
        ------
        TailscaleError
            If the API returns an error.
        """
        with self._http_client() as client:
            response = client.post(
                "/api/v2/oauth/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self._client_secret.get_secret_value(),
                    "grant_type": "client_credentials",
                    "scope": "auth_keys devices:core",
                },
            )
        self._raise_for_error(response)
        body = response.json()
        token: str = body["access_token"]
        self._cached_token = token
        return token

    def _bearer_token(self) -> str:
        """Return a cached or freshly exchanged bearer token."""
        if self._cached_token is None:
            return self.token()
        return self._cached_token

    def mint_join_key(
        self,
        tag: str,
        expiry_s: int = 3600,
    ) -> dict[str, Any]:
        """Mint a single-use Tailscale auth key for the given tag.

        Parameters
        ----------
        tag : str
            The Tailscale ACL tag (e.g. ``"tag:ember"``).
        expiry_s : int
            Key expiry in seconds; defaults to 3600.

        Returns
        -------
        dict[str, Any]
            The API response body (includes ``id`` and ``key``).

        Raises
        ------
        TailscaleError
            If the API returns an error (e.g. tag ownership failure).
        """
        bearer = self._bearer_token()
        with self._http_client() as client:
            response = client.post(
                "/api/v2/tailnet/-/keys",
                json={
                    "capabilities": {
                        "devices": {
                            "create": {
                                "reusable": False,
                                "ephemeral": False,
                                "preauthorized": True,
                                "tags": [tag],
                            }
                        }
                    },
                    "expirySeconds": expiry_s,
                },
                headers={"Authorization": f"Bearer {bearer}"},
            )
        self._raise_for_error(response)
        result: dict[str, Any] = response.json()
        return result

    def delete_key(self, key_id: str) -> None:
        """Delete a Tailscale auth key by ID.

        Parameters
        ----------
        key_id : str
            The key ID returned by :meth:`mint_join_key`.

        Raises
        ------
        TailscaleError
            If the API returns an error.
        """
        bearer = self._bearer_token()
        with self._http_client() as client:
            response = client.delete(
                f"/api/v2/tailnet/-/keys/{key_id}",
                headers={"Authorization": f"Bearer {bearer}"},
            )
        self._raise_for_error(response)

    def devices(self) -> list[dict[str, Any]]:
        """List all devices on the tailnet.

        Returns
        -------
        list[dict[str, Any]]
            The list of device objects from the API.

        Raises
        ------
        TailscaleError
            If the API returns an error.
        """
        bearer = self._bearer_token()
        with self._http_client() as client:
            response = client.get(
                "/api/v2/tailnet/-/devices",
                headers={"Authorization": f"Bearer {bearer}"},
            )
        self._raise_for_error(response)
        body = response.json()
        result: list[dict[str, Any]] = body.get("devices", [])
        return result

    def delete_devices(self, hostname: str, tag: str) -> None:
        """Delete tailnet devices matching both hostname and tag.

        Only devices whose ``hostname`` equals ``hostname`` **and** whose
        ``tags`` list includes ``tag`` are deleted.

        Parameters
        ----------
        hostname : str
            The exact hostname to match (e.g. ``"ember-default"``).
        tag : str
            The tag that must be present (e.g. ``"tag:ember"``).

        Raises
        ------
        TailscaleError
            If the API returns an error.
        """
        all_devices = self.devices()
        for device in all_devices:
            device_hostname = device.get("hostname", "")
            device_tags: list[str] = device.get("tags", [])
            if device_hostname == hostname and tag in device_tags:
                bearer = self._bearer_token()
                with self._http_client() as client:
                    response = client.delete(
                        f"/api/v2/device/{device['id']}",
                        headers={"Authorization": f"Bearer {bearer}"},
                    )
                self._raise_for_error(response)

    def tailnet_dns(self) -> dict[str, Any]:
        """Return MagicDNS status and the tailnet suffix.

        Queries ``GET /api/v2/tailnet/-/dns/preferences``.

        Returns
        -------
        dict[str, Any]
            A dict with keys ``magic_dns`` (bool) and ``suffix`` (str,
            the ``<tailnet>.ts.net`` domain).

        Raises
        ------
        TailscaleError
            If the API returns an error.
        """
        bearer = self._bearer_token()
        with self._http_client() as client:
            response = client.get(
                "/api/v2/tailnet/-/dns/preferences",
                headers={"Authorization": f"Bearer {bearer}"},
            )
        self._raise_for_error(response)
        body = response.json()
        magic_dns: bool = body.get("magicDNS", False)
        domains: list[dict[str, Any]] = body.get("domains", [])
        suffix = domains[0]["suffix"] if domains else ""
        return {"magic_dns": magic_dns, "suffix": suffix}
