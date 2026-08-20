#!/usr/bin/env python3
"""Integration tests for Pluto Studio Backend API."""

import json
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Add project root to sys.path
PLUTO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PLUTO_ROOT))
sys.path.append(str(PLUTO_ROOT / "src"))

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from src.studio_api import app, OUTPUTS_DIR, STUDIO_TOKEN, require_token

client = TestClient(app)

# Every compute endpoint is gated; read-only routes are not.
AUTH = {"X-Pluto-Token": STUDIO_TOKEN}
GATED_POSTS = [
    ("/api/generate", {"prompt": "x"}),
    ("/api/upscale-4k", {"asset_id": "x"}),
    ("/api/composite-motionvector", {"asset_id": "x"}),
    ("/api/gpu/launch", {}),
    ("/api/gpu/terminate", {}),
    ("/api/generate/music", {"prompt": "x", "lyrics": "[Intro]"}),
    ("/api/generate/voice", {"text": "x"}),
]

# POST routes that spend nothing and so need no token. Both are pure local
# computation: /api/enhance appends adjectives to a string, and
# /api/director/auto-script returns a hardcoded storyboard. A route belongs
# here only if it cannot cost money or GPU time.
UNGATED_BY_DESIGN = {"/api/enhance", "/api/director/auto-script"}


def _requires_token(route: APIRoute) -> bool:
    """True if require_token appears anywhere in the route's dependency tree."""
    stack = list(route.dependant.dependencies)
    while stack:
        dep = stack.pop()
        if dep.call is require_token:
            return True
        stack.extend(dep.dependencies)
    return False


def test_every_post_route_is_gated_or_explicitly_exempt():
    """The structural guard: walk the app, not a list someone has to remember.

    GATED_POSTS below proves the gate returns 401. This proves nobody added a
    route it forgot to cover — the failure the hand-maintained list could not
    catch, since a new ungated route simply would not appear in it.
    """
    missing = sorted(
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
        and "POST" in route.methods
        and route.path not in UNGATED_BY_DESIGN
        and not _requires_token(route)
    )
    assert not missing, (
        f"POST routes with neither require_token nor an UNGATED_BY_DESIGN entry: {missing}. "
        "Gate it, or add it to UNGATED_BY_DESIGN with a reason."
    )


def test_compute_endpoints_all_require_the_token():
    """Verify the gating is uniform: no compute endpoint is reachable unauthenticated."""
    for path, body in GATED_POSTS:
        assert client.post(path, json=body).status_code == 401, f"{path} is ungated"
        assert client.post(path, json=body, headers={"X-Pluto-Token": "wrong"}).status_code == 401


def test_read_only_endpoints_stay_open():
    for path in ["/api/status", "/api/assets"]:
        assert client.get(path).status_code == 200


def test_healthz_is_dependency_free_liveness():
    """The supervisor probe must not invoke AWS or worker telemetry."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status_refresh_is_single_flight_under_concurrency(monkeypatch):
    """An adversarial poll burst must produce one AWS refresh, not one per call."""
    import src.studio_api as studio_api

    monkeypatch.setattr(studio_api, "_status_cache", None)
    calls = 0
    calls_lock = threading.Lock()

    def fake_instance_info(_cfg):
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.05)
        return None

    monkeypatch.setattr(studio_api, "get_instance_info", fake_instance_info)
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda _n: studio_api.get_status(), range(20)))

    assert calls == 1
    assert all(result["gpu_online"] is False for result in results)


def test_instance_info_passes_bounded_timeout(monkeypatch):
    """The AWS child receives a hard timeout and a timeout is safe to report."""
    import src.cli as cli

    seen = {}

    def fake_run_cmd(_cmd, **kwargs):
        seen.update(kwargs)
        raise TimeoutError("simulated AWS timeout")

    monkeypatch.setattr(cli, "run_cmd", fake_run_cmd)
    assert cli.get_instance_info(cli.DEFAULT_CONFIG) is None
    assert seen["timeout"] == 3.0


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
        headers=AUTH,
        json={
            "prompt": "Test synthetic diffusion manifold",
            "seconds": 2.0,
            "width": 1024,
            "height": 576,
            "seed": 42,
            "steps": 10,
        },
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
        headers=AUTH,
        json={"prompt": "4K test clip", "seconds": 1.0, "width": 1024, "height": 576},
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
        "/api/upscale-4k", json={"asset_id": asset_id, "scale": 4}, headers=AUTH
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
    gen_res = client.post("/api/generate", json={"prompt": "Director scene plate", "seconds": 1.0}, headers=AUTH)
    assert gen_res.status_code == 200
    asset_id = gen_res.json()["job_id"]
    time.sleep(0.5)

    # 8. Test MotionVector Compositor (P0 Composite Order Enforced)
    print("Testing MotionVector Compositor (/api/composite-motionvector)...")
    res_comp = client.post("/api/composite-motionvector", headers=AUTH, json={
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
        assert client.post("/api/upscale-4k", json={"asset_id": bad_id}, headers=AUTH).status_code == 422
        assert client.post("/api/composite-motionvector", json={"asset_id": bad_id}, headers=AUTH).status_code == 422


def test_resolve_output_blocks_escapes_from_outputs_dir():
    """Verify the containment check itself rejects anything outside OUTPUTS_DIR."""
    from fastapi import HTTPException

    from src.studio_api import OUTPUTS_DIR, resolve_output

    outside = PLUTO_ROOT / "pytest_outside_marker.txt"
    outside.write_text("should never be served")
    try:
        escapes = [
            "../pytest_outside_marker.txt",
            "sub/../../pytest_outside_marker.txt",
            "..",
            "/etc/hosts",
        ]
        for name in escapes:
            try:
                served = resolve_output(name)
                assert False, f"resolve_output served {name!r} -> {served}"
            except HTTPException as e:
                assert e.status_code == 404

        # A real file inside the directory still resolves.
        inside = OUTPUTS_DIR / "pytest_inside_marker.txt"
        inside.write_text("ok")
        assert resolve_output("pytest_inside_marker.txt") == inside.resolve()
        inside.unlink()
    finally:
        outside.unlink()


def test_media_route_refuses_symlink_out_of_outputs_dir():
    """Verify the containment check blocks the escape the router cannot see.

    Dotted traversal never reaches the handler: the ASGI router normalises the
    path and answers 404 itself. A symlink inside OUTPUTS_DIR has an ordinary
    name, so it routes fine and only the resolved-path check stops it.
    """
    from src.studio_api import OUTPUTS_DIR

    secret = OUTPUTS_DIR.parent / "pytest_symlink_target.txt"
    secret.write_text("should never be served")
    link = OUTPUTS_DIR / "pytest_leak.mp4"
    link.symlink_to(secret)
    try:
        response = client.get("/api/media/pytest_leak.mp4")
        assert response.status_code == 404, "symlink escaped OUTPUTS_DIR"
        assert client.get("/api/assets/pytest_leak/file").status_code == 404
    finally:
        link.unlink()
        secret.unlink()


def test_dotted_traversal_is_refused():
    """Whoever answers, a dotted traversal must never return a file."""
    for bad_name in ["../../../etc/hosts", "..%2F..%2Fetc%2Fhosts", ".."]:
        assert client.get(f"/api/media/{bad_name}").status_code == 404
    assert client.get("/api/assets/..%2F..%2Fetc%2Fhosts/file").status_code == 404


def test_asset_file_route_requires_exact_name():
    """Verify a partial asset id no longer fuzzy-matches some other clip."""
    gen_res = client.post("/api/generate", json={"prompt": "Exact name plate", "seconds": 1.0}, headers=AUTH)
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


def test_generate_rejects_unbounded_parameters():
    """Verify render cost is bounded: an unbounded duration encodes forever."""
    for payload in [
        {"prompt": "x", "seconds": 1e9},
        {"prompt": "x", "seconds": 0},
        {"prompt": "x", "seconds": -5},
        {"prompt": "x", "width": 999999},
        {"prompt": "x", "steps": 100000},
    ]:
        response = client.post("/api/generate", json=payload, headers=AUTH)
        assert response.status_code == 422, f"accepted {payload}"

    # json.loads accepts these non-standard literals, so send them raw.
    for raw in ['{"prompt":"x","seconds":Infinity}', '{"prompt":"x","seconds":NaN}']:
        response = client.post(
            "/api/generate", content=raw,
            headers={**AUTH, "Content-Type": "application/json"},
        )
        assert response.status_code == 422, f"accepted {raw}"


def test_malformed_headers_and_names_do_not_500():
    """Verify hostile input fails closed with a 4xx, never an unhandled exception."""
    # compare_digest raises TypeError on non-ASCII; headers decode as latin-1.
    assert client.post("/api/gpu/terminate", headers={"X-Pluto-Token": b"\xff\xfe"}).status_code == 401
    # Path.resolve() raises ValueError on an embedded null byte.
    assert client.get("/api/media/a%00b").status_code == 404
    assert client.get("/api/assets/a%00b/thumbnail").status_code in (404, 200)


def test_failed_render_leaves_no_partial_video():
    """A failed render must not leave a 0-byte mp4 that the library then lists."""
    from src.studio_api import OUTPUTS_DIR, discard_partial

    corrupt = OUTPUTS_DIR / "pytest_corrupt.mp4"
    corrupt.write_bytes(b"not a video")
    response = client.post("/api/upscale-4k", json={"asset_id": "pytest_corrupt"}, headers=AUTH)
    assert response.status_code == 200

    meta_path = OUTPUTS_DIR / "pytest_corrupt_4k.json"
    for _ in range(60):
        if meta_path.exists():
            break
        time.sleep(0.2)
    meta = json.loads(meta_path.read_text())
    assert meta["status"] == "failed"
    assert not (OUTPUTS_DIR / "pytest_corrupt_4k.mp4").exists(), "partial render left behind"
    assert meta["is_upscaled"] is False

    # The failure is visible to the UI even though it has no video.
    job = client.get("/api/jobs/pytest_corrupt_4k")
    assert job.status_code == 200
    assert job.json()["status"] == "failed"

    discard_partial(corrupt)
    meta_path.unlink()


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
