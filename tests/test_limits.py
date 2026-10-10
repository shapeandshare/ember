"""Unit tests for ember.serving.limits: the effective maximum and per-request cap."""

from __future__ import annotations

import dataclasses
import json
import logging
import subprocess
import sys

import pytest
from ember import models
from ember.cfg import paths
from ember.serving.governing_limit import GoverningLimit
from ember.serving.limit_source import LimitSource
from ember.serving.limits import (
    FALLBACK_MAX_LENGTH,
    Limits,
    declared_max_length,
    default_request_cap,
    from_config,
    model_max_length,
    resolve,
)
from pydantic import ValidationError

DECLARED = 262144


def _limits(**overrides: object) -> Limits:
    fields: dict[str, object] = {
        "max_length": DECLARED,
        "max_length_source": LimitSource.MODEL,
        "max_request_length": 32768,
        "max_request_length_source": LimitSource.FALLBACK,
    }
    fields.update(overrides)
    return Limits(**fields)


def _measure(monkeypatch, name: str, cap: int | None) -> None:
    spec = models.REGISTRY[name]
    monkeypatch.setitem(
        models.REGISTRY, name, dataclasses.replace(spec, max_request_length=cap)
    )


def _fallback(monkeypatch, name: str, cap: int) -> None:
    spec = models.REGISTRY[name]
    monkeypatch.setitem(
        models.REGISTRY, name, dataclasses.replace(spec, fallback_request_length=cap)
    )


def _model_dir(tmp_path, max_position_embeddings: int = DECLARED):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(
        json.dumps(
            {"text_config": {"max_position_embeddings": max_position_embeddings}}
        )
    )
    return model_dir


@pytest.fixture
def isolated_config(monkeypatch, tmp_path):
    """An empty config file, no limit env vars, and no measured registry caps."""
    monkeypatch.setattr(paths, "config_path", lambda: tmp_path / "config.json")
    for name in ("EMBER_MAX_LENGTH", "EMBER_MAX_REQUEST_LENGTH", "EMBER_MODEL_DIR"):
        monkeypatch.delenv(name, raising=False)
    for name in models.REGISTRY:
        _measure(monkeypatch, name, None)


# ###########################################################################
# (a) enums
# ###########################################################################
def test_limit_source_members_and_values():
    assert {member.name: member.value for member in LimitSource} == {
        "MODEL": "model",
        "FALLBACK": "fallback",
        "OPERATOR": "operator",
        "MEASURED": "measured",
    }


def test_governing_limit_members_and_values():
    assert {member.name: member.value for member in GoverningLimit} == {
        "CAP": "cap",
        "MAXIMUM": "maximum",
    }


# ###########################################################################
# (b) Limits field rules
# ###########################################################################
def test_limits_is_frozen():
    limits = _limits()
    with pytest.raises(ValidationError):
        limits.max_length = 1


def test_limits_rejects_a_max_length_below_one():
    with pytest.raises(ValidationError):
        _limits(max_length=0)


@pytest.mark.parametrize(
    "source", [LimitSource.MODEL, LimitSource.FALLBACK, LimitSource.OPERATOR]
)
def test_limits_accepts_each_max_length_source(source):
    assert _limits(max_length_source=source).max_length_source is source


def test_limits_rejects_a_measured_max_length_source():
    with pytest.raises(ValidationError):
        _limits(max_length_source=LimitSource.MEASURED)


def test_limits_rejects_a_negative_cap():
    with pytest.raises(ValidationError):
        _limits(max_request_length=-1, max_request_length_source=LimitSource.OPERATOR)


@pytest.mark.parametrize(
    "source", [LimitSource.MEASURED, LimitSource.FALLBACK, LimitSource.OPERATOR]
)
def test_limits_accepts_each_cap_source(source):
    assert _limits(max_request_length_source=source).max_request_length_source is source


def test_limits_rejects_a_model_cap_source():
    with pytest.raises(ValidationError):
        _limits(max_request_length_source=LimitSource.MODEL)


def test_a_disabled_cap_must_come_from_the_operator():
    with pytest.raises(ValidationError):
        _limits(max_request_length=0, max_request_length_source=LimitSource.FALLBACK)
    disabled = _limits(
        max_request_length=0, max_request_length_source=LimitSource.OPERATOR
    )
    assert disabled.max_request_length == 0


# ###########################################################################
# (c) enforced and governing
# ###########################################################################
def test_enforced_is_the_smaller_limit_when_the_cap_is_enabled():
    assert _limits(max_length=65536, max_request_length=32768).enforced == 32768
    assert _limits(max_length=16384, max_request_length=32768).enforced == 16384


def test_enforced_is_the_maximum_when_the_cap_is_disabled():
    disabled = _limits(
        max_request_length=0, max_request_length_source=LimitSource.OPERATOR
    )
    assert disabled.enforced == DECLARED


def test_the_cap_governs_when_enabled_and_not_above_the_maximum():
    below = _limits(max_length=65536, max_request_length=32768)
    equal = _limits(max_length=32768, max_request_length=32768)
    assert below.governing is GoverningLimit.CAP
    assert equal.governing is GoverningLimit.CAP


def test_the_maximum_governs_when_the_cap_is_disabled_or_larger():
    disabled = _limits(
        max_request_length=0, max_request_length_source=LimitSource.OPERATOR
    )
    larger = _limits(max_length=16384, max_request_length=32768)
    assert disabled.governing is GoverningLimit.MAXIMUM
    assert larger.governing is GoverningLimit.MAXIMUM


# ###########################################################################
# (d) resolution table (contracts/config.md)
# ###########################################################################
def test_unset_values_use_the_declared_maximum_and_the_measured_cap(monkeypatch):
    _measure(monkeypatch, "flash", 8192)
    limits = resolve(DECLARED, "flash")
    assert limits == Limits(
        max_length=DECLARED,
        max_length_source=LimitSource.MODEL,
        max_request_length=8192,
        max_request_length_source=LimitSource.MEASURED,
    )


def test_an_unreadable_config_and_an_unmeasured_model_fall_back(monkeypatch):
    _measure(monkeypatch, "flash", None)
    _fallback(monkeypatch, "flash", 20480)
    limits = resolve(None, "flash")
    assert limits == Limits(
        max_length=FALLBACK_MAX_LENGTH,
        max_length_source=LimitSource.FALLBACK,
        max_request_length=20480,
        max_request_length_source=LimitSource.FALLBACK,
    )
    assert FALLBACK_MAX_LENGTH == 32768


def test_a_model_outside_the_registry_gets_the_lowest_measured_cap(monkeypatch):
    _measure(monkeypatch, "flash", 16384)
    _measure(monkeypatch, "full", 8192)
    limits = resolve(DECLARED, None)
    assert (limits.max_length, limits.max_length_source) == (
        DECLARED,
        LimitSource.MODEL,
    )
    assert (limits.max_request_length, limits.max_request_length_source) == (
        8192,
        LimitSource.FALLBACK,
    )


def test_a_model_outside_the_registry_gets_the_lowest_fallback(monkeypatch):
    _measure(monkeypatch, "flash", None)
    _measure(monkeypatch, "full", None)
    _fallback(monkeypatch, "flash", 24576)
    _fallback(monkeypatch, "full", 12288)
    limits = resolve(DECLARED, None)
    assert (limits.max_request_length, limits.max_request_length_source) == (
        12288,
        LimitSource.FALLBACK,
    )


def test_a_model_outside_the_registry_counts_unmeasured_fallbacks(monkeypatch):
    _measure(monkeypatch, "flash", 16384)
    _measure(monkeypatch, "full", None)
    _fallback(monkeypatch, "full", 8192)
    limits = resolve(DECLARED, None)
    assert (limits.max_request_length, limits.max_request_length_source) == (
        8192,
        LimitSource.FALLBACK,
    )


def test_an_operator_maximum_within_the_declared_maximum_is_used():
    limits = resolve(DECLARED, "flash", max_length=1024)
    assert (limits.max_length, limits.max_length_source) == (
        1024,
        LimitSource.OPERATOR,
    )


def test_an_operator_maximum_above_the_declared_maximum_is_clamped(caplog):
    with caplog.at_level(logging.WARNING):
        limits = resolve(4096, "flash", max_length=65536)
    assert (limits.max_length, limits.max_length_source) == (4096, LimitSource.MODEL)
    assert "65536" in caplog.text
    assert "4096" in caplog.text


def test_an_operator_maximum_is_used_as_given_when_the_declared_is_unknown():
    limits = resolve(None, "flash", max_length=65536)
    assert (limits.max_length, limits.max_length_source) == (
        65536,
        LimitSource.OPERATOR,
    )


def test_an_operator_cap_is_used(monkeypatch):
    _measure(monkeypatch, "flash", 8192)
    limits = resolve(DECLARED, "flash", max_request_length=16384)
    assert (limits.max_request_length, limits.max_request_length_source) == (
        16384,
        LimitSource.OPERATOR,
    )


def test_a_zero_maximum_means_the_declared_maximum():
    limits = resolve(DECLARED, "flash", max_length=0)
    assert (limits.max_length, limits.max_length_source) == (
        DECLARED,
        LimitSource.MODEL,
    )


def test_a_zero_cap_disables_the_cap():
    limits = resolve(DECLARED, "flash", max_request_length=0)
    assert (limits.max_request_length, limits.max_request_length_source) == (
        0,
        LimitSource.OPERATOR,
    )
    assert limits.enforced == DECLARED


@pytest.mark.parametrize("value", [-5, "-5", "abc", 1.5, True])
def test_an_invalid_operator_maximum_is_ignored_with_a_warning(value, caplog):
    with caplog.at_level(logging.WARNING):
        limits = resolve(DECLARED, "flash", max_length=value)
    assert (limits.max_length, limits.max_length_source) == (
        DECLARED,
        LimitSource.MODEL,
    )
    assert "max_length" in caplog.text


@pytest.mark.parametrize("value", [-5, "-5", "abc", 1.5, True])
def test_an_invalid_operator_cap_is_ignored_with_a_warning(value, monkeypatch, caplog):
    _measure(monkeypatch, "flash", None)
    _fallback(monkeypatch, "flash", 20480)
    with caplog.at_level(logging.WARNING):
        limits = resolve(DECLARED, "flash", max_request_length=value)
    assert (limits.max_request_length, limits.max_request_length_source) == (
        20480,
        LimitSource.FALLBACK,
    )
    assert "max_request_length" in caplog.text


def test_integer_strings_are_operator_values():
    limits = resolve(DECLARED, "flash", max_length="1024", max_request_length="512")
    assert (limits.max_length, limits.max_request_length) == (1024, 512)


# ###########################################################################
# (e) default_request_cap and the registry
# ###########################################################################
def test_default_request_cap_uses_each_models_own_fallback_until_measured(monkeypatch):
    _measure(monkeypatch, "flash", None)
    _measure(monkeypatch, "full", None)
    _fallback(monkeypatch, "flash", 20480)
    _fallback(monkeypatch, "full", 12288)
    assert default_request_cap("flash") == (20480, LimitSource.FALLBACK)
    assert default_request_cap("full") == (12288, LimitSource.FALLBACK)


def test_default_request_cap_uses_the_measured_value(monkeypatch):
    _measure(monkeypatch, "flash", 12288)
    assert default_request_cap("flash") == (12288, LimitSource.MEASURED)


def test_default_request_cap_outside_the_registry(monkeypatch):
    _measure(monkeypatch, "flash", 16384)
    _measure(monkeypatch, "full", 8192)
    assert default_request_cap(None) == (8192, LimitSource.FALLBACK)
    _measure(monkeypatch, "flash", None)
    _measure(monkeypatch, "full", None)
    _fallback(monkeypatch, "flash", 24576)
    _fallback(monkeypatch, "full", 12288)
    assert default_request_cap(None) == (12288, LimitSource.FALLBACK)


def test_every_registered_model_declares_a_memory_budget_above_its_weights():
    for spec in models.REGISTRY.values():
        assert spec.memory_budget_bytes > spec.approx_bytes


def test_every_registered_model_declares_its_own_fallback():
    for spec in models.REGISTRY.values():
        assert spec.fallback_request_length >= 2048


@pytest.mark.parametrize(("name", "fallback"), [("flash", 24576), ("full", 8192)])
def test_each_model_falls_back_to_the_longest_length_its_memory_check_fit(
    name, fallback
):
    # Memory checks, 2026-10-10. The fallback must leave 4 GiB of the budget free for
    # the OS: flash peaked at 27.83 GiB at 24,576 tokens and 32.35 GiB at 32,768
    # (32 GiB budget); full at 59.54 GiB at 8,192 and 63.54 GiB at 16,384 (64 GiB).
    assert models.get(name).fallback_request_length == fallback


def test_registry_key_names_the_registry_entry(monkeypatch):
    monkeypatch.delenv("EMBER_MODEL_DIR", raising=False)
    assert models.registry_key("FLASH") == "flash"
    assert models.registry_key(None) == models.DEFAULT


def test_registry_key_is_none_when_the_model_dir_is_overridden(monkeypatch, tmp_path):
    monkeypatch.setenv("EMBER_MODEL_DIR", str(tmp_path))
    assert models.registry_key("flash") is None


# ###########################################################################
# (f) from_config
# ###########################################################################
def test_from_config_defaults(isolated_config, tmp_path):
    limits = from_config(_model_dir(tmp_path), "flash")
    assert limits == Limits(
        max_length=DECLARED,
        max_length_source=LimitSource.MODEL,
        max_request_length=models.get("flash").fallback_request_length,
        max_request_length_source=LimitSource.FALLBACK,
    )


def test_from_config_reads_an_operator_cap_from_the_environment(
    isolated_config, monkeypatch, tmp_path
):
    monkeypatch.setenv("EMBER_MAX_REQUEST_LENGTH", "16384")
    limits = from_config(_model_dir(tmp_path), "flash")
    assert (limits.max_request_length, limits.max_request_length_source) == (
        16384,
        LimitSource.OPERATOR,
    )


def test_from_config_zero_disables_the_cap(isolated_config, monkeypatch, tmp_path):
    monkeypatch.setenv("EMBER_MAX_REQUEST_LENGTH", "0")
    limits = from_config(_model_dir(tmp_path), "flash")
    assert (limits.max_request_length, limits.max_request_length_source) == (
        0,
        LimitSource.OPERATOR,
    )


@pytest.mark.parametrize("value", ["-5", "abc"])
def test_from_config_ignores_an_invalid_cap_with_a_warning(
    value, isolated_config, monkeypatch, tmp_path, caplog
):
    monkeypatch.setenv("EMBER_MAX_REQUEST_LENGTH", value)
    with caplog.at_level(logging.WARNING):
        limits = from_config(_model_dir(tmp_path), "flash")
    assert (limits.max_request_length, limits.max_request_length_source) == (
        models.get("flash").fallback_request_length,
        LimitSource.FALLBACK,
    )
    assert "max_request_length" in caplog.text.lower()


def test_from_config_reads_an_operator_maximum(isolated_config, monkeypatch, tmp_path):
    monkeypatch.setenv("EMBER_MAX_LENGTH", "1024")
    limits = from_config(_model_dir(tmp_path), "flash")
    assert (limits.max_length, limits.max_length_source) == (
        1024,
        LimitSource.OPERATOR,
    )


def test_from_config_warns_about_a_non_integer_maximum(
    isolated_config, monkeypatch, tmp_path, caplog
):
    monkeypatch.setenv("EMBER_MAX_LENGTH", "abc")
    with caplog.at_level(logging.WARNING):
        limits = from_config(_model_dir(tmp_path), "flash")
    assert (limits.max_length, limits.max_length_source) == (
        DECLARED,
        LimitSource.MODEL,
    )
    assert "EMBER_MAX_LENGTH" in caplog.text


def test_from_config_reads_the_config_file(isolated_config, tmp_path):
    paths.config_path().write_text(json.dumps({"max_request_length": 4096}))
    limits = from_config(_model_dir(tmp_path), "flash")
    assert (limits.max_request_length, limits.max_request_length_source) == (
        4096,
        LimitSource.OPERATOR,
    )


def test_from_config_without_a_model_dir_falls_back(isolated_config):
    limits = from_config(None, "flash")
    assert (limits.max_length, limits.max_length_source) == (
        FALLBACK_MAX_LENGTH,
        LimitSource.FALLBACK,
    )


# ###########################################################################
# (g) declared_max_length and model_max_length
# ###########################################################################
def test_declared_max_length_is_none_without_a_config(tmp_path):
    assert declared_max_length(tmp_path / "missing") is None


def test_declared_max_length_is_none_for_unreadable_json(tmp_path):
    (tmp_path / "config.json").write_text("not json")
    assert declared_max_length(tmp_path) is None


def test_declared_max_length_reads_text_config(tmp_path):
    assert declared_max_length(_model_dir(tmp_path, 4096)) == 4096


def test_declared_max_length_is_none_when_not_positive(tmp_path):
    assert declared_max_length(_model_dir(tmp_path, 0)) is None


# Moved from tests/test_runtime_unit.py (Article XI §11.3: move, never delete).
def test_model_max_length_reads_text_config(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(
        json.dumps({"text_config": {"max_position_embeddings": 4096}})
    )
    assert model_max_length(model_dir) == 4096


def test_model_max_length_reads_top_level_config(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(
        json.dumps({"max_position_embeddings": 8192})
    )
    assert model_max_length(model_dir) == 8192


def test_model_max_length_falls_back_without_a_config(tmp_path):
    assert model_max_length(tmp_path / "missing") == FALLBACK_MAX_LENGTH


def test_model_max_length_falls_back_when_zero(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(
        json.dumps({"text_config": {"max_position_embeddings": 0}})
    )
    assert model_max_length(model_dir) == FALLBACK_MAX_LENGTH


# ###########################################################################
# (h) torch-free import
# ###########################################################################
def test_limits_import_does_not_load_torch():
    code = "import sys, ember.serving.limits; assert 'torch' not in sys.modules"
    result = subprocess.run(  # noqa: S603 - this interpreter with a literal script
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
