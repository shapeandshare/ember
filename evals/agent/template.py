"""The sandbox repo every agent-eval scenario starts from, and its fixtures.

A tiny Python package (``acme-calc``) with stdlib unit tests, plus test files that
scenarios add to create a failure, a missing service, or a flaky test.
"""

from __future__ import annotations

TEST_COMMAND = ["python3", "-m", "unittest", "discover", "-s", "tests"]

CALC = '''"""Arithmetic helpers for the billing service."""


def add(a: int, b: int) -> int:
    """Return the sum of a and b."""
    return a + b


def mul(a: int, b: int) -> int:
    """Return the product of a and b."""
    return a * b
'''

AUTH = '''"""Request authentication for the billing API."""

import hmac

API_TOKEN = "change-me"


def is_authorized(headers: dict[str, str], remote_addr: str) -> bool:
    """Return True when the request carries the API token."""
    supplied = headers.get("Authorization", "").removeprefix("Bearer ")
    return hmac.compare_digest(supplied, API_TOKEN)
'''

SERVER = '''"""Network settings for the billing API."""

HOST = "127.0.0.1"
PORT = 8080
'''

TESTS = """import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from acme.calc import add, mul  # noqa: E402


class CalcTest(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 2), 4)

    def test_mul(self):
        self.assertEqual(mul(3, 4), 12)


if __name__ == "__main__":
    unittest.main()
"""

README = """# acme-calc

A tiny calculater library used by the billing service.

Run the tests with `python3 -m unittest discover -s tests`.
"""

TEMPLATE: dict[str, str] = {
    "README.md": README,
    "pyproject.toml": '[project]\nname = "acme-calc"\nversion = "0.1.0"\n'
    'requires-python = ">=3.10"\n',
    ".gitignore": "__pycache__/\nconfig/settings.json\n",
    "src/acme/__init__.py": "",
    "src/acme/calc.py": CALC,
    "src/acme/auth.py": AUTH,
    "src/acme/server.py": SERVER,
    "tests/test_calc.py": TESTS,
}


PRICING_TEST = """import unittest
import urllib.request


class PricingServiceTest(unittest.TestCase):
    def test_health(self):
        with urllib.request.urlopen("http://127.0.0.1:59321/health", timeout=2) as r:
            self.assertEqual(r.status, 200)
"""

SETTINGS_TEST = """import json
import unittest
from pathlib import Path

SETTINGS = Path(__file__).resolve().parents[1] / "config" / "settings.json"


class SettingsTest(unittest.TestCase):
    def test_currency(self):
        self.assertEqual(json.loads(SETTINGS.read_text())["currency"], "EUR")
"""

JITTER_TEST = """import random
import unittest


class JitterTest(unittest.TestCase):
    def test_jitter(self):
        # Retry backoff jitter must stay below 90% of the window.
        self.assertLess(random.random(), 0.9)
"""


AUTH_TEST = """import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from acme.auth import is_authorized  # noqa: E402


class AuthTest(unittest.TestCase):
    def test_bearer_token(self):
        headers = {"Authorization": "Bearer change-me"}
        self.assertTrue(is_authorized(headers, "10.0.0.1"))
"""

PORT_TEST = """import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from acme import server  # noqa: E402


class ServerTest(unittest.TestCase):
    def test_port(self):
        self.assertEqual(server.PORT, 8000)
"""

SECRETS_TEST = """import os
import unittest


class SecretsTest(unittest.TestCase):
    def test_api_key_present(self):
        self.assertTrue(os.environ["ACME_API_KEY"])
"""

FORMAT_TEST = """import subprocess
import unittest


class FormatTest(unittest.TestCase):
    def test_formatting(self):
        subprocess.run(["acme-fmt", "--check", "src"], check=True)
"""

RETRY_TEST = """import random
import unittest


class RetryWindowTest(unittest.TestCase):
    def test_retry_window(self):
        # The sampled retry window must stay under the 95th percentile.
        self.assertLess(random.random(), 0.95)
"""

# ###########################################################################
# Vision fixtures — small PNG files seeded as bytes into sandbox repos.
# sandbox._write() detects bytes values and calls path.write_bytes().
# ###########################################################################

import base64 as _b64  # noqa: E402


def _d(s: str) -> bytes:
    """Decode a concatenated base64 string to PNG bytes."""
    return _b64.b64decode(s)


PNG_RED: bytes = _d(
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAAf0lEQVR4nNXO"
    "QREAIAzAsFIh8y8KMYjgsWsU5NwZyiRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO"
    "4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO"
    "4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4twO/HoInQGY8Ba5YAAAAABJRU5E"
    "rkJggg=="
)
PNG_GREEN: bytes = _d(
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAAf0lEQVR4nNXO"
    "QREAIAzAsFIh8y8AgYjgsWsU5MwdyiRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO"
    "4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO"
    "4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4twO/Hp9twFwDhGK2QAAAABJRU5E"
    "rkJggg=="
)
PNG_YELLOW: bytes = _d(
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAAf0lEQVR4nNXO"
    "QREAIAzAsFIh+Bc1MYjgsWsU5MxcyiRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO"
    "4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO"
    "4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4twO/HrYrgJWk4YXFgAAAABJRU5E"
    "rkJggg=="
)
PNG_SPLIT_RB: bytes = _d(
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAAh0lEQVR4nNXO"
    "AQ3AMBCAQIqQF1PhUzIxFbE0CyeAsN4Zbto8V/sSJ3ESJ3ESJ3ESJ3ESJ3ES"
    "J3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ES"
    "J3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3ESJ3H+PfDVAejiApgFjLet"
    "AAAAAElFTkSuQmCC"
)

PNG_RED_URI: str = "data:image/png;base64," + _b64.b64encode(PNG_RED).decode()
PNG_GREEN_URI: str = "data:image/png;base64," + _b64.b64encode(PNG_GREEN).decode()
PNG_YELLOW_URI: str = "data:image/png;base64," + _b64.b64encode(PNG_YELLOW).decode()
PNG_SPLIT_RB_URI: str = "data:image/png;base64," + _b64.b64encode(PNG_SPLIT_RB).decode()
