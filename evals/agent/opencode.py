"""Run opencode headless inside a sandbox and parse its JSON event stream.

Isolation follows the opencode source (``sst/opencode``, ``run.ts``,
``global.ts``, ``plugin/index.ts``):

- ``--pure`` loads no external plugins; HOME and the XDG directories point into
  the sandbox, so no global config, skills, sessions, or auth database apply.
- ``opencode run`` without ``--port`` or ``--attach`` serves in-process and binds
  no TCP port, so it cannot collide with the user's opencode instances.
- The provider key travels only in the child's environment; nothing is written.
- Permissions come from the sandbox ``opencode.json``; anything that still asks
  is auto-rejected by ``run``, so a session never hangs on a prompt.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .sandbox import Sandbox, git_env

DROP_PREFIXES = ("OPENCODE", "EMBER_", "XDG_")
PROVIDER_KEYS = {"openrouter": "OPENROUTER_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
AUTH_FILE = Path.home() / ".local" / "share" / "opencode" / "auth.json"


# Provider failures worth retrying: credit reservations, rate limits, overloads.
TRANSIENT = (
    '"statuscode": 402',
    '"statuscode": 429',
    '"statuscode": 500',
    '"statuscode": 502',
    '"statuscode": 503',
    '"statuscode": 529',
    "overloaded",
    "rate limit",
)


def transient(errors: list[str], stderr: str) -> bool:
    """Return whether a failed session's errors look like a passing provider issue."""
    blob = (" ".join(errors) + stderr).lower()
    return any(marker in blob for marker in TRANSIENT)


@dataclass(frozen=True)
class ToolCall:
    """One completed (or failed) tool call, in the order it finished."""

    index: int
    name: str
    input: dict[str, Any]
    output: str
    status: str
    per_call_ms: float | None = None


@dataclass
class Transcript:
    """What one ``opencode run`` session did."""

    exit_code: int
    timed_out: bool
    seconds: float
    tool_calls: list[ToolCall] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    cost: float = 0.0
    tokens: dict[str, int] = field(default_factory=dict)
    steps: int = 0
    errors: list[str] = field(default_factory=list)
    stderr: str = ""

    @property
    def reply(self) -> str:
        """Return the agent's final text."""
        return self.texts[-1] if self.texts else ""


def binary() -> str:
    """Return the opencode executable, or raise ``RuntimeError``."""
    found = shutil.which("opencode") or str(Path.home() / ".bun" / "bin" / "opencode")
    if not Path(found).exists():
        raise RuntimeError("opencode is not installed or not on PATH")
    return found


def provider_env(model: str) -> dict[str, str]:
    """Return the API-key variable for ``model``'s provider, from env or auth.json."""
    provider = model.split("/", 1)[0]
    variable = PROVIDER_KEYS.get(provider)
    if variable is None:
        raise RuntimeError(f"no key mapping for provider {provider!r}")
    if os.environ.get(variable):
        return {variable: os.environ[variable]}
    try:
        stored = json.loads(AUTH_FILE.read_text(encoding="utf-8"))[provider]["key"]
    except (OSError, KeyError, ValueError) as exc:
        raise RuntimeError(
            f"no {provider} key: set {variable} or run `opencode auth login`"
        ) from exc
    return {variable: str(stored)}


def environment(sandbox: Sandbox, keys: dict[str, str]) -> dict[str, str]:
    """Return the child environment: the user's minus opencode/ember/XDG state."""
    home = sandbox.home
    env = {k: v for k, v in os.environ.items() if not k.startswith(DROP_PREFIXES)}
    env.update(git_env(home))
    env.update(
        XDG_CONFIG_HOME=str(home / ".config"),
        XDG_DATA_HOME=str(home / ".local" / "share"),
        XDG_CACHE_HOME=str(home / ".cache"),
        XDG_STATE_HOME=str(home / ".local" / "state"),
        OPENCODE_DISABLE_AUTOUPDATE="1",
        OPENCODE_DISABLE_TERMINAL_TITLE="1",
    )
    env.update(keys)
    return env


def command(
    executable: str, model: str, sandbox: Sandbox, prompt: str, title: str
) -> list[str]:
    """Return the ``opencode run`` argv for one session."""
    return [
        executable,
        "run",
        "--pure",
        "--format",
        "json",
        "--dir",
        str(sandbox.repo),
        "-m",
        model,
        "--title",
        title,
        prompt,
    ]


def parse(stdout: str, transcript: Transcript) -> Transcript:
    """Fill ``transcript`` from ``--format json`` event lines."""
    tokens = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind, part = event.get("type"), event.get("part") or {}
        if kind == "tool_use":
            state = part.get("state") or {}
            timing = state.get("time") or {}
            start_ms = float(timing.get("start") or 0)
            end_ms = float(timing.get("end") or 0)
            per_call = (end_ms - start_ms) if start_ms and end_ms else None
            transcript.tool_calls.append(
                ToolCall(
                    index=len(transcript.tool_calls),
                    name=str(part.get("tool", "")),
                    input=state.get("input") or {},
                    output=str(state.get("output") or state.get("error") or ""),
                    status=str(state.get("status", "")),
                    per_call_ms=per_call,
                )
            )
        elif kind == "text" and part.get("text"):
            transcript.texts.append(str(part["text"]))
        elif kind == "step_finish":
            transcript.steps += 1
            transcript.cost += float(part.get("cost") or 0.0)
            used = part.get("tokens") or {}
            tokens["input"] += int(used.get("input") or 0)
            tokens["output"] += int(used.get("output") or 0)
            tokens["reasoning"] += int(used.get("reasoning") or 0)
            tokens["cache_read"] += int((used.get("cache") or {}).get("read") or 0)
        elif kind == "error":
            transcript.errors.append(json.dumps(event.get("error"))[:600])
    transcript.tokens = tokens
    return transcript


def _stop(process: subprocess.Popen[str]) -> None:
    """Stop the session's own process group (the child leads it)."""
    for sig, wait in ((signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            continue


def run(argv: list[str], env: dict[str, str], cwd: Path, timeout: float) -> Transcript:
    """Run one session to completion or timeout and parse its events."""
    started = time.monotonic()
    process = subprocess.Popen(  # noqa: S603 - argv built from fixed parts
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _stop(process)
        stdout, stderr = process.communicate()
    transcript = Transcript(
        exit_code=process.returncode,
        timed_out=timed_out,
        seconds=time.monotonic() - started,
        stderr=(stderr or "")[-2000:],
    )
    return parse(stdout or "", transcript)
