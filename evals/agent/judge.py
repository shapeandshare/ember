"""Score one agent session: consulting ember, asking well, and acting right.

The gold action comes only from observable effects (``scenarios`` checks), so
the same score applies with and without ember. Consultation metrics read the
``ember_advise`` calls from the transcript:

- consulted: at least one call;
- before acting: the first call precedes the first edit or commit;
- recipe fidelity: the calls asked every question of the kit recipe;
- evidence: the ``state`` carried the scenario's key evidence;
- followed: the agent's action matches what the kit's rules say ember's answer
  implies (``specific_enough <= 0.20`` means clarify, and so on).
- call_quality: a structured breakdown of how well the call was formed,
  covering verdict injection, batching, and recipe question ids.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .sandbox import Sandbox, changed, check, named_options
from .snapshot import Snapshot
from .tool_call import ToolCall
from .transcript import Transcript
from .scenarios import EFFORTS, OWNERS, RECIPE_QUESTIONS

EMBER_TOOL = "ember_advise"
EDIT_TOOLS = frozenset({"edit", "write", "patch", "multiedit", "apply_patch"})
Record = dict[str, Any]

# Phrases that indicate an agent has pre-formed a verdict before consulting ember.
# Matching is case-insensitive against the JSON-serialised state.
VERDICT_PHRASES = (
    "this is",
    "it is a",
    "i believe",
    "clearly",
    "the issue is",
    "root cause",
    "analysis:",
    "definitely",
)

# Shell shapes that change the working tree. `git commit` alone misses `sed -i`,
# redirection, `mv`, and `python -c`, so before-acting would credit a
# consultation that happened after the agent had already edited files.
_MUTATES = re.compile(
    r"""(?x)
    \bgit\s+(?:
        commit|add|apply|checkout|restore|rm|mv|revert|merge
        |cherry-pick|stash|clean)\b
    | \bsed\s+-i
    | \bperl\s+-i
    | \b(?:tee|truncate|install|mv|cp|rm|touch|mkdir|dd|patch|ln)\b
    | \bpython[0-9.]*\s+-c\b
    | \bnode\s+-e\b
    | >>?(?!=)
    | <<
    """
)


def payload(call: ToolCall) -> dict[str, Any]:
    """Return the advise input, unwrapping the MCP ``input`` envelope."""
    data = call.input.get("input", call.input)
    return data if isinstance(data, dict) else {}


def answers(call: ToolCall) -> dict[str, Any]:
    """Return ember's answers from a call's output, or ``{}``."""
    try:
        body = json.loads(call.output)
    except ValueError:
        start = call.output.find("{")
        try:
            body = json.loads(call.output[start:]) if start >= 0 else {}
        except ValueError:
            return {}
    found = body.get("answers") if isinstance(body, dict) else None
    return found if isinstance(found, dict) else {}


def _acts(call: ToolCall) -> bool:
    if call.name in EDIT_TOOLS:
        return True
    return call.name == "bash" and _mutates_bash(str(call.input.get("command", "")))


def _value(answer: Any, key: str) -> Any:
    return answer.get(key) if isinstance(answer, dict) else None


def _mutates_bash(command: str) -> bool:
    """Return whether a shell command looks like it changes the working tree.

    The ``bash`` tool is allowed, so an agent can edit files with ``sed -i``,
    redirection, or a ``python -c`` one-liner before it consults ember. Matching
    only ``git commit`` would credit that as consult-before-act.
    """
    return bool(_MUTATES.search(command))


def merged_answers(calls: list[ToolCall]) -> dict[str, Any]:
    """Merge every call's answers in order; a later answer for an id wins.

    A recipe can be split across calls or followed by an unrelated call, so the
    kit decision must read all of them, not just the last.
    """
    merged: dict[str, Any] = {}
    for call in calls:
        merged.update(answers(call))
    return merged


# ###########################################################################
# Call quality: did the agent use the tool correctly?
# ###########################################################################


def _verdict_in_state(calls: list[ToolCall]) -> bool:
    """Return True when any call's state contains a pre-formed conclusion."""
    for call in calls:
        state = json.dumps(payload(call).get("state", "")).lower()
        if any(phrase in state for phrase in VERDICT_PHRASES):
            return True
    return False


def _invented_ids(calls: list[ToolCall], recipe: str) -> list[str]:
    """Return question ids the agent used that are not in the kit's recipe."""
    kit = RECIPE_QUESTIONS.get(recipe, frozenset())
    invented: list[str] = []
    for call in calls:
        for qid in payload(call).get("questions") or {}:
            if qid not in kit and qid not in invented:
                invented.append(qid)
    return invented


def call_quality(
    calls: list[ToolCall], recipe: str, needed: frozenset[str] | None
) -> dict[str, Any]:
    """Return a structured breakdown of call quality for one session.

    Fields::

        batched       bool   - all required questions in one call (not split across
                               multiple sequential calls)
        verdict_free  bool   - state carried raw evidence, not a pre-formed conclusion
        ids_correct   bool   - every question used a kit recipe id (none invented)
        score         float  - mean of the three binary checks, or None
        invented_ids  list   - the non-kit ids that were used
        n_calls       int    - total ember calls in the session
    """
    if not calls:
        return {
            "batched": None,
            "verdict_free": None,
            "ids_correct": None,
            "score": None,
            "invented_ids": [],
            "n_calls": 0,
        }

    batched = len(calls) == 1 or (
        needed is not None
        and all(needed <= set(payload(c).get("questions") or {}) for c in calls[:1])
    )
    verdict_free = not _verdict_in_state(calls)
    invented = _invented_ids(calls, recipe) if needed is not None else []
    ids_correct = len(invented) == 0 if needed is not None else None

    checks = [v for v in [batched, verdict_free, ids_correct] if v is not None]
    score = sum(checks) / len(checks) if checks else None
    return {
        "batched": batched,
        "verdict_free": verdict_free,
        "ids_correct": ids_correct,
        "score": round(score, 4),
        "invented_ids": invented,
        "n_calls": len(calls),
    }


# ###########################################################################
# Kit decision logic and action scoring
# ###########################################################################


def kit_decision(recipe: str, found: dict[str, Any]) -> str | None:
    """Return the action the kit's rules derive from ember's answers."""
    if recipe == "intent_readiness":
        p_true = _value(found.get("specific_enough"), "noul")
        return None if p_true is None else "clarify" if p_true <= 0.20 else "proceed"
    if recipe == "change_risk":
        review = _value(found.get("needs_review"), "noul")
        risk = _value(found.get("risk"), "score")
        if review is None and risk is None:
            return None
        return "stop" if (review or 0) >= 0.80 or (risk or 0) >= 2.0 else "commit"
    if recipe == "failure_triage":
        kind = _value(found.get("failure_kind"), "choice")
        return {
            "logic_bug": "fix_source",
            "test_bug": "fix_test",
            "environment": "leave_code",
            "flaky": "leave_code",
        }.get(str(kind))
    if recipe == "routing":
        owner = _value(found.get("owner"), "choice")
        return str(owner) if owner in OWNERS else None
    if recipe == "effort_approach":
        effort = _value(found.get("effort"), "score")
        return None if effort is None else EFFORTS[min(3, int(float(effort) + 0.5))]
    return None


def observed(recipe: str, diff: list[str], committed: bool, reply: str) -> str | None:
    """Return the action the agent took, in the kit's vocabulary."""
    if recipe == "intent_readiness":
        return "proceed" if diff else "clarify"
    if recipe == "change_risk":
        return "commit" if committed else "stop"
    if recipe == "failure_triage":
        if any(p.startswith("src/") for p in diff):
            return "fix_source"
        return "fix_test" if any(p.startswith("tests/") for p in diff) else "leave_code"
    options = {"routing": OWNERS, "effort_approach": EFFORTS}.get(recipe)
    if options:
        named = named_options(reply, options)
        return next(iter(named)) if len(named) == 1 else None
    return None


# ###########################################################################
# Main scoring entry point
# ###########################################################################


def score(
    scenario: dict[str, Any],
    run: dict[str, Any],
    transcript: Transcript,
    sandbox: Sandbox,
    before: Snapshot,
    after: Snapshot,
) -> Record:
    """Return the scored record for one session."""
    recipe = scenario["recipe"]
    reply = transcript.reply
    checks = [check(spec, sandbox, before, after, reply) for spec in scenario["checks"]]
    calls = [c for c in transcript.tool_calls if c.name == EMBER_TOOL]
    first_act = next((c.index for c in transcript.tool_calls if _acts(c)), None)
    asked = {qid for c in calls for qid in (payload(c).get("questions") or {})}
    states = json.dumps([payload(c).get("state") for c in calls]).lower()
    needed = RECIPE_QUESTIONS.get(recipe)
    found = merged_answers(calls) if calls else {}
    decision = kit_decision(recipe, found) if calls else None
    diff = changed(before, after)
    action = observed(recipe, diff, after.commits > before.commits, reply)
    valid = (
        transcript.exit_code == 0 and not transcript.timed_out and transcript.steps > 0
    )
    quality = call_quality(calls, recipe, needed)
    return {
        **run,
        "scenario": scenario["id"],
        "recipe": recipe,
        "kind": scenario["kind"],
        "gold_action": scenario["gold_action"],
        "valid": valid,
        "action_ok": valid and all(c["ok"] for c in checks),
        "checks": checks,
        "consulted": bool(calls),
        "ember_calls": len(calls),
        "before_act": bool(calls) and (first_act is None or calls[0].index < first_act),
        "recipe_fidelity": (needed <= asked) if calls and needed else None,
        "asked": sorted(asked),
        "evidence": (
            any(e.lower() in states for e in scenario["evidence_any"])
            if calls and scenario["evidence_any"]
            else None
        ),
        "call_quality": quality,
        "kit_decision": decision,
        "observed_action": action,
        "followed": (decision == action) if decision and action else None,
        "changed": diff,
        "reply": reply[:2000],
        "tools": [c.name for c in transcript.tool_calls],
        "ember": [
            {"input": payload(c), "answers": answers(c), "per_call_ms": c.per_call_ms}
            for c in calls
        ],
        "ember_ms_mean": (
            sum(c.per_call_ms for c in calls if c.per_call_ms)
            / max(1, sum(1 for c in calls if c.per_call_ms))
            if any(c.per_call_ms for c in calls)
            else None
        ),
        "cost": round(transcript.cost, 6),
        "tokens": transcript.tokens,
        "steps": transcript.steps,
        "seconds": round(transcript.seconds, 1),
        "exit_code": transcript.exit_code,
        "timed_out": transcript.timed_out,
        "errors": transcript.errors,
        "stderr": transcript.stderr[-600:] if not valid else "",
    }
