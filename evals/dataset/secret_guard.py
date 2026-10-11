"""The credential guard: no live-credential format may enter an item's state.

Documented example values (``example_secrets.json``) are the only allow-list;
the rule is enforced for every recipe whatever its lint mode (specs/004 R24).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .records.example_secret import ExampleSecret
from .records.item import Item
from .records.lint_finding import LintFinding
from .records.lint_rule import LintRule

SECRET_PATTERNS: Mapping[str, re.Pattern[str]] = {
    "aws access key id": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "github token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36}\b"),
    "slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]+"),
    "google api key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "signed web token": re.compile(
        r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"
    ),
}


def _strings(state: str | dict[str, Any]) -> Iterable[str]:
    if isinstance(state, str):
        yield state
        return
    stack: list[Any] = [state]
    while stack:
        value = stack.pop()
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            stack.extend(value.values())
        elif isinstance(value, list | tuple):
            stack.extend(value)


def no_live_secret(
    items: Sequence[Item], examples: Sequence[ExampleSecret]
) -> list[LintFinding]:
    """Flag any state carrying a live-credential format not on the example list."""
    allowed = {example.value for example in examples}
    findings: list[LintFinding] = []
    for item in items:
        for text in _strings(item.state):
            for label, pattern in SECRET_PATTERNS.items():
                for match in pattern.finditer(text):
                    if any(
                        value in text[match.start() : match.end() + 64]
                        for value in allowed
                    ):
                        continue
                    if match.group(0) in allowed:
                        continue
                    findings.append(
                        LintFinding(
                            rule=LintRule.no_live_secret,
                            category=item.category,
                            item_id=item.id,
                            message=(
                                f"{item.id}: state carries a {label} that is not "
                                "a documented example"
                            ),
                            enforced=True,
                        )
                    )
    return findings
