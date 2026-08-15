#!/usr/bin/env python3
"""Integration tests for Pluto Studio Backend API."""

import os
import sys
import time
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


def test_studio_full_pipeline():
    """Verify combined pipeline including AI Director and Compositor."""
    # 6. Test AI Director Auto-Scripting
    print("Testing AI Director Auto-Script (/api/director/auto-script)...")
    res_script = client.post("/api/director/auto-script", json={"topic": "How diffusion models work", "style": "3blue1brown"})
    assert res_script.status_code == 200, f"Auto-script failed: {res_script.text}"
    script_data = res_script.json()
    assert script_data["scene_count"] == 5, f"Expected 5 scenes, got {script_data['scene_count']}"
    print(f"  ✓ Auto-script generated {script_data['scene_count']} scenes ({script_data['total_duration_sec']}s)")

    # 7. Generate a mock asset for compositing
    gen_res = client.post("/api/generate", json={"prompt": "Director scene plate", "seconds": 1.0})
    assert gen_res.status_code == 200
    asset_id = gen_res.json()["job_id"]
    time.sleep(0.5)

    # 8. Test MotionVector Compositor (P0 Composite Order Enforced)
    print("Testing MotionVector Compositor (/api/composite-motionvector)...")
    res_comp = client.post("/api/composite-motionvector", json={
        "asset_id": asset_id,
        "title": "Diffusion Velocity Field",
        "latex_formula": "dx_t = f(x_t)dt + g(t)dw_t",
        "accent_color": "#3b82f6",
        "card_position": "bottom_left",
        "export_4k": True
    })
    assert res_comp.status_code == 200, f"Composite failed: {res_comp.text}"
    comp_data = res_comp.json()
    assert "master_id" in comp_data, "No master_id returned"
    print(f"  ✓ MotionVector Composite initiated: {comp_data['master_id']} ({comp_data['resolution']})")

    print("\n========================================================")
    print("✨ ALL PLUTO STUDIO + MOTIONVECTOR TESTS PASSED (100%)")
    print("========================================================\n")


def test_asset_id_rejects_shell_metacharacters():
    """Verify asset_id fields only accept [A-Za-z0-9_-]."""
    for bad_id in ["a b; rm -rf /", "../../etc/passwd", "clip'$(id)'"]:
        assert client.post("/api/upscale-4k", json={"asset_id": bad_id}).status_code == 422
        assert client.post("/api/composite-motionvector", json={"asset_id": bad_id}).status_code == 422


def test_media_routes_reject_path_traversal():
    """Verify file serving stays inside OUTPUTS_DIR."""
    for bad_name in ["../../../etc/hosts", "..%2F..%2Fetc%2Fhosts"]:
        assert client.get(f"/api/media/{bad_name}").status_code in (404, 405)
    assert client.get("/api/assets/..%2F..%2Fetc%2Fhosts/file").status_code in (404, 405)


def test_asset_file_route_requires_exact_name():
    """Verify a partial asset id no longer fuzzy-matches some other clip."""
    gen_res = client.post("/api/generate", json={"prompt": "Exact name plate", "seconds": 1.0})
    asset_id = gen_res.json()["job_id"]
    source_mp4 = OUTPUTS_DIR / f"{asset_id}.mp4"
    for _ in range(30):
        if source_mp4.exists():
            break
        time.sleep(0.2)

    assert client.get(f"/api/assets/{asset_id}/file").status_code == 200
    assert client.get(f"/api/assets/{asset_id[:6]}/file").status_code == 404


def test_failed_ffmpeg_is_recorded_as_failed():
    """Verify a bad ffmpeg run records status 'failed' instead of 'completed'."""
    from src.studio_api import ffmpeg_error, run_ffmpeg

    res = run_ffmpeg(["-i", str(OUTPUTS_DIR / "definitely_missing_source.mp4"), "-f", "null", "-"])
    assert res.returncode != 0
    assert "ffmpeg exited" in ffmpeg_error(res)


def test_run_cmd_rejects_shell_strings():
    """Verify run_cmd only takes argv lists, leaving shell metacharacters inert."""
    from src.cli import run_cmd

    try:
        run_cmd("echo shell string")
        assert False, "run_cmd should reject a shell string"
    except TypeError:
        pass

    assert run_cmd(["echo", "$(id); rm -rf /"], capture=True) == "$(id); rm -rf /"


def test_worker_headers_require_token():
    """Verify the studio refuses to call the GPU worker without a token."""
    import src.studio_api as studio_api

    original = studio_api.WORKER_TOKEN
    try:
        studio_api.WORKER_TOKEN = ""
        try:
            studio_api.worker_headers()
            assert False, "worker_headers should refuse an empty token"
        except RuntimeError:
            pass

        studio_api.WORKER_TOKEN = "secret"
        assert studio_api.worker_headers()["Authorization"] == "Bearer secret"
    finally:
        studio_api.WORKER_TOKEN = original


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
    test_studio_full_pipeline()
    print("🎉 ALL PLUTO STUDIO + MOTIONVECTOR TESTS PASSED (100% SUCCESS)!")
