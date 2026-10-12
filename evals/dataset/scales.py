"""SCALES: the declared poles, anchors, and dangerous end of every ``score`` question."""

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
        anchors=[
            "Fully reversible routine change; no user-visible effect and no "
            "data or security surface touched.",
            "User-visible but easily reverted; limited to one surface with no "
            "data or security impact.",
            "Meaningful user or data exposure with a manageable rollback; "
            "recovery needs a deliberate response.",
            "Irreversible or security/data-integrity impact on many users or "
            "critical paths; rollback is costly or impossible.",
        ],
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
        anchors=[
            "A single obvious edit, verified as soon as it runs.",
            "One file or function, a quick test, and no design decisions.",
            "Several files or a small design step; needs tests and a review pass.",
            "Cross-cutting design work, a migration, or unknown scope that "
            "needs investigation first.",
        ],
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
        anchors=[
            "The scene reads normal; nothing draws attention.",
            "A minor irregularity worth noting; no attention required.",
            "A clear anomaly or warning state that needs review.",
            "A critical alert state (danger or error) needing immediate attention.",
        ],
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
