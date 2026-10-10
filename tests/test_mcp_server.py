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


def test_gated_tools_are_removed():
    import spacepilot.mcp_server as server

    gated_names = {
        "spacepilot_create_checkpoint",
        "spacepilot_restore_checkpoint",
        "spacepilot_list_checkpoints",
        "spacepilot_train_lora",
        "spacepilot_download_model_recipe",
    }
    tools = asyncio.run(mcp.list_tools())
    registered_names = {t.name for t in tools}

    for name in gated_names:
        assert name not in registered_names, f"{name} should not be registered in MCP tools"
        assert not hasattr(server, name), f"{name} should not be exported from spacepilot.mcp_server"


def test_spacepilot_download_weights_mcp(monkeypatch, tmp_path):
    from spacepilot.mcp_server import spacepilot_download_weights

    called = {}

    def mock_download(variant, dest_dir, stage="all", concurrency=16, download_engine=None):
        called["variant"] = variant
        called["dest_dir"] = dest_dir
        called["stage"] = stage
        return dest_dir / "weights"

    monkeypatch.setattr("spacepilot.services.model_downloader.download_weights", mock_download)

    res = spacepilot_download_weights(
        model="minimax-h3",
        stage="stage1",
        dest=str(tmp_path / "models"),
    )
    assert res["status"] == "success"
    assert res["model"] == "minimax-h3"
    assert res["stage"] == "stage1"
    assert res["dest"] == str(tmp_path / "models" / "weights")
    assert called["stage"] == "stage1"


def test_spacepilot_download_weights_mcp_default_dest(monkeypatch):
    from spacepilot.mcp_server import spacepilot_download_weights
    from pathlib import Path

    called = {}

    def mock_download(variant, dest_dir, stage="all", concurrency=16, download_engine=None):
        called["variant"] = variant
        called["dest_dir"] = dest_dir
        return dest_dir

    monkeypatch.setattr("spacepilot.services.model_downloader.download_weights", mock_download)

    res = spacepilot_download_weights(model="minimax-h3")
    assert res["status"] == "success"
    assert "models/minimax-h3" in res["dest"]


def test_spacepilot_load_runtime_mcp(monkeypatch, tmp_path):
    from spacepilot.mcp_server import spacepilot_load_runtime

    called = {}

    def mock_load(model_id, weights_dir, backend="sglang", port=30010, tp=1, **kwargs):
        called["model_id"] = model_id
        called["weights_dir"] = weights_dir
        called["backend"] = backend
        called["port"] = port
        called["tp"] = tp
        return {
            "model_id": model_id,
            "weights_dir": str(weights_dir),
            "backend": backend,
            "port": port,
            "tp": tp,
            "pid": 9999,
            "loaded_at": 123456.78,
            "healthy": True,
        }

    monkeypatch.setattr("spacepilot.services.runtime_manager.load_model", mock_load)

    res = spacepilot_load_runtime(
        model_id="minimax-h3",
        weights_dir=str(tmp_path / "weights"),
        backend="sglang",
        port=30010,
        tp=2,
    )
    assert res["status"] == "success"
    assert res["runtime"]["model_id"] == "minimax-h3"
    assert res["runtime"]["port"] == 30010
    assert res["runtime"]["tp"] == 2
    assert res["runtime"]["healthy"] is True


def test_spacepilot_unload_runtime_mcp(monkeypatch):
    from spacepilot.mcp_server import spacepilot_unload_runtime

    called = {}

    def mock_unload(model_id=None, port=None, all_models=False, **kwargs):
        called["model_id"] = model_id
        called["all_models"] = all_models
        return {
            "status": "success",
            "unloaded_count": 1,
            "unloaded": [{"model_id": model_id, "pid": 9999}],
            "errors": [],
        }

    monkeypatch.setattr("spacepilot.services.runtime_manager.unload_model", mock_unload)

    res = spacepilot_unload_runtime(model_id="minimax-h3")
    assert res["status"] == "success"
    assert res["unloaded_count"] == 1
    assert called["model_id"] == "minimax-h3"
    assert called["all_models"] is False


def test_spacepilot_get_resident_models_mcp(monkeypatch):
    from spacepilot.mcp_server import spacepilot_get_resident_models

    def mock_get(state_path=None, verify_alive=True):
        return [
            {
                "model_id": "minimax-h3",
                "weights_dir": "/tmp/weights",
                "backend": "sglang",
                "port": 30010,
                "tp": 1,
                "pid": 9999,
                "healthy": True,
            }
        ]

    monkeypatch.setattr("spacepilot.services.runtime_manager.get_resident_models", mock_get)

    res = spacepilot_get_resident_models()
    assert res["status"] == "success"
    assert len(res["models"]) == 1
    assert res["models"][0]["model_id"] == "minimax-h3"

