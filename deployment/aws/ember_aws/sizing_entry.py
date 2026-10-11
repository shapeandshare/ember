"""SizingEntry: one row in the sizing table (data-model.md)."""

from __future__ import annotations

from pydantic import BaseModel

from .cap_source import CapSource
from .sizing_status import SizingStatus


class SizingEntry(BaseModel):
    """One row in ``deployment/aws/sizing.json``.

    Parameters
    ----------
    model : str
        Registry key (e.g. ``"flash"``).
    instance_type : str
        EC2 instance type (e.g. ``"g6e.xlarge"``).
    gpu : str
        GPU model name (e.g. ``"L40S"``).
    gpu_memory_gib : int
        GPU VRAM in gibibytes.
    status : SizingStatus
        Whether this instance type is suitable for the model.
    default : bool
        ``True`` for the recommended default instance type (exactly one
        ``supported`` default per model).
    request_cap : int
        Per-request token cap for this instance type.
    cap_source : CapSource
        Whether the cap was measured or is a pre-declared fallback.
    hourly_usd : dict[str, float]
        On-demand hourly price by AWS region code.
    priced_on : str
        ISO date the price was last checked (``YYYY-MM-DD``).
    note : str
        Human-readable note about this entry.
    """

    model: str
    instance_type: str
    gpu: str
    gpu_memory_gib: int
    status: SizingStatus
    default: bool
    request_cap: int
    cap_source: CapSource
    hourly_usd: dict[str, float]
    priced_on: str
    note: str
