"""ember model server: loads the model once and serves the Jev/SystemOne API.

The MCP server (``ember.mcp_server``) talks to this process over HTTP, so the MCP
handshake stays instant and the model stays warm across agent sessions.

Run:  ember serve        (or: python -m ember.server)
Env:  EMBER_HOST (127.0.0.1), EMBER_PORT (8765),
      EMBER_DEVICE (auto|mps|cpu), EMBER_MAX_LENGTH (0 = the model's maximum),
      EMBER_MODEL_DIR (default: the pinned model)
"""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import config, models
from .runtime import Engine

_ENGINE: Engine | None = None


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
    try:
        yield
    finally:
        _ENGINE = None


app = FastAPI(title="ember", version="0.1.0", lifespan=lifespan)


class AdviseRequest(BaseModel):
    model: str = "clef-flash"
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
        default=None, description="Optional image/video processor arguments."
    )


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok" if _ENGINE is not None else "loading",
        "pid": os.getpid(),
        "engine": _ENGINE.describe() if _ENGINE is not None else None,
    }


@app.post("/v1/systemone")
def systemone_endpoint(req: AdviseRequest) -> dict[str, Any]:
    if _ENGINE is None:
        raise HTTPException(status_code=503, detail="model not loaded yet")
    started = time.time()
    try:
        result = _ENGINE.advise(
            req.state,
            req.questions,
            model_name=req.model,
            images=req.images,
            videos=req.videos,
            media_kwargs=req.media_kwargs,
        )
    except ValueError as exc:  # malformed questions or media
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result["latency_ms"] = round((time.time() - started) * 1000, 1)
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
