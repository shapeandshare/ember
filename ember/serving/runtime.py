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

from .. import models as _models
from . import media
from .integrity import verify_model_dir

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_DIR = REPO_ROOT / ".models" / "clef-flash"

#: Used only if a model's config.json has no max_position_embeddings.
FALLBACK_MAX_LENGTH = 32768

#: Maximum number of concurrent advise calls allowed to queue behind the engine
#: lock (D-001). When all slots are taken, new calls fail fast with a 503-mapped
#: AdmissionError rather than growing an unbounded queue that pins the server busy.
#: 4 comfortably covers the MCP server's normal single-call flow while bounding
#: memory growth from a runaway agent or loopback flood.
MAX_PENDING_ADVISE = 4


class AdmissionError(RuntimeError):
    """Raised when the admission semaphore is full (D-001).

    Signals that ``MAX_PENDING_ADVISE`` requests are already queued. The HTTP
    layer maps this to 503 so the agent knows to retry shortly.
    """


class RequestTooLargeError(ValueError):
    """Raised when tokenized input exceeds the per-request cap (D-002).

    The HTTP layer maps this to 413 so the agent knows to reduce input size
    or raise ``EMBER_MAX_REQUEST_LENGTH``.
    """


#: Explicit allowlist of processor keyword arguments callers may pass through.
#: Switching from a blocklist to an allowlist (T-003) closes the gap where any
#: non-reserved key was forwarded unchecked to joint_schema_model.systemone.
ALLOWED_MEDIA_KWARGS = frozenset(
    {
        "min_pixels",
        "max_pixels",
        "fps",
        "min_frames",
        "max_frames",
        "do_resize",
        "size",
        "do_convert_rgb",
    }
)

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


def _classify_dir(
    model_dir: Path,
    hint: _models.ModelSpec | None = None,
) -> tuple[_models.ModelSpec, bool]:
    """Return the best-matching registry spec and whether the dir is official.

    "Official" means the directory is the one the registry itself resolves to
    for a given spec (checkout ``.models/<dir>`` or the HF-cache snapshot at
    the pinned revision).  The HF-cache layout
    ``~/.cache/huggingface/hub/models--Cloudflare--clef-flash/snapshots/<sha>``
    does not match on ``dir_name`` alone, so we compare against the path
    ``models.resolve_dir`` returns with ``override=False``.

    Parameters
    ----------
    model_dir : Path
        Directory to classify.
    hint : ModelSpec | None, optional
        Caller-supplied spec.  When provided it is returned as-is; only the
        ``official`` flag is still computed so the correct enforcement level
        applies.  Degrades to ``(hint, False)`` when ``resolve_dir`` raises.

    Returns
    -------
    tuple[ModelSpec, bool]
        ``(spec, True)`` when ``model_dir`` matches the registry's own
        resolution for that spec; ``(spec, False)`` otherwise.
    """
    resolved = model_dir.resolve()
    for spec in _models.REGISTRY.values():
        try:
            official_path = _models.resolve_dir(spec.name, override=False)
        except Exception:
            official_path = None
        if official_path is not None and resolved == official_path.resolve():
            return hint if hint is not None else spec, True
    return hint if hint is not None else _models.REGISTRY[_models.DEFAULT], False


def joint_module(
    model_dir: Path,
    spec: _models.ModelSpec | None = None,
) -> Any:
    """Import Cloudflare's ``joint_schema_model`` from the model directory.

    Parameters
    ----------
    model_dir : Path
        Directory containing ``joint_schema_model.py``.
    spec : ModelSpec | None, optional
        Registry entry supplying pinned hashes for integrity verification.
        When ``None``, the spec is resolved from the registry by directory name.

    Returns
    -------
    Any
        The imported ``joint_schema_model`` module.

    Raises
    ------
    RuntimeError
        If integrity verification fails (missing files or hash mismatch).
    """
    global _JOINT_MODULE
    if _JOINT_MODULE is None:
        resolved_spec, official = _classify_dir(model_dir, hint=spec)
        verify_model_dir(model_dir, resolved_spec, official=official)
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
    spec: _models.ModelSpec | None = None,
) -> tuple[Any, Any]:
    """Load a SystemOne-compatible backbone + joint schema head + processor.

    Parameters
    ----------
    model_dir : str | os.PathLike[str], optional
        Directory containing the model snapshot. Defaults to
        ``DEFAULT_MODEL_DIR``.
    device : str | None, optional
        Compute device; resolved by ``pick_device`` when ``None``.
    dtype : torch.dtype | None, optional
        Floating-point dtype; resolved by ``pick_dtype`` when ``None``.
    spec : ModelSpec | None, optional
        Registry entry for integrity verification. When ``None``, resolved
        from the registry by directory name.

    Returns
    -------
    tuple[Any, Any]
        ``(ClefModel, processor)``.

    Raises
    ------
    FileNotFoundError
        If ``model_dir`` does not exist.
    RuntimeError
        If integrity verification fails before any model code is loaded.
    """
    model_dir = Path(model_dir)
    if not model_dir.is_dir():
        raise FileNotFoundError(f"model dir not found: {model_dir}")

    js = joint_module(model_dir, spec=spec)
    device = pick_device(device)
    if dtype is None:
        dtype = pick_dtype(device)

    # import-placement:allow - deferred to load_clef(); ML deps must not load at import
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

    Parameters
    ----------
    model_dir : str | os.PathLike[str], optional
        Directory containing the model snapshot. Defaults to ``DEFAULT_MODEL_DIR``.
    device : str | None, optional
        Compute device; resolved by ``pick_device`` when ``None``.
    dtype : torch.dtype | None, optional
        Floating-point dtype; resolved by ``pick_dtype`` when ``None``.
    max_length : int | None, optional
        Server-level token budget passed to ``joint_schema_model.systemone``.
        ``None`` derives it from the model's ``config.json``.
    model_name : str | None, optional
        Label echoed in responses. Defaults to the model directory name.
    spec : ModelSpec | None, optional
        Registry entry for integrity verification.
    max_request_length : int, optional
        Per-request token cap enforced after tokenization and before the model
        forward pass (D-002). ``0`` disables the cap. Defaults to ``0``.
    """

    def __init__(
        self,
        model_dir: str | os.PathLike[str] = DEFAULT_MODEL_DIR,
        device: str | None = None,
        dtype: torch.dtype | None = None,
        max_length: int | None = None,
        model_name: str | None = None,
        spec: _models.ModelSpec | None = None,
        max_request_length: int = 0,
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
        self.max_request_length = max_request_length
        self._spec = spec
        self.model, self.processor = load_clef(
            self.model_dir, self.device, self.dtype, spec=spec
        )
        self._lock = threading.Lock()
        self._admission = threading.Semaphore(MAX_PENDING_ADVISE)

    def advise(
        self,
        state: Any,
        questions: dict[str, Any],
        max_length: int | None = None,
        images: list[media.MediaRef] | None = None,
        videos: list[list[media.MediaRef]] | None = None,
        media_kwargs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run a Jev/SystemOne request and return the SystemOne response body.

        Parameters
        ----------
        state : Any
            The situation to read: a string or JSON value.
        questions : dict[str, Any]
            Mapping of question ID to typed question schema.
        max_length : int | None, optional
            Override the server-level token budget for this request.
        images : list[MediaRef] | None, optional
            Images as data: URIs or ``{content_type, base64}`` objects.
        videos : list[list[MediaRef]] | None, optional
            Videos, each a list of frame refs.
        media_kwargs : dict[str, Any] | None, optional
            Processor keyword arguments; only allowlisted keys are accepted.

        Returns
        -------
        dict[str, Any]
            SystemOne response body including ``answers`` and ``usage``.

        Raises
        ------
        AdmissionError
            If the admission semaphore is full (server busy — retry shortly).
        RequestTooLargeError
            If ``max_request_length`` is positive and the tokenized input
            exceeds it.
        ValueError
            If ``media_kwargs`` contains disallowed keys.
        """
        if not self._admission.acquire(blocking=False):
            raise AdmissionError(
                f"server busy: {MAX_PENDING_ADVISE} requests already queued. "
                "Retry shortly."
            )
        try:
            return self._run_advise(
                state, questions, max_length, images, videos, media_kwargs
            )
        finally:
            self._admission.release()

    def _run_advise(
        self,
        state: Any,
        questions: dict[str, Any],
        max_length: int | None,
        images: list[media.MediaRef] | None,
        videos: list[list[media.MediaRef]] | None,
        media_kwargs: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Execute the advise request after admission is granted.

        Parameters
        ----------
        state : Any
            The situation to read.
        questions : dict[str, Any]
            Mapping of question ID to typed question schema.
        max_length : int | None
            Per-call token budget override.
        images : list[MediaRef] | None
            Image refs.
        videos : list[list[MediaRef]] | None
            Video frame refs.
        media_kwargs : dict[str, Any] | None
            Processor keyword arguments.

        Returns
        -------
        dict[str, Any]
            SystemOne response body.

        Raises
        ------
        RequestTooLargeError
            If the tokenized input exceeds ``max_request_length``.
        ValueError
            If ``media_kwargs`` contains disallowed keys.
        """
        if self.max_request_length > 0:
            text = str(state)
            tokens = self.processor.tokenizer(text)
            token_count = len(tokens["input_ids"])
            if token_count > self.max_request_length:
                raise RequestTooLargeError(
                    f"request too large: {token_count} tokens exceeds the "
                    f"{self.max_request_length}-token per-request cap. "
                    "Reduce input size or raise EMBER_MAX_REQUEST_LENGTH "
                    "(set to 0 to use the model maximum)."
                )
        js = joint_module(self.model_dir, spec=self._spec)
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
            disallowed = set(media_kwargs) - ALLOWED_MEDIA_KWARGS
            if disallowed:
                raise ValueError(
                    "media_kwargs keys not permitted: "
                    + ", ".join(sorted(disallowed))
                    + ". Permitted keys: "
                    + ", ".join(sorted(ALLOWED_MEDIA_KWARGS))
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
