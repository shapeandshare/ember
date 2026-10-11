"""RecipeSpec: everything the harness and the report know about one recipe."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .compliance_ref import ComplianceRef
from .family import Family
from .item_kind import ItemKind
from .lint_mode import LintMode


class RecipeSpec(BaseModel):
    """One recipe's prose, family, risk posture, and lint mode.

    Parameters
    ----------
    category : str
        The dataset ``category`` the recipe scores.
    title, when, state, decides : str
        The prose the report's recipe card shows.
    family : Family
        The family the recipe belongs to; decides headline membership.
    phase : int
        The programme phase that introduced the recipe.
    risk : bool
        Whether a missed danger costs more than a false alarm (asymmetric metrics).
    compliance : tuple[ComplianceRef, ...]
        References into external compliance catalogues; never invented.
    policy_slot : bool
        Whether the recipe accepts project policy text in place of fixed criteria.
    dangerous_options : dict[str, frozenset[str]]
        For each ``choice`` question of a risk recipe, the options counted unsafe.
    lint : LintMode
        Whether lint findings fail the build (``enforce``) or are reported.
    exemptions : dict[ItemKind, str]
        Item kinds the recipe cannot fill, each with the documented reason.
    """

    model_config = ConfigDict(frozen=True)

    category: str = Field(min_length=1)
    title: str = Field(min_length=1)
    when: str = Field(min_length=1)
    state: str = Field(min_length=1)
    decides: str = Field(min_length=1)
    family: Family
    phase: int = Field(ge=0)
    risk: bool = False
    compliance: tuple[ComplianceRef, ...] = ()
    policy_slot: bool = False
    dangerous_options: dict[str, frozenset[str]] = Field(default_factory=dict)
    lint: LintMode = LintMode.report
    exemptions: dict[ItemKind, str] = Field(default_factory=dict)

    @property
    def headline(self) -> bool:
        """Whether the recipe counts toward the headline accuracy."""
        return self.family not in (Family.vision, Family.integration)
