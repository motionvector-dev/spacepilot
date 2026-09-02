import sys
import os
import asyncio
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from spacepilot.mcp_server import (
    mcp,
    spacepilot_decompose_storyboard,
    spacepilot_list_model_recipes,
)

# Five tools used to live here as one-line stubs: generate_video, extend_video,
# generate_audio, generate_music and get_render_status. Their tests asserted the
# fabricated values — test_pluto_get_render_status pinned status == "completed"
# for a job id that never existed — so the suite certified the lie rather than
# catching it. The tools are gone; see the deliberately-absent block at the end
# of spacepilot/mcp_server.py.
FABRICATORS = {
    "spacepilot_generate_video",
    "spacepilot_extend_video",
    "spacepilot_generate_audio",
    "spacepilot_generate_music",
    "spacepilot_get_render_status",
}


def test_mcp_registers_only_spacepilot_names():
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert names
    assert all(name.startswith("spacepilot_") for name in names)
    assert not any(name.startswith("pluto_") for name in names)
    assert "spacepilot_check" in names
    assert "spacepilot_measurements" in names
    assert "spacepilot_system_summary" in names


def test_no_tool_returns_a_job_id_for_work_it_never_started():
    """The stubs answered any caller with a plausible id and a fixed status.

    get_render_status was the worst: "completed" for ANY job id, including one
    that never existed, so a polling agent could never learn otherwise. The real
    work exists over HTTP in routes/generate.py and routes/audio.py — these
    tools simply never called it.
    """
    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert names, "list_tools() returned nothing — this assertion proves nothing"
    assert not (names & FABRICATORS)

    import spacepilot.mcp_server as server
    for name in FABRICATORS:
        assert not hasattr(server, name), f"{name} is still importable"
        alias = "pluto_" + name[len("spacepilot_"):]
        assert not hasattr(server, alias), f"{alias} alias survives the removal"


def test_spacepilot_decompose_storyboard():
    result = spacepilot_decompose_storyboard(script="Cosmic voyage across the multiverse", scene_count=6)
    assert result["status"] == "success"
    assert len(result["scenes"]) == 6


def test_model_recipes_mcp_carries_caveats():
    result = spacepilot_list_model_recipes()
    assert result["status"] == "success"
    distil = next(r for r in result["recipes"] if r["recipe_id"] == "distil-large-v3-ggml")
    assert distil["caveats"][0]["capability"] == "audio.transcription"
    assert distil["caveats"][0]["provenance"] == "declared"
