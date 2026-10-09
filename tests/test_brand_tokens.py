"""Text on a filled accent button stays readable in every colour theme."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

TOKENS = Path(__file__).resolve().parents[1] / "assets" / "brand" / "tokens.css"

LIGHT = ":root"
SYSTEM_DARK = ':root:not([data-theme="light"])'
EXPLICIT_DARK = ':root[data-theme="dark"]'

_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
_DECLARATION = re.compile(r"(--ember-[\w-]+)\s*:\s*([^;]+);")
_VAR = re.compile(r"var\((--ember-[\w-]+)\)")


def _theme(selector: str) -> dict[str, str]:
    """Return a theme's tokens: the base ``:root`` ones with its overrides on top."""
    css = _COMMENT.sub("", TOKENS.read_text(encoding="utf-8"))
    rules = {
        rule.strip(): dict(_DECLARATION.findall(body))
        for rule, body in _RULE.findall(css)
    }
    return {**rules[LIGHT], **rules[selector]}


def _resolve(tokens: dict[str, str], name: str) -> str:
    """Follow ``var()`` references until a literal colour remains."""
    value = tokens[name].strip()
    reference = _VAR.fullmatch(value)
    return _resolve(tokens, reference.group(1)) if reference else value


def _luminance(colour: str) -> float:
    """WCAG relative luminance of a ``#rrggbb`` colour."""
    channels = [int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    red, green, blue = (
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels
    )
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast(first: str, second: str) -> float:
    lighter, darker = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize("selector", [LIGHT, SYSTEM_DARK, EXPLICIT_DARK])
def test_on_accent_text_meets_wcag_aa_on_the_accent(selector: str) -> None:
    tokens = _theme(selector)
    text = _resolve(tokens, "--ember-on-accent")
    fill = _resolve(tokens, "--ember-accent")
    assert _contrast(text, fill) >= 4.5
