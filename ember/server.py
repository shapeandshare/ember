"""ember model server: loads the model once and serves the Jev/SystemOne API.

The MCP server (``ember.mcp_server``) talks to this process over HTTP, so the MCP
handshake stays instant and the model stays warm across agent sessions.

Run:  ember serve        (or: python -m ember.server)
Env:  EMBER_HOST (127.0.0.1), EMBER_PORT (8765),
      EMBER_DEVICE (auto|mps|cpu), EMBER_MAX_LENGTH (16384),
      EMBER_MODEL_DIR (default: the pinned model)
"""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, Field

from . import config, models
from .runtime import Engine

_ENGINE: Engine | None = None

ADVISE_REQUESTS = Counter(
    "ember_advise_requests_total",
    "advise requests by HTTP status.",
    ["status"],
)
ADVISE_LATENCY = Histogram(
    "ember_advise_latency_seconds",
    "advise request latency in seconds.",
)
ADVISE_INPUT_TOKENS = Counter(
    "ember_advise_input_tokens_total",
    "Input tokens processed by advise.",
)
ADVISE_OUTPUT_TOKENS = Counter(
    "ember_advise_output_tokens_total",
    "Output tokens produced by advise.",
)
MODEL_INFO = Gauge(
    "ember_model_info",
    "Metadata for the loaded model (value is always 1).",
    ["model", "device", "dtype"],
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _ENGINE
    name = config.resolve("model")
    model_dir = models.resolve_dir(name)
    if model_dir is None:
        raise RuntimeError(
            f"model {name!r} not found (check EMBER_MODEL_DIR); "
            f"run: ember model pull {name}"
        )
    _ENGINE = Engine(
        model_dir,
        device=config.resolve("device"),
        max_length=int(config.resolve("max_length")),
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


app = FastAPI(title="ember", version="0.1.0", lifespan=lifespan)


class AdviseRequest(BaseModel):
    model: str = "clef-flash"
    state: Any = Field(description="Any string or JSON value describing the situation.")
    questions: dict[str, Any] = Field(description="Mapping of question ID to question.")


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok" if _ENGINE is not None else "loading",
        "pid": os.getpid(),
        "engine": _ENGINE.describe() if _ENGINE is not None else None,
    }


@app.get("/metrics")
def metrics() -> Response:
    """Prometheus exposition of server metrics."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/systemone")
def systemone_endpoint(req: AdviseRequest) -> dict[str, Any]:
    if _ENGINE is None:
        ADVISE_REQUESTS.labels(status="503").inc()
        raise HTTPException(status_code=503, detail="model not loaded yet")
    started = time.time()
    try:
        result = _ENGINE.advise(req.state, req.questions, model_name=req.model)
    except ValueError as exc:  # malformed questions, rejected by Clef's own validation
        ADVISE_REQUESTS.labels(status="422").inc()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        ADVISE_REQUESTS.labels(status="500").inc()
        raise
    elapsed = time.time() - started
    ADVISE_LATENCY.observe(elapsed)
    usage = result.get("usage") or {}
    ADVISE_INPUT_TOKENS.inc(int(usage.get("input_tokens", 0) or 0))
    ADVISE_OUTPUT_TOKENS.inc(int(usage.get("output_tokens", 0) or 0))
    ADVISE_REQUESTS.labels(status="200").inc()
    result["latency_ms"] = round(elapsed * 1000, 1)
    return result


def main() -> None:
    import uvicorn

    uvicorn.run(
        app,
        host=config.resolve("host"),
        port=int(config.resolve("port")),
        log_level="info",
    )


if __name__ == "__main__":
    main()
