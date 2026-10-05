"""Unit tests for model-file integrity verification (E-001, T-001, T-002, S-002).

Covers:
- ModelSpec has well-formed schema_sha256 and head_sha256 fields for every
  registry entry.
- verify_model_dir accepts a directory whose files match the spec hashes.
- verify_model_dir raises RuntimeError when required structural files are
  missing.
- verify_model_dir raises RuntimeError when joint_schema_model.py hash
  mismatches (always).
- verify_model_dir raises RuntimeError when joint_head.safetensors mismatches
  in official mode.
- verify_model_dir warns (not raises) when joint_head.safetensors mismatches
  in custom mode.
- verify_model_dir still raises on schema mismatch even in custom mode.
- joint_module() refuses to import a tampered joint_schema_model.py.
"""

from __future__ import annotations

import hashlib
import logging
import sys
from pathlib import Path

import pytest
from ember.models import REGISTRY, ModelSpec

# ###########################################################################
# Pinned hash constants (from the task spec — sourced from HF API at pinned revisions)
# ###########################################################################
SCHEMA_SHA256 = "0e304cf7c6500e8bb59bef7e2afd2c6373f82596dfb3b57d1aa93c175e2dc3a3"
HEAD_SHA256_FLASH = "19cdcec8c81dc9212be320fff47462ab342fbc1278be4368fb3da71241cf5ba0"
HEAD_SHA256_FULL = "a010ac04f078e699988e4049cbea5e62c962393f59fec366640b64e8d69a4953"


# ###########################################################################
# ModelSpec registry — hash fields
# ###########################################################################
def test_registry_flash_has_well_formed_schema_sha256():
    spec = REGISTRY["flash"]
    assert len(spec.schema_sha256) == 64
    assert all(c in "0123456789abcdef" for c in spec.schema_sha256)


def test_registry_flash_has_well_formed_head_sha256():
    spec = REGISTRY["flash"]
    assert len(spec.head_sha256) == 64
    assert all(c in "0123456789abcdef" for c in spec.head_sha256)


def test_registry_full_has_well_formed_schema_sha256():
    spec = REGISTRY["full"]
    assert len(spec.schema_sha256) == 64
    assert all(c in "0123456789abcdef" for c in spec.schema_sha256)


def test_registry_full_has_well_formed_head_sha256():
    spec = REGISTRY["full"]
    assert len(spec.head_sha256) == 64
    assert all(c in "0123456789abcdef" for c in spec.head_sha256)


def test_registry_flash_schema_sha256_matches_pinned_value():
    assert REGISTRY["flash"].schema_sha256 == SCHEMA_SHA256


def test_registry_full_schema_sha256_matches_pinned_value():
    assert REGISTRY["full"].schema_sha256 == SCHEMA_SHA256


def test_registry_flash_head_sha256_matches_pinned_value():
    assert REGISTRY["flash"].head_sha256 == HEAD_SHA256_FLASH


def test_registry_full_head_sha256_matches_pinned_value():
    assert REGISTRY["full"].head_sha256 == HEAD_SHA256_FULL


# ###########################################################################
# Helpers
# ###########################################################################
def _sha256_of(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _make_fake_spec(
    schema_sha256: str, head_sha256: str, name: str = "flash"
) -> ModelSpec:
    return ModelSpec(
        name=name,
        repo="Cloudflare/clef-flash",
        dir_name="clef-flash",
        params="9B",
        approx_bytes=18 * 2**30,
        revision="17f0b0ad64efb65d273590632833508766b2aae6",
        schema_sha256=schema_sha256,
        head_sha256=head_sha256,
    )


def _populate_model_dir(
    model_dir: Path,
    schema_content: bytes = b"# fake schema",
    head_content: bytes = b"fake head weights",
) -> tuple[str, str]:
    (model_dir / "config.json").write_bytes(b"{}")
    (model_dir / "joint_head_config.json").write_bytes(b"{}")
    (model_dir / "joint_schema_model.py").write_bytes(schema_content)
    (model_dir / "joint_head.safetensors").write_bytes(head_content)
    (model_dir / "model.safetensors.index.json").write_bytes(b"{}")
    return _sha256_of(schema_content), _sha256_of(head_content)


from ember.serving.integrity import verify_model_dir  # noqa: E402


# ###########################################################################
# T-002: structural validation
# ###########################################################################
def test_verify_model_dir_accepts_complete_directory(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    schema_sha, head_sha = _populate_model_dir(model_dir)
    spec = _make_fake_spec(schema_sha256=schema_sha, head_sha256=head_sha)
    verify_model_dir(model_dir, spec, official=True)


def test_verify_model_dir_raises_on_missing_config_json(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    schema_sha, head_sha = _populate_model_dir(model_dir)
    (model_dir / "config.json").unlink()
    spec = _make_fake_spec(schema_sha256=schema_sha, head_sha256=head_sha)
    with pytest.raises(RuntimeError, match=r"config\.json"):
        verify_model_dir(model_dir, spec, official=True)


def test_verify_model_dir_raises_on_missing_joint_schema_model(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    schema_sha, head_sha = _populate_model_dir(model_dir)
    (model_dir / "joint_schema_model.py").unlink()
    spec = _make_fake_spec(schema_sha256=schema_sha, head_sha256=head_sha)
    with pytest.raises(RuntimeError, match=r"joint_schema_model\.py"):
        verify_model_dir(model_dir, spec, official=True)


def test_verify_model_dir_raises_on_missing_joint_head_safetensors(
    tmp_path: Path,
) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    schema_sha, head_sha = _populate_model_dir(model_dir)
    (model_dir / "joint_head.safetensors").unlink()
    spec = _make_fake_spec(schema_sha256=schema_sha, head_sha256=head_sha)
    with pytest.raises(RuntimeError, match=r"joint_head\.safetensors"):
        verify_model_dir(model_dir, spec, official=True)


def test_verify_model_dir_raises_on_missing_joint_head_config(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    schema_sha, head_sha = _populate_model_dir(model_dir)
    (model_dir / "joint_head_config.json").unlink()
    spec = _make_fake_spec(schema_sha256=schema_sha, head_sha256=head_sha)
    with pytest.raises(RuntimeError, match=r"joint_head_config\.json"):
        verify_model_dir(model_dir, spec, official=True)


# ###########################################################################
# E-001 / T-001: joint_schema_model.py hash enforcement (always)
# ###########################################################################
def test_verify_model_dir_raises_on_schema_hash_mismatch_official(
    tmp_path: Path,
) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    _schema_sha, head_sha = _populate_model_dir(model_dir)
    spec = _make_fake_spec(schema_sha256="a" * 64, head_sha256=head_sha)
    with pytest.raises(RuntimeError, match=r"joint_schema_model\.py"):
        verify_model_dir(model_dir, spec, official=True)


def test_verify_model_dir_raises_on_schema_hash_mismatch_custom(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    _schema_sha, head_sha = _populate_model_dir(model_dir)
    spec = _make_fake_spec(schema_sha256="b" * 64, head_sha256=head_sha)
    with pytest.raises(RuntimeError, match=r"joint_schema_model\.py"):
        verify_model_dir(model_dir, spec, official=False)


def test_verify_model_dir_error_message_names_expected_and_actual_hash(
    tmp_path: Path,
) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    _schema_sha, head_sha = _populate_model_dir(model_dir)
    wrong_hash = "c" * 64
    spec = _make_fake_spec(schema_sha256=wrong_hash, head_sha256=head_sha)
    with pytest.raises(RuntimeError) as exc_info:
        verify_model_dir(model_dir, spec, official=True)
    msg = str(exc_info.value)
    assert "joint_schema_model.py" in msg
    assert wrong_hash[:8] in msg
    assert "pull" in msg.lower() or "re-pull" in msg.lower()


# ###########################################################################
# S-002: joint_head.safetensors hash enforcement
# ###########################################################################
def test_verify_model_dir_raises_on_head_hash_mismatch_official(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    schema_sha, _head_sha = _populate_model_dir(model_dir)
    spec = _make_fake_spec(schema_sha256=schema_sha, head_sha256="d" * 64)
    with pytest.raises(RuntimeError, match=r"joint_head\.safetensors"):
        verify_model_dir(model_dir, spec, official=True)


def test_verify_model_dir_warns_not_raises_on_head_hash_mismatch_custom(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    schema_sha, _head_sha = _populate_model_dir(model_dir)
    spec = _make_fake_spec(schema_sha256=schema_sha, head_sha256="e" * 64)
    with caplog.at_level(logging.WARNING, logger="ember.serving.integrity"):
        verify_model_dir(model_dir, spec, official=False)
    assert any("joint_head.safetensors" in r.message for r in caplog.records)


def test_verify_model_dir_custom_schema_mismatch_still_raises_with_correct_head(
    tmp_path: Path,
) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    _schema_sha, head_sha = _populate_model_dir(model_dir)
    spec = _make_fake_spec(schema_sha256="f" * 64, head_sha256=head_sha)
    with pytest.raises(RuntimeError, match=r"joint_schema_model\.py"):
        verify_model_dir(model_dir, spec, official=False)


# ###########################################################################
# E-001 / T-001: joint_module() refuses tampered schema at import time
# ###########################################################################
def test_joint_module_refuses_tampered_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ember.serving import runtime

    model_dir = tmp_path / "model"
    model_dir.mkdir()
    schema_content = b"# legitimate schema\ndef systemone(): pass\n"
    schema_sha = _sha256_of(schema_content)
    head_content = b"fake head"
    head_sha = _sha256_of(head_content)
    _populate_model_dir(model_dir, schema_content, head_content)
    (model_dir / "joint_schema_model.py").write_bytes(b"import os; os.system('id')")
    spec = _make_fake_spec(schema_sha256=schema_sha, head_sha256=head_sha)
    monkeypatch.setattr(runtime, "_JOINT_MODULE", None)
    sys.modules.pop("joint_schema_model", None)
    with pytest.raises(RuntimeError, match=r"joint_schema_model\.py"):
        runtime.joint_module(model_dir, spec=spec)


def test_joint_module_accepts_correct_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ember.serving import runtime

    model_dir = tmp_path / "model"
    model_dir.mkdir()
    schema_content = b"# schema\ndef systemone(): pass\n"
    schema_sha = _sha256_of(schema_content)
    head_content = b"fake head"
    head_sha = _sha256_of(head_content)
    _populate_model_dir(model_dir, schema_content, head_content)
    spec = _make_fake_spec(schema_sha256=schema_sha, head_sha256=head_sha)
    monkeypatch.setattr(runtime, "_JOINT_MODULE", None)
    sys.modules.pop("joint_schema_model", None)
    module = runtime.joint_module(model_dir, spec=spec)
    assert module is not None
    path_str = str(model_dir.resolve())
    if path_str in sys.path:
        sys.path.remove(path_str)
    sys.modules.pop("joint_schema_model", None)
    monkeypatch.setattr(runtime, "_JOINT_MODULE", None)


# ###########################################################################
# _classify_dir: official vs custom classification
# ###########################################################################
def test_classify_dir_returns_official_when_dir_matches_resolve_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ember import models
    from ember.serving import runtime

    flash_spec = REGISTRY["flash"]
    monkeypatch.setattr(
        models,
        "resolve_dir",
        lambda name, override=True: tmp_path if name == "flash" else None,
    )
    returned_spec, official = runtime._classify_dir(tmp_path, hint=None)
    assert official is True
    assert returned_spec is flash_spec


def test_classify_dir_returns_false_for_custom_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ember import models
    from ember.serving import runtime

    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    monkeypatch.setattr(models, "resolve_dir", lambda name, override=True: None)
    _spec, official = runtime._classify_dir(custom_dir, hint=None)
    assert official is False


def test_classify_dir_returns_hint_spec_when_provided_and_official(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ember import models
    from ember.serving import runtime

    hint = _make_fake_spec(schema_sha256="a" * 64, head_sha256="b" * 64)
    monkeypatch.setattr(models, "resolve_dir", lambda name, override=True: tmp_path)
    returned_spec, official = runtime._classify_dir(tmp_path, hint=hint)
    assert official is True
    assert returned_spec is hint


def test_classify_dir_returns_hint_spec_when_provided_and_custom(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ember import models
    from ember.serving import runtime

    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    hint = _make_fake_spec(schema_sha256="c" * 64, head_sha256="d" * 64)
    monkeypatch.setattr(models, "resolve_dir", lambda name, override=True: None)
    returned_spec, official = runtime._classify_dir(custom_dir, hint=hint)
    assert official is False
    assert returned_spec is hint


def test_classify_dir_degrades_gracefully_when_resolve_dir_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ember import models
    from ember.serving import runtime

    def _raise(name: str, override: bool = True) -> None:
        raise RuntimeError("no weights")

    monkeypatch.setattr(models, "resolve_dir", _raise)
    _spec, official = runtime._classify_dir(tmp_path, hint=None)
    assert official is False


# ###########################################################################
# Engine: spec stored and threaded through advise
# ###########################################################################
def test_engine_stores_spec_on_instance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ember.serving import runtime

    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_bytes(b"{}")
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))
    spec = _make_fake_spec(schema_sha256="e" * 64, head_sha256="f" * 64)
    engine = runtime.Engine(model_dir, spec=spec)
    assert engine._spec is spec


def test_engine_stores_none_spec_when_not_provided(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ember.serving import runtime

    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_bytes(b"{}")
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))
    engine = runtime.Engine(model_dir)
    assert engine._spec is None


def test_engine_advise_passes_spec_to_joint_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ember.serving import runtime

    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_bytes(b"{}")
    monkeypatch.setattr(runtime, "load_clef", lambda *a, **kw: (object(), object()))
    spec = _make_fake_spec(schema_sha256="1" * 64, head_sha256="2" * 64)
    engine = runtime.Engine(model_dir, spec=spec)

    captured: dict[str, object] = {}

    def _fake_joint_module(md: Path, spec: object = None) -> object:
        captured["spec"] = spec
        fake_mod = type(
            "M",
            (),
            {
                "systemone": lambda *a, **kw: {
                    "answers": {},
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                }
            },
        )()
        return fake_mod

    monkeypatch.setattr(runtime, "joint_module", _fake_joint_module)
    engine.advise("state", {})
    assert captured["spec"] is spec


# ###########################################################################
# Registry: exact pinned hash values (regression guard)
# ###########################################################################
def test_registry_flash_head_sha256_exact_pin() -> None:
    assert (
        REGISTRY["flash"].head_sha256
        == "19cdcec8c81dc9212be320fff47462ab342fbc1278be4368fb3da71241cf5ba0"
    )


def test_registry_full_head_sha256_exact_pin() -> None:
    assert (
        REGISTRY["full"].head_sha256
        == "a010ac04f078e699988e4049cbea5e62c962393f59fec366640b64e8d69a4953"
    )


def test_registry_flash_schema_sha256_exact_pin() -> None:
    assert (
        REGISTRY["flash"].schema_sha256
        == "0e304cf7c6500e8bb59bef7e2afd2c6373f82596dfb3b57d1aa93c175e2dc3a3"
    )


def test_registry_full_schema_sha256_exact_pin() -> None:
    assert (
        REGISTRY["full"].schema_sha256
        == "0e304cf7c6500e8bb59bef7e2afd2c6373f82596dfb3b57d1aa93c175e2dc3a3"
    )
