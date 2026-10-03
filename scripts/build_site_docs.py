#!/usr/bin/env python3
"""Assemble the Jekyll site's content from the repository's own markdown.

Run before ``jekyll build`` (the deploy workflow and ``make site`` do this).
It reads ``site/_data/docs.json`` and copies each source document into
``site/_docs/`` with Jekyll front matter, rewriting links so the rendered pages
do not 404: links to published documents point at their site URL, links to brand
assets point at the site's ``/assets``, and links to anything else in the
repository point at its blob on GitHub.

Only the copy step knows this mapping, so ``site/_docs/`` and the copied brand
assets are generated output and are gitignored.

Usage
-----
    python3 scripts/build_site_docs.py
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SITE = REPO / "site"
DOCS_OUT = SITE / "_docs"
ASSETS_OUT = SITE / "assets" / "brand"
BLOB = "https://github.com/shapeandshare/ember/blob/main"
SCHEMES = ("#", "http://", "https://", "mailto:", "tel:", "data:")

# Brand assets the site serves, copied from the repository's single source.
ASSETS = (
    "assets/brand/tokens.css",
    "assets/brand/hero-light.svg",
    "assets/brand/hero-dark.svg",
    "assets/brand/svg/ember-light.svg",
    "assets/brand/svg/ember-dark.svg",
    "assets/brand/svg/ember-auto.svg",
)

_MD_LINK = re.compile(r"(!?\[[^\]]*\]\()([^)]+)(\))")
_HTML_ATTR = re.compile(
    r"(?P<attr>\b(?:src|srcset|href|poster)=)(?P<q>[\"'])(?P<url>[^\"']+)(?P=q)"
)
_FRONT_MATTER = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)


def _load_manifest() -> list[dict[str, str]]:
    return json.loads((SITE / "_data" / "docs.json").read_text(encoding="utf-8"))


def _rewrite_url(
    url: str, by_path: dict[str, str], by_name: dict[str, str], assets: set[str]
) -> str:
    """Map one link target to its site URL, asset path, or GitHub blob."""
    url = url.strip()
    if not url or url.startswith(SCHEMES):
        return url
    path, _, fragment = url.partition("#")
    path = path.strip().lstrip("./")
    if not path:
        return url
    if path in by_path:
        target = f"{{{{ '/docs/{by_path[path]}/' | relative_url }}}}"
    elif "/" not in path and path in by_name:
        target = f"{{{{ '/docs/{by_name[path]}/' | relative_url }}}}"
    elif path in assets:
        target = f"{{{{ '/{path}' | relative_url }}}}"
    else:
        target = f"{BLOB}/{path}"
    return f"{target}#{fragment}" if fragment else target


def _rewrite(
    text: str, by_path: dict[str, str], by_name: dict[str, str], assets: set[str]
) -> str:
    def md(match: re.Match[str]) -> str:
        head, target, tail = match.groups()
        title = ""
        if " " in target and target.startswith("<") and target.endswith(">"):
            target = target[1:-1]
        elif ' "' in target and target.endswith('"'):
            target, _, quoted = target.partition(" ")
            title = " " + quoted
        return f"{head}{_rewrite_url(target, by_path, by_name, assets)}{title}{tail}"

    def html(match: re.Match[str]) -> str:
        attr, quote, value = match.group("attr"), match.group("q"), match.group("url")
        parts = []
        for piece in value.split(","):
            url, _, descriptor = piece.strip().partition(" ")
            url = _rewrite_url(url, by_path, by_name, assets)
            parts.append(f"{url} {descriptor}".strip())
        return f"{attr}{quote}{', '.join(parts)}{quote}"

    return _HTML_ATTR.sub(html, _MD_LINK.sub(md, text))


def main() -> int:
    manifest = _load_manifest()
    by_path = {entry["source"]: entry["slug"] for entry in manifest}
    by_name = {Path(entry["source"]).name: entry["slug"] for entry in manifest}
    assets = set(ASSETS)

    shutil.rmtree(DOCS_OUT, ignore_errors=True)
    DOCS_OUT.mkdir(parents=True)
    for entry in manifest:
        source = REPO / entry["source"]
        if not source.is_file():
            print(f"error: missing source {entry['source']}", file=sys.stderr)
            return 1
        body = _FRONT_MATTER.sub("", source.read_text(encoding="utf-8"))
        body = _rewrite(body, by_path, by_name, assets)
        front = (
            "---\n"
            "layout: doc\n"
            f"title: {entry['title']}\n"
            f"permalink: /docs/{entry['slug']}/\n"
            "---\n"
        )
        (DOCS_OUT / f"{entry['slug']}.md").write_text(front + body, encoding="utf-8")
        print(f"  docs  {entry['source']} -> /docs/{entry['slug']}/")

    for relative in ASSETS:
        source = REPO / relative
        target = ASSETS_OUT / Path(relative).relative_to("assets/brand")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    print(f"  assets {len(ASSETS)} files -> site/assets/brand/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
