"""Model-backed checks that the announced limits match the model's real encoding.

The ``flash`` fixture needs only the snapshot files (config, tokenizer,
``joint_schema_model.py``). The ``engine`` fixture loads the weights once per
module, for the refusal and boundary checks.
"""

from __future__ import annotations

import base64
import io
import os
import subprocess
import sys
import threading
import time

import pytest
from ember import models
from ember.serving import limits, media, request_size, runtime
from ember.serving.limit_source import LimitSource
from ember.serving.limits import Limits
from PIL import Image

pytestmark = pytest.mark.model

#: Qwen's tokenizer encodes this word as one token, so N repeats are N tokens.
WORD = " the"
N = 1000
DECLARED = 262144
QUESTIONS = {
    "urgent": {"type": "noul", "instructions": "Is this urgent?"},
    "team": {
        "type": "choice",
        "instructions": "Which team should handle this?",
        "criteria": {"db": "Database issues", "web": "Frontend issues"},
    },
}
KINDS = ["dict", "string", "image"]


def _model_dir(name: str):
    model_dir = models.resolve_dir(name, override=False)
    if model_dir is None:
        if name == "flash" and os.environ.get("EMBER_REQUIRE_MODEL") == "1":
            pytest.fail("model flash is not pulled (EMBER_REQUIRE_MODEL=1)")
        pytest.skip(f"model {name} is not pulled")
    return model_dir


def _png_data_uri() -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (220, 30, 30)).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def _state(kind: str, tokens: int):
    filler = WORD * tokens
    return {"service": "checkout", "log": filler} if kind == "dict" else filler


def _images(kind: str) -> list[str] | None:
    return [_png_data_uri()] if kind == "image" else None


def _limits(
    max_length: int,
    max_source: LimitSource,
    cap: int,
    cap_source: LimitSource = LimitSource.OPERATOR,
) -> Limits:
    return Limits(
        max_length=max_length,
        max_length_source=max_source,
        max_request_length=cap,
        max_request_length_source=cap_source,
    )


def _config(name: str) -> tuple[Limits, str]:
    if name == "default":
        cap, source = limits.default_request_cap("flash")
        return (
            _limits(DECLARED, LimitSource.MODEL, cap, source),
            "EMBER_MAX_REQUEST_LENGTH",
        )
    if name == "maximum 1024":
        return _limits(1024, LimitSource.OPERATOR, 0), "EMBER_MAX_LENGTH"
    return _limits(DECLARED, LimitSource.MODEL, 1024), "EMBER_MAX_REQUEST_LENGTH"


def _rss_bytes() -> int:
    out = subprocess.run(  # noqa: S603 - fixed argv, this test's own pid
        ["ps", "-o", "rss=", "-p", str(os.getpid())],  # noqa: S607 - system ps
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return int(out.strip()) * 1024


def _rss_growth_while(action) -> int:
    start = _rss_bytes()
    peak = [start]
    done = threading.Event()

    def poll() -> None:
        while not done.is_set():
            peak[0] = max(peak[0], _rss_bytes())
            done.wait(0.05)

    poller = threading.Thread(target=poll, daemon=True)
    poller.start()
    try:
        action()
    finally:
        done.set()
        poller.join()
    return peak[0] - start


@pytest.fixture(scope="module")
def flash():
    # import-placement:allow - deferred; transformers must not load at collection
    from transformers import AutoProcessor

    model_dir = _model_dir("flash")
    processor = AutoProcessor.from_pretrained(str(model_dir), local_files_only=True)
    return processor, runtime.joint_module(model_dir)


@pytest.fixture(scope="module")
def engine():
    model_dir = _model_dir("flash")
    declared = limits.declared_max_length(model_dir)
    return runtime.Engine(model_dir, limits=limits.resolve(declared, "flash"))


# ###########################################################################
# US1: the declared maximum and exact counting
# ###########################################################################
@pytest.mark.parametrize("name", ["flash", "full"])
def test_the_declared_maximum_is_the_models_window(name):
    assert limits.declared_max_length(_model_dir(name)) == DECLARED


def test_measure_counts_exactly_what_encode_record_sees(flash):
    processor, js = flash
    state = WORD * N
    assert len(processor.tokenizer(state, add_special_tokens=False).input_ids) == N
    request = {
        "model": "clef-flash",
        "state": state,
        "questions": {"urgent": {"type": "noul"}},
    }
    size = request_size.measure(js, processor, request)
    encoded = js.encode_record(
        processor.tokenizer, request, max_length=sys.maxsize, processor=processor
    )
    assert size.state == N
    assert size.total == len(encoded.input_ids)


# ###########################################################################
# US2: totals, the boundary, and refusals on the real model
# ###########################################################################
@pytest.mark.parametrize("kind", KINDS)
def test_measured_totals_match_encode_record_exactly(flash, kind):
    processor, js = flash
    request = {
        "model": "clef-flash",
        "state": _state(kind, 200),
        "questions": QUESTIONS,
    }
    if kind == "image":
        request["images"] = media.decode_images(_images(kind) or [])
    size = request_size.measure(js, processor, request)
    encoded = js.encode_record(
        processor.tokenizer, request, max_length=sys.maxsize, processor=processor
    )
    assert size.total == len(encoded.input_ids)
    assert size.state + size.media + size.fixed == size.total
    assert (size.media > 0) == (kind == "image")


def test_the_boundary_is_served_and_one_token_more_is_refused(engine, monkeypatch):
    state = _state("string", 300)
    request = {"model": engine.model_name, "state": state, "questions": QUESTIONS}
    js = runtime.joint_module(engine.model_dir)
    total = request_size.measure(js, engine.processor, request).total
    monkeypatch.setattr(engine, "limits", _limits(DECLARED, LimitSource.MODEL, total))
    assert engine.advise(state, QUESTIONS)["usage"]["input_tokens"] == total
    monkeypatch.setattr(
        engine, "limits", _limits(DECLARED, LimitSource.MODEL, total - 1)
    )
    with pytest.raises(runtime.RequestTooLargeError):
        engine.advise(state, QUESTIONS)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("config", ["default", "maximum 1024", "cap 1024"])
def test_every_over_limit_request_is_refused(engine, monkeypatch, kind, config):
    engine_limits, setting = _config(config)
    monkeypatch.setattr(engine, "limits", engine_limits)
    with pytest.raises(runtime.RequestTooLargeError) as excinfo:
        engine.advise(
            _state(kind, engine_limits.enforced + 100),
            QUESTIONS,
            images=_images(kind),
        )
    assert f"({setting})" in str(excinfo.value)


@pytest.mark.parametrize("config", ["default", "cap disabled"])
def test_a_huge_state_is_refused_quickly_without_a_memory_spike(
    engine, monkeypatch, config
):
    if config == "cap disabled":
        monkeypatch.setattr(engine, "limits", _limits(DECLARED, LimitSource.MODEL, 0))
    state = WORD * 1_000_000
    refusals: list[str] = []

    def refuse() -> None:
        with pytest.raises(runtime.RequestTooLargeError) as excinfo:
            engine.advise(state, QUESTIONS)
        refusals.append(str(excinfo.value))

    started = time.monotonic()
    growth = _rss_growth_while(refuse)
    assert time.monotonic() - started < 60
    assert growth < 2 * 2**30
    if config == "cap disabled":
        assert "(EMBER_MAX_LENGTH)" in refusals[0]
        assert refusals[0].endswith(
            "This is the model's own maximum and cannot be raised."
        )
