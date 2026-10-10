"""ember runtime: loads a SystemOne-compatible model on MPS, CUDA, or CPU.

Wraps Cloudflare's shipped ``joint_schema_model.py`` with a loader that works
around a segfault seen when ``device_map={"": "mps"}`` is passed to
``from_pretrained`` under torch 2.14 / transformers 5.18. Loading on CPU and then
moving the module to the target device is stable — this applies to MPS (where
the direct ``device_map`` load segfaults) and is reused for CUDA (which has no
such issue, but a single code path is simpler than two — constitution
Article XV §15.3). See constitution Article VI ("Apple Silicon and CUDA").

Fixes applied:
  * PYTORCH_ENABLE_MPS_FALLBACK=1 so unimplemented MPS ops fall back to CPU
    instead of erroring (the Qwen3.5 Gated DeltaNet layers use a pure-PyTorch
    fallback path; a few ops may still be missing).
  * TORCH_DISABLE_NATIVE_JIT=1 by default so torch 2.14's torch._native does
    not register Triton-backed op overrides (e.g. aten::bmm's outer-product
    specialization, hit by Qwen3.5's RoPE forward on CUDA) that JIT-compile a
    kernel at first use via a C compiler — a minimal CUDA container (e.g.
    Outerbounds' Fast Bakery base image) has none, and there is no supported
    way to install one through that deployment's contract, so the first real
    request on such a host raised an uncaught RuntimeError ("Failed to find
    C compiler"). Set EMBER_TORCH_DISABLE_NATIVE_JIT=0 to opt back into the
    Triton path on a host with a working compiler toolchain. Unlike the MPS
    fallback above, torch provides no automatic fallback here — the override
    is simply never registered, so the standard eager/ATen aten::bmm runs
    instead (same operation, different and mature cuBLAS-backed kernel).
  * CPU -> target-device load (avoids the MPS loader segfault; CUDA has no
    such constraint but shares the same load path).
  * float16 on MPS and CUDA, float32 on CPU.
  * pad_token_id fallback to eos (some models leave it null in config).

One model per process. ``joint_schema_model`` is imported by a fixed module name
from the model directory; Python caches it in ``sys.modules`` under that name, so
a second model's ``joint_schema_model.py`` in the same process would silently reuse
the first import. Run one server process per model (different ports) to isolate
them.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any

# Must be set before torch's dispatch tables are built.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
os.environ.setdefault(
    "TORCH_DISABLE_NATIVE_JIT", os.environ.get("EMBER_TORCH_DISABLE_NATIVE_JIT", "1")
)

import torch

from . import media
from .devices import pick_device, pick_dtype
from .limit_source import LimitSource
from .limits import Limits, declared_max_length, resolve
from .request_size import RequestSize, measure, refusal_message

_log = logging.getLogger(__name__)

# ember/serving/runtime.py -> parents[2] is the checkout root (matches models._dev_dir).
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_DIR = REPO_ROOT / ".models" / "clef-flash"

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
    """Raised when the encoded request exceeds the enforced limit.

    The HTTP layer maps this to 413, with the message as ``detail``.

    Parameters
    ----------
    message : str
        The refusal, from ``request_size.refusal_message``.
    size : RequestSize
        The refused request's measured size.
    limits : Limits
        The limits it exceeded.
    """

    def __init__(self, message: str, *, size: RequestSize, limits: Limits) -> None:
        super().__init__(message)
        self.size = size
        self.limits = limits


_JOINT_MODULE: Any = None


def joint_module(model_dir: Path) -> Any:
    """Import Cloudflare's ``joint_schema_model`` from the model directory.

    Constitution Article V ("Model Loading"): ember supports any model that
    can run under its loader contract; this performs no integrity
    verification of ``model_dir`` before importing from it.

    The model directory is added to ``sys.path`` only for the duration of
    the import, then removed immediately (I-003). This limits the window
    during which the path appears in tracebacks.

    Parameters
    ----------
    model_dir : Path
        Directory containing ``joint_schema_model.py``.

    Returns
    -------
    Any
        The imported ``joint_schema_model`` module.
    """
    global _JOINT_MODULE
    if _JOINT_MODULE is None:
        path = str(model_dir.resolve())
        added = path not in sys.path
        if added:
            sys.path.insert(0, path)
        try:
            # import-placement:allow - joint_schema_model ships in the model snapshot.
            import joint_schema_model  # type: ignore[import-not-found]

            _JOINT_MODULE = joint_schema_model
        finally:
            # I-003: remove the model dir from sys.path after the import so it
            # does not appear in tracebacks for the rest of the process lifetime.
            if added and path in sys.path:
                sys.path.remove(path)
    return _JOINT_MODULE


def load_clef(
    model_dir: str | os.PathLike[str] = DEFAULT_MODEL_DIR,
    device: str | None = None,
    dtype: torch.dtype | None = None,
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

    Returns
    -------
    tuple[Any, Any]
        ``(ClefModel, processor)``.

    Raises
    ------
    FileNotFoundError
        If ``model_dir`` does not exist.
    """
    model_dir = Path(model_dir)
    if not model_dir.is_dir():
        raise FileNotFoundError(f"model dir not found: {model_dir}")

    js = joint_module(model_dir)
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
    model_name : str | None, optional
        Label echoed in responses. Defaults to the model directory name.
    limits : Limits | None, optional
        The effective maximum and the per-request cap. ``None`` uses the
        model's declared maximum and the default cap for a model outside the
        registry, with no config read; the server passes the resolved limits.
    """

    def __init__(
        self,
        model_dir: str | os.PathLike[str] = DEFAULT_MODEL_DIR,
        device: str | None = None,
        dtype: torch.dtype | None = None,
        model_name: str | None = None,
        limits: Limits | None = None,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.model_name = model_name if model_name is not None else self.model_dir.name
        self.device = pick_device(device)
        self.dtype = dtype or pick_dtype(self.device)
        self.declared = declared_max_length(self.model_dir)
        self.limits = limits if limits is not None else resolve(self.declared, None)
        self.model, self.processor = load_clef(self.model_dir, self.device, self.dtype)
        self._lock = threading.Lock()
        self._admission = threading.Semaphore(MAX_PENDING_ADVISE)

    @property
    def max_length(self) -> int:
        """The effective maximum: the most tokens the model processes."""
        return self.limits.max_length

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
            If the encoded request exceeds the enforced limit.
        ValueError
            If ``media_kwargs`` contains disallowed keys, or the request is
            malformed.
        RuntimeError
            If the loaded model can't count requests, or it saw a different
            number of tokens than ember counted.
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
        """Build the request, refuse it if it is too large, then run the model.

        Takes ``advise``'s arguments and raises its errors, once admission is
        granted.
        """
        js = joint_module(self.model_dir)
        request: dict[str, Any] = {
            "model": self.model_name,
            "state": state,
            "questions": questions,
        }
        if media_kwargs:
            media.check_media_kwargs(media_kwargs)
        if images:
            request["images"] = media.decode_images(images)
        if videos:
            request["videos"] = media.decode_videos(videos)
        if media_kwargs:
            request["media_kwargs"] = media_kwargs
        applied = self.limits
        if max_length is not None:
            applied = Limits(
                max_length=max_length,
                max_length_source=LimitSource.OPERATOR,
                max_request_length=applied.max_request_length,
                max_request_length_source=applied.max_request_length_source,
            )
        size: RequestSize | None
        try:
            size = measure(js, self.processor, request)
        except (KeyError, TypeError, AttributeError, ValueError):
            # A malformed request: systemone raises the same error, mapped to 422.
            size = None
        if size is not None and size.total > applied.enforced:
            raise RequestTooLargeError(
                refusal_message(size, applied, self.declared),
                size=size,
                limits=applied,
            )
        with self._lock:
            response: dict[str, Any] = js.systemone(
                self.model, self.processor, request, max_length=applied.max_length
            )
        served = (response.get("usage") or {}).get("input_tokens")
        if size is not None and served != size.total:
            _log.error(
                "size check mismatch: counted %d tokens, served %s", size.total, served
            )
            raise RuntimeError(
                "size check mismatch; refusing to answer from a possibly "
                "shortened input"
            )
        return response

    def describe(self) -> dict[str, Any]:
        """Return a summary of this engine's loaded configuration.

        Returns
        -------
        dict[str, Any]
            ``model``, ``device``, ``dtype``, ``max_length``,
            ``max_length_source``, ``max_request_length`` (``0`` when the cap
            is disabled), and ``max_request_length_source``; sources are
            ``LimitSource`` string values. ``model_dir`` is intentionally
            omitted: ``/health`` forwards this dict to any loopback caller,
            and the filesystem path is not needed by any external consumer
            (I-001).
        """
        return {
            "model": self.model_name,
            "device": self.device,
            "dtype": str(self.dtype).replace("torch.", ""),
            "max_length": self.limits.max_length,
            "max_length_source": self.limits.max_length_source.value,
            "max_request_length": self.limits.max_request_length,
            "max_request_length_source": self.limits.max_request_length_source.value,
        }
