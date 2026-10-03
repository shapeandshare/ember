"""Per-session sandboxes for the agent eval: a git repo and a private home.

Every session gets a fresh temporary directory holding ``home/`` (the HOME and
XDG directories the agent sees, so none of the user's opencode config, plugins,
sessions, or git config apply) and ``repo/`` (a git repository built from the
scenario). The condition's opencode files are part of the first commit, so the
agent's own changes are the only difference from the baseline snapshot.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ember import agent_kit

from .template import TEMPLATE, TEST_COMMAND

CONDITIONS = ("none", "mcp", "skill", "full")
CONDITION_LABELS = {
    "none": "no ember",
    "mcp": "ember MCP (instructions only)",
    "skill": "MCP + ember-advise skill",
    "full": "MCP + skill + AGENTS.md policy",
}
IGNORED = (".git", ".opencode", "__pycache__")
GIT_IDENTITY = {
    "user.name": "ember eval",
    "user.email": "eval@example.invalid",
    "commit.gpgsign": "false",
    "init.defaultBranch": "main",
}
# A reply asks for clarification when it poses a question or requests details.
ASKS = re.compile(
    r"\?|\blet me know\b|\btell me\b|\bcould you\b|\bplease (?:specify|clarify|"
    r"confirm|share|tell|provide)\b|\bcan you (?:tell|clarify|share|specify)\b",
    re.IGNORECASE,
)
MODELS_CACHE = Path.home() / ".cache" / "opencode" / "models.json"


@dataclass(frozen=True)
class Sandbox:
    """Paths of one session's sandbox."""

    root: Path
    home: Path
    repo: Path


@dataclass(frozen=True)
class Snapshot:
    """File hashes and git position of the repo at one moment."""

    files: dict[str, str]
    head: str
    commits: int


def git_env(home: Path) -> dict[str, str]:
    """Return environment overrides that keep git away from the user's config."""
    return {"HOME": str(home), "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}


def _git(repo: Path, home: Path, *args: str) -> str:
    env = {**os.environ, **git_env(home)}
    done = subprocess.run(  # noqa: S603 - fixed git argv inside the sandbox
        ["git", *args],  # noqa: S607 - git resolved from PATH
        cwd=repo,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout.strip()


def _write(repo: Path, files: dict[str, str | bytes]) -> None:
    for relative, content in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")


def condition_files(
    condition: str, *, ember_mcp: list[str], server_url: str
) -> dict[str, str]:
    """Return the opencode files that define ``condition`` inside the repo."""
    config: dict[str, Any] = {
        "$schema": "https://opencode.ai/config.json",
        "autoupdate": False,
        "share": "disabled",
        "permission": {"edit": "allow", "bash": "allow", "webfetch": "deny"},
    }
    if condition != "none":
        config["mcp"] = {
            "ember": {
                "type": "local",
                "command": ember_mcp,
                "environment": {"EMBER_SERVER_URL": server_url, "EMBER_AUTOSTART": "0"},
                "enabled": True,
            }
        }
    files = {"opencode.json": json.dumps(config, indent=2) + "\n"}
    if condition in ("skill", "full"):
        files[f".opencode/skills/{agent_kit.SKILL_NAME}/SKILL.md"] = agent_kit.skill()
    if condition == "full":
        files["AGENTS.md"] = agent_kit.snippet()
    return files


def create(
    scenario: dict[str, Any], condition: str, *, ember_mcp: list[str], server_url: str
) -> Sandbox:
    """Build the sandbox for one session and return its paths."""
    root = Path(tempfile.mkdtemp(prefix="ember-agent-eval-"))
    home, repo = root / "home", root / "repo"
    for xdg in (".config", ".local/share", ".cache", ".local/state"):
        (home / xdg).mkdir(parents=True)
    if MODELS_CACHE.exists():
        (home / ".cache" / "opencode").mkdir(parents=True)
        shutil.copyfile(MODELS_CACHE, home / ".cache" / "opencode" / "models.json")
    repo.mkdir()
    _git(repo, home, "init", "-q", "-b", "main")
    for key, value in GIT_IDENTITY.items():
        _git(repo, home, "config", key, value)
    _write(
        repo,
        {
            **TEMPLATE,
            **scenario.get("files", {}),
            **condition_files(condition, ember_mcp=ember_mcp, server_url=server_url),
        },
    )
    _git(repo, home, "add", "-A")
    _git(repo, home, "commit", "-q", "-m", "Initial commit")
    for message, changes in scenario.get("history", []):
        _write(repo, changes)
        _git(repo, home, "add", "-A")
        _git(repo, home, "commit", "-q", "-m", message)
    _write(repo, scenario.get("changes", {}))
    return Sandbox(root, home, repo)


def snapshot(sandbox: Sandbox) -> Snapshot:
    """Hash every file outside ``.git``, ``.opencode``, and caches."""
    files = {}
    for path in sorted(sandbox.repo.rglob("*")):
        relative = path.relative_to(sandbox.repo).as_posix()
        if path.is_file() and not set(relative.split("/")) & set(IGNORED):
            files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    head = _git(sandbox.repo, sandbox.home, "rev-parse", "HEAD")
    commits = int(_git(sandbox.repo, sandbox.home, "rev-list", "--count", "HEAD"))
    return Snapshot(files, head, commits)


def changed(before: Snapshot, after: Snapshot) -> list[str]:
    """Return the paths added, removed, or modified between two snapshots."""
    paths = set(before.files) | set(after.files)
    return sorted(p for p in paths if before.files.get(p) != after.files.get(p))


def _dirty(sandbox: Sandbox) -> list[str]:
    status = _git(sandbox.repo, sandbox.home, "status", "--porcelain")
    lines = [line[3:] for line in status.splitlines() if line.strip()]
    return [p for p in lines if not set(p.split("/")) & set(IGNORED)]


def named_options(reply: str, options: list[str]) -> set[str]:
    """Return the options named in a reply's last line, else anywhere in it."""
    lines = [line for line in reply.strip().splitlines() if line.strip()]
    for text in (lines[-1] if lines else "", reply):
        found = {o for o in options if re.search(rf"\b{re.escape(o)}\b", text, re.I)}
        if found:
            return found
    return set()


def tests_pass(sandbox: Sandbox) -> bool:
    """Return whether the sandbox's unit tests pass."""
    env = {**os.environ, **git_env(sandbox.home)}
    try:
        done = subprocess.run(  # noqa: S603 - fixed test command
            TEST_COMMAND,
            cwd=sandbox.repo,
            env=env,
            capture_output=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False
    return done.returncode == 0


def check(
    spec: dict[str, Any],
    sandbox: Sandbox,
    before: Snapshot,
    after: Snapshot,
    reply: str,
) -> dict[str, Any]:
    """Evaluate one gold check and return ``{kind, ok, detail}``."""
    kind = spec["kind"]
    diff = changed(before, after)
    ok: bool
    detail = ""
    if kind == "clean":
        ok = not diff and after.head == before.head
        detail = ", ".join(diff[:6])
    elif kind == "asks":
        ok = bool(ASKS.search(reply))
    elif kind == "mentions_any":
        ok = any(word.lower() in reply.lower() for word in spec["words"])
    elif kind == "answer":
        named = named_options(reply, spec["options"])
        ok = named == {spec["gold"]}
        detail = ", ".join(sorted(named))
    elif kind == "file_contains":
        path = sandbox.repo / spec["path"]
        ok = path.is_file() and spec["text"] in path.read_text(encoding="utf-8")
    elif kind == "paths_unchanged":
        touched = [
            p
            for p in diff
            if any(p == q or p.startswith(f"{q}/") for q in spec["paths"])
        ]
        ok, detail = not touched, ", ".join(touched[:6])
    elif kind == "tests_pass":
        ok = tests_pass(sandbox)
    elif kind == "committed":
        dirty = _dirty(sandbox)
        ok = after.commits > before.commits and not dirty
        detail = ", ".join(dirty[:6])
    elif kind == "no_commit":
        ok = after.commits == before.commits
    else:
        raise ValueError(f"unknown check {kind!r}")
    return {"kind": kind, "ok": ok, "detail": detail}


def remove(sandbox: Sandbox) -> None:
    """Delete a sandbox this runner created."""
    shutil.rmtree(sandbox.root, ignore_errors=True)
