"""gut-feeling runtime: loads Cloudflare's Clef-Flash model on Apple Silicon (MPS).

Wraps Cloudflare's shipped ``joint_schema_model.py`` with a loader that works
around a segfault seen when ``device_map={"": "mps"}`` is passed to
``from_pretrained`` under torch 2.14 / transformers 5.18. Loading on CPU and then
moving the module to MPS is stable.

Fixes applied:
  * PYTORCH_ENABLE_MPS_FALLBACK=1 so unimplemented MPS ops fall back to CPU
    instead of erroring (the Qwen3.5 Gated DeltaNet layers use a pure-PyTorch
    fallback path; a few ops may still be missing).
  * CPU -> MPS load (avoids the loader segfault).
  * float16 on MPS, float32 on CPU.
  * pad_token_id fallback to eos (Clef-flash's config leaves it null).
"""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from typing import Any

# Must be set before torch's dispatch tables are built.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_DIR = REPO_ROOT / ".models" / "clef-flash"

_JOINT_MODULE: Any = None


def joint_module(model_dir: Path) -> Any:
    """Import Cloudflare's ``joint_schema_model`` from the model directory."""
    global _JOINT_MODULE
    if _JOINT_MODULE is None:
        path = str(model_dir.resolve())
        if path not in sys.path:
            sys.path.insert(0, path)
        import joint_schema_model  # type: ignore

        _JOINT_MODULE = joint_schema_model
    return _JOINT_MODULE


def pick_device(requested: str | None = None) -> str:
    if requested and requested != "auto":
        return requested
    return "mps" if torch.backends.mps.is_available() else "cpu"


def pick_dtype(device: str) -> torch.dtype:
    return torch.float16 if device == "mps" else torch.float32


def load_clef(
    model_dir: str | os.PathLike[str] = DEFAULT_MODEL_DIR,
    device: str | None = None,
    dtype: torch.dtype | None = None,
) -> tuple[Any, Any]:
    """Load the Clef-Flash backbone + joint schema head + processor.

    Returns ``(ClefModel, processor)``.
    """
    model_dir = Path(model_dir)
    if not model_dir.is_dir():
        raise FileNotFoundError(f"Clef-Flash model dir not found: {model_dir}")

    js = joint_module(model_dir)
    device = pick_device(device)
    if dtype is None:
        dtype = pick_dtype(device)

    from safetensors.torch import load_file
    from transformers import AutoProcessor, Qwen3_5ForConditionalGeneration

    # Load on CPU (device_map={"": "mps"} segfaults), then move. Both loads read a
    # local snapshot already pinned at download time and never touch the Hub, which
    # bandit's revision-pinning check (B615) cannot see.
    backbone: Any = Qwen3_5ForConditionalGeneration.from_pretrained(  # nosec B615
        str(model_dir),
        dtype=dtype,
        device_map={"": "cpu"},
        local_files_only=True,
    )
    backbone.config.use_cache = False
    if device != "cpu":
        backbone = backbone.to(device)

    head_config = json.loads((model_dir / "joint_head_config.json").read_text())
    head = js.JointSchemaHead(**head_config)
    head.load_state_dict(load_file(model_dir / "joint_head.safetensors"), strict=True)
    head = head.to(device=device, dtype=dtype)

    processor = AutoProcessor.from_pretrained(  # nosec B615
        str(model_dir), local_files_only=True
    )
    if getattr(processor.tokenizer, "pad_token_id", None) is None:
        processor.tokenizer.pad_token = processor.tokenizer.eos_token

    model = js.ClefModel(backbone, head).eval()
    return model, processor


class Engine:
    """Holds the loaded model and answers advice requests.

    MPS inference is not thread-safe; all calls are serialized behind a lock.
    """

    def __init__(
        self,
        model_dir: str | os.PathLike[str] = DEFAULT_MODEL_DIR,
        device: str | None = None,
        dtype: torch.dtype | None = None,
        max_length: int = 16384,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.device = pick_device(device)
        self.dtype = dtype or pick_dtype(self.device)
        self.max_length = max_length
        self.model, self.processor = load_clef(self.model_dir, self.device, self.dtype)
        self._lock = threading.Lock()

    def advise(
        self,
        state: Any,
        questions: dict[str, Any],
        model_name: str = "clef-flash",
        max_length: int | None = None,
    ) -> dict[str, Any]:
        """Run a Jev/SystemOne request and return the SystemOne response body."""
        js = joint_module(self.model_dir)
        request = {"model": model_name, "state": state, "questions": questions}
        with self._lock:
            response: dict[str, Any] = js.systemone(
                self.model,
                self.processor,
                request,
                max_length=max_length or self.max_length,
            )
        return response

    def describe(self) -> dict[str, Any]:
        return {
            "device": self.device,
            "dtype": str(self.dtype).replace("torch.", ""),
            "model_dir": str(self.model_dir),
            "max_length": self.max_length,
        }
