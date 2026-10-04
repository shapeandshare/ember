"""Agent-in-the-loop harness: sandboxes, isolation, event parsing, and scoring.

Nothing here launches opencode (constitution Article IV); transcripts are
scripted, and sandboxes are real temporary git repos.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from evals.agent import judge, opencode, sandbox, summary
from evals.agent.opencode import ToolCall
from evals.agent.scenarios import RECIPE_QUESTIONS, SCENARIOS

SCENARIO = {s["id"]: s for s in SCENARIOS}
CHECK_KINDS = {
    "clean",
    "asks",
    "mentions_any",
    "answer",
    "file_contains",
    "paths_unchanged",
    "tests_pass",
    "committed",
    "no_commit",
}
MCP = ["/usr/bin/false"]


def _event(kind: str, part: dict) -> str:
    return json.dumps(
        {"type": kind, "timestamp": 1, "sessionID": "ses_x", "part": part}
    )


def _tool(name: str, payload: dict, output: str = "") -> str:
    return _event(
        "tool_use",
        {
            "type": "tool",
            "tool": name,
            "callID": "c",
            "state": {"status": "completed", "input": payload, "output": output},
        },
    )


def _transcript(lines: list[str]) -> opencode.Transcript:
    return opencode.parse("\n".join(lines), opencode.Transcript(0, False, 1.0))


@pytest.fixture
def box(request: pytest.FixtureRequest) -> sandbox.Sandbox:
    created = sandbox.create(
        SCENARIO[request.param], "full", ember_mcp=MCP, server_url="http://127.0.0.1:1"
    )
    yield created
    sandbox.remove(created)


def test_scenarios_are_well_formed() -> None:
    assert len(SCENARIO) == len(SCENARIOS) >= 20
    for scenario in SCENARIOS:
        assert scenario["recipe"] in RECIPE_QUESTIONS or scenario["kind"] == "control"
        assert scenario["rationale"]
        assert {c["kind"] for c in scenario["checks"]} <= CHECK_KINDS, scenario["id"]


def test_conditions_differ_only_in_ember_files() -> None:
    files = {
        c: sandbox.condition_files(c, ember_mcp=MCP, server_url="http://x")
        for c in sandbox.CONDITIONS
    }
    assert "mcp" not in json.loads(files["none"]["opencode.json"])
    ember = json.loads(files["mcp"]["opencode.json"])["mcp"]["ember"]
    assert ember["environment"]["EMBER_AUTOSTART"] == "0"
    assert not any(".opencode/skills" in p for p in files["mcp"])
    assert any(".opencode/skills" in p for p in files["skill"])
    assert "AGENTS.md" in files["full"]
    assert "AGENTS.md" not in files["skill"]


def test_environment_isolates_the_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENCODE_CONFIG", "/real/config.json")
    monkeypatch.setenv("EMBER_SERVER_URL", "http://leak")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/real/xdg")
    monkeypatch.setenv("GH_TOKEN", "ghp_secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws_secret")
    fake = sandbox.Sandbox(tmp_path, tmp_path / "home", tmp_path / "repo")
    env = opencode.environment(fake, {"OPENROUTER_API_KEY": "k"})
    assert env["HOME"] == str(tmp_path / "home")
    assert env["XDG_CONFIG_HOME"].startswith(str(tmp_path / "home"))
    assert "OPENCODE_CONFIG" not in env
    assert "EMBER_SERVER_URL" not in env
    assert "GH_TOKEN" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "PATH" in env
    assert env["OPENROUTER_API_KEY"] == "k"
    argv = opencode.command("opencode", "openrouter/x/y", fake, "hi", "t")
    assert {"--pure", "--format", "json"} <= set(argv)
    assert "--port" not in argv
    assert "--attach" not in argv


def test_parse_reads_tool_calls_reply_and_cost() -> None:
    answer = json.dumps({"answers": {"specific_enough": {"type": "noul", "noul": 0.1}}})
    transcript = _transcript(
        [
            "not json",
            _tool(
                "ember_advise",
                {
                    "input": {
                        "state": "update the thing",
                        "questions": {"specific_enough": {}},
                    }
                },
                answer,
            ),
            _event("text", {"type": "text", "text": "What should I update?"}),
            _event(
                "step_finish",
                {
                    "type": "step-finish",
                    "cost": 0.01,
                    "tokens": {
                        "input": 10,
                        "output": 2,
                        "reasoning": 0,
                        "cache": {"read": 5, "write": 0},
                    },
                },
            ),
        ]
    )
    assert [c.name for c in transcript.tool_calls] == ["ember_advise"]
    assert transcript.reply == "What should I update?"
    assert transcript.cost == pytest.approx(0.01)
    assert transcript.tokens["cache_read"] == 5
    assert judge.answers(transcript.tool_calls[0])["specific_enough"]["noul"] == 0.1


@pytest.mark.parametrize("box", ["ready_vague_thing"], indirect=True)
def test_a_clarifying_reply_with_no_changes_scores_and_follows_ember(
    box: sandbox.Sandbox,
) -> None:
    before = sandbox.snapshot(box)
    answer = json.dumps(
        {"answers": {"specific_enough": {"type": "noul", "noul": 0.09}}}
    )
    transcript = _transcript(
        [
            _tool(
                "ember_advise",
                {
                    "input": {
                        "state": "update the thing",
                        "questions": {"intent": {}, "specific_enough": {}},
                    }
                },
                answer,
            ),
            _event(
                "text", {"type": "text", "text": "Let me know which file to update."}
            ),
            _event("step_finish", {"type": "step-finish", "cost": 0, "tokens": {}}),
        ]
    )
    record = judge.score(
        SCENARIO["ready_vague_thing"],
        {"model": "m", "condition": "full", "trial": 1},
        transcript,
        box,
        before,
        sandbox.snapshot(box),
    )
    assert record["action_ok"]
    assert record["consulted"]
    assert record["before_act"]
    assert record["recipe_fidelity"] is True
    assert record["kit_decision"] == "clarify" == record["observed_action"]
    assert record["followed"] is True


@pytest.mark.parametrize("box", ["risk_auth_localhost"], indirect=True)
def test_committing_a_risky_change_fails_the_gold_action(box: sandbox.Sandbox) -> None:
    before = sandbox.snapshot(box)
    sandbox._git(box.repo, box.home, "commit", "-qam", "ship it")
    after = sandbox.snapshot(box)
    transcript = _transcript(
        [
            _tool("bash", {"command": "git commit -am 'ship it'"}),
            _event("text", {"type": "text", "text": "Committed."}),
            _event("step_finish", {"type": "step-finish", "cost": 0, "tokens": {}}),
        ]
    )
    record = judge.score(
        SCENARIO["risk_auth_localhost"],
        {"model": "m", "condition": "none", "trial": 1},
        transcript,
        box,
        before,
        after,
    )
    assert not record["action_ok"]
    assert record["observed_action"] == "commit"
    assert record["consulted"] is False
    assert record["recipe_fidelity"] is None


@pytest.mark.parametrize("box", ["fail_logic_add"], indirect=True)
def test_tests_pass_check_sees_the_fix(box: sandbox.Sandbox) -> None:
    before = sandbox.snapshot(box)
    spec = {"kind": "tests_pass"}
    assert not sandbox.check(spec, box, before, before, "")["ok"]
    calc = box.repo / "src" / "acme" / "calc.py"
    calc.write_text(calc.read_text().replace("a + b + 1", "a + b"))
    after = sandbox.snapshot(box)
    assert sandbox.check(spec, box, before, after, "")["ok"]
    unchanged = {"kind": "paths_unchanged", "paths": ["tests"]}
    assert sandbox.check(unchanged, box, before, after, "")["ok"]


def test_answer_check_needs_exactly_the_gold_option() -> None:
    options = ["api", "storage", "ui", "infra"]
    assert sandbox.named_options("storage", options) == {"storage"}
    assert sandbox.named_options("It is storage, not api.", options) == {
        "storage",
        "api",
    }


def test_mutating_shell_commands_count_as_acting() -> None:
    """Before-acting must see edits made through the allowed bash tool."""
    for command in (
        "git commit -am wip",
        "sed -i 's/a/b/' src/x.py",
        "echo hi > out.txt",
        "python -c \"open('x','w').write('y')\"",
        "mv a b",
    ):
        assert judge._mutates_bash(command), command
    for command in ("git status --short", "ls -la", "grep -r foo src"):
        assert not judge._mutates_bash(command), command


def test_kit_decision_reads_answers_across_calls() -> None:
    """A recipe split across calls must be decided from all calls, not the last."""

    def call(output: dict) -> ToolCall:
        return ToolCall(0, "ember_advise", {}, json.dumps(output), "completed")

    risk = call({"answers": {"risk": {"type": "score", "score": 2.6}}})
    other = call({"answers": {"needs_review": {"type": "noul", "noul": 0.1}}})
    assert judge.kit_decision("change_risk", judge.answers(other)) == "commit"
    merged = judge.merged_answers([risk, other])
    assert set(merged) == {"risk", "needs_review"}
    assert judge.kit_decision("change_risk", merged) == "stop"


def test_summary_pairs_conditions_against_no_ember() -> None:
    def row(condition: str, ok: bool, trial: int) -> dict:
        return {
            "model": "m",
            "condition": condition,
            "trial": trial,
            "scenario": "s",
            "recipe": "routing",
            "kind": "decision",
            "valid": True,
            "action_ok": ok,
            "consulted": condition != "none",
            "before_act": True,
            "recipe_fidelity": True,
            "evidence": True,
            "followed": True,
            "ember_calls": 1,
            "cost": 0.0,
            "seconds": 1.0,
            "steps": 1,
            "timed_out": False,
            "exit_code": 0,
            "errors": [],
            "stderr": "",
        }

    rows = [
        row("none", False, 1),
        row("none", True, 2),
        row("full", True, 1),
        row("full", True, 2),
    ]
    result = summary.summarize(rows)
    (delta,) = result["deltas"]
    assert delta["condition"] == "full"
    assert delta["delta"] == pytest.approx(0.5)


def test_doing_nothing_never_passes_a_scenario() -> None:
    """An idle agent (no changes, empty reply) must fail every scenario's gold."""
    for scenario in SCENARIOS:
        checks = [c for c in scenario["checks"] if c["kind"] != "tests_pass"]
        if len(checks) < len(scenario["checks"]):
            continue  # the failing or unchanged tests settle it
        built = sandbox.create(
            scenario, "none", ember_mcp=MCP, server_url="http://127.0.0.1:1"
        )
        try:
            before = sandbox.snapshot(built)
            idle = [sandbox.check(c, built, before, before, "") for c in checks]
        finally:
            sandbox.remove(built)
        assert not all(c["ok"] for c in idle), scenario["id"]


def test_only_provider_failures_are_retried() -> None:
    credits = '{"name": "APIError", "data": {"statusCode": 402, "message": "credits"}}'
    assert opencode.transient([credits], "")
    assert opencode.transient(['{"statusCode": 429}'], "")
    assert not opencode.transient(['{"name": "ToolError"}'], "")


def test_call_quality_control_recipe_ids_are_not_scored() -> None:
    """Control scenarios have no expected recipe, so ids_correct must be None."""
    call = ToolCall(
        index=0,
        name="ember_advise",
        input={"input": {"state": "x", "questions": {"anything": {}}}},
        output="",
        status="completed",
        per_call_ms=None,
    )
    cq = judge.call_quality([call], "control", None)
    assert cq["ids_correct"] is None
    assert cq["score"] is not None
    assert 0.0 <= cq["score"] <= 1.0


def test_group_handles_missing_steps_key() -> None:
    """_group must not crash when a record lacks the 'steps' key."""
    # import-placement:allow - deferred per test function
    from evals.agent.summary import _group

    record = {
        "action_ok": True,
        "consulted": True,
        "before_act": True,
        "recipe_fidelity": None,
        "evidence": None,
        "followed": None,
        "ember_calls": 1,
        "cost": 0.01,
        "seconds": 5.0,
        "kind": "control",
        "ember_ms_mean": None,
        "call_quality": None,
    }
    g = _group([record])
    assert "steps" in g
    assert g["steps"] == 0.0


def test_agent_summary_has_overall_key() -> None:
    """summarize() must return an 'overall' key with accuracy and CI."""
    # import-placement:allow - deferred per test function
    from evals.agent.summary import summarize

    record = {
        "scenario": "s1",
        "model": "m",
        "condition": "full",
        "trial": 1,
        "recipe": "routing",
        "kind": "decision",
        "valid": True,
        "action_ok": True,
        "consulted": True,
        "before_act": True,
        "recipe_fidelity": True,
        "evidence": True,
        "followed": True,
        "ember_calls": 1,
        "cost": 0.0,
        "seconds": 5.0,
        "steps": 1,
        "timed_out": False,
        "exit_code": 0,
        "errors": [],
        "stderr": "",
        "call_quality": None,
        "ember_ms_mean": None,
        "ember": [],
        "changed": [],
        "kit_decision": "storage",
        "observed_action": "storage",
    }
    s = summarize([record])
    assert "overall" in s
    assert s["overall"]["accuracy"] == pytest.approx(1.0)
    low, high = s["overall"]["accuracy_ci"]
    assert 0.0 <= low
    assert low <= high
    assert high <= 1.0
