"""The landing page's quick start stays complete and in step with the README."""

from __future__ import annotations

import html
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LANDING = (ROOT / "site" / "index.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
SKILL = (ROOT / "ember" / "agent_kit" / "ember-advise" / "SKILL.md").read_text(
    encoding="utf-8"
)

_CODE_BLOCK = re.compile(r"```bash\n(.*?)```", re.DOTALL)
_TRAILING_COMMENT = re.compile(r"\s+#\s.*$")
_DECISION = re.compile(r'<figure class="decision[^"]*"[^>]*>(.*?)</figure>', re.DOTALL)
_EVIDENCE = re.compile(
    r'<blockquote class="decision-evidence">\s*(.*?)\s*</blockquote>', re.DOTALL
)
_ANSWER = re.compile(r"<li[^>]*>.*?<code>(\w+)</code>.*?<b>([\d.]+)</b>", re.DOTALL)


def _landing_commands() -> list[str]:
    """Every command line in the landing page's shell blocks, without comments."""
    lines = (
        _TRAILING_COMMENT.sub("", line).strip()
        for block in _CODE_BLOCK.findall(LANDING)
        for line in block.splitlines()
    )
    return [line for line in lines if line]


def test_landing_commands_appear_verbatim_in_the_readme() -> None:
    missing = [command for command in _landing_commands() if command not in README]
    assert missing == []


@pytest.mark.parametrize(
    "registration",
    [
        "ember init --opencode --global",
        "claude mcp add --scope user ember -- ember-mcp",
        "ember init --codex",
        "ember init --kilocode",
    ],
)
def test_landing_shows_how_to_connect_each_supported_agent(registration: str) -> None:
    assert registration in _landing_commands()


def _observed_row(evidence: str) -> str:
    """Return the SKILL.md recipe row that records ``evidence``, or ``""``."""
    rows = (line for line in SKILL.splitlines() if line.startswith("|"))
    return next((row for row in rows if evidence in row), "")


def test_landing_decisions_quote_observed_skill_output() -> None:
    decisions = _DECISION.findall(LANDING)
    assert len(decisions) >= 3
    for decision in decisions:
        evidence = _EVIDENCE.search(decision)
        assert evidence, decision
        row = _observed_row(html.unescape(evidence.group(1)))
        answers = _ANSWER.findall(decision)
        assert row, evidence.group(1)
        assert answers, decision
        for question, value in answers:
            assert f"`{question}` {value}" in row


_LIQUID = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.DOTALL)
_MARKUP = re.compile(r"<[^>]*>")
_NUMBER = re.compile(r"\b\d[\d,.]*\b")


def _prose_numbers() -> list[str]:
    """Numbers typed into the landing page's visible prose.

    Generated values (Liquid), the checked decision cards, the quick start, and
    markup attributes are excluded; anything left would go stale by hand.
    """
    text = _DECISION.sub("", LANDING.split("---", 2)[2])
    text = text.split('id="get-started"', 1)[0]
    text = _MARKUP.sub(" ", _LIQUID.sub(" ", text))
    return _NUMBER.findall(text)


# Install requirements, illustrative examples, and the weights' license:
# none of them come from a benchmark run.
_ALLOWED_NUMBERS = {"32", "18", "0.96", "96", "93", "0", "3", "2.0"}


def test_landing_prose_has_no_hand_typed_benchmark_numbers() -> None:
    stray = [n for n in _prose_numbers() if n not in _ALLOWED_NUMBERS]
    assert stray == []


def test_hero_questions_come_from_the_generated_pool() -> None:
    assert "site.data.benchmark.hero" in LANDING
    assert 'id="hero-pool"' in LANDING


def test_hero_has_a_pause_control_for_its_motion() -> None:
    # WCAG 2.2.2: motion that starts by itself and lasts over 5 s needs a pause.
    assert 'class="hero-pause"' in LANDING
