"""SCALES: the declared poles and dangerous end of every ``score`` question."""

from __future__ import annotations

from .protocol import FOUNDATIONS_VERSION
from .records.dangerous_end import DangerousEnd
from .records.scale import Scale

SCALES: dict[tuple[str, str], Scale] = {
    ("change_risk", "risk"): Scale(
        category="change_risk",
        question="risk",
        quantity="risk of shipping unreviewed",
        low="Negligible",
        high="High",
        dangerous_end=DangerousEnd.high,
        dangerous_from=2,
        since=FOUNDATIONS_VERSION,
    ),
    ("effort_approach", "effort"): Scale(
        category="effort_approach",
        question="effort",
        quantity="work required",
        low="Trivial (minutes)",
        high="Large (a day or more)",
        dangerous_end=DangerousEnd.none,
        dangerous_from=None,
        since=FOUNDATIONS_VERSION,
    ),
    ("vision_score", "alert_level"): Scale(
        category="vision_score",
        question="alert_level",
        quantity="alert severity",
        low="No alert (calm green)",
        high="High (red)",
        dangerous_end=DangerousEnd.high,
        dangerous_from=2,
        since=FOUNDATIONS_VERSION,
    ),
}


def scale_for(category: str, question: str) -> Scale | None:
    """Return the registered scale for ``(category, question)``, or ``None``.

    Parameters
    ----------
    category : str
        The recipe the question belongs to.
    question : str
        The question id within that recipe.

    Returns
    -------
    Scale | None
        The declared scale, or ``None`` when the question has none.
    """
    return SCALES.get((category, question))
