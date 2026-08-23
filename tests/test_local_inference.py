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

from src.device_probe import GIB, DeviceProfile, probe_local_device, usable_memory_bytes
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
    profile = probe_local_device()
    assert isinstance(profile, DeviceProfile)
    assert profile.os_type in ["darwin", "linux", "windows"]
    assert profile.vram_total_gb > 0
    assert profile.vram_usable_gb >= 0
    assert profile.backend in ["metal", "cuda", "cpu", "rocm"]
    assert isinstance(profile.is_local_capable, bool)

    data = profile.to_dict()
    assert "os_type" in data
    assert "vram_usable_gb" in data


def test_probe_reads_this_machine_not_a_default():
    """A probe that cannot measure must say so, never substitute a plausible spec.

    Magnitude reported this 32 GB M1 Max MacBook Pro as an 8 GB 4-core x86
    MacBook Air, because its probe failed and fell back to constants. The
    recommendation it built on top was confidently wrong and unfalsifiable.
    """
    profile = probe_local_device()

    # Whatever is reported must be backed by a measurement or recorded as unknown.
    for field in ("memory_total_bytes", "cpu_cores"):
        assert getattr(profile, field) is not None or field in profile.unknown

    if profile.os_type == "darwin":
        # These come from sysctl/system_profiler and cannot be guessed.
        assert profile.chip, "chip must come from machdep.cpu.brand_string"
        assert profile.arch in ("arm64", "x86_64")
        assert profile.machine_model, "hw.model must be read"
        if profile.arch == "arm64":
            assert profile.memory_unified is True
            assert profile.backend == "metal"


def test_usable_memory_prefers_the_platforms_own_limit():
    """Metal reports ~78% of RAM, not the 90% a flat reserve would assume."""
    metal = DeviceProfile(
        memory_total_bytes=32 * GIB, memory_unified=True, backend="metal",
        memory_limit_bytes=int(24.96 * GIB), memory_limit_source="metal",
    )
    assert usable_memory_bytes(metal) == int(24.96 * GIB)

    # No platform answer: fall back to capacity minus max(10%, 3 GB).
    heuristic = DeviceProfile(
        memory_total_bytes=64 * GIB, memory_unified=True, backend="metal")
    assert usable_memory_bytes(heuristic) == 64 * GIB - int(64 * GIB * 0.10)

    small = DeviceProfile(
        memory_total_bytes=8 * GIB, memory_unified=True, backend="metal")
    assert usable_memory_bytes(small) == 8 * GIB - 3 * GIB  # floor, not 10%

    # Nothing measured: promise nothing.
    assert usable_memory_bytes(DeviceProfile()) == 0


def test_model_recommender_task_routing():
    """Test model recommender on different hardware profiles."""
    high_end_profile = DeviceProfile(
        os_name="macOS", arch="arm64", chip="Apple M4 Max", backend="metal",
        memory_total_bytes=64 * GIB, memory_free_bytes=40 * GIB, memory_unified=True,
        memory_limit_bytes=int(49.7 * GIB), memory_limit_source="metal",
    )
    res_high = recommend_models_for_device(high_end_profile)
    assert res_high["total_models"] >= 6
    recs_high = {m["model_id"]: m for m in res_high["recommendations"]}
    assert recs_high["kokoro-82m-tts"]["execution_route"] == "local"
    assert recs_high["ltx-video-2.5-fp8"]["execution_route"] == "local"

    low_profile = DeviceProfile(
        os_name="Linux", arch="x86_64", chip="Generic CPU", backend="cpu",
        memory_total_bytes=8 * GIB, memory_free_bytes=4 * GIB,
        memory_limit_bytes=int(4.9 * GIB), memory_limit_source="heuristic",
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
