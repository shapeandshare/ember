"""ember runtime: loads a SystemOne-compatible model on Apple Silicon (MPS).

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
  * pad_token_id fallback to eos (some models leave it null in config).

One model per process. ``joint_schema_model`` is imported by a fixed module name
from the model directory; Python caches it in ``sys.modules`` under that name, so
a second model's ``joint_schema_model.py`` in the same process would silently reuse
the first import. Run one server process per model (different ports) to isolate
them.
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

from . import media

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_DIR = REPO_ROOT / ".models" / "clef-flash"

#: Used only if a model's config.json has no max_position_embeddings.
FALLBACK_MAX_LENGTH = 32768

#: Keys the Clef encoder sets itself; media_kwargs must not override them.
RESERVED_MEDIA_KWARGS = frozenset({"text", "images", "videos", "return_tensors"})

_JOINT_MODULE: Any = None


def model_max_length(model_dir: str | os.PathLike[str] = DEFAULT_MODEL_DIR) -> int:
    """Resolve the backbone's declared context window from config.json.

    ``0`` in the config means "the model's own maximum"; this resolves it. The
    value is read from the pinned snapshot, so it tracks a model revision bump
    instead of a hardcoded number.

    Parameters
    ----------
    model_dir : str | os.PathLike[str], optional
        Directory containing the model's ``config.json``. Defaults to
        ``DEFAULT_MODEL_DIR``.

    Returns
    -------
    int
        The resolved ``max_position_embeddings`` value, or
        ``FALLBACK_MAX_LENGTH`` if it cannot be read or is non-positive.
    """
    try:
        config = json.loads((Path(model_dir) / "config.json").read_text())
    except (OSError, json.JSONDecodeError):
        return FALLBACK_MAX_LENGTH
    text = config.get("text_config")
    text = text if isinstance(text, dict) else {}
    value = text.get("max_position_embeddings") or config.get("max_position_embeddings")
    try:
        result = int(value)
    except (TypeError, ValueError):
        return FALLBACK_MAX_LENGTH
    return result if result > 0 else FALLBACK_MAX_LENGTH


def joint_module(model_dir: Path) -> Any:
    """Import Cloudflare's ``joint_schema_model`` from the model directory."""
    global _JOINT_MODULE
    if _JOINT_MODULE is None:
        path = str(model_dir.resolve())
        if path not in sys.path:
            sys.path.insert(0, path)
        # import-placement:allow - joint_schema_model ships in the model snapshot.
        import joint_schema_model  # type: ignore[import-not-found]

        _JOINT_MODULE = joint_schema_model
    return _JOINT_MODULE


def pick_device(requested: str | None = None) -> str:
    """Resolve the compute device to run on.

    Parameters
    ----------
    requested : str | None, optional
        ``"mps"``, ``"cpu"``, or ``"auto"``/``None`` to detect automatically.

    Returns
    -------
    str
        ``requested`` if given and not ``"auto"``; otherwise ``"mps"`` when
        available, else ``"cpu"``.
    """
    if requested and requested != "auto":
        return requested
    return "mps" if torch.backends.mps.is_available() else "cpu"


def pick_dtype(device: str) -> torch.dtype:
    """Resolve the floating-point dtype to load the model in.

    Parameters
    ----------
    device : str
        The compute device, as returned by ``pick_device``.

    Returns
    -------
    torch.dtype
        ``torch.float16`` on MPS, ``torch.float32`` otherwise.
    """
    return torch.float16 if device == "mps" else torch.float32


def load_clef(
    model_dir: str | os.PathLike[str] = DEFAULT_MODEL_DIR,
    device: str | None = None,
    dtype: torch.dtype | None = None,
) -> tuple[Any, Any]:
    """Load a SystemOne-compatible backbone + joint schema head + processor.

    Returns ``(ClefModel, processor)``.
    """
    model_dir = Path(model_dir)
    if not model_dir.is_dir():
        raise FileNotFoundError(f"model dir not found: {model_dir}")

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
        max_length: int | None = None,
        model_name: str | None = None,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.model_name = model_name if model_name is not None else self.model_dir.name
        self.device = pick_device(device)
        self.dtype = dtype or pick_dtype(self.device)
        if max_length is not None and max_length <= 0:
            raise ValueError("max_length must be a positive integer or None")
        self.max_length = (
            max_length if max_length is not None else model_max_length(self.model_dir)
        )
        self.model, self.processor = load_clef(self.model_dir, self.device, self.dtype)
        self._lock = threading.Lock()

    def advise(
        self,
        state: Any,
        questions: dict[str, Any],
        max_length: int | None = None,
        images: list[media.MediaRef] | None = None,
        videos: list[list[media.MediaRef]] | None = None,
        media_kwargs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run a Jev/SystemOne request and return the SystemOne response body."""
        js = joint_module(self.model_dir)
        request: dict[str, Any] = {
            "model": self.model_name,
            "state": state,
            "questions": questions,
        }
        if images:
            request["images"] = media.decode_images(images)
        if videos:
            request["videos"] = media.decode_videos(videos)
        if media_kwargs:
            reserved = RESERVED_MEDIA_KWARGS.intersection(media_kwargs)
            if reserved:
                raise ValueError(
                    "media_kwargs may not set reserved keys: "
                    + ", ".join(sorted(reserved))
                )
            request["media_kwargs"] = media_kwargs
        with self._lock:
            response: dict[str, Any] = js.systemone(
                self.model,
                self.processor,
                request,
                max_length=self.max_length if max_length is None else max_length,
            )
        return response

    def describe(self) -> dict[str, Any]:
        """Return a summary of this engine's loaded configuration.

        Returns
        -------
        dict[str, Any]
            ``model``, ``device``, ``dtype``, ``model_dir``, and ``max_length``.
        """
        return {
            "model": self.model_name,
            "device": self.device,
            "dtype": str(self.dtype).replace("torch.", ""),
            "model_dir": str(self.model_dir),
            "max_length": self.max_length,
        }
