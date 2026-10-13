"""TagVocabulary: the vault's controlled vocabulary as read at a revision."""

from __future__ import annotations

import re
from typing import Final

from pydantic import BaseModel, ConfigDict

AXES: Final = ("type", "domain", "status", "layer", "concept")

VALUE_RE: Final = re.compile(
    r"^- `((?:type|domain|status|layer|concept)/[a-z0-9-]+)` — (.+)$",
    re.MULTILINE,
)


class TagVocabulary(BaseModel):
    """Every controlled tag with its one-line description, as read at the pin.

    Parameters
    ----------
    descriptions : dict[str, str]
        Tag value to its as-read one-line description.
    """

    model_config = ConfigDict(frozen=True)

    descriptions: dict[str, str]

    @classmethod
    def from_tags_md(cls, text: str) -> TagVocabulary:
        """Parse ``_meta/tags.md``; only value-list lines count as vocabulary.

        Changelog quotes and prose are ignored by construction (the pattern
        matches list items only), so a retired tag mentioned in the history
        never enters the universe.

        Parameters
        ----------
        text : str
            The committed ``tags.md`` text.

        Returns
        -------
        TagVocabulary
            The as-read vocabulary.

        Raises
        ------
        ValueError
            When no controlled tag values are found.
        """
        found = {tag: description for tag, description in VALUE_RE.findall(text)}
        if not found:
            raise ValueError("no controlled tag values found in tags.md")
        return cls(descriptions=found)

    def contains(self, tag: str) -> bool:
        """Whether ``tag`` is part of the as-read vocabulary."""
        return tag in self.descriptions

    def values_for(self, axis: str) -> list[str]:
        """Return the axis's tag values, sorted."""
        return sorted(tag for tag in self.descriptions if tag.startswith(f"{axis}/"))

    def description_of(self, tag: str) -> str:
        """Return the tag's as-read one-line description."""
        return self.descriptions[tag]

    def as_state_block(self) -> str:
        """Render the vocabulary for an item's state, grouped by axis (FR-017)."""
        lines = ["Controlled tag vocabulary (as read):"]
        for axis in AXES:
            values = self.values_for(axis)
            if not values:
                continue
            lines.append(f"{axis}/*:")
            lines.extend(f"- `{tag}` — {self.descriptions[tag]}" for tag in values)
        return "\n".join(lines)
