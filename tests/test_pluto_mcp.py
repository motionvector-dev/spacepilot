import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from src.pluto_mcp_server import (
    pluto_generate_video,
    pluto_extend_video,
    pluto_generate_audio,
    pluto_generate_music,
    pluto_get_render_status,
    pluto_get_fleet_status,
    get_ltx25_model_info,
    get_voice_catalogue
)

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

def test_pluto_get_fleet_status():
    result = pluto_get_fleet_status()
    assert "vram_usage" in result
    assert "instances" in result
    assert result["status"] == "healthy"

def test_get_ltx25_model_info():
    result = get_ltx25_model_info()
    assert "Float8" in result
    assert "48GB" in result
    assert "24fps" in result

def test_get_voice_catalogue():
    result = get_voice_catalogue()
    assert "af_heart" in result
    import json
    data = json.loads(result)
    assert len(data) == 10
