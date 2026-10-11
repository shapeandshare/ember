"""CheckResult: the outcome of a single preflight check."""

from __future__ import annotations

from pydantic import BaseModel

from .preflight_check import PreflightCheck


class CheckResult(BaseModel):
    """The outcome of one preflight check.

    Parameters
    ----------
    check : PreflightCheck
        Which check this result is for.
    ok : bool
        ``True`` if the check passed.
    problem : str
        Human-readable description of the failure (empty when ``ok=True``).
    fix : str
        Actionable fix instruction (empty when ``ok=True``).
    blocking : bool
        ``True`` if a failure here should prevent deployment.
        ``tailscale-https`` is always ``False`` (cannot be verified pre-deploy).
    """

    check: PreflightCheck
    ok: bool
    problem: str
    fix: str
    blocking: bool
