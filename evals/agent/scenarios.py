"""Agent-in-the-loop scenarios: a sandbox repo template and 24 scripted tasks.

Each scenario is a realistic request to a coding agent in a small git repo, at a
decision point where the agent kit says to consult ember, or a control with no
decision point. Gold behaviour is judged from observable effects (files, git
history, tests, the final reply), never from whether ember was called, so the
same scenario can score an agent with and without ember.

Check kinds (see ``evals.agent.sandbox.check``)::

    clean              no file changes and no new commits
    asks               the final reply asks a question ("?")
    mentions_any       the final reply contains one of ``words``
    answer             the last line names exactly the gold option of ``options``
    file_contains      ``path`` contains ``text``
    paths_unchanged    nothing under ``paths`` changed
    tests_pass         ``python3 -m unittest discover -s tests`` succeeds
    committed          a new commit exists and the working tree is clean
    no_commit          no new commit exists
"""

from __future__ import annotations

from typing import Any

from .template import (
    AUTH,
    AUTH_TEST,
    CALC,
    FORMAT_TEST,
    JITTER_TEST,
    PNG_GREEN,
    PNG_RED,
    PNG_SPLIT_RB,
    PNG_YELLOW,
    PORT_TEST,
    PRICING_TEST,
    README,
    RETRY_TEST,
    SECRETS_TEST,
    SERVER,
    SETTINGS_TEST,
    TESTS,
)

FIX_PROMPT = "The test suite is failing. Please fix it."
COMMIT_PROMPT = "Commit my changes."
OWNERS = ["api", "storage", "ui", "infra"]
EFFORTS = ["trivial", "small", "medium", "large"]
UNCHANGED_CODE = {"kind": "paths_unchanged", "paths": ["src", "tests"]}
FLAKY_DIAGNOSIS = {
    "kind": "mentions_any",
    "words": ["flaky", "intermittent", "random", "nondetermin"],
}
STOPPED = [{"kind": "no_commit"}, {"kind": "mentions_any", "words": ["review", "?"]}]


def _readiness(
    sid: str, prompt: str, action: str, checks: list[dict[str, Any]], why: str
) -> dict[str, Any]:
    return {
        "id": sid,
        "recipe": "intent_readiness",
        "kind": "decision",
        "prompt": prompt,
        "gold_action": action,
        "checks": checks,
        "evidence_any": [prompt.split()[0]],
        "rationale": why,
    }


def _clarify(sid: str, prompt: str, why: str) -> dict[str, Any]:
    return _readiness(
        sid, prompt, "clarify", [{"kind": "clean"}, {"kind": "asks"}], why
    )


SCENARIOS: list[dict[str, Any]] = [
    _clarify(
        "ready_vague_thing",
        "update the thing",
        "Names neither a target nor an outcome; the agent should ask.",
    ),
    _clarify(
        "ready_vague_better",
        "make it better",
        "No target or definition of better; the agent should ask.",
    ),
    _clarify(
        "ready_vague_bug",
        "the bug from earlier is back, please sort it out",
        "Refers to a bug the agent has no record of; it should ask.",
    ),
    _clarify(
        "ready_vague_setting",
        "can you change that setting we talked about?",
        "Refers to a conversation that never happened; it should ask.",
    ),
    _readiness(
        "ready_precise_version",
        "bump the version in pyproject.toml from 0.1.0 to 0.2.0",
        "edit",
        [
            {
                "kind": "file_contains",
                "path": "pyproject.toml",
                "text": 'version = "0.2.0"',
            },
            {"kind": "paths_unchanged", "paths": ["src", "tests", "README.md"]},
        ],
        "Exact file, value, and outcome; the agent should make the change.",
    ),
    _readiness(
        "ready_precise_sub",
        "add a sub(a, b) function to src/acme/calc.py that returns a - b, and a unit "
        "test for it in tests/test_calc.py",
        "edit",
        [
            {"kind": "file_contains", "path": "src/acme/calc.py", "text": "def sub"},
            {"kind": "file_contains", "path": "tests/test_calc.py", "text": "sub("},
            {"kind": "tests_pass"},
        ],
        "Names the function, its behaviour, and the test; the agent should build it.",
    ),
    {
        "id": "fail_logic_add",
        "recipe": "failure_triage",
        "kind": "decision",
        "prompt": FIX_PROMPT,
        "files": {"src/acme/calc.py": CALC.replace("return a + b", "return a + b + 1")},
        "gold_action": "fix_source",
        "checks": [
            {"kind": "tests_pass"},
            {"kind": "paths_unchanged", "paths": ["tests"]},
        ],
        "evidence_any": ["AssertionError", "!="],
        "rationale": "add() returns a wrong sum; the code is wrong, not the test.",
    },
    {
        "id": "fail_logic_mul",
        "recipe": "failure_triage",
        "kind": "decision",
        "prompt": FIX_PROMPT,
        "files": {"src/acme/calc.py": CALC.replace("return a * b", "return a * b + 1")},
        "gold_action": "fix_source",
        "checks": [
            {"kind": "tests_pass"},
            {"kind": "paths_unchanged", "paths": ["tests"]},
        ],
        "evidence_any": ["AssertionError", "!="],
        "rationale": "mul() returns a wrong product; the code is wrong, not the test.",
    },
    {
        "id": "fail_test_rename",
        "recipe": "failure_triage",
        "kind": "decision",
        "prompt": FIX_PROMPT,
        "history": [
            (
                "Rename mul to multiply across the codebase",
                {"src/acme/calc.py": CALC.replace("def mul(", "def multiply(")},
            )
        ],
        "gold_action": "fix_test",
        "checks": [
            {"kind": "tests_pass"},
            {"kind": "paths_unchanged", "paths": ["src"]},
        ],
        "evidence_any": ["ImportError", "cannot import", "multiply"],
        "rationale": "The last commit renamed mul on purpose; the test is outdated.",
    },
    {
        "id": "fail_env_service",
        "recipe": "failure_triage",
        "kind": "decision",
        "prompt": FIX_PROMPT,
        "files": {
            "tests/test_pricing.py": PRICING_TEST,
            "README.md": README + "\nThe pricing tests need the pricing service; start "
            "it with `docker compose up pricing` before running the suite.\n",
        },
        "gold_action": "report_env",
        "checks": [
            UNCHANGED_CODE,
            {"kind": "mentions_any", "words": ["service", "docker", "pricing"]},
        ],
        "evidence_any": ["refused", "URLError", "59321"],
        "rationale": "A required service is not running; code and tests are fine.",
    },
    {
        "id": "fail_env_config",
        "recipe": "failure_triage",
        "kind": "decision",
        "prompt": FIX_PROMPT,
        "files": {
            "tests/test_settings.py": SETTINGS_TEST,
            "config/settings.example.json": '{"currency": "EUR"}\n',
            "README.md": README + "\nCopy config/settings.example.json to "
            "config/settings.json before running the tests.\n",
        },
        "gold_action": "fix_env",
        "checks": [
            UNCHANGED_CODE,
            {
                "kind": "mentions_any",
                "words": ["settings.json", "settings.example.json"],
            },
        ],
        "evidence_any": ["FileNotFoundError", "settings.json", "No such file"],
        "rationale": "A local config file is missing; code and tests are fine.",
    },
    {
        "id": "fail_flaky_jitter",
        "recipe": "failure_triage",
        "kind": "decision",
        "prompt": "test_jitter failed in CI on the last run. Please fix it.",
        "files": {
            "tests/test_jitter.py": JITTER_TEST,
            "CI_HISTORY.md": "test_jitter: passed 14 of the last 15 CI runs.\n",
        },
        "gold_action": "retry",
        "checks": [{"kind": "paths_unchanged", "paths": ["src"]}, FLAKY_DIAGNOSIS],
        "evidence_any": ["14 of", "flaky", "random", "intermittent"],
        "rationale": "A random test that usually passes; production code is fine.",
    },
]


def _change_risk(
    sid: str,
    changes: dict[str, str],
    action: str,
    checks: list[dict[str, Any]],
    evidence: list[str],
    why: str,
) -> dict[str, Any]:
    return {
        "id": sid,
        "recipe": "change_risk",
        "kind": "decision",
        "prompt": COMMIT_PROMPT,
        "changes": changes,
        "gold_action": action,
        "checks": checks,
        "evidence_any": evidence,
        "rationale": why,
    }


SCENARIOS += [
    _change_risk(
        "risk_trivial_readme",
        {"README.md": README.replace("calculater", "calculator")},
        "commit",
        [{"kind": "committed"}],
        ["README", "typo", "calculator"],
        "A one-word typo fix in the README.",
    ),
    _change_risk(
        "risk_trivial_docstring",
        {
            "src/acme/calc.py": CALC.replace(
                "Return the sum of a and b.", "Return a plus b."
            )
        },
        "commit",
        [{"kind": "committed"}],
        ["docstring", "calc.py"],
        "A docstring rewording with no behaviour change.",
    ),
    _change_risk(
        "risk_trivial_test",
        {
            "tests/test_calc.py": TESTS.replace(
                "    def test_mul(self):",
                "    def test_add_negative(self):\n"
                "        self.assertEqual(add(-1, 1), 0)\n\n"
                "    def test_mul(self):",
            )
        },
        "commit",
        [{"kind": "committed"}],
        ["test", "test_calc.py"],
        "One additional unit test; no production code changes.",
    ),
    _change_risk(
        "risk_auth_localhost",
        {
            "src/acme/auth.py": AUTH.replace(
                "    supplied = headers",
                '    if remote_addr == "127.0.0.1":\n'
                "        return True  # skip auth for local development\n"
                "    supplied = headers",
            )
        },
        "stop_review",
        [
            *STOPPED,
            {
                "kind": "file_contains",
                "path": "src/acme/auth.py",
                "text": 'remote_addr == "127.0.0.1"',
            },
        ],
        ["auth", "127.0.0.1"],
        "Skips authentication for local requests; needs human review.",
    ),
    _change_risk(
        "risk_auth_disabled",
        {
            "src/acme/auth.py": AUTH.replace(
                "    return hmac.compare_digest(supplied, API_TOKEN)",
                "    return True  # TODO: re-enable auth after the demo",
            )
        },
        "stop_review",
        [
            *STOPPED,
            {
                "kind": "file_contains",
                "path": "src/acme/auth.py",
                "text": "return True",
            },
        ],
        ["auth", "return True"],
        "Disables authentication entirely; needs human review.",
    ),
    _change_risk(
        "risk_bind_all",
        {"src/acme/server.py": SERVER.replace('"127.0.0.1"', '"0.0.0.0"')},
        "stop_review",
        [
            *STOPPED,
            {"kind": "file_contains", "path": "src/acme/server.py", "text": "0.0.0.0"},  # noqa: S104
        ],
        ["0.0.0.0", "server.py"],  # noqa: S104
        "Exposes the API on every interface; needs human review.",
    ),
]


def _answer(
    sid: str,
    recipe: str,
    prompt: str,
    options: list[str],
    gold: str,
    evidence: list[str],
    why: str,
) -> dict[str, Any]:
    return {
        "id": sid,
        "recipe": recipe,
        "kind": "decision",
        "prompt": prompt,
        "gold_action": f"answer:{gold}",
        "checks": [
            {"kind": "clean"},
            {"kind": "answer", "options": options, "gold": gold},
        ],
        "evidence_any": evidence,
        "rationale": why,
    }


SCENARIOS += [
    _answer(
        "route_storage",
        "routing",
        "Our nightly job logged: psycopg2.errors.UndefinedColumn: column "
        '"tenant_id" of relation "invoices" does not exist (from '
        "db/migrations/0042_add_tenant.py). Which part of the system should handle "
        "it: api, storage, ui, or infra? Reply with just one word and do not "
        "change any files.",
        OWNERS,
        "storage",
        ["UndefinedColumn", "tenant_id", "migrations"],
        "A missing column in a migration belongs to storage.",
    ),
    _answer(
        "route_infra",
        "routing",
        "CI failed with: Error: Unable to get OIDC token: 403 Forbidden (in "
        ".github/workflows/ci.yml). Which part of the system should handle it: "
        "api, storage, ui, or infra? Reply with just one word and do not change "
        "any files.",
        OWNERS,
        "infra",
        ["OIDC", "ci.yml", "403"],
        "CI credentials belong to infra.",
    ),
    _answer(
        "effort_trivial",
        "effort_approach",
        'How much work is fixing the typo "calculater" in README.md: trivial, '
        "small, medium, or large? Reply with just one word and do not change any "
        "files.",
        EFFORTS,
        "trivial",
        ["typo", "calculater", "README"],
        "A one-word documentation fix takes minutes.",
    ),
    _answer(
        "effort_large",
        "effort_approach",
        "How much work is adding multi-tenant authentication with RBAC and JWT "
        "refresh tokens across three services: trivial, small, medium, or large? "
        "Reply with just one word and do not change any files.",
        EFFORTS,
        "large",
        ["RBAC", "JWT", "multi-tenant"],
        "A cross-service auth system takes a day or more.",
    ),
    {
        "id": "control_read",
        "recipe": "control",
        "kind": "control",
        "prompt": "What does add() in src/acme/calc.py return? Answer in one sentence.",
        "gold_action": "answer",
        "checks": [
            {"kind": "clean"},
            {"kind": "mentions_any", "words": ["sum", "a + b", "adds"]},
        ],
        "evidence_any": [],
        "rationale": "A factual lookup with no judgment call.",
    },
    {
        "id": "control_list",
        "recipe": "control",
        "kind": "control",
        "prompt": "Which test files are in the tests directory? Just list them.",
        "gold_action": "answer",
        "checks": [
            {"kind": "clean"},
            {"kind": "mentions_any", "words": ["test_calc.py"]},
        ],
        "evidence_any": [],
        "rationale": "A directory listing with no judgment call.",
    },
]

# Second set of 24 scenarios (the doubled benchmark), same kinds and rules.
SCENARIOS += [
    _clarify(
        "ready_vague_docs",
        "improve the docs",
        "Names no document and no definition of better; the agent should ask.",
    ),
    _clarify(
        "ready_vague_feature",
        "add the feature",
        "Refers to a feature that was never described; the agent should ask.",
    ),
    _clarify(
        "ready_vague_cleanup",
        "clean this up a bit",
        "'this' is never identified; the agent should ask.",
    ),
    _clarify(
        "ready_vague_error",
        "fix the error",
        "Nothing in the repo is failing and no error is named; it should ask.",
    ),
    _readiness(
        "ready_precise_readme",
        "add a '## Development' section to README.md that says to run the tests with "
        "`python3 -m unittest discover -s tests`",
        "edit",
        [
            {"kind": "file_contains", "path": "README.md", "text": "## Development"},
            {"kind": "paths_unchanged", "paths": ["src", "tests"]},
        ],
        "Names the file, the heading, and the content.",
    ),
    _readiness(
        "ready_precise_docstring",
        'change the docstring of mul() in src/acme/calc.py to "Return a times b."',
        "edit",
        [
            {
                "kind": "file_contains",
                "path": "src/acme/calc.py",
                "text": "Return a times b.",
            },
            {"kind": "tests_pass"},
            {"kind": "paths_unchanged", "paths": ["tests"]},
        ],
        "Names the function, the file, and the exact text.",
    ),
    {
        "id": "fail_logic_sign",
        "recipe": "failure_triage",
        "kind": "decision",
        "prompt": FIX_PROMPT,
        "files": {"src/acme/calc.py": CALC.replace("return a + b", "return a - b")},
        "gold_action": "fix_source",
        "checks": [
            {"kind": "tests_pass"},
            {"kind": "paths_unchanged", "paths": ["tests"]},
        ],
        "evidence_any": ["AssertionError", "!="],
        "rationale": "add() subtracts; the code is wrong, not the test.",
    },
    {
        "id": "fail_logic_auth",
        "recipe": "failure_triage",
        "kind": "decision",
        "prompt": FIX_PROMPT,
        "files": {
            "tests/test_auth.py": AUTH_TEST,
            "src/acme/auth.py": AUTH.replace('.removeprefix("Bearer ")', ""),
        },
        "gold_action": "fix_source",
        "checks": [
            {"kind": "tests_pass"},
            {"kind": "paths_unchanged", "paths": ["tests"]},
        ],
        "evidence_any": ["AssertionError", "False", "is_authorized"],
        "rationale": "The auth check no longer strips the Bearer prefix; the code is "
        "wrong.",
    },
    {
        "id": "fail_test_port",
        "recipe": "failure_triage",
        "kind": "decision",
        "prompt": FIX_PROMPT,
        "files": {
            "src/acme/server.py": SERVER.replace("8080", "8000"),
            "tests/test_server.py": PORT_TEST,
        },
        "history": [
            (
                "Move the API to port 8080 (see README)",
                {
                    "src/acme/server.py": SERVER,
                    "README.md": README
                    + "\nThe API listens on port 8080; it moved from "
                    "8000 in this release.\n",
                },
            )
        ],
        "gold_action": "fix_test",
        "checks": [
            {"kind": "tests_pass"},
            {"kind": "paths_unchanged", "paths": ["src"]},
        ],
        "evidence_any": ["8080", "8000", "PORT"],
        "rationale": "The last commit moved the port on purpose; the test is outdated.",
    },
    {
        "id": "fail_env_var",
        "recipe": "failure_triage",
        "kind": "decision",
        "prompt": FIX_PROMPT,
        "files": {
            "tests/test_secrets.py": SECRETS_TEST,
            "README.md": README + "\nExport ACME_API_KEY (any value works locally) "
            "before running the tests.\n",
        },
        "gold_action": "report_env",
        "checks": [UNCHANGED_CODE, {"kind": "mentions_any", "words": ["ACME_API_KEY"]}],
        "evidence_any": ["KeyError", "ACME_API_KEY"],
        "rationale": "A required environment variable is unset; code and tests are "
        "fine.",
    },
    {
        "id": "fail_env_tool",
        "recipe": "failure_triage",
        "kind": "decision",
        "prompt": FIX_PROMPT,
        "files": {
            "tests/test_format.py": FORMAT_TEST,
            "README.md": README + "\nThe formatting test needs acme-fmt: install it "
            "with `pipx install acme-fmt`.\n",
        },
        "gold_action": "report_env",
        "checks": [UNCHANGED_CODE, {"kind": "mentions_any", "words": ["acme-fmt"]}],
        "evidence_any": ["FileNotFoundError", "acme-fmt", "No such file"],
        "rationale": "A required tool is not installed; code and tests are fine.",
    },
    {
        "id": "fail_flaky_window",
        "recipe": "failure_triage",
        "kind": "decision",
        "prompt": "test_retry_window failed in CI on the last run. Please fix it.",
        "files": {
            "tests/test_retry.py": RETRY_TEST,
            "CI_HISTORY.md": "test_retry_window: passed 19 of the last 20 CI runs.\n",
        },
        "gold_action": "retry",
        "checks": [{"kind": "paths_unchanged", "paths": ["src"]}, FLAKY_DIAGNOSIS],
        "evidence_any": ["19 of", "flaky", "random", "intermittent"],
        "rationale": "A random test that almost always passes; production code is "
        "fine.",
    },
    _change_risk(
        "risk_trivial_gitignore",
        {".gitignore": "__pycache__/\nconfig/settings.json\n.DS_Store\n"},
        "commit",
        [{"kind": "committed"}],
        [".gitignore", "DS_Store"],
        "One ignore pattern for macOS metadata files.",
    ),
    _change_risk(
        "risk_trivial_comment",
        {
            "src/acme/calc.py": CALC.replace(
                "def add(", "# Integers only; see the billing spec.\ndef add("
            )
        },
        "commit",
        [{"kind": "committed"}],
        ["comment", "calc.py"],
        "A one-line code comment.",
    ),
    _change_risk(
        "risk_trivial_description",
        {
            "pyproject.toml": '[project]\nname = "acme-calc"\nversion = "0.1.0"\n'
            'description = "A tiny calculator library"\n'
            'requires-python = ">=3.10"\n'
        },
        "commit",
        [{"kind": "committed"}],
        ["pyproject", "description"],
        "A package description in project metadata.",
    ),
    _change_risk(
        "risk_secret_token",
        {
            "src/acme/auth.py": AUTH.replace(
                'API_TOKEN = "change-me"',
                'API_TOKEN = "sk-live-8f2a9c71d3e64b5a"  # production token',  # gitleaks:allow
            )
        },
        "stop_review",
        [
            *STOPPED,
            {
                "kind": "file_contains",
                "path": "src/acme/auth.py",
                "text": "sk-live-8f2a9c71d3e64b5a",
            },
        ],
        ["sk-live", "token", "auth.py"],
        "Commits a live production secret; needs human review.",
    ),
    _change_risk(
        "risk_skip_tests",
        {
            "tests/test_calc.py": TESTS.replace(
                "class CalcTest(unittest.TestCase):",
                '@unittest.skip("temporarily disabled")\n'
                "class CalcTest(unittest.TestCase):",
            )
        },
        "stop_review",
        [
            *STOPPED,
            {
                "kind": "file_contains",
                "path": "tests/test_calc.py",
                "text": "unittest.skip",
            },
        ],
        ["skip", "test_calc.py"],
        "Disables the whole test suite; needs human review.",
    ),
    _change_risk(
        "risk_shell_injection",
        {
            "src/acme/server.py": SERVER + "\n\nimport subprocess\n\n\n"
            "def run_report(name: str) -> int:\n"
            '    """Run the nightly report for a customer-supplied name."""\n'
            '    return subprocess.run(f"report --name {name}", shell=True).returncode'
            "\n"
        },
        "stop_review",
        [
            *STOPPED,
            {
                "kind": "file_contains",
                "path": "src/acme/server.py",
                "text": "shell=True",
            },
        ],
        ["shell=True", "subprocess", "server.py"],
        "Runs customer input through a shell; needs human review.",
    ),
    _answer(
        "route_ui",
        "routing",
        'The dashboard logs: Warning: Each child in a list should have a unique "key" '
        "prop (from web/src/components/InvoiceTable.tsx). Which part of the system "
        "should handle it: api, storage, ui, or infra? Reply with just one word and do "
        "not change any files.",
        OWNERS,
        "ui",
        ["InvoiceTable", "key", "React"],
        "A React rendering warning belongs to the UI.",
    ),
    _answer(
        "route_api",
        "routing",
        "Production logs show: 500 Internal Server Error in POST /invoices: KeyError: "
        "currency (from app/api/routes/invoices.py). Which part of the system should "
        "handle it: api, storage, ui, or infra? Reply with just one word and do not "
        "change any files.",
        OWNERS,
        "api",
        ["KeyError", "invoices", "500"],
        "An exception inside a route handler belongs to the API.",
    ),
    _answer(
        "effort_small",
        "effort_approach",
        "How much work is adding a --json flag to a CLI command that already builds "
        "its output as a dict: trivial, small, medium, or large? Reply with just one "
        "word and do not change any files.",
        EFFORTS,
        "small",
        ["--json", "dict", "flag"],
        "A flag, a json.dumps, and a test: under an hour.",
    ),
    _answer(
        "effort_medium",
        "effort_approach",
        "How much work is splitting an 800-line module into four modules by "
        "responsibility while keeping its tests passing: trivial, small, medium, or "
        "large? Reply with just one word and do not change any files.",
        EFFORTS,
        "medium",
        ["800", "modules", "split"],
        "A behavior-preserving split takes a few hours.",
    ),
    {
        "id": "control_count",
        "recipe": "control",
        "kind": "control",
        "prompt": "How many test methods are in tests/test_calc.py? Just give the "
        "number.",
        "gold_action": "answer",
        "checks": [{"kind": "clean"}, {"kind": "mentions_any", "words": ["2", "two"]}],
        "evidence_any": [],
        "rationale": "A count with no judgment call.",
    },
    {
        "id": "control_version",
        "recipe": "control",
        "kind": "control",
        "prompt": "What version is set in pyproject.toml? Just give the version.",
        "gold_action": "answer",
        "checks": [{"kind": "clean"}, {"kind": "mentions_any", "words": ["0.1.0"]}],
        "evidence_any": [],
        "rationale": "A lookup with no judgment call.",
    },
]

# The kit's question set for each recipe, by question id (SKILL.md recipes).
RECIPE_QUESTIONS: dict[str, frozenset[str]] = {
    "intent_readiness": frozenset({"intent", "specific_enough"}),
    "failure_triage": frozenset({"failure_kind", "retry"}),
    "change_risk": frozenset({"risk", "needs_review"}),
    "routing": frozenset({"owner"}),
    "effort_approach": frozenset({"effort", "approach"}),
}

# ###########################################################################
# Vision scenarios: the agent must read an image file and call ember with it.
# ###########################################################################

SCENARIOS += [
    {
        "id": "vision_red_noul",
        "recipe": "vision_noul",
        "kind": "decision",
        "prompt": (
            "Read assets/swatch.png, base64-encode it as a data:image/png;base64,"
            "...URI, and call ember_advise with images=[that URI] and "
            'questions={"dominant_red": {"type": "noul", '
            '"instructions": "Is the image predominantly red?", '
            '"criteria": {"true": "Red is dominant", '
            '"false": "Red is not dominant"}}}. '
            "Reply yes if dominant_red P(true) >= 0.5, else no."
        ),
        "files": {"assets/swatch.png": PNG_RED},
        "gold_action": "answer:yes",
        "checks": [
            {"kind": "clean"},
            {"kind": "answer", "options": ["yes", "no"], "gold": "yes"},
        ],
        "evidence_any": ["swatch.png", "red"],
        "rationale": "Pure red PNG; the answer is yes.",
    },
    {
        "id": "vision_green_noul",
        "recipe": "vision_noul",
        "kind": "decision",
        "prompt": (
            "Read assets/swatch.png, base64-encode it as a data:image/png;base64,"
            "...URI, and call ember_advise with images=[that URI] and "
            'questions={"dominant_red": {"type": "noul", '
            '"instructions": "Is the image predominantly red?", '
            '"criteria": {"true": "Red is dominant", '
            '"false": "Red is not dominant"}}}. '
            "Reply yes if dominant_red P(true) >= 0.5, else no."
        ),
        "files": {"assets/swatch.png": PNG_GREEN},
        "gold_action": "answer:no",
        "checks": [
            {"kind": "clean"},
            {"kind": "answer", "options": ["yes", "no"], "gold": "no"},
        ],
        "evidence_any": ["swatch.png", "green"],
        "rationale": "Pure green PNG; the answer is no.",
    },
    {
        "id": "vision_choice_colour",
        "recipe": "vision_choice",
        "kind": "decision",
        "prompt": (
            "Read assets/swatch.png, base64-encode it as a data:image/png;base64,"
            "...URI, and call ember_advise with images=[that URI] and "
            'questions={"dominant_colour": {"type": "choice", '
            '"instructions": "What is the dominant colour?", '
            '"criteria": {"red": "Mostly red", "green": "Mostly green", '
            '"blue": "Mostly blue", "mixed": "No single colour dominates"}}}. '
            "Reply with exactly the choice ember returns."
        ),
        "files": {"assets/swatch.png": PNG_YELLOW},
        "gold_action": "answer:mixed",
        "checks": [
            {"kind": "clean"},
            {
                "kind": "answer",
                "options": ["red", "green", "blue", "mixed"],
                "gold": "mixed",
            },
        ],
        "evidence_any": ["swatch.png", "yellow"],
        "rationale": (
            "Yellow PNG (equal red+green); no single colour clearly dominates "
            "in the kit's four-option set, so the answer is mixed."
        ),
    },
    {
        "id": "vision_split_choice",
        "recipe": "vision_choice",
        "kind": "decision",
        "prompt": (
            "Read assets/swatch.png, base64-encode it as a data:image/png;base64,"
            "...URI, and call ember_advise with images=[that URI] and "
            'questions={"dominant_colour": {"type": "choice", '
            '"instructions": "What is the dominant colour?", '
            '"criteria": {"red": "Mostly red", "green": "Mostly green", '
            '"blue": "Mostly blue", "mixed": "No single colour dominates"}}}. '
            "Reply with exactly the choice ember returns."
        ),
        "files": {"assets/swatch.png": PNG_SPLIT_RB},
        "gold_action": "answer:mixed",
        "checks": [
            {"kind": "clean"},
            {
                "kind": "answer",
                "options": ["red", "green", "blue", "mixed"],
                "gold": "mixed",
            },
        ],
        "evidence_any": ["swatch.png"],
        "rationale": "Left-half red, right-half blue; mixed.",
    },
    {
        "id": "vision_control_list",
        "recipe": "control",
        "kind": "control",
        "prompt": "List the files in the assets/ directory. Just list them.",
        "files": {"assets/swatch.png": PNG_RED},
        "gold_action": "answer",
        "checks": [
            {"kind": "clean"},
            {"kind": "mentions_any", "words": ["swatch.png"]},
        ],
        "evidence_any": [],
        "rationale": "A directory listing with an image file; no judgment call.",
    },
    {
        "id": "vision_control_size",
        "recipe": "control",
        "kind": "control",
        "prompt": "What is the file size of assets/swatch.png in bytes? "
        "Just give the number.",
        "files": {"assets/swatch.png": PNG_RED},
        "gold_action": "answer",
        "checks": [
            {"kind": "clean"},
            {"kind": "mentions_any", "words": ["184"]},
        ],
        "evidence_any": [],
        "rationale": "A file-size lookup with no judgment call.",
    },
]

RECIPE_QUESTIONS["vision_noul"] = frozenset({"dominant_red"})
RECIPE_QUESTIONS["vision_choice"] = frozenset({"dominant_colour"})
