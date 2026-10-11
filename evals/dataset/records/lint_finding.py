"""LintFinding: one dataset lint result."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .lint_rule import LintRule


class LintFinding(BaseModel):
    """A rule that a recipe or an item failed.

    Parameters
    ----------
    rule : LintRule
        The rule.
    category : str
        The recipe the finding belongs to.
    message : str
        What failed, with the numbers.
    item_id : str | None
        The item, when the finding is about one.
    enforced : bool
        Whether this finding fails the build.
    """

    model_config = ConfigDict(frozen=True)

    rule: LintRule
    category: str
    message: str
    item_id: str | None = None
    enforced: bool = False
