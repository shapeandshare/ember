#!/usr/bin/env python3
"""Re-check every data-source register row online (network; not a test).

For each row: fetch each URL (HEAD, then GET) and record ``url_ok``; re-read the
licence page and record whether the SPDX id or licence name still appears
(``licence_reading_unchanged``, a heuristic); for ``used`` rows retrieve the
mirror and compare its SHA-256 (``mirror_ok``). Writes
``evals/dataset/register-audit.json`` and exits 1 when a ``used`` row fails
``mirror_ok`` or any of its URLs. A changed licence reading is reported, never
applied to the register.

Usage
-----
    python3 scripts/audit_data_sources.py [--rows id,id] [--timeout 20]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from evals.dataset.records.register_row import RegisterRow  # noqa: E402
from evals.dataset.records.verdict import Verdict  # noqa: E402
from evals.dataset.register import (  # noqa: E402
    REGISTER_PATH,
    load,
    load_example_secrets,
)
from evals.export import write_atomic  # noqa: E402

AUDIT_PATH = REGISTER_PATH.with_name("register-audit.json")
HEADERS = {
    "User-Agent": "ember-data-source-audit/1.0 (+https://github.com/shapeandshare/ember)"
}


def _fetch(client: httpx.Client, url: str) -> httpx.Response | None:
    try:
        response = client.head(url, follow_redirects=True)
        if response.status_code >= 400 or response.status_code == 405:
            response = client.get(url, follow_redirects=True)
        return response
    except httpx.HTTPError:
        return None


def _reading_present(text: str, row: RegisterRow) -> bool | None:
    needles = [n for n in (row.licence.spdx, row.licence.reading) if n]
    if not needles:
        return None
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in needles)


def _mirror_ok(client: httpx.Client, row: RegisterRow) -> bool | None:
    if row.mirror is None:
        return None
    if not row.mirror.location.startswith(("http://", "https://")):
        return None  # object storage is checked with its own tooling
    try:
        with client.stream(
            "GET", row.mirror.location, follow_redirects=True
        ) as response:
            if response.status_code >= 400:
                return False
            digest = hashlib.sha256()
            for chunk in response.iter_bytes():
                digest.update(chunk)
    except httpx.HTTPError:
        return False
    return digest.hexdigest() == row.mirror.sha256


def audit_row(client: httpx.Client, row: RegisterRow) -> dict[str, Any]:
    """Audit one row and return its result record."""
    urls = {}
    for reading in row.urls:
        response = _fetch(client, reading.url)
        urls[reading.url] = response is not None and response.status_code < 400
    licence_page = _fetch(client, row.licence.read_at)
    unchanged = (
        _reading_present(licence_page.text, row)
        if licence_page is not None
        and licence_page.status_code < 400
        and licence_page.text
        else None
    )
    return {
        "url_ok": urls,
        "licence_reading_unchanged": unchanged,
        "mirror_ok": _mirror_ok(client, row),
        "verdict": row.verdict.value,
    }


def audit_examples(client: httpx.Client) -> dict[str, bool]:
    """Check that every example-secret URL still answers."""
    results = {}
    for entry in load_example_secrets():
        response = _fetch(client, entry.url)
        results[entry.url] = response is not None and response.status_code < 400
    return results


def main(argv: list[str] | None = None) -> int:
    """Run the audit and write ``register-audit.json``."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--rows", default=None, help="comma-separated row ids (default: all)"
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args(argv)
    rows = load()
    if args.rows:
        wanted = set(args.rows.split(","))
        rows = [row for row in rows if row.id in wanted]
    results: dict[str, Any] = {}
    failed = False
    with httpx.Client(timeout=args.timeout, headers=HEADERS) as client:
        for row in rows:
            result = audit_row(client, row)
            results[row.id] = result
            if row.verdict is Verdict.used and (
                result["mirror_ok"] is False or not all(result["url_ok"].values())
            ):
                failed = True
            status = "ok " if all(result["url_ok"].values()) else "URL"
            unchanged = result["licence_reading_unchanged"]
            print(f"{status} {row.id:<44} licence unchanged: {unchanged}")
        examples = audit_examples(client)
    write_atomic(
        AUDIT_PATH,
        json.dumps(
            {
                "audited_on": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "rows": results,
                "example_secrets": examples,
            },
            indent=2,
        )
        + "\n",
    )
    print(f"wrote {AUDIT_PATH}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
