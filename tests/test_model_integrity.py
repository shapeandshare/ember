"""Unit tests for the model registry's structure and pull/list/rm behavior.

Constitution Article V ("Model Loading"): ember supports any model that can
run under its loader contract, not a hand-maintained allowlist of
individually hash-verified weights — there is no integrity-verification
subsystem to test here. REGISTRY only ever holds Hugging-Face-sourced
entries; a hosted deployment supplying its own S3 model location uses
``EMBER_MODEL_S3_URI`` instead (see ``tests/test_hosted.py``), independent of
this registry entirely.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ember import models
from ember.models import REGISTRY


def test_registry_entries_are_decision_models():
    assert all(spec.kind == "decision" for spec in REGISTRY.values())


def test_list_models_rows_include_kind(monkeypatch):
    monkeypatch.setattr(models, "resolve_dir", lambda *args, **kwargs: None)
    rows = models.list_models()
    assert rows
    assert all(row["kind"] == "decision" for row in rows)


def test_default_is_flash():
    """flash is the default registry entry — a plain Hugging Face Hub pull,
    no AWS S3 or credentials required."""
    assert models.DEFAULT == "flash"
    assert models.DEFAULT in REGISTRY


def test_model_revisions_are_full_commit_shas_when_set():
    """revision is optional (constitution Article V, "Model Loading"); when a
    REGISTRY entry does set one (as both current entries do, for download
    targeting), it must be a full commit SHA, not a branch name or partial
    hash."""
    import re

    for spec in REGISTRY.values():
        if spec.revision is not None:
            assert re.fullmatch(r"[0-9a-f]{40}", spec.revision), (
                f"{spec.name}'s revision is set but not a full commit SHA"
            )


def test_pull_flash_raises_actionable_error_on_low_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(models, "_dev_dir", lambda spec: tmp_path / "nope")
    monkeypatch.setattr(
        models,
        "_disk_ok",
        lambda target, required: (False, "low disk: need ~18 GB free, have 1.0 GB"),
    )
    with pytest.raises(RuntimeError, match=r"low disk.*allow-low-disk"):
        models.pull("flash")


def test_pull_unknown_name_lists_valid_choices() -> None:
    with pytest.raises(KeyError, match=r"flash.*full|full.*flash"):
        models.get("not-a-real-model")


def test_get_resolves_default_when_name_is_none() -> None:
    assert models.get(None) is REGISTRY[models.DEFAULT]


def test_get_is_case_insensitive() -> None:
    assert models.get("FLASH") is REGISTRY["flash"]
