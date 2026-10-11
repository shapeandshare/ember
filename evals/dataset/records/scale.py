"""Scale: the declared poles and dangerous end of one ``score`` question."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .dangerous_end import DangerousEnd


class Scale(BaseModel):
    """The direction of one ``score`` question's ordered levels.

    Parameters
    ----------
    category : str
        The recipe the question belongs to (a key of ``RECIPES``).
    question : str
        The question id within that recipe.
    quantity : str
        What the scale measures, in the words of its instruction.
    low : str
        The text of level 0; must equal the dataset's ``criteria[0]``.
    high : str
        The text of the top level; must equal ``criteria[-1]``.
    dangerous_end : DangerousEnd
        Which pole calls for caution, or ``none``.
    dangerous_from : int | None
        The first level counted as dangerous; required exactly when
        ``dangerous_end`` is not ``none``.
    since : str
        The dataset version (content hash) these rubric anchors first apply
        to (FR-046); a changed pole is recorded under the version it starts with.
    """

    model_config = ConfigDict(frozen=True)

    category: str = Field(min_length=1)
    question: str = Field(min_length=1)
    quantity: str = Field(min_length=1)
    low: str = Field(min_length=1)
    high: str = Field(min_length=1)
    dangerous_end: DangerousEnd
    dangerous_from: int | None = Field(default=None, ge=0)
    since: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _dangerous_from_matches_end(self) -> Scale:
        dangerous = self.dangerous_end is not DangerousEnd.none
        if dangerous and self.dangerous_from is None:
            raise ValueError(
                "dangerous_from is required when dangerous_end is not none"
            )
        if not dangerous and self.dangerous_from is not None:
            raise ValueError("dangerous_from must be None when dangerous_end is none")
        return self

    def legend(self, levels: int) -> str:
        """Return the legend ``0 <low> → <levels - 1> <high>``.

        Parameters
        ----------
        levels : int
            The number of levels the dataset's ``criteria`` list has.

        Returns
        -------
        str
            The legend a report prints beside this question's table.
        """
        return f"0 {self.low} → {levels - 1} {self.high}"
