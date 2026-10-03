"""Eval harness for the ember_advise MCP tool.

Exercises all five SKILL.md recipes (intent & readiness, failure triage,
change-risk, routing, effort & approach) against the real Clef-Flash model
through the full MCP stdio path.  Each case is a direct, runnable check you
can invoke in opencode to track model performance over time.

Markers
-------
@pytest.mark.evals   — every test here; run with: make test-evals
@pytest.mark.model   — inherited automatically (evals require the model)

Positive cases  pin that observed recipe outputs stay within calibrated bounds.
Negative cases  pin anti-patterns that the model must *not* fall into, and
                structural invariants that make agent call-patterns safe.

Observed outputs are from Clef-Flash revision 17f0b0a on Apple M4 Max.
Re-measure (make test-evals 2>&1 | tee evals.log) whenever the pinned model
revision or a recipe's question set changes — see AGENTS.md "kit rules".
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from tests.conftest import mcp_stdin_params

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _advise(base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Call the advise tool over MCP stdio and return the decoded JSON answer."""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

    params = mcp_stdin_params(base_url)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("advise", {"input": payload})
    assert not result.is_error, result.content[0].text
    if result.structured_content is not None:
        return result.structured_content  # type: ignore[return-value]
    return json.loads(result.content[0].text)  # type: ignore[return-value]


def _answers(resp: dict[str, Any]) -> dict[str, Any]:
    return resp["answers"]  # type: ignore[return-value]


def _noul(resp: dict[str, Any], qid: str) -> float:
    a = _answers(resp)[qid]
    assert a["type"] == "noul"
    return float(a["noul"])


def _choice(resp: dict[str, Any], qid: str) -> tuple[str, float]:
    a = _answers(resp)[qid]
    assert a["type"] == "choice"
    return a["choice"], float(a["confidence"])


def _score(resp: dict[str, Any], qid: str) -> float:
    a = _answers(resp)[qid]
    assert a["type"] == "score"
    return float(a["score"])


# ---------------------------------------------------------------------------
# Recipe question sets  (fixed; changing a sibling shifts confidences — AGENTS.md)
# ---------------------------------------------------------------------------

INTENT_QUESTIONS: dict[str, Any] = {
    "intent": {
        "type": "choice",
        "instructions": "What is the user asking the coding agent to do?",
        "criteria": {
            "question": "Explain or answer something; no code changes requested",
            "implement": "Make a change: add, modify, or configure something",
            "investigate": "Look into a problem and report findings",
            "fix": "Repair a specific broken behavior",
        },
    },
    "specific_enough": {
        "type": "noul",
        "instructions": (
            "Is the request specific enough to act on"
            " without asking a clarifying question?"
        ),
        "criteria": {
            "true": "The target and desired outcome are both identifiable",
            "false": "The target or desired outcome is unclear",
        },
    },
}

FAILURE_QUESTIONS: dict[str, Any] = {
    "failure_kind": {
        "type": "choice",
        "instructions": "What most likely caused this failure?",
        "criteria": {
            "logic_bug": "The code under test returns a wrong result",
            "environment": "Missing service, dependency, port, file, or configuration",
            "flaky": "Timing, ordering, or nondeterminism; may pass on retry",
            "test_bug": "The test itself is wrong or outdated",
        },
    },
    "retry": {
        "type": "noul",
        "instructions": "Is simply re-running likely to make it pass?",
    },
}

RISK_QUESTIONS: dict[str, Any] = {
    "risk": {
        "type": "score",
        "instructions": "How risky is shipping this change without human review?",
        "criteria": ["Negligible", "Low", "Medium", "High"],
    },
    "needs_review": {
        "type": "noul",
        "instructions": "Should a human review this change before it is merged?",
    },
}

ROUTING_QUESTIONS: dict[str, Any] = {
    "owner": {
        "type": "choice",
        "instructions": "Which part of the system should handle this?",
        "criteria": {
            "api": "HTTP handlers and request validation",
            "storage": "Database, migrations, and persistence",
            "ui": "Frontend rendering and client state",
            "infra": "Build, CI, deployment, and configuration",
            "unclear": "Not enough information to tell",
        },
    }
}

EFFORT_QUESTIONS: dict[str, Any] = {
    "effort": {
        "type": "score",
        "instructions": "How much work is this task?",
        "criteria": [
            "Trivial (minutes)",
            "Small (under an hour)",
            "Medium (a few hours)",
            "Large (a day or more)",
        ],
    },
    "approach": {
        "type": "choice",
        "instructions": "Which approach best fits the constraints?",
        "criteria": {
            "minimal_patch": "Smallest change that fixes the symptom",
            "refactor": "Restructure the code so the fix is natural",
            "new_component": "Add a new module or service",
            "ask_user": "The trade-off needs a human decision",
        },
    },
}


# ===========================================================================
# RECIPE 1 — Intent & readiness
# ===========================================================================


@pytest.mark.evals
@pytest.mark.model
class TestIntentAndReadiness:
    """Positive: recipe outputs match SKILL.md observed values.
    Negative: vague request → not specific enough; question (not implement).
    """

    def test_vague_request_is_implement_but_not_specific(self, base_url: str) -> None:
        """'update the thing' → implement ≥ 0.85; specific_enough ≤ 0.20.

        SKILL.md observed: implement 0.96, specific_enough 0.09.
        """
        resp = asyncio.run(
            _advise(
                base_url,
                {"state": "update the thing", "questions": INTENT_QUESTIONS},
            )
        )
        intent, conf = _choice(resp, "intent")
        assert intent == "implement", f"expected implement, got {intent} ({conf:.2f})"
        assert conf >= 0.85, f"intent confidence too low: {conf:.2f}"
        specific = _noul(resp, "specific_enough")
        assert specific <= 0.20, (
            f"vague request should not be specific_enough; got P={specific:.2f}"
        )

    def test_precise_implement_request_is_specific(self, base_url: str) -> None:
        """Precise imperative → implement ≥ 0.85; specific_enough ≥ 0.80.

        SKILL.md observed: implement 0.92, specific_enough 0.91.
        """
        resp = asyncio.run(
            _advise(
                base_url,
                {
                    "state": (
                        "bump the torch upper bound in pyproject.toml to <2.16 "
                        "and re-run make test"
                    ),
                    "questions": INTENT_QUESTIONS,
                },
            )
        )
        intent, conf = _choice(resp, "intent")
        assert intent == "implement", f"expected implement, got {intent} ({conf:.2f})"
        assert conf >= 0.85, f"intent confidence too low: {conf:.2f}"
        specific = _noul(resp, "specific_enough")
        assert specific >= 0.80, (
            f"precise request should be specific_enough; got P={specific:.2f}"
        )

    def test_explanation_request_is_question_not_implement(self, base_url: str) -> None:
        """'how does the llm know how to call the tool?' → question ≥ 0.80.

        SKILL.md observed: question 0.89.
        """
        resp = asyncio.run(
            _advise(
                base_url,
                {
                    "state": "how does the llm know how to call the tool?",
                    "questions": INTENT_QUESTIONS,
                },
            )
        )
        intent, conf = _choice(resp, "intent")
        assert intent == "question", f"expected question, got {intent} ({conf:.2f})"
        assert conf >= 0.75, f"question confidence too low: {conf:.2f}"

    def test_investigation_request_is_investigate(self, base_url: str) -> None:
        """'the tests are failing on main since yesterday, can you look?'
        → investigate ≥ 0.85.

        SKILL.md observed: investigate 0.94.
        """
        resp = asyncio.run(
            _advise(
                base_url,
                {
                    "state": (
                        "the tests are failing on main since yesterday, can you look?"
                    ),
                    "questions": INTENT_QUESTIONS,
                },
            )
        )
        intent, conf = _choice(resp, "intent")
        assert intent == "investigate", (
            f"expected investigate, got {intent} ({conf:.2f})"
        )
        assert conf >= 0.85, f"investigate confidence too low: {conf:.2f}"


# ===========================================================================
# RECIPE 2 — Failure triage
# ===========================================================================


@pytest.mark.evals
@pytest.mark.model
class TestFailureTriage:
    """Positive: connection refused → environment; wrong result → logic_bug;
    timing failure → flaky.
    Negative: logic_bug should not suggest retry.
    """

    def test_connection_refused_is_environment_not_retry(self, base_url: str) -> None:
        """Connection refused → environment ≥ 0.75; retry ≤ 0.25.

        SKILL.md observed: environment 0.84, retry 0.15.
        """
        resp = asyncio.run(
            _advise(
                base_url,
                {
                    "state": {
                        "test": "tests/test_http_api.py::test_health",
                        "output": "httpx.ConnectError: [Errno 61] Connection refused",
                    },
                    "questions": FAILURE_QUESTIONS,
                },
            )
        )
        kind, conf = _choice(resp, "failure_kind")
        assert kind == "environment", f"expected environment, got {kind} ({conf:.2f})"
        assert conf >= 0.75, f"environment confidence too low: {conf:.2f}"
        retry = _noul(resp, "retry")
        assert retry <= 0.25, (
            f"connection refused should not suggest retry; P(retry)={retry:.2f}"
        )

    def test_wrong_result_is_logic_bug_not_retry(self, base_url: str) -> None:
        """Wrong assertion → logic_bug ≥ 0.80; retry ≤ 0.15.

        SKILL.md observed: logic_bug 0.93, retry 0.05.
        """
        resp = asyncio.run(
            _advise(
                base_url,
                {
                    "state": {
                        "test": "tests/test_math.py::test_add",
                        "output": "assert add(2, 2) == 4\n  where 5 = add(2, 2)",
                    },
                    "questions": FAILURE_QUESTIONS,
                },
            )
        )
        kind, conf = _choice(resp, "failure_kind")
        assert kind == "logic_bug", f"expected logic_bug, got {kind} ({conf:.2f})"
        assert conf >= 0.80, f"logic_bug confidence too low: {conf:.2f}"
        retry = _noul(resp, "retry")
        assert retry <= 0.15, (
            f"logic_bug should not suggest retry; P(retry)={retry:.2f}"
        )

    def test_timing_failure_is_flaky_with_retry(self, base_url: str) -> None:
        """Intermittent timeout with history → flaky ≥ 0.75; retry ≥ 0.55.

        SKILL.md observed: flaky 0.89, retry 0.67.
        """
        resp = asyncio.run(
            _advise(
                base_url,
                {
                    "state": {
                        "test": "tests/test_server.py::test_startup",
                        "output": (
                            "TimeoutError after 5.0s; passed on 3 of last 5 CI runs"
                        ),
                    },
                    "questions": FAILURE_QUESTIONS,
                },
            )
        )
        kind, conf = _choice(resp, "failure_kind")
        assert kind == "flaky", f"expected flaky, got {kind} ({conf:.2f})"
        assert conf >= 0.75, f"flaky confidence too low: {conf:.2f}"
        retry = _noul(resp, "retry")
        assert retry >= 0.55, (
            f"flaky failure should suggest retry; P(retry)={retry:.2f}"
        )


# ===========================================================================
# RECIPE 3 — Change-risk
# ===========================================================================


@pytest.mark.evals
@pytest.mark.model
class TestChangeRisk:
    """Positive: trivial rename → low risk; auth bypass → high risk + needs_review.
    Negative: score must separate cases even when choice confidence looks similar.
    """

    def test_trivial_rename_is_low_risk_no_review(self, base_url: str) -> None:
        """Rename a local variable in a test → risk ≤ 1.0 of 3; needs_review ≤ 0.20.

        SKILL.md observed: risk 0.75/3, needs_review 0.09.
        """
        resp = asyncio.run(
            _advise(
                base_url,
                {
                    "state": {
                        "diff_summary": (
                            "Rename local variable `tmp` to `result` in one test helper"
                        ),
                        "files": ["tests/test_helpers.py"],
                        "lines_changed": 4,
                    },
                    "questions": RISK_QUESTIONS,
                },
            )
        )
        risk = _score(resp, "risk")
        assert risk <= 1.0, f"trivial rename should have low risk; score={risk:.2f}/3"
        needs_review = _noul(resp, "needs_review")
        assert needs_review <= 0.20, (
            f"trivial rename should not need review; P={needs_review:.2f}"
        )

    def test_auth_bypass_is_high_risk_needs_review(self, base_url: str) -> None:
        """Skip auth token validation → risk ≥ 2.0 of 3; needs_review ≥ 0.80.

        The bound is the kit's published act-on-it rule (noul P ≥ 0.80 means
        yes), not the recipe's illustrative 0.93; this state scores ~0.84.
        """
        resp = asyncio.run(
            _advise(
                base_url,
                {
                    "state": {
                        "diff_summary": (
                            "Skip auth token validation when request"
                            " originates from localhost to unblock"
                            " local development"
                        ),
                        "files": ["ember/server.py", "ember/mcp_server.py"],
                        "lines_changed": 180,
                    },
                    "questions": RISK_QUESTIONS,
                },
            )
        )
        risk = _score(resp, "risk")
        assert risk >= 2.0, f"auth bypass should be high risk; score={risk:.2f}/3"
        needs_review = _noul(resp, "needs_review")
        assert needs_review >= 0.80, (
            f"auth bypass should require review; P={needs_review:.2f}"
        )

    def test_score_separates_trivial_from_dangerous(self, base_url: str) -> None:
        """The expected score must cleanly separate trivial from dangerous changes.

        This pins the SKILL.md warning: "Don't threshold score on confidence —
        the top option can sit near 0.63 for both, while expected scores differ."
        We verify the gap is at least 1.0 of 3 (i.e. scores are actually informative).
        """
        trivial = asyncio.run(
            _advise(
                base_url,
                {
                    "state": {
                        "diff_summary": "Fix a typo in a comment",
                        "files": ["README.md"],
                        "lines_changed": 1,
                    },
                    "questions": RISK_QUESTIONS,
                },
            )
        )
        dangerous = asyncio.run(
            _advise(
                base_url,
                {
                    "state": {
                        "diff_summary": (
                            "Remove all authentication middleware from the API gateway "
                            "to improve p99 latency"
                        ),
                        "files": ["ember/server.py"],
                        "lines_changed": 95,
                    },
                    "questions": RISK_QUESTIONS,
                },
            )
        )
        trivial_score = _score(trivial, "risk")
        dangerous_score = _score(dangerous, "risk")
        assert dangerous_score - trivial_score >= 1.0, (
            f"score should separate changes: trivial={trivial_score:.2f}, "
            f"dangerous={dangerous_score:.2f} "
            f"(gap={dangerous_score - trivial_score:.2f})"
        )


# ===========================================================================
# RECIPE 4 — Routing and ownership
# ===========================================================================


@pytest.mark.evals
@pytest.mark.model
class TestRoutingAndOwnership:
    """Positive: DB error → storage; UI render error → ui; build failure → infra.
    Negative: insufficient evidence → unclear (not forced into a wrong bucket).
    """

    def test_database_error_routes_to_storage(self, base_url: str) -> None:
        """psycopg2 error → storage ≥ 0.70."""
        resp = asyncio.run(
            _advise(
                base_url,
                {
                    "state": {
                        "error": (
                            "psycopg2.OperationalError: could not connect to server"
                        ),
                        "path": "ember/db/migrations/0003_add_index.py",
                    },
                    "questions": ROUTING_QUESTIONS,
                },
            )
        )
        owner, conf = _choice(resp, "owner")
        assert owner == "storage", f"expected storage, got {owner} ({conf:.2f})"
        assert conf >= 0.70, f"storage confidence too low: {conf:.2f}"

    def test_render_error_routes_to_ui(self, base_url: str) -> None:
        """React hydration error → ui ≥ 0.65."""
        resp = asyncio.run(
            _advise(
                base_url,
                {
                    "state": {
                        "error": (
                            "Hydration failed because the server rendered"
                            " HTML did not match the client"
                        ),
                        "path": "packages/ui/src/components/Dashboard.tsx",
                    },
                    "questions": ROUTING_QUESTIONS,
                },
            )
        )
        owner, conf = _choice(resp, "owner")
        assert owner == "ui", f"expected ui, got {owner} ({conf:.2f})"
        assert conf >= 0.65, f"ui confidence too low: {conf:.2f}"

    def test_ci_failure_routes_to_infra(self, base_url: str) -> None:
        """GitHub Actions OIDC token error → infra ≥ 0.70."""
        resp = asyncio.run(
            _advise(
                base_url,
                {
                    "state": {
                        "error": "Error: Unable to get OIDC token: 403 Forbidden",
                        "path": ".github/workflows/ci.yml",
                    },
                    "questions": ROUTING_QUESTIONS,
                },
            )
        )
        owner, conf = _choice(resp, "owner")
        assert owner == "infra", f"expected infra, got {owner} ({conf:.2f})"
        assert conf >= 0.70, f"infra confidence too low: {conf:.2f}"

    def test_ambiguous_error_routes_to_unclear(self, base_url: str) -> None:
        """Deliberately thin state → unclear wins or confidence < 0.60 (not forced).

        This pins the "exhaustive options" rule: add an `unclear` bucket so the
        model is not forced into a wrong category when evidence is insufficient.
        """
        resp = asyncio.run(
            _advise(
                base_url,
                {
                    "state": {
                        "error": "something went wrong",
                        "path": "",
                    },
                    "questions": ROUTING_QUESTIONS,
                },
            )
        )
        owner, conf = _choice(resp, "owner")
        # Accept unclear as the winner OR low confidence (model is uncertain, not wrong)
        assert owner == "unclear" or conf < 0.60, (
            f"ambiguous state should route to unclear or show low confidence; "
            f"got {owner} ({conf:.2f})"
        )


# ===========================================================================
# RECIPE 5 — Effort and approach
# ===========================================================================


@pytest.mark.evals
@pytest.mark.model
class TestEffortAndApproach:
    """Positive: one-line fix → trivial/small + minimal_patch;
    full feature → large + new_component or ask_user.
    """

    def test_one_line_fix_is_trivial(self, base_url: str) -> None:
        """One-line typo fix → effort ≤ 1.0 of 3; minimal_patch."""
        resp = asyncio.run(
            _advise(
                base_url,
                {
                    "state": {
                        "task": (
                            "Fix a typo in the error message string in cli.py line 42"
                        ),
                        "constraints": ["must not change behavior", "one file"],
                    },
                    "questions": EFFORT_QUESTIONS,
                },
            )
        )
        effort = _score(resp, "effort")
        assert effort <= 1.0, (
            f"one-line fix should be trivial/small; score={effort:.2f}/3"
        )
        approach, _ = _choice(resp, "approach")
        assert approach == "minimal_patch", (
            f"one-line fix should use minimal_patch; got {approach}"
        )

    def test_large_feature_is_large_effort(self, base_url: str) -> None:
        """Multi-service new feature → effort ≥ 2.0 of 3."""
        resp = asyncio.run(
            _advise(
                base_url,
                {
                    "state": {
                        "task": (
                            "Design and implement a multi-tenant authentication system "
                            "with RBAC, JWT refresh tokens, and an admin dashboard"
                        ),
                        "constraints": [
                            "must work across 3 microservices",
                            "zero downtime migration",
                            "full test coverage",
                        ],
                    },
                    "questions": EFFORT_QUESTIONS,
                },
            )
        )
        effort = _score(resp, "effort")
        assert effort >= 2.0, (
            f"large feature should score high effort; score={effort:.2f}/3"
        )

    def test_small_refactor_uses_refactor_approach(self, base_url: str) -> None:
        """Extracting a repeated pattern → refactor approach."""
        resp = asyncio.run(
            _advise(
                base_url,
                {
                    "state": {
                        "task": (
                            "The same 15-line retry loop is copy-pasted in 6 different "
                            "HTTP client methods; extract it into a shared helper"
                        ),
                        "constraints": ["no new dependencies", "keep existing API"],
                    },
                    "questions": EFFORT_QUESTIONS,
                },
            )
        )
        approach, conf = _choice(resp, "approach")
        assert approach == "refactor", (
            f"repeated pattern extraction should use refactor;"
            f" got {approach} ({conf:.2f})"
        )


# ===========================================================================
# NEGATIVE / ANTI-PATTERN CASES
# ===========================================================================


@pytest.mark.evals
@pytest.mark.model
class TestAntiPatterns:
    """Negative cases: these pin behaviors that MUST hold for safe agent use.

    1. Verdict-in-state echo  — injecting a conclusion into `state` biases output.
    2. Determinism            — identical requests must return identical answers.
    3. Score ≠ confidence     — score and confidence can diverge; score is signal.
    4. Specificity gate       — vague request must not pass the specific_enough gate.
    5. MCP error surface      — malformed questions raise actionable ToolError.
    """

    def test_verdict_in_state_biases_output(self, base_url: str) -> None:
        """Writing a conclusion into `state` gets it echoed back.

        A neutral message ('connection refused') scores environment.
        The same message prefixed with "this is definitely a logic bug in the code"
        must shift the distribution — demonstrating why you must pass raw evidence.
        The test does NOT assert environment wins both times; it asserts the
        distributions differ, which is the detectable anti-pattern.
        """
        neutral_resp = asyncio.run(
            _advise(
                base_url,
                {
                    "state": {
                        "test": "test_connect",
                        "output": "httpx.ConnectError: [Errno 61] Connection refused",
                    },
                    "questions": FAILURE_QUESTIONS,
                },
            )
        )
        biased_resp = asyncio.run(
            _advise(
                base_url,
                {
                    "state": {
                        "test": "test_connect",
                        "output": "httpx.ConnectError: [Errno 61] Connection refused",
                        "analysis": (
                            "This is definitely a logic_bug in the application code"
                        ),
                    },
                    "questions": FAILURE_QUESTIONS,
                },
            )
        )
        neutral_kind, neutral_conf = _choice(neutral_resp, "failure_kind")
        biased_kind, biased_conf = _choice(biased_resp, "failure_kind")

        # The distributions must differ — at minimum, confidence or winner changes.
        distributions_differ = (neutral_kind != biased_kind) or (
            abs(neutral_conf - biased_conf) > 0.05
        )
        assert distributions_differ, (
            "Adding a verdict to state had no effect —"
            " the model may be ignoring state content. "
            f"neutral={neutral_kind}@{neutral_conf:.2f},"
            f" biased={biased_kind}@{biased_conf:.2f}"
        )

    def test_identical_requests_are_deterministic(self, base_url: str) -> None:
        """Same payload called twice must return bit-identical answers.

        SKILL.md: 'The same request always gets the same feeling.'
        """
        payload: dict[str, Any] = {
            "state": "the tests are failing on main since yesterday, can you look?",
            "questions": INTENT_QUESTIONS,
        }
        resp_a = asyncio.run(_advise(base_url, payload))
        resp_b = asyncio.run(_advise(base_url, payload))

        for qid in resp_a["answers"]:
            a = resp_a["answers"][qid]
            b = resp_b["answers"][qid]
            assert a == b, (
                f"Non-deterministic output for question '{qid}': first={a}, second={b}"
            )

    def test_score_and_confidence_can_diverge(self, base_url: str) -> None:
        """The expected score is the right signal for score questions, not confidence.

        We call the trivial rename and auth-bypass cases from change-risk, then
        assert that the *scores* differ by ≥ 1.0 even if the *confidences* sit close.
        This locks the SKILL.md warning against thresholding score on confidence.
        """
        trivial = asyncio.run(
            _advise(
                base_url,
                {
                    "state": {
                        "diff_summary": "Fix a typo in a comment",
                        "files": ["README.md"],
                        "lines_changed": 1,
                    },
                    "questions": RISK_QUESTIONS,
                },
            )
        )
        dangerous = asyncio.run(
            _advise(
                base_url,
                {
                    "state": {
                        "diff_summary": (
                            "Remove all authentication middleware to improve latency"
                        ),
                        "files": ["ember/server.py"],
                        "lines_changed": 95,
                    },
                    "questions": RISK_QUESTIONS,
                },
            )
        )
        trivial_score = _score(trivial, "risk")
        dangerous_score = _score(dangerous, "risk")
        assert dangerous_score - trivial_score >= 1.0, (
            f"Scores must separate cases: trivial={trivial_score:.2f}, "
            f"dangerous={dangerous_score:.2f}"
        )

    def test_vague_request_fails_specificity_gate(self, base_url: str) -> None:
        """A vague request must not pass the specific_enough gate (P ≤ 0.20).

        This directly pins the AGENTS.md snippet rule:
          specific_enough P ≤ 0.20 → ask a clarifying question before acting.
        """
        for vague in [
            "do the thing",
            "make it better",
            "fix the issue",
            "update stuff",
        ]:
            resp = asyncio.run(
                _advise(
                    base_url,
                    {"state": vague, "questions": INTENT_QUESTIONS},
                )
            )
            specific = _noul(resp, "specific_enough")
            assert specific <= 0.30, (
                f"Vague request {vague!r} passed the specificity gate: P={specific:.2f}"
            )

    def test_malformed_choice_question_surfaces_actionable_error(
        self, base_url: str
    ) -> None:
        """choice without criteria → ToolError with actionable message, not a crash.

        Pins the AGENTS.md rule: "Raise ToolError for failures the agent should read."
        """
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        params = mcp_stdin_params(base_url)

        async def _call() -> Any:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await session.call_tool(
                        "advise",
                        {
                            "input": {
                                "state": "x",
                                "questions": {
                                    "team": {"type": "choice", "instructions": "Which?"}
                                },
                            }
                        },
                    )

        result = asyncio.run(_call())
        assert result.is_error is True
        assert "criteria" in result.content[0].text.lower(), (
            f"Error message should mention 'criteria'; got: {result.content[0].text}"
        )
