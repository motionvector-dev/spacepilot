"""MCP and HTTP describe the same calls, so they must accept the same inputs.

The MCP tool for storyboard decomposition declared "Number of scenes (4-10)"
in its docstring and validated nothing.  A caller asking for 50 got 10 back
labelled ``"status": "success"``, with no signal that its request had been
changed; the same body over HTTP was a 422.  These tests drive both surfaces
with the same values and fail if the two ever disagree again.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from spacepilot.api.deps import require_token
from spacepilot.mcp_server import spacepilot_decompose_storyboard
from spacepilot.web_api import app


SCENE_COUNTS = [-1, 0, 1, 3, 4, 5, 6, 10, 11, 50]
DURATIONS = [0.0, 1.0, 9.9, 10.0, 60.0, 300.0, 300.1, 10_000.0]


@pytest.fixture(autouse=True)
def _stub_decomposer(monkeypatch):
    """Neither surface should reach a network provider to answer a bad request."""

    def _fake(script, target_duration_sec=60.0, scene_count=6, style="cinematic",
              model="gemini-3.7-flash", character_seed=None):
        return {"status": "success", "scene_count": scene_count,
                "target_duration_sec": target_duration_sec}

    monkeypatch.setattr("spacepilot.storyboard_decomposer.decompose_storyboard", _fake)
    monkeypatch.setattr("spacepilot.api.routes.storyboard.decompose_storyboard", _fake)


@pytest.fixture
def client():
    app.dependency_overrides[require_token] = lambda: None
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(require_token, None)


def _http_rejected(client, **body) -> bool:
    response = client.post("/api/storyboard/decompose", json={"script": "a story", **body})
    assert response.status_code in (200, 422), response.text
    return response.status_code == 422


def _mcp_rejected(result: dict) -> bool:
    return result.get("status") == "error"


@pytest.mark.parametrize("scene_count", SCENE_COUNTS)
def test_mcp_and_http_accept_the_same_scene_counts(client, scene_count):
    http = _http_rejected(client, scene_count=scene_count)
    result = spacepilot_decompose_storyboard(script="a story", scene_count=scene_count)
    assert _mcp_rejected(result) == http, (
        f"scene_count={scene_count}: HTTP {'rejected' if http else 'accepted'} it, "
        f"MCP answered {result}"
    )


@pytest.mark.parametrize("duration", DURATIONS)
def test_mcp_and_http_accept_the_same_durations(client, duration):
    http = _http_rejected(client, target_duration_sec=duration)
    result = spacepilot_decompose_storyboard(script="a story", target_duration_sec=duration)
    assert _mcp_rejected(result) == http, (
        f"target_duration_sec={duration}: HTTP {'rejected' if http else 'accepted'} it, "
        f"MCP answered {result}"
    )


@pytest.mark.parametrize("scene_count", [0, 3, 11, 50])
def test_a_refused_scene_count_names_the_field_and_its_bounds(scene_count):
    result = spacepilot_decompose_storyboard(script="a story", scene_count=scene_count)
    assert result["status"] == "error"
    message = result["message"]
    assert "scene_count" in message
    assert "4" in message and "10" in message, message


def test_mcp_never_answers_with_a_scene_count_the_caller_did_not_ask_for():
    """Silent clamping is the specific failure: 3 came back as 4, 50 as 10."""
    for asked in (4, 6, 10):
        result = spacepilot_decompose_storyboard(script="a story", scene_count=asked)
        assert result["scene_count"] == asked
    for asked in (3, 0, 50):
        result = spacepilot_decompose_storyboard(script="a story", scene_count=asked)
        assert "scene_count" not in result, (
            f"asked for {asked} and got a scene_count back instead of a refusal: {result}"
        )


def test_the_lora_tool_refuses_a_rank_http_refuses():
    """`rank` must be a positive power of two on both surfaces."""
    from spacepilot.mcp_server import spacepilot_train_lora

    result = spacepilot_train_lora(
        name="x", base_model="m", image_paths=["a.png"], trigger_word="t", rank=17,
    )
    assert result["status"] == "error"
    assert "rank" in result["message"]
