"""LintMode: Whether a lint finding on a recipe fails the build or is only reported."""

from __future__ import annotations

from enum import StrEnum


class LintMode(StrEnum):
    """Whether a lint finding on a recipe fails the build or is only reported."""

    report = "report"
    enforce = "enforce"
