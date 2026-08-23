#!/usr/bin/env python3
"""Unit tests for SpacePilot Gemini Storyboard & Script Decomposer."""

import pytest
from spacepilot.storyboard_decomposer import (
    decompose_storyboard,
    decompose_script_rule_based,
    call_gemini_decompose_api,
    CAMERA_MOTIONS,
    SHOT_TYPES,
)


def test_storyboard_rule_based_decomposition():
    script = (
        "Opening on a solitary astronaut standing atop a lunar crater at dawn. "
        "The lunar dust begins to levitate in zero gravity. "
        "A portal of iridescent blue light opens across the horizon. "
        "The astronaut steps forward through the event horizon into hyperspace."
    )
    result = decompose_script_rule_based(
        script=script,
        target_duration_sec=60.0,
        scene_count=6,
        style="cinematic sci-fi",
    )
    assert result["status"] == "success"
    assert result["scene_count"] == 6
    assert len(result["scenes"]) == 6
    assert abs(result["total_duration_sec"] - 60.0) < 0.1

    # Check scene fields and camera vectors
    for idx, scene in enumerate(result["scenes"]):
        assert scene["scene_idx"] == idx + 1
        assert "prompt" in scene
        assert len(scene["prompt"]) > 20
        assert "camera_vector" in scene
        vec = scene["camera_vector"]
        assert all(k in vec for k in ("pan", "tilt", "zoom", "roll", "orbit"))
        assert scene["character_seed"] == result["character_seed"]


def test_storyboard_custom_scene_counts():
    for count in [4, 7, 8, 10]:
        res = decompose_script_rule_based(
            script="A high speed cyberpunk drone chase through neo-shanghai.",
            target_duration_sec=40.0,
            scene_count=count,
        )
        assert len(res["scenes"]) == count
        assert abs(res["total_duration_sec"] - 40.0) < 0.1


def test_decompose_storyboard_unified_fallback(monkeypatch):
    # Test that when Gemini API is unconfigured or fails, fallback succeeds seamlessly
    monkeypatch.setenv("GEMINI_PRIMARY_API_KEY", "")
    monkeypatch.setenv("GEMINI_SECONDARY_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "")

    res = decompose_storyboard(
        script="A deep sea exploration vessel encounters a bioluminescent leviathan.",
        target_duration_sec=50.0,
        scene_count=5,
    )
    assert res["status"] == "success"
    assert len(res["scenes"]) == 5
