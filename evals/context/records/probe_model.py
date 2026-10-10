"""A model the long-context probe measures, as its manifest records it."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProbeModel(BaseModel):
    """One registered model in a probe run.

    Attributes
    ----------
    name : str
        Registry key, such as ``"flash"``.
    repo : str
        Hugging Face repo id.
    revision : str | None
        The registry's download revision.
    params : str
        Human-readable parameter count.
    memory_budget_bytes : int
        The pre-declared peak-memory budget: 32 GiB for flash, 64 GiB for full.
    recommended_max_memory_bytes : int | None
        ``torch.mps.recommended_max_memory()``, recorded for context only.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    repo: str
    revision: str | None
    params: str
    memory_budget_bytes: int = Field(gt=0)
    recommended_max_memory_bytes: int | None = None
