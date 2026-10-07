"""StrEnum contracts for the agent-eval condition and report tone (Article X §10.7).

Nothing here loads the model; these are pure enum/serialization checks plus a
few call-site contracts that must keep using the enum, not a bare string.
"""

from __future__ import annotations

import json

from evals.agent.condition import Condition
from evals.render.tone import Tone


def test_condition_has_the_four_members_in_kit_order() -> None:
    assert tuple(Condition) == (
        Condition.NONE,
        Condition.MCP,
        Condition.SKILL,
        Condition.FULL,
    )


def test_condition_compares_equal_to_its_string_value() -> None:
    assert Condition("full") == "full"
    assert Condition.FULL == "full"
    assert "full" == Condition.FULL


def test_condition_serializes_as_its_bare_string() -> None:
    assert json.dumps(Condition.FULL) == '"full"'
    assert json.dumps({"condition": Condition.NONE}) == '{"condition": "none"}'


def test_tone_has_the_four_members() -> None:
    assert {t.value for t in Tone} == {"good", "warn", "info", "bad"}


def test_tone_compares_equal_to_its_string_value() -> None:
    assert Tone("good") == "good"
    assert Tone.BAD == "bad"


def test_tone_serializes_as_its_bare_string() -> None:
    assert json.dumps(Tone.WARN) == '"warn"'


def test_sandbox_conditions_tuple_is_condition_members_in_order() -> None:
    # import-placement:allow - deferred to avoid importing sandbox at module load
    from evals.agent import sandbox

    assert sandbox.CONDITIONS == tuple(Condition)
    assert all(isinstance(c, Condition) for c in sandbox.CONDITIONS)


def test_sandbox_condition_labels_are_keyed_by_condition_members() -> None:
    # import-placement:allow - deferred to avoid importing sandbox at module load
    from evals.agent import sandbox

    assert set(sandbox.CONDITION_LABELS) == set(Condition)
    assert all(isinstance(c, Condition) for c in sandbox.CONDITION_LABELS)


def test_render_html_tone_label_is_keyed_by_tone_members() -> None:
    # import-placement:allow - deferred to avoid importing render_html at module load
    from evals.render import render_html

    assert all(isinstance(t, Tone) for t in render_html.TONE_LABEL)
    assert all(isinstance(t, Tone) for t in render_html.ICONS)


def test_render_markdown_tone_label_is_keyed_by_tone_members() -> None:
    # import-placement:allow - deferred to avoid importing render_markdown at load
    from evals.render import render_markdown

    assert all(isinstance(t, Tone) for t in render_markdown.TONE_LABEL)
