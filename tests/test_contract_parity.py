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
SCRIPTS = ["a story", "", "   ", "\n\t "]


def test_importing_the_mcp_server_does_not_build_settings_or_write_a_secret(tmp_path):
    """Settings' default factory mints `.studio_token` into the install tree.

    The stdio MCP server imported no config before, so it never constructed
    Settings at all.  Reading the version from there would have written a
    secret into `lib/python3.x/` under `uv tool install` — which is the bug
    #155 exists to fix.  The version comes from the package instead.
    """
    import subprocess
    import sys

    probe = (
        "import spacepilot.mcp_server as m, sys, json;"
        "print(json.dumps({"
        "'config_imported': 'spacepilot.core.config' in sys.modules,"
        "'version': m.SERVER_VERSION}))"
    )
    import os
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    env = dict(os.environ, PYTHONPATH=str(root))
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True, text=True, cwd=tmp_path, check=True, env=env,
    )
    import json as _json

    answer = _json.loads(result.stdout.strip().splitlines()[-1])
    assert answer["config_imported"] is False, (
        "spacepilot.core.config was imported, so Settings was constructible at "
        "MCP import time — that is what writes .studio_token"
    )

    from spacepilot import __version__

    assert answer["version"] == __version__


def test_the_package_version_is_declared_in_exactly_one_place():
    """The PR body claimed "the one place that holds it"; make that true."""
    import tomllib
    from pathlib import Path

    from spacepilot import __version__
    from spacepilot.core.config import get_settings

    pyproject = tomllib.loads(
        (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text()
    )
    assert "version" not in pyproject["project"], (
        "pyproject pins its own copy of the version; make it dynamic from "
        "spacepilot.__version__"
    )
    assert get_settings().version == __version__


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


def _http_rejected_script(client, script: str) -> bool:
    response = client.post("/api/storyboard/decompose", json={"script": script})
    assert response.status_code in (200, 400, 422), response.text
    return response.status_code in (400, 422)


def _mcp_rejected(result: dict) -> bool:
    return result.get("status") == "error"


def test_every_refusal_carries_the_same_error_key(client):
    """One key a client can test to know it failed.

    This server had two error shapes: validation refusals returned
    `{"status": "error", "message": ...}` and unknown ids returned
    `{"error": ..., "known": [...]}`.  `status` stays for whatever reads it.
    """
    from spacepilot.mcp_server import spacepilot_measurements

    refusal = spacepilot_decompose_storyboard(script="a story", scene_count=50)
    assert refusal["status"] == "error"
    assert refusal["error"] == refusal["message"]

    unknown = spacepilot_measurements("no-such-variant-at-all")
    assert "error" in unknown


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


@pytest.mark.parametrize("script", SCRIPTS)
def test_mcp_and_http_accept_the_same_scripts(client, script):
    """`script.strip()` emptiness was checked in the route body, not the model.

    So MCP accepted a blank script that HTTP refused — the same split as
    scene_count, on the same endpoint.
    """
    http = _http_rejected_script(client, script)
    result = spacepilot_decompose_storyboard(script=script)
    assert _mcp_rejected(result) == http, (
        f"script={script!r}: HTTP {'rejected' if http else 'accepted'} it, "
        f"MCP answered {result}"
    )


@pytest.mark.parametrize("rank", [0, -4, 17, 100])
def test_mcp_and_http_refuse_the_same_lora_ranks(client, rank):
    """`rank` must be a positive power of two on both surfaces.

    This test used to drive MCP only, despite its name.
    """
    from spacepilot.mcp_server import spacepilot_train_lora

    body = {"name": "x", "base_model": "m", "image_paths": ["a.png"],
            "trigger_word": "t", "rank": rank}
    response = client.post("/api/lora/train", json=body)
    assert response.status_code == 422, (
        f"HTTP accepted rank={rank}: {response.status_code} {response.text}"
    )

    result = spacepilot_train_lora(**body)
    assert result["status"] == "error"
    assert "rank" in result["message"]


def test_tools_list_publishes_the_bounds_not_just_the_refusal():
    """A schema-validating client should read the range, not infer it."""
    import asyncio

    from spacepilot.api import contracts as c
    from spacepilot.mcp_server import mcp

    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}
    schema = tools["spacepilot_decompose_storyboard"].input_schema["properties"]
    assert schema["scene_count"]["minimum"] == c.SCENE_COUNT_MIN
    assert schema["scene_count"]["maximum"] == c.SCENE_COUNT_MAX
    assert schema["target_duration_sec"]["minimum"] == c.DURATION_MIN_SEC
    assert schema["target_duration_sec"]["maximum"] == c.DURATION_MAX_SEC


def test_no_clamp_survives_beneath_the_contract():
    """A `max(4, min(10, n))` under the contract is the original defect again.

    Both entrances validate now.  A clamp underneath them is invisible to the
    parity tests and silently returns something other than what was asked for
    the moment the contract's range moves.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    offenders = []
    for path in sorted(root.glob("spacepilot/**/*.py")):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(r"scene_count\s*=\s*max\s*\(.*min\s*\(", line):
                offenders.append(f"{path.relative_to(root)}:{number}: {line.strip()}")
    assert not offenders, (
        "scene_count is clamped below the validated boundary:\n" + "\n".join(offenders)
    )
