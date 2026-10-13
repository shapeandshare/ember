"""Render a per-release conda recipe for the interim Anaconda.org channel.

`conda/recipe.yaml` is a frozen submission snapshot for conda-forge. The interim
self-hosted channel publishes every release, so CI renders a copy of that recipe with
the released version and the matching PyPI sdist sha256; the committed recipe is never
edited by a release.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "conda" / "recipe.yaml"
DIST = "ember-advise"
_VERSION_LINE = re.compile(r'(?m)^(\s*version:\s*)".*"$')
_SHA256_LINE = re.compile(r"(?m)^(\s*sha256:\s*)[0-9a-f]{64}$")
_VERSION_FORMAT = re.compile(r"\d+\.\d+\.\d+")
_SHA256_FORMAT = re.compile(r"[0-9a-f]{64}")


def render(recipe_text: str, version: str, sha256: str) -> str:
    """Return ``recipe_text`` with the context version and sdist sha256 replaced.

    Parameters
    ----------
    recipe_text : str
        The committed recipe's contents.
    version : str
        The release version, e.g. ``"0.15.0"``.
    sha256 : str
        The lowercase hex sha256 of that version's PyPI sdist.

    Returns
    -------
    str
        The recipe with ``context.version`` and ``source.sha256`` set.

    Raises
    ------
    ValueError
        If ``version`` or ``sha256`` is malformed.
    """
    if not _VERSION_FORMAT.fullmatch(version):
        raise ValueError(f"malformed version: {version!r}")
    if not _SHA256_FORMAT.fullmatch(sha256):
        raise ValueError(f"malformed sha256: {sha256!r}")
    text = _VERSION_LINE.sub(rf'\g<1>"{version}"', recipe_text, count=1)
    return _SHA256_LINE.sub(rf"\g<1>{sha256}", text, count=1)


def fetch_sdist_sha256(version: str, *, timeout: float = 30.0) -> str:
    """Return the sha256 of the PyPI sdist published for ``version``."""
    url = f"https://pypi.org/pypi/{DIST}/{version}/json"
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload: dict[str, Any] = json.load(response)
    for artifact in payload["urls"]:
        if artifact["packagetype"] == "sdist":
            return str(artifact["digests"]["sha256"])
    raise LookupError(f"no sdist published for {DIST} {version}")


def main() -> int:
    """Render the recipe for ``argv[1]`` (a version) to ``argv[2]`` (a path)."""
    if len(sys.argv) != 3:
        sys.stderr.write("usage: render_conda_recipe.py <version> <output-path>\n")
        return 2
    version, destination = sys.argv[1], Path(sys.argv[2])
    rendered = render(
        RECIPE.read_text(encoding="utf-8"), version, fetch_sdist_sha256(version)
    )
    destination.write_text(rendered, encoding="utf-8")
    print(f"rendered {destination} for {DIST} {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
