"""Client inference endpoint: resolution, loopback classification, and auth headers.

The endpoint is where the MCP client and CLI send advise requests. It is loopback by
default (local-first); a remote endpoint is opt-in through configuration. This module
also owns the transport-security guard (plaintext to a non-local host is refused unless
explicitly overridden) and the credential header construction.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from pydantic import BaseModel

from . import config

HTTP_PORT = 80
HTTPS_PORT = 443
DEFAULT_TIMEOUT = 900


class InvalidEndpointError(ValueError):
    """Raised when the configured endpoint URL is malformed."""


class InsecureEndpointError(ValueError):
    """Raised when a non-local endpoint would be used over plaintext HTTP."""


def is_loopback_host(host: str | None) -> bool:
    """Return whether a host is loopback.

    Parameters
    ----------
    host : str | None
        Hostname or IP literal, typically parsed from the endpoint URL.

    Returns
    -------
    bool
        ``True`` for ``localhost``, any address in ``127.0.0.0/8``, ``::1``, and
        IPv4-mapped IPv6 loopback (``::ffff:127.0.0.1``). DNS hostnames other than
        ``localhost`` are treated as non-loopback; ember does not resolve DNS here.
    """
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped.is_loopback
    return address.is_loopback


class Endpoint(BaseModel):
    """A resolved inference endpoint and its transport/credential rules.

    Attributes
    ----------
    url : str
        Normalised base URL, without a trailing slash.
    host : str
        Hostname or IP literal parsed from ``url``.
    scheme : str
        ``"http"`` or ``"https"``.
    is_local : bool
        Whether ``host`` is a loopback host.
    allow_insecure_transport : bool
        Whether plaintext to a non-local host is explicitly permitted.
    request_timeout : int
        Seconds bounding a request to this endpoint.
    """

    url: str
    host: str
    scheme: str
    is_local: bool
    allow_insecure_transport: bool
    request_timeout: int

    @classmethod
    def resolve(cls, url: str | None = None) -> Endpoint:
        """Resolve and validate the configured endpoint.

        Parameters
        ----------
        url : str | None, optional
            Explicit URL overriding the configured value (CLI flag > env > config).

        Returns
        -------
        Endpoint
            The resolved endpoint.

        Raises
        ------
        InvalidEndpointError
            If the URL is malformed or lacks an ``http``/``https`` scheme.
        InsecureEndpointError
            If the endpoint is non-local over plaintext and the insecure override
            is not enabled.
        """
        raw = str(url if url is not None else config.resolve("server_url") or "")
        raw = raw.rstrip("/")
        parsed = urlparse(raw)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise InvalidEndpointError(f"server_url {raw!r} is not a valid http(s) URL")
        host = parsed.hostname
        is_local = is_loopback_host(host)
        allow_insecure = bool(config.resolve("allow_insecure_transport"))
        if not is_local and parsed.scheme == "http" and not allow_insecure:
            raise InsecureEndpointError(
                f"refusing plaintext http to non-local endpoint {raw!r}; "
                "use https or set EMBER_ALLOW_INSECURE_TRANSPORT=true"
            )
        try:
            timeout = int(config.resolve("request_timeout") or DEFAULT_TIMEOUT)
        except (TypeError, ValueError):
            timeout = DEFAULT_TIMEOUT
        if timeout <= 0:
            timeout = DEFAULT_TIMEOUT
        return cls(
            url=raw,
            host=host,
            scheme=parsed.scheme,
            is_local=is_local,
            allow_insecure_transport=allow_insecure,
            request_timeout=timeout,
        )

    @property
    def port(self) -> int:
        """Return the URL's explicit port, or the scheme default.

        Returns
        -------
        int
            The port to use for lifecycle health probes.
        """
        parsed = urlparse(self.url)
        return parsed.port or (HTTPS_PORT if self.scheme == "https" else HTTP_PORT)


def build_auth_headers() -> dict[str, str]:
    """Build the credential header for the configured endpoint.

    Returns
    -------
    dict[str, str]
        ``{}`` when no ``auth_token`` is configured; otherwise a single header —
        ``Authorization: Bearer <token>`` when the header name is ``Authorization``,
        else ``<auth_header>: <token>``.
    """
    token = config.resolve("auth_token")
    if not token:
        return {}
    header = str(config.resolve("auth_header") or "Authorization")
    if header.lower() == "authorization":
        return {"Authorization": f"Bearer {token}"}
    return {header: str(token)}
