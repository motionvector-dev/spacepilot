"""Transcription entries, and the caveat field they made necessary.

`license.restrictions` exists because "SOTA but you may not ship it" is a fact
about a model that no size or speed number can carry. `caveats` is the same
idea one layer down: a derived build can keep one capability and lose another,
and distil-whisper is the case that proves it — its word timestamps were never
trained, so it is right for subtitles and wrong for cutting filler words, and
nothing else in the schema can say that.
"""

import json
from pathlib import Path

import pytest

from spacepilot.pluto.registry import CAVEAT_STATUSES, RegistryError, parse_model, registry
from spacepilot.pluto.runtimes import runtimes

ROOT = Path(__file__).resolve().parent.parent


def _model(variant: dict) -> dict:
    return {
        "schema": 1, "id": "x", "name": "X", "family": "f", "kind": "transcription",
        "license": {"id": "mit", "open_source": True},
        "variants": [{
            "id": "x-1", "name": "X 1", "repo": "a/b", "backends": ["cpu"],
            "download": {"value": 1, "source": "huggingface-api", "checked": "2026-08-23"},
            "working_set": {"value": 1, "source": "estimated", "note": "n"},
            **variant,
        }],
    }


def test_a_caveat_without_its_effect_is_rejected():
    """A bare status says something changed and not whether it matters."""
    bad = _model({"caveats": [{"capability": "word_timestamps", "status": "degraded"}]})
    with pytest.raises(RegistryError, match="what the effect is"):
        parse_model(bad, "bad.yaml")


def test_an_unknown_caveat_status_is_rejected():
    bad = _model({"caveats": [
        {"capability": "word_timestamps", "status": "probably fine", "detail": "d"}]})
    with pytest.raises(RegistryError, match="not one of"):
        parse_model(bad, "bad.yaml")


def test_preserved_is_not_counted_as_a_compromise():
    m = parse_model(_model({"caveats": [
        {"capability": "word_timestamps", "status": "preserved", "detail": "d"},
        {"capability": "wer", "status": "degraded", "detail": "under 1%"},
    ]}), "ok.yaml")
    v = m.variants[0]
    assert v.compromised == ["wer"]
    assert [c.is_safe for c in v.caveats] == [True, False]


def test_every_caveat_in_the_registry_says_what_it_costs():
    for v in registry().variants:
        for c in v.caveats:
            assert c.status in CAVEAT_STATUSES
            assert c.detail.strip(), f"{v.id}: caveat on {c.capability} with no detail"


def test_the_registry_can_transcribe_something():
    """The gap this file closes: 17 models and no way to turn speech into text."""
    variants = registry().by_kind("transcription")
    assert variants, "no transcription model in the registry"
    assert any("transcription" in r.serves for r in runtimes().values())
    assert any("vad" in r.serves for r in runtimes().values()), (
        "silence trimming needs a VAD, which is not transcription and not generation")


def test_whisper_cpp_names_models_that_exist():
    whisper_cpp = runtimes()["whisper-cpp"]
    for model_id in whisper_cpp.runs:
        assert registry().model(model_id), f"whisper-cpp claims to run {model_id}, which is not here"


def test_the_dtw_trap_travels_with_the_runtime():
    """`--dtw` silently does nothing without `-nfa`: flash attention is on by
    default and disables it. A user hits this once and loses a day."""
    notes = runtimes()["whisper-cpp"].notes or ""
    assert "-nfa" in notes and "dtw" in notes.lower()


def test_quantisation_preserved_the_timestamps_and_distillation_did_not():
    """The distinction the field exists for.

    whisper.cpp computes timestamps in its own decoder logic, so a quantised
    build aligns as well as f16. distil-whisper distilled only segment-level
    output, so its word timestamps are inherited and unvalidated. Both are
    "the small fast one" to a reader skimming sizes.
    """
    quantised = registry().variant("whisper-base-en-q5-1")
    assert any(c.capability == "word_timestamps" and c.status == "preserved"
               for c in quantised.caveats)

    distil = registry().variant("distil-large-v3-ggml")
    word = next(c for c in distil.caveats if c.capability == "word_timestamps")
    assert word.status == "untrained"
    assert "word_timestamps" in distil.compromised


def test_caveats_reach_the_page():
    """The public page has no server behind it, so an unexported caveat is a
    caveat nobody reads."""
    data = json.loads((ROOT / "web" / "registry.json").read_text())
    variants = [v for m in data["models"] for v in m["variants"]]
    distil = next(v for v in variants if v["id"] == "distil-large-v3-ggml")
    assert distil["compromised"] == ["word_timestamps"]
    assert any(c["status"] == "untrained" and c["detail"] for c in distil["caveats"])
    assert "${v.caveats" in (ROOT / "web" / "models.html").read_text(), (
        "registry.json carries caveats that models.html never renders")
