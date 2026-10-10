"""Leaderboard model: group tracked benchmark runs by model and deployment,
keep the latest run per group, and shape the comparison table the site shows.

Synthetic ``model.json``-shaped dicts stand in for snapshotted runs, so
nothing here touches the real ``benchmark/`` tree or loads a model.
"""

from __future__ import annotations

from typing import Any

from evals import leaderboard


def _run(
    *,
    run_id: str,
    run_at: str,
    model: str,
    model_spec: dict[str, Any] | None = None,
    device: str = "mps",
    dtype: str = "float16",
    server: str = "http://127.0.0.1:8765",
    server_version: str | None = None,
    client_version: str | None = "0.10.2",
    accuracy: float = 0.80,
    accuracy_ci: tuple[float, float] = (0.75, 0.85),
    item_accuracy: float = 0.70,
    items: int = 100,
    questions: int = 200,
    latency_p50: float = 500.0,
) -> dict[str, Any]:
    packages = {}
    if client_version is not None:
        packages["ember-advise"] = client_version
    return {
        "meta": {
            "run_id": run_id,
            "run_at": run_at,
            "model": model,
            "model_spec": model_spec or {},
            "engine": {"device": device, "dtype": dtype},
            "server_version": server_version,
            "host": {"packages": packages},
            "server": server,
            "n_items": items,
            "n_errors": 0,
        },
        "summary": {
            "overall": {
                "items": items,
                "questions": questions,
                "accuracy": accuracy,
                "accuracy_ci": list(accuracy_ci),
                "item_accuracy": item_accuracy,
            }
        },
        "latency": {"p50": latency_p50, "p95": latency_p50 * 1.3},
    }


def test_deployment_key_groups_same_server_and_device() -> None:
    a = _run(run_id="a", run_at="2026-10-01 00:00 UTC", model="clef-flash")
    b = _run(run_id="b", run_at="2026-10-02 00:00 UTC", model="clef-flash")
    assert leaderboard.deployment_key(a["meta"]) == leaderboard.deployment_key(
        b["meta"]
    )


def test_deployment_key_distinguishes_different_servers_or_devices() -> None:
    local = _run(run_id="a", run_at="2026-10-01 00:00 UTC", model="clef-flash")
    hosted = _run(
        run_id="b",
        run_at="2026-10-02 00:00 UTC",
        model="clef-flash",
        device="cuda",
        server="https://hosted.example.com",
    )
    assert leaderboard.deployment_key(local["meta"]) != leaderboard.deployment_key(
        hosted["meta"]
    )


def test_model_key_prefers_registry_name_over_raw_model_string() -> None:
    hosted = _run(
        run_id="a",
        run_at="2026-10-01 00:00 UTC",
        model="Cloudflare__clef-flash",
        model_spec={"name": "flash", "repo": "Cloudflare/clef-flash"},
    )
    local = _run(
        run_id="b",
        run_at="2026-10-02 00:00 UTC",
        model="clef-flash",
        model_spec={"name": "flash", "repo": "Cloudflare/clef-flash"},
    )
    assert leaderboard.model_key(hosted["meta"]) == leaderboard.model_key(local["meta"])
    assert leaderboard.model_key(hosted["meta"]) == "flash"


def test_model_key_falls_back_to_raw_model_string_when_unmatched() -> None:
    run = _run(run_id="a", run_at="2026-10-01 00:00 UTC", model="some-custom-model")
    assert leaderboard.model_key(run["meta"]) == "some-custom-model"


def test_build_keeps_only_the_latest_run_per_model_and_deployment() -> None:
    older_local = _run(
        run_id="clef-flash_a", run_at="2026-10-01 00:00 UTC", model="clef-flash"
    )
    newer_local = _run(
        run_id="clef-flash_b",
        run_at="2026-10-05 00:00 UTC",
        model="clef-flash",
        accuracy=0.90,
    )
    hosted = _run(
        run_id="Cloudflare__clef-flash_c",
        run_at="2026-10-10 00:00 UTC",
        model="Cloudflare__clef-flash",
        model_spec={"name": "flash", "repo": "Cloudflare/clef-flash"},
        device="cuda",
        server="https://hosted.example.com",
    )
    board = leaderboard.build([older_local, newer_local, hosted])
    run_ids = {row["run_id"] for row in board["rows"]}
    assert run_ids == {"clef-flash_b", "Cloudflare__clef-flash_c"}
    assert len(board["rows"]) == 2


def test_build_sorts_rows_by_accuracy_descending() -> None:
    low = _run(run_id="low", run_at="2026-10-01 00:00 UTC", model="full", accuracy=0.60)
    high = _run(
        run_id="high", run_at="2026-10-01 00:00 UTC", model="flash", accuracy=0.90
    )
    board = leaderboard.build([low, high])
    assert [row["run_id"] for row in board["rows"]] == ["high", "low"]


def test_row_carries_version_and_datetime_fields() -> None:
    run = _run(
        run_id="a",
        run_at="2026-10-10 19:27 UTC",
        model="Cloudflare__clef-flash",
        model_spec={"name": "flash", "repo": "Cloudflare/clef-flash", "params": "9B"},
        device="cuda",
        server="https://hosted.example.com",
        server_version="0.10.2",
        client_version="0.10.3",
    )
    board = leaderboard.build([run])
    (row,) = board["rows"]
    assert row["run_at"] == "2026-10-10 19:27 UTC"
    assert row["ember_server_version"] == "0.10.2"
    assert row["ember_client_version"] == "0.10.3"
    assert row["device"] == "cuda"
    assert row["model_repo"] == "Cloudflare/clef-flash"
    assert row["params"] == "9B"


def test_row_version_fields_are_none_when_not_recorded() -> None:
    run = _run(
        run_id="a",
        run_at="2026-10-01 00:00 UTC",
        model="clef-flash",
        server_version=None,
        client_version=None,
    )
    board = leaderboard.build([run])
    (row,) = board["rows"]
    assert row["ember_server_version"] is None
    assert row["ember_client_version"] is None


def test_build_with_no_runs_returns_empty_rows() -> None:
    board = leaderboard.build([])
    assert board["rows"] == []
