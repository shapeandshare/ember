"""ComplianceRef: one reference from a recipe into an external compliance catalogue."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .compliance_framework import ComplianceFramework


class ComplianceRef(BaseModel):
    """A reference such as OWASP LLM Top 10 ``LLM06`` attached to a recipe.

    Parameters
    ----------
    framework : ComplianceFramework
        The catalogue the reference comes from.
    ref : str
        The identifier within that catalogue (for example ``LLM06``).
    title : str
        The catalogue's title for the entry.
    """

    model_config = ConfigDict(frozen=True)

    framework: ComplianceFramework
    ref: str = Field(min_length=1)
    title: str = Field(min_length=1)
