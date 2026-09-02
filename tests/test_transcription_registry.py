"""Caveats make an optimisation's capability trade-offs machine-readable."""

import json
from pathlib import Path

import pytest

from spacepilot.model_registry import (
    CAVEAT_CAPABILITIES,
    CAVEAT_PROVENANCES,
    CAVEAT_STATUSES,
    RegistryError,
    parse_model,
    registry,
)
from spacepilot.runtimes import runtimes

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
    bad = _model({"caveats": [{
        "capability": "audio.word-timestamps", "status": "degraded", "provenance": "declared",
    }]})
    with pytest.raises(RegistryError, match="what the effect is"):
        parse_model(bad, "bad.yaml")


def test_an_unknown_caveat_status_is_rejected():
    bad = _model({"caveats": [
        {"capability": "audio.word-timestamps", "status": "probably fine", "detail": "d",
         "provenance": "declared"}]})
    with pytest.raises(RegistryError, match="not one of"):
        parse_model(bad, "bad.yaml")


def test_preserved_is_not_counted_as_a_compromise():
    m = parse_model(_model({"caveats": [
        {"capability": "audio.word-timestamps", "status": "preserved", "detail": "d",
         "provenance": "declared"},
        {"capability": "audio.transcription-accuracy", "status": "degraded", "detail": "under 1%",
         "provenance": "measured", "metric": "WER", "method": "GGML q5_1"},
    ]}), "ok.yaml")
    v = m.variants[0]
    assert v.compromised == ["audio.transcription-accuracy"]
    assert [c.is_safe for c in v.caveats] == [True, False]
    assert v.caveats[1].metric == "WER"
    assert v.caveats[1].method == "GGML q5_1"


def test_caveat_provenance_is_required_and_validated():
    missing = _model({"caveats": [{
        "capability": "audio.transcription", "status": "preserved", "detail": "d",
    }]})
    with pytest.raises(RegistryError, match="provenance"):
        parse_model(missing, "missing.yaml")

    bad = _model({"caveats": [{
        "capability": "audio.transcription", "status": "preserved", "detail": "d",
        "provenance": "probably fine",
    }]})
    with pytest.raises(RegistryError, match="not one of"):
        parse_model(bad, "bad.yaml")


def test_caveat_capabilities_are_canonicalized_and_unknown_ones_are_refused():
    parsed = parse_model(_model({"caveats": [{
        "capability": "word_timestamps", "status": "preserved", "detail": "d",
        "provenance": "inferred",
    }]}), "alias.yaml")
    assert parsed.variants[0].caveats[0].capability == "audio.word-timestamps"

    bad = _model({"caveats": [{
        "capability": "audio.unknown", "status": "preserved", "detail": "d",
        "provenance": "declared",
    }]})
    with pytest.raises(RegistryError, match="capability"):
        parse_model(bad, "bad.yaml")


def test_every_caveat_in_the_registry_says_what_it_costs():
    for v in registry().variants:
        for c in v.caveats:
            assert c.status in CAVEAT_STATUSES
            assert c.provenance in CAVEAT_PROVENANCES
            assert c.capability in CAVEAT_CAPABILITIES
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


def test_distil_ggml_transcription_claim_is_sourceable_and_exact():
    distil = registry().variant("distil-large-v3-ggml")
    assert len(distil.caveats) == 1
    transcription = distil.caveats[0]
    assert transcription.capability == "audio.transcription"
    assert transcription.status == "preserved"
    assert transcription.provenance == "declared"
    assert "huggingface.co/distil-whisper/distil-large-v3-ggml" in transcription.detail
    assert "2026-08-25" in transcription.detail


def test_registry_does_not_claim_unmeasured_word_timestamp_quality():
    assert not any(
        c.capability == "audio.word-timestamps"
        for v in registry().variants
        for c in v.caveats
    )


def test_caveats_reach_the_page():
    """The public page has no server behind it, so an unexported caveat is a
    caveat nobody reads."""
    data = json.loads((ROOT / "web" / "registry.json").read_text())
    variants = [v for m in data["models"] for v in m["variants"]]
    distil = next(v for v in variants if v["id"] == "distil-large-v3-ggml")
    assert distil["compromised"] == []
    assert distil["caveats"] == [{
        "capability": "audio.transcription",
        "status": "preserved",
        "provenance": "declared",
        "metric": "long-form WER (English)",
        "method": "GGML f16 conversion",
        "detail": distil["caveats"][0]["detail"],
        "is_safe": True,
    }]
    assert "${v.caveats" in (ROOT / "web" / "models.html").read_text(), (
        "registry.json carries caveats that models.html never renders")
