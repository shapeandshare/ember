"""Pick the compute device and dtype the model runs on (constitution Article VI)."""

from __future__ import annotations

import os

# Must be set before torch's dispatch tables are built.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import torch


def pick_device(requested: str | None = None) -> str:
    """Resolve the compute device to run on.

    Parameters
    ----------
    requested : str | None, optional
        ``"mps"``, ``"cuda"``, ``"cpu"``, or ``"auto"``/``None`` to detect
        automatically.

    Returns
    -------
    str
        ``requested`` if given and not ``"auto"``; otherwise ``"mps"`` when
        available (constitution Article VI: Apple Silicon is the
        local-first default), else ``"cuda"`` when available (the hosted-
        deployment path, e.g. Outerbounds compute, which is Linux and has
        no MPS), else ``"cpu"``.
    """
    if requested and requested != "auto":
        return requested
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def pick_dtype(device: str) -> torch.dtype:
    """Resolve the floating-point dtype to load the model in.

    Parameters
    ----------
    device : str
        The compute device, as returned by ``pick_device``.

    Returns
    -------
    torch.dtype
        ``torch.float16`` on MPS or CUDA, ``torch.float32`` otherwise
        (constitution Article VI).
    """
    return torch.float16 if device in ("mps", "cuda") else torch.float32
