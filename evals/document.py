"""Assemble a report model into numbered sections of document blocks."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .render.blocks import Section
from .sections import sections_agent, sections_front, sections_results, sections_review

BUILDERS: tuple[Callable[[Mapping[str, Any]], sections_front.Built], ...] = (
    sections_front.summary,
    sections_front.context,
    sections_front.system,
    sections_front.design,
    sections_front.metrics,
    sections_results.results,
    sections_results.calibration,
    sections_results.decisions,
    sections_results.ordinal,
    sections_results.confusion,
    sections_review.errors,
    sections_review.latency,
    sections_review.limitations,
    sections_review.reproducibility,
    sections_review.glossary,
    sections_review.references,
    sections_review.appendix,
)


def build(report: Mapping[str, Any]) -> list[Section]:
    """Return the report's sections in reading order, numbered from 1.

    When an agent-in-the-loop run is attached (``report["agent"]``), its section
    follows the summary, because it measures ember the way agents use it.
    """
    builders = list(BUILDERS)
    if report.get("agent"):
        builders.insert(1, sections_agent.agent_section)
    sections = []
    for number, builder in enumerate(builders, 1):
        anchor, title, blocks = builder(report)
        sections.append(Section(anchor, number, title, tuple(blocks)))
    return sections
