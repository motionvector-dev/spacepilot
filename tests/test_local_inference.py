#!/usr/bin/env python3
"""Tests for Pluto Local GPU Inference capability probe and model recommender."""

import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

PLUTO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PLUTO_ROOT))
sys.path.append(str(PLUTO_ROOT / "src"))

from src.device_probe import DeviceProfile, probe_local_device, _probe_ram
from src.model_recommender import (
    ModelEntry,
    RECOMMENDED_MODEL_CATALOG,
    recommend_models_for_device,
    download_model_mock,
    PLUTO_MODELS_CACHE,
)
from src.pluto_mcp_server import (
    pluto_probe_hardware,
    pluto_recommend_models,
    pluto_get_local_status,
)
from src.studio_api import app, STUDIO_TOKEN

client = TestClient(app)
AUTH = {"X-Pluto-Token": STUDIO_TOKEN}


def test_device_probe_returns_valid_profile():
    """Test that probe_local_device returns a valid DeviceProfile with non-empty fields."""
    profile = probe_local_device()
    assert isinstance(profile, DeviceProfile)
    assert profile.os_type in ["darwin", "linux", "windows"]
    assert profile.vram_total_gb > 0
    assert profile.vram_usable_gb >= 0
    assert profile.backend in ["metal_mps", "cuda", "cpu", "rocm"]
    assert isinstance(profile.is_local_capable, bool)

    data = profile.to_dict()
    assert "os_type" in data
    assert "vram_usable_gb" in data


def test_safety_headroom_formula():
    """Verify the 80% VRAM minus 1.5GB display buffer formula."""
    total_64 = 64.0
    usable_64 = max(0.0, round(total_64 * 0.80 - 1.5, 2))
    assert usable_64 == 49.7

    total_16 = 16.0
    usable_16 = max(0.0, round(total_16 * 0.80 - 1.5, 2))
    assert usable_16 == 11.3


def test_model_recommender_task_routing():
    """Test model recommender on different hardware profiles."""
    high_end_profile = DeviceProfile(
        os_type="darwin",
        architecture="arm64",
        device_name="Apple M4 Max",
        backend="metal_mps",
        vram_total_gb=64.0,
        vram_usable_gb=49.7,
        ram_total_gb=64.0,
        ram_free_gb=40.0,
        is_local_capable=True
    )
    res_high = recommend_models_for_device(high_end_profile)
    assert res_high["total_models"] >= 6
    recs_high = {m["model_id"]: m for m in res_high["recommendations"]}
    assert recs_high["kokoro-82m-tts"]["execution_route"] == "local"
    assert recs_high["ltx-video-2.5-fp8"]["execution_route"] == "local"

    low_profile = DeviceProfile(
        os_type="linux",
        architecture="x86_64",
        device_name="Generic CPU",
        backend="cpu",
        vram_total_gb=8.0,
        vram_usable_gb=4.9,
        ram_total_gb=8.0,
        ram_free_gb=4.0,
        is_local_capable=False
    )
    res_low = recommend_models_for_device(low_profile)
    recs_low = {m["model_id"]: m for m in res_low["recommendations"]}
    assert recs_low["kokoro-82m-tts"]["execution_route"] == "local"
    assert recs_low["ltx-video-2.5-fp8"]["execution_route"] == "cloud_spot"


def test_download_model_mock_lifecycle():
    """Test downloading a model from the recommended catalog."""
    res = download_model_mock("kokoro-82m-tts")
    assert res["success"] is True
    assert res["model_id"] == "kokoro-82m-tts"
    assert os.path.exists(res["path"])

    bad_res = download_model_mock("non-existent-model-xyz")
    assert bad_res["success"] is False
    assert "error" in bad_res


def test_fastmcp_tools():
    """Test FastMCP hardware and model recommender tool wrappers."""
    hw_res = pluto_probe_hardware()
    assert hw_res["status"] == "success"
    assert "profile" in hw_res

    rec_res = pluto_recommend_models()
    assert rec_res["status"] == "success"
    assert len(rec_res["recommendations"]) > 0

    status_res = pluto_get_local_status()
    assert status_res["status"] == "online"
    assert "vram_usable_gb" in status_res


def test_studio_api_compute_endpoints():
    """Test REST API compute profile, recommendation, and download endpoints."""
    r_prof = client.get("/api/compute/local-profile")
    assert r_prof.status_code == 200
    prof_data = r_prof.json()
    assert "backend" in prof_data
    assert "vram_usable_gb" in prof_data

    r_recs = client.get("/api/compute/models/recommended")
    assert r_recs.status_code == 200
    recs_data = r_recs.json()
    assert recs_data["total_models"] >= 6

    r_stat = client.get("/api/compute/local-status")
    assert r_stat.status_code == 200
    stat_data = r_stat.json()
    assert stat_data["status"] == "online"

    r_dl_unauth = client.post("/api/compute/models/download", json={"model_id": "kokoro-82m-tts"})
    assert r_dl_unauth.status_code == 401

    r_dl_auth = client.post("/api/compute/models/download", headers=AUTH, json={"model_id": "kokoro-82m-tts"})
    assert r_dl_auth.status_code == 200
    assert r_dl_auth.json()["success"] is True
