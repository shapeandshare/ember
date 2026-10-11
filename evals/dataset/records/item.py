"""Item: one benchmark line — the scored content plus its annotations."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .item_kind import ItemKind
from .source import Source
from .split import Split

Gold = bool | int | str


class Item(BaseModel):
    """One dataset item.

    Parameters
    ----------
    id, category, split : str, str, Split
        Identity; the split is assigned once and pinned for life.
    state, images, videos, media_kwargs
        The evidence the model is scored on.
    questions : dict[str, dict[str, Any]]
        The recipe's fixed question set (identical across the recipe).
    gold_labels : dict[str, Gold]
        One gold label per question.
    rationale : str
        One line saying why the gold is what it is.
    source : Source
        Provenance with a regeneration reference.
    kind : ItemKind | None
        Composition role; ``None`` means not yet tagged.
    parent_id, template_family, external_label, acted, acted_differs,
    second_review, second_pass, tier
        Annotations filled by later phases; none of them enters the content hash.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    split: Split
    state: str | dict[str, Any]
    images: list[Any] | None = None
    videos: list[Any] | None = None
    media_kwargs: dict[str, Any] | None = None
    questions: dict[str, dict[str, Any]] = Field(min_length=1)
    gold_labels: dict[str, Gold] = Field(min_length=1)
    rationale: str
    source: Source
    kind: ItemKind | None = None
    parent_id: str | None = None
    template_family: str | None = None
    external_label: dict[str, Any] | None = None
    acted: dict[str, Any] | None = None
    acted_differs: bool = False
    second_review: bool = False
    second_pass: dict[str, Any] | None = None
    tier: Literal["easy"] | None = None

    @model_validator(mode="after")
    def _gold_matches_questions(self) -> Item:
        if not self.rationale.strip():
            raise ValueError(f"{self.id}: rationale is empty")
        if set(self.gold_labels) != set(self.questions):
            raise ValueError(f"{self.id}: gold_labels keys differ from questions")
        return self
