"""RECIPES: the single registry of benchmark recipes."""

from __future__ import annotations

from .records.family import Family
from .records.recipe_spec import RecipeSpec


def _coding(
    category: str, title: str, when: str, state: str, decides: str
) -> RecipeSpec:
    return RecipeSpec(
        category=category,
        title=title,
        when=when,
        state=state,
        decides=decides,
        family=Family.coding,
        phase=0,
    )


def _vision(
    category: str, title: str, when: str, state: str, decides: str
) -> RecipeSpec:
    return RecipeSpec(
        category=category,
        title=title,
        when=when,
        state=state,
        decides=decides,
        family=Family.vision,
        phase=0,
    )


RECIPES: dict[str, RecipeSpec] = {
    "intent_readiness": _coding(
        "intent_readiness",
        "Intent and readiness",
        "Before changing files in response to a conversational request.",
        "The user's latest message, verbatim.",
        "What the user is asking for, and whether it is specific enough "
        "to act on without a clarifying question.",
    ),
    "failure_triage": _coding(
        "failure_triage",
        "Failure triage",
        "Before retrying or fixing a failing test or command.",
        "The test or command, and the relevant error lines.",
        "The most likely cause, and whether a plain re-run would pass.",
    ),
    "change_risk": _coding(
        "change_risk",
        "Change risk",
        "Before committing, pushing, or merging.",
        "A diff summary, the files touched, and the lines changed.",
        "How risky the change is to ship unreviewed, and whether a "
        "person should review it.",
    ),
    "routing": _coding(
        "routing",
        "Routing and ownership",
        "When an error needs an owner.",
        "The error message and the file or module it came from.",
        "Which part of the system should handle it. The option set is "
        "a template that projects replace with their own.",
    ),
    "effort_approach": _coding(
        "effort_approach",
        "Effort and approach",
        "When planning a task.",
        "The task and its constraints.",
        "How much work the task is, and which approach fits. The option "
        "sets are templates.",
    ),
    "vision_noul": _vision(
        "vision_noul",
        "Vision: dominant colour, yes/no",
        "Smoke check of the vision path.",
        "One synthetic colour swatch.",
        "Whether one colour dominates the image.",
    ),
    "vision_choice": _vision(
        "vision_choice",
        "Vision: dominant colour, choice",
        "Smoke check of the vision path.",
        "One synthetic colour swatch.",
        "Which colour dominates the image.",
    ),
    "vision_score": _vision(
        "vision_score",
        "Vision: alert level, score",
        "Smoke check of the vision path.",
        "One synthetic status indicator.",
        "How severe the alert the indicator signals is.",
    ),
    "vision_video": _vision(
        "vision_video",
        "Vision: colour change across frames",
        "Smoke check of the video path.",
        "Two synthetic frames.",
        "Whether the dominant colour changed between the frames.",
    ),
}


def recipe_for(category: str) -> RecipeSpec:
    """Return the registered recipe for ``category``.

    Parameters
    ----------
    category : str
        A dataset ``category``.

    Returns
    -------
    RecipeSpec
        The registered recipe.

    Raises
    ------
    KeyError
        If the category is not registered.
    """
    return RECIPES[category]


def headline_categories() -> frozenset[str]:
    """Return the categories that count toward the headline accuracy."""
    return frozenset(c for c, spec in RECIPES.items() if spec.headline)
