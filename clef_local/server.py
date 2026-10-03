"""FastAPI model server for Clef-Flash on Apple Silicon.

Loads the model once into a warm process and exposes a Jev/SystemOne-compatible
endpoint. The MCP client (``clef_local.mcp_server``) talks to this over HTTP so
that opencode's MCP startup stays instant and the model stays warm across
sessions.

Run:
    .venv/bin/python -m clef_local.server
Env:
    CLEF_HOST (default 127.0.0.1), CLEF_PORT (default 8765)
    CLEF_DEVICE (auto|mps|cpu), CLEF_MAX_LENGTH (default 16384)
"""

from __future__ import annotations

import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from clef_local.runtime import DEFAULT_MODEL_DIR, ClefEngine  # type: ignore
else:
    from .runtime import DEFAULT_MODEL_DIR, ClefEngine

_ENGINE: ClefEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ENGINE
    device = os.environ.get("CLEF_DEVICE", "auto")
    max_length = int(os.environ.get("CLEF_MAX_LENGTH", "16384"))
    model_dir = os.environ.get("CLEF_MODEL_DIR") or str(DEFAULT_MODEL_DIR)
    _ENGINE = ClefEngine(model_dir, device=device, max_length=max_length)
    try:
        yield
    finally:
        _ENGINE = None


app = FastAPI(title="Clef-Flash Local", version="0.1.0", lifespan=lifespan)


class DecideRequest(BaseModel):
    model: str = "clef-flash"
    state: Any = Field(description="Any string or JSON value describing the situation.")
    questions: dict[str, Any] = Field(description="Mapping of question ID to question.")


class Question(BaseModel):
    type: str
    instructions: str | None = None
    criteria: Any | None = None


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok" if _ENGINE is not None else "loading",
        "pid": os.getpid(),
        "engine": _ENGINE.describe() if _ENGINE is not None else None,
    }


@app.post("/v1/systemone")
def systemone_endpoint(req: DecideRequest) -> dict[str, Any]:
    if _ENGINE is None:
        raise HTTPException(status_code=503, detail="model not loaded yet")
    started = time.time()
    try:
        result = _ENGINE.decide(req.state, req.questions, model_name=req.model)
    except ValueError as exc:  # bad request shape from Clef's own validation
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result["latency_ms"] = round((time.time() - started) * 1000, 1)
    return result


def main() -> None:
    import uvicorn

    host = os.environ.get("CLEF_HOST", "127.0.0.1")
    port = int(os.environ.get("CLEF_PORT", "8765"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
