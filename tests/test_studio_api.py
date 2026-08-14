#!/usr/bin/env python3
"""Integration tests for Pluto Studio Backend API."""

import os
import sys
from pathlib import Path

# Add project root to sys.path
PLUTO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PLUTO_ROOT))
sys.path.append(str(PLUTO_ROOT / "src"))

from fastapi.testclient import TestClient
from src.studio_api import app, OUTPUTS_DIR

client = TestClient(app)


def test_studio_status_endpoint():
    """Verify /api/status returns telemetry and instance state."""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "gpu_online" in data
    assert "estimated_cost_usd" in data
    assert "worker_ready" in data


def test_studio_enhance_prompt():
    """Verify /api/enhance enriches prompt with cinematic tokens."""
    response = client.post("/api/enhance", json={"prompt": "astronaut riding horse"})
    assert response.status_code == 200
    data = response.json()
    assert "enhanced_prompt" in data
    assert len(data["enhanced_prompt"]) > len("astronaut riding horse")
    assert "cinematic" in data["enhanced_prompt"].lower()


def test_studio_generate_mock_pipeline():
    """Verify /api/generate successfully creates and records a video."""
    response = client.post(
        "/api/generate",
        json={
            "prompt": "Test synthetic diffusion manifold",
            "seconds": 2.0,
            "width": 1024,
            "height": 576,
            "seed": 42,
            "steps": 10
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert "job_id" in data
    job_id = data["job_id"]

    # Verify metadata on disk
    meta_path = OUTPUTS_DIR / f"{job_id}.json"
    assert meta_path.exists()


def test_studio_assets_list():
    """Verify /api/assets lists files from outputs directory."""
    response = client.get("/api/assets")
    assert response.status_code == 200
    data = response.json()
    assert "assets" in data
    assert isinstance(data["assets"], list)


def test_studio_4k_upscale_chain():
    """Verify /api/upscale-4k handles 4K Super-Resolution export."""
    # First create a mock asset if none exists
    gen_res = client.post(
        "/api/generate",
        json={
            "prompt": "4K test clip",
            "seconds": 1.0,
            "width": 1024,
            "height": 576,
        }
    )
    asset_id = gen_res.json()["job_id"]
    
    # Wait for mock generation to finish file creation
    import time
    source_mp4 = OUTPUTS_DIR / f"{asset_id}.mp4"
    for _ in range(30):
        if source_mp4.exists():
            break
        time.sleep(0.2)

    upscale_res = client.post(
        "/api/upscale-4k",
        json={"asset_id": asset_id, "scale": 4}
    )
    assert upscale_res.status_code == 200, f"Upscale failed with status {upscale_res.status_code}: {upscale_res.text}"
    data = upscale_res.json()
    assert data["status"] == "upscaling"
    assert data["output_id"] == f"{asset_id}_4k"


if __name__ == "__main__":
    print("Running Pluto Studio API integration tests...")
    test_studio_status_endpoint()
    print("✓ Status telemetry test passed")
    test_studio_enhance_prompt()
    print("✓ Prompt enhancement test passed")
    test_studio_generate_mock_pipeline()
    print("✓ Generate mock pipeline test passed")
    test_studio_assets_list()
    print("✓ Assets listing test passed")
    test_studio_4k_upscale_chain()
    print("✓ 4K Super-Resolution chain test passed")
    print("\n🎉 ALL PLUTO STUDIO TESTS PASSED (100% SUCCESS)!")
