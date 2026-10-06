"""ember model server: loads the model once and serves the Jev/SystemOne API.

The MCP server (``ember.mcp.mcp_server``) talks to this process over HTTP, so the
MCP handshake stays instant and the model stays warm across agent sessions.

Run:  ember serve        (or: python -m ember.serving.server)
Env:  EMBER_HOST (127.0.0.1), EMBER_PORT (8765),
      EMBER_DEVICE (auto|mps|cpu), EMBER_MAX_LENGTH (0 = the model's maximum),
      EMBER_MODEL_DIR (default: the pinned model)
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, Field

from .. import models
from ..cfg import config
from .runtime import AdmissionError, Engine, RequestTooLargeError

log = logging.getLogger(__name__)

_ENGINE: Engine | None = None

REGISTRY = CollectorRegistry()

ADVISE_REQUESTS = Counter(
    "ember_advise_requests_total",
    "advise requests by HTTP status.",
    ["status"],
    registry=REGISTRY,
)
ADVISE_LATENCY = Histogram(
    "ember_advise_latency_seconds",
    "advise request latency in seconds.",
    ["status"],
    registry=REGISTRY,
)
ADVISE_INPUT_TOKENS = Counter(
    "ember_advise_input_tokens_total",
    "Input tokens processed by advise.",
    registry=REGISTRY,
)
ADVISE_OUTPUT_TOKENS = Counter(
    "ember_advise_output_tokens_total",
    "Output tokens produced by advise.",
    registry=REGISTRY,
)
MODEL_INFO = Gauge(
    "ember_model_info",
    "Metadata for the loaded model (value is always 1).",
    ["model", "device", "dtype"],
    registry=REGISTRY,
)

_bearer_scheme = HTTPBearer(auto_error=False)


def _package_version() -> str:
    """Return the installed distribution version, or ``"unknown"``.

    Returns
    -------
    str
        The version of the ``gut`` distribution, or ``"unknown"`` when it cannot
        be determined (e.g. running from a source tree).
    """
    try:
        return _dist_version("gut")
    except PackageNotFoundError:
        return "unknown"


def require_server_auth(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
) -> None:
    """Enforce the optional server bearer token on protected routes.

    A no-op when ``server_auth_token`` is unset (auth disabled, delegated to a
    proxy). Otherwise the caller must present ``Authorization: Bearer <token>``;
    a missing or wrong token yields one generic ``401`` with
    ``WWW-Authenticate: Bearer`` (no oracle). Comparison is constant-time.

    Parameters
    ----------
    credentials : HTTPAuthorizationCredentials | None
        Parsed bearer credentials, or ``None`` when the header is absent.

    Raises
    ------
    HTTPException
        401 when auth is enabled and the token is missing or wrong.
    """
    expected = config.resolve("server_auth_token")
    if not expected:
        return
    presented = credentials.credentials if credentials is not None else ""
    if not secrets.compare_digest(presented.encode(), str(expected).encode()):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load the model once at startup and tear it down at shutdown.

    Parameters
    ----------
    app : FastAPI
        The FastAPI application this lifespan is bound to.

    Yields
    ------
    None
        Control, while the global ``_ENGINE`` is loaded.

    Raises
    ------
    RuntimeError
        If the configured model is not found on disk.
    """
    global _ENGINE
    name = config.resolve("model")
    model_dir = models.resolve_dir(name)
    if model_dir is None:
        # Article XIV §14.1 — pit of success: start in unloaded state rather
        # than crashing. POST /v1/systemone returns 503; GET /health returns
        # {"status": "loading"}. process.start() already validates weights
        # before spawning, so ember start / MCP autostart still fail fast with
        # an actionable error message via that path.
        log.warning(
            "model %r not found — server starting in unloaded state "
            "(advise calls will return 503). Run: ember model pull %s",
            name,
            name,
        )
        yield
        return
    raw_length = int(config.resolve("max_length"))
    raw_request_length = int(config.resolve("max_request_length"))
    _ENGINE = Engine(
        model_dir,
        device=config.resolve("device"),
        max_length=raw_length if raw_length > 0 else None,
        model_name=name,
        spec=models.get(name),
        max_request_length=raw_request_length,
    )
    MODEL_INFO.clear()
    MODEL_INFO.labels(
        model=name,
        device=_ENGINE.device,
        dtype=str(_ENGINE.dtype).replace("torch.", ""),
    ).set(1)
    try:
        yield
    finally:
        _ENGINE = None
        MODEL_INFO.clear()


app = FastAPI(title="ember", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def observe_advise(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Count and time every /v1/systemone request, whatever its outcome."""
    if request.url.path != "/v1/systemone":
        return await call_next(request)
    started = time.time()
    try:
        response = await call_next(request)
    except Exception:
        ADVISE_REQUESTS.labels(status="500").inc()
        ADVISE_LATENCY.labels(status="500").observe(time.time() - started)
        raise
    status = str(response.status_code)
    ADVISE_REQUESTS.labels(status=status).inc()
    ADVISE_LATENCY.labels(status=status).observe(time.time() - started)
    return response


class AdviseRequest(BaseModel):
    """Request body for ``POST /v1/systemone``."""

    model: str = Field(
        default="clef-flash",
        description=(
            "Informational label only. The server always responds with the model "
            "it loaded at startup; this field is not used for routing."
        ),
    )
    state: Any = Field(description="Any string or JSON value describing the situation.")
    questions: dict[str, Any] = Field(description="Mapping of question ID to question.")
    images: list[str | dict[str, Any]] | None = Field(
        default=None,
        description=(
            "Images as data: URIs or {content_type, base64} objects. "
            "Remote URLs and local paths are rejected."
        ),
    )
    videos: list[list[str | dict[str, Any]]] | None = Field(
        default=None,
        description="Videos, each a list of frame refs in the images format.",
    )
    media_kwargs: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional image/video processor arguments. "
            "Only the following keys are permitted: "
            "min_pixels, max_pixels, fps, min_frames, max_frames, "
            "do_resize, size, do_convert_rgb. "
            "Any other key is rejected with a 422 error."
        ),
    )


@app.get("/health")
async def health() -> dict[str, Any]:
    """Report whether the model is loaded, the contract version, and auth need.

    Returns
    -------
    dict[str, Any]
        ``status`` (``"ok"`` or ``"loading"``), ``pid``, ``engine`` (the loaded
        ``Engine.describe()`` output, or ``None``), ``version`` (the package
        version), and ``auth_required`` (whether the server requires a bearer
        token). ``version``/``auth_required`` are additive and let a client or a
        third-party implementation learn the contract without a credential.
    """
    return {
        "status": "ok" if _ENGINE is not None else "loading",
        "pid": os.getpid(),
        "engine": _ENGINE.describe() if _ENGINE is not None else None,
        "version": _package_version(),
        "auth_required": bool(config.resolve("server_auth_token")),
    }


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus exposition of ember's own metrics."""
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


@app.post(
    "/v1/systemone",
    responses={
        503: {"description": "Model not loaded yet or admission queue full."},
        413: {"description": "Tokenized input exceeds the per-request cap."},
        422: {"description": "Malformed questions, media, or kwargs."},
    },
)
def systemone_endpoint(
    req: AdviseRequest,
    _: None = Depends(require_server_auth),
) -> dict[str, Any]:  # async-first:exception - engine lock is synchronous
    """Run an advise request against the loaded model and record metrics.

    Parameters
    ----------
    req : AdviseRequest
        The parsed request body.

    Returns
    -------
    dict[str, Any]
        The SystemOne response body, with a ``latency_ms`` field added.

    Raises
    ------
    HTTPException
        503 if the model has not finished loading or the admission queue is
        full; 413 if the tokenized input exceeds the per-request cap; 422 if
        ``req`` contains malformed questions, media, or kwargs.
    """
    if _ENGINE is None:
        raise HTTPException(status_code=503, detail="model not loaded yet")
    started = time.time()
    try:
        result = _ENGINE.advise(
            req.state,
            req.questions,
            images=req.images,
            videos=req.videos,
            media_kwargs=req.media_kwargs,
        )
    except AdmissionError as exc:  # admission semaphore full — server busy
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RequestTooLargeError as exc:  # per-request token cap exceeded
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ValueError as exc:  # malformed questions, media, or kwargs
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    usage = result.get("usage") or {}
    ADVISE_INPUT_TOKENS.inc(int(usage.get("input_tokens", 0) or 0))
    ADVISE_OUTPUT_TOKENS.inc(int(usage.get("output_tokens", 0) or 0))
    result["latency_ms"] = round((time.time() - started) * 1000, 1)
    return result


def main() -> None:
    """Run the model server in the foreground with uvicorn."""
    # import-placement:allow - deferred to main(); avoids uvicorn import at module load
    import uvicorn

    uvicorn.run(
        app,
        host=config.resolve("host"),
        port=int(config.resolve("port")),
        log_level="info",
        limit_concurrency=16,
    )


if __name__ == "__main__":
    main()
