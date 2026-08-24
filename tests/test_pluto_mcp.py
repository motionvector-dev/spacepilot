import sys
import os
import asyncio
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from spacepilot.pluto_mcp_server import (
    mcp,
    pluto_generate_video,
    pluto_extend_video,
    pluto_generate_audio,
    pluto_generate_music,
    pluto_get_render_status,
    pluto_decompose_storyboard,
    pluto_list_model_recipes,
    spacepilot_generate_video,
)


def test_mcp_registers_only_spacepilot_names_but_keeps_python_pluto_aliases():
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert names
    assert all(name.startswith("spacepilot_") for name in names)
    assert not any(name.startswith("pluto_") for name in names)
    assert "spacepilot_check" in names
    assert "spacepilot_measurements" in names
    assert "spacepilot_system_summary" in names
    assert pluto_generate_video is spacepilot_generate_video

def test_pluto_generate_video():
    result = pluto_generate_video(prompt="A cinematic shot of a forest", seconds=4.0)
    assert "job_id" in result
    assert result["status"] == "processing"

def test_pluto_extend_video():
    result = pluto_extend_video(asset_id="vid-12345", prompt="Continuing the shot")
    assert "job_id" in result
    assert result["status"] == "processing"

def test_pluto_generate_audio():
    result = pluto_generate_audio(text="Hello world")
    assert "job_id" in result
    assert result["status"] == "processing"

def test_pluto_generate_music():
    result = pluto_generate_music(prompt="Epic orchestral", lyrics="")
    assert "job_id" in result
    assert result["status"] == "processing"

def test_pluto_get_render_status():
    result = pluto_get_render_status(job_id="vid-12345")
    assert result["job_id"] == "vid-12345"
    assert result["status"] == "completed"



def test_pluto_decompose_storyboard():
    result = pluto_decompose_storyboard(script="Cosmic voyage across the multiverse", scene_count=6)
    assert result["status"] == "success"
    assert len(result["scenes"]) == 6


def test_model_recipes_mcp_carries_caveats():
    result = pluto_list_model_recipes()
    assert result["status"] == "success"
    distil = next(r for r in result["recipes"] if r["recipe_id"] == "distil-large-v3-ggml")
    assert distil["caveats"][0]["capability"] == "audio.transcription"
    assert distil["caveats"][0]["provenance"] == "declared"
