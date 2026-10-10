"""The 'System under test' section surfaces the server's ember version and a
generic deployment description, never a raw server URL.

A hosted deployment's client (the machine running the benchmark) and server
(the machine running the model) can run different ``ember-advise`` versions;
the report must show both when they differ, not only the client's. The
deployment itself is described generically (``meta.deployment_label``, e.g.
"Remote hosted (GPU, CUDA)") — the real server URL never appears in the
published report (vault/decisions/2026-10-10-generic-deployment-labels.md).
"""

from __future__ import annotations

from typing import Any

from evals.render.blocks import Table
from evals.sections import sections_front

BASE_TEXT = {
    "system": ["System paragraph."],
    "architecture": {"nodes": [], "edges": []},
    "architecture_text": "",
}


def _report(
    *,
    server_version: str | None,
    client_version: str | None,
    deployment_label: str = "Remote hosted (GPU, CUDA)",
) -> dict[str, Any]:
    packages: dict[str, str] = {}
    if client_version is not None:
        packages["ember-advise"] = client_version
    return {
        "meta": {
            "model": "clef-flash",
            "model_spec": {},
            "engine": {"device": "cuda", "dtype": "float16"},
            "server_version": server_version,
            "host": {
                "cpu": "Apple M4 Max",
                "platform": "",
                "python": "3.12.11",
                "packages": packages,
            },
            "deployment_label": deployment_label,
            "git_hash": "abc1234",
            "run_at": "2026-10-10 00:00 UTC",
            "generated_at": "2026-10-10 00:05 UTC",
            "dataset": {
                "name": "clef-flash.jsonl",
                "sha256": "deadbeef",
                "matches": True,
            },
            "n_errors": 0,
        },
        "text": BASE_TEXT,
    }


def _facts(blocks: list[Any]) -> dict[str, Any]:
    (table,) = (b for b in blocks if isinstance(b, Table))
    return {row[0].value: row[1] for row in table.rows}


def test_software_fact_shows_server_version_when_it_differs_from_client() -> None:
    report = _report(server_version="0.10.2", client_version="0.10.3")
    _, _, blocks = sections_front.system(report)
    facts = _facts(blocks)
    software = facts["Software"].value
    assert "server 0.10.2" in software
    assert "client 0.10.3" in software


def test_software_fact_shows_one_version_when_client_and_server_match() -> None:
    report = _report(server_version="0.10.2", client_version="0.10.2")
    _, _, blocks = sections_front.system(report)
    facts = _facts(blocks)
    software = facts["Software"].value
    assert software.count("0.10.2") == 1
    assert "server" not in software
    assert "client" not in software


def test_software_fact_omits_server_version_when_not_recorded() -> None:
    report = _report(server_version=None, client_version="0.10.3")
    _, _, blocks = sections_front.system(report)
    facts = _facts(blocks)
    software = facts["Software"].value
    assert "0.10.3" in software
    assert "server" not in software


def test_system_table_shows_the_generic_deployment_label_not_a_url() -> None:
    report = _report(
        server_version="0.10.2",
        client_version="0.10.2",
        deployment_label="Remote hosted (GPU, CUDA)",
    )
    _, _, blocks = sections_front.system(report)
    facts = _facts(blocks)
    assert facts["Deployment"].value == "Remote hosted (GPU, CUDA)"
    assert "Server" not in facts


def test_system_table_never_contains_a_url_scheme() -> None:
    """No fact in the System-under-test table may contain ``://`` — the
    table must never leak a raw server URL, S3 URI, or similar.
    """
    report = _report(server_version="0.10.2", client_version="0.10.2")
    _, _, blocks = sections_front.system(report)
    facts = _facts(blocks)
    for label, cell in facts.items():
        assert "://" not in str(cell.value), f"{label} leaks a URL: {cell.value}"
