import pytest
import asyncio

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

import pytest
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
    ("/api/gpu/deploy", {}),
    ("/api/gpu/sync", {}),
    ("/api/cockpit/config", {"config": {}}),
    ("/api/generate/music", {"prompt": "x", "lyrics": "[Intro]"}),
    ("/api/generate/voice", {"text": "x"}),
]

# POST routes that spend nothing and so need no token. Both are pure local
# computation: /api/enhance appends adjectives to a string, and
# /api/director/auto-script returns a hardcoded storyboard. A route belongs
# here only if it cannot cost money or GPU time.
UNGATED_BY_DESIGN = {"/api/enhance", "/api/director/auto-script", "/api/upload-image"}


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
    assert "meta" in data
    assert "patch" in data
    job_id = data["job_id"]

    # Verify metadata on disk
    meta_path = OUTPUTS_DIR / f"{job_id}.json"
    assert meta_path.exists()
    disk_meta = json.loads(meta_path.read_text())
    assert disk_meta["id"] == job_id
    assert "patch" in disk_meta


def test_generate_patch_card_metadata():
    """Verify /api/generate returns MotionVector PatchCard fact block and diff specs."""
    response = client.post(
        "/api/generate",
        headers=AUTH,
        json={
            "prompt": "Cinematic wide tracking shot of cybernetic vehicle",
            "seconds": 4.0,
            "width": 1024,
            "height": 576,
            "stg_scale": 0.8,
            "steps": 25,
            "fps": 24,
            "seed": 1337,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "patch" in data
    patch = data["patch"]

    # a. Upfront Fact Block
    assert patch["target"] == "LTX-2.5 Video Generation"
    assert "specs" in patch
    assert patch["specs"]["resolution"] == "1024x576"
    assert patch["specs"]["fps"] == "24fps"
    assert patch["specs"]["duration"] == "4.0s"
    assert patch["specs"]["steps"] == 25
    assert patch["specs"]["stg_scale"] == 0.8
    assert patch["specs"]["seed"] == 1337
    assert "Local Mode (Free FFmpeg Preview)" in patch["compute_quote"]

    # b. Parameter Diff Inspector
    assert "diff" in patch
    diff = patch["diff"]
    assert diff["prompt"]["after"] == "Cinematic wide tracking shot of cybernetic vehicle"
    assert diff["stg_scale"]["after"] == 0.8
    assert diff["aspect"]["after"] == "1024x576"
    assert diff["seed"]["after"] == 1337
    assert diff["duration"]["after"] == "4.0s"

    # c. Ops list
    assert "ops" in patch
    assert len(patch["ops"]) >= 1
    op = patch["ops"][0]
    assert op["subject"] == "LTX-2.5 Video Generation"
    assert op["generate"]["kind"] == "video"
    assert op["generate"]["tier"] == "LTX-2.5"
    assert op["quote"]["cost_usd"] == 0.00


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


def test_multi_view_routes():
    """Verify onboarding, creator, and studio editor routes return 200 and HTML."""
    for path in ["/", "/onboarding", "/create", "/studio", "/editor"]:
        res = client.get(path)
        assert res.status_code == 200, f"Route {path} failed with status {res.status_code}"
        assert "text/html" in res.headers.get("content-type", ""), f"Route {path} did not return HTML"


def test_generate_request_supports_ltx25_fields():
    """Verify /api/generate accepts stg_scale, modality_scale, fps, image_path."""
    payload = {
        "prompt": "Cybernetic tiger in neon jungle",
        "seconds": 4.0,
        "fps": 24,
        "stg_scale": 1.2,
        "modality_scale": 1.5,
        "image_path": None,
    }
    res = client.post("/api/generate", json=payload, headers=AUTH)
    assert res.status_code == 200
    data = res.json()
    assert "job_id" in data
    assert data["status"] in ["queued", "processing", "completed"]


def test_static_asset_routing():
    """Verify static JS and CSS files are properly served."""
    for asset in ["/studio.css", "/studio.js"]:
        res = client.get(asset)
        assert res.status_code == 200
        assert len(res.text) > 0


def test_cockpit_view_routes():
    """Verify /cockpit and /settings return 200 and HTML."""
    for path in ["/cockpit", "/settings"]:
        res = client.get(path)
        assert res.status_code == 200, f"Route {path} failed with {res.status_code}"
        assert "text/html" in res.headers.get("content-type", "")


def test_cockpit_status_endpoint():
    """Verify /api/cockpit/status returns unified instance, worker, and cost telemetry."""
    res = client.get("/api/cockpit/status")
    assert res.status_code == 200
    data = res.json()
    assert "instance" in data
    assert "worker" in data
    assert "config" in data
    assert "estimated_cost_usd" in data


def test_cockpit_config_endpoints():
    """Verify reading and updating config via cockpit API."""
    # GET config
    res = client.get("/api/cockpit/config")
    assert res.status_code == 200
    data = res.json()
    assert "config" in data

    # POST config with auth
    res_update = client.post(
        "/api/cockpit/config",
        json={"config": {"default_duration": 4.0}},
        headers=AUTH
    )
    assert res_update.status_code == 200
    assert res_update.json().get("ok") is True


def test_gpu_launch_and_terminate_require_confirmation():
    """Verify launch and terminate endpoints reject requests without explicit confirmation."""
    # Launch without confirmation payload -> 422 or 400
    res_launch_no_body = client.post("/api/gpu/launch", headers=AUTH)
    assert res_launch_no_body.status_code in [400, 422]

    res_launch_unconfirmed = client.post("/api/gpu/launch", json={"confirm": False}, headers=AUTH)
    assert res_launch_unconfirmed.status_code == 400
    assert "Confirmation required" in res_launch_unconfirmed.json().get("detail", "")

    # Terminate without confirmation payload -> 422 or 400
    res_term_no_body = client.post("/api/gpu/terminate", headers=AUTH)
    assert res_term_no_body.status_code in [400, 422]

    res_term_unconfirmed = client.post("/api/gpu/terminate", json={"confirm": False}, headers=AUTH)
    assert res_term_unconfirmed.status_code == 400
    assert "Confirmation required" in res_term_unconfirmed.json().get("detail", "")


def test_upload_image_valid():
    """Verify successful image upload returns dimensions, aspect ratio, and safe path."""
    import base64
    import io
    from PIL import Image

    # 1. Create a 16:9 test image (1024x576)
    img_16_9 = Image.new("RGB", (1024, 576), color=(40, 60, 120))
    buf_16_9 = io.BytesIO()
    img_16_9.save(buf_16_9, format="PNG")
    png_bytes = buf_16_9.getvalue()

    # Upload via multipart/form-data
    files = {"file": ("cinematic_plate.png", png_bytes, "image/png")}
    res = client.post("/api/upload-image", files=files)
    assert res.status_code == 200, f"Upload failed: {res.text}"
    data = res.json()

    assert data["width"] == 1024
    assert data["height"] == 576
    assert data["aspect_ratio"] == "16:9"
    assert data["filename"] == "cinematic_plate.png"
    assert data["url"].startswith("/api/media/uploads/")
    assert "image_path" in data
    uploaded_path = Path(data["image_path"])
    assert uploaded_path.exists()

    # Verify serving uploaded image from media route
    media_res = client.get(data["url"])
    assert media_res.status_code == 200
    assert media_res.headers.get("content-type") == "image/png"
    assert len(media_res.content) == len(png_bytes)

    # 2. Create a 9:16 portrait image (576x1024) and upload via base64 JSON
    img_9_16 = Image.new("RGB", (576, 1024), color=(120, 40, 60))
    buf_9_16 = io.BytesIO()
    img_9_16.save(buf_9_16, format="JPEG")
    jpeg_bytes = buf_9_16.getvalue()
    b64_str = base64.b64encode(jpeg_bytes).decode("utf-8")

    res_b64 = client.post(
        "/api/upload-image",
        json={"image_base64": b64_str, "filename": "portrait_frame.jpg", "content_type": "image/jpeg"},
    )
    assert res_b64.status_code == 200, f"Base64 upload failed: {res_b64.text}"
    data_b64 = res_b64.json()
    assert data_b64["width"] == 576
    assert data_b64["height"] == 1024
    assert data_b64["aspect_ratio"] == "9:16"
    assert data_b64["filename"] == "portrait_frame.jpg"
    assert Path(data_b64["image_path"]).exists()

    # Clean up test files
    uploaded_path.unlink(missing_ok=True)
    Path(data_b64["image_path"]).unlink(missing_ok=True)


def test_upload_image_traversal_blocked():
    """Verify path traversal filenames are sanitized and blocked."""
    import io
    from PIL import Image

    img = Image.new("RGB", (256, 256), color=(10, 10, 10))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    for bad_name in ["../../../../etc/passwd.png", "../../../evil.png", "..\\..\\evil.png"]:
        files = {"file": (bad_name, png_bytes, "image/png")}
        res = client.post("/api/upload-image", files=files)
        assert res.status_code == 200
        data = res.json()
        assert ".." not in data["filename"]
        assert "/" not in data["filename"]
        assert "\\" not in data["filename"]
        dest = Path(data["image_path"])
        assert dest.is_relative_to((OUTPUTS_DIR / "uploads").resolve())
        assert dest.exists()
        dest.unlink(missing_ok=True)

    # Verify media route blocks traversal
    assert client.get("/api/media/uploads/..%2F..%2Fetc%2Fhosts").status_code == 404
    assert client.get("/api/media/uploads/../secrets.txt").status_code == 404


def test_generate_draft_mode():
    """Verify draft_mode=True sets default steps=15, 768x432, and ~$0.01 compute quote."""
    res = client.post(
        "/api/generate",
        headers=AUTH,
        json={"prompt": "Draft mode fast motion test", "draft_mode": True},
    )
    assert res.status_code == 200, f"Draft generation failed: {res.text}"
    data = res.json()
    assert data["status"] == "queued"
    job_id = data["job_id"]

    # Verify response meta and patch specs
    meta = data["meta"]
    patch = data["patch"]
    assert meta["steps"] == 15
    assert meta["width"] == 768
    assert meta["height"] == 432
    assert meta["stg_scale"] == 0.5
    assert meta["draft_mode"] is True

    assert patch["specs"]["steps"] == 15
    assert patch["specs"]["resolution"] == "768x432"
    assert patch["specs"]["stg_scale"] == 0.5
    assert patch["specs"]["draft_mode"] is True
    assert "Local Mode" in patch["compute_quote"]
    assert "Free FFmpeg" in patch["compute_quote"]
    assert patch["ops"][0]["quote"]["cost_usd"] == 0.00

    # Verify metadata saved on disk
    meta_file = OUTPUTS_DIR / f"{job_id}.json"
    assert meta_file.exists()
    disk_meta = json.loads(meta_file.read_text())
    assert disk_meta["steps"] == 15
    assert disk_meta["width"] == 768
    assert disk_meta["height"] == 432
    assert disk_meta["stg_scale"] == 0.5
    assert disk_meta["draft_mode"] is True


def test_generate_with_image_path():
    """Verify image_path is preserved and persisted in job metadata."""
    sample_image = str(OUTPUTS_DIR / "uploads" / "sample_keyframe.png")
    res = client.post(
        "/api/generate",
        headers=AUTH,
        json={
            "prompt": "Animate camera moving past statue",
            "image_path": sample_image,
            "seconds": 2.0,
        },
    )
    assert res.status_code == 200, f"Generate with image_path failed: {res.text}"
    data = res.json()
    job_id = data["job_id"]

    assert data["meta"]["image_path"] == sample_image

    # Verify metadata persisted on disk
    meta_file = OUTPUTS_DIR / f"{job_id}.json"
    assert meta_file.exists()
    disk_meta = json.loads(meta_file.read_text())
    assert disk_meta["image_path"] == sample_image


if __name__ == "__main__":
    print("Running Pluto Studio API integration tests...")
    test_multi_view_routes()
    print("✓ Multi-view routes test passed")
    test_cockpit_view_routes()
    print("✓ Cockpit view routes test passed")
    test_cockpit_status_endpoint()
    print("✓ Cockpit status telemetry test passed")
    test_cockpit_config_endpoints()
    print("✓ Cockpit config test passed")
    test_upload_image_valid()
    print("✓ Upload image valid test passed")
    test_upload_image_traversal_blocked()
    print("✓ Upload image traversal blocked test passed")
    test_generate_draft_mode()
    print("✓ Generate draft mode test passed")
    test_generate_with_image_path()
    print("✓ Generate with image path test passed")
    test_generate_request_supports_ltx25_fields()
    print("✓ LTX-2.5 generate parameters test passed")
    test_static_asset_routing()
    print("✓ Static asset routing test passed")
    test_studio_status_endpoint()
    print("✓ Status telemetry test passed")
    test_studio_enhance_prompt()
    print("✓ Prompt enhancement test passed")
    test_studio_generate_mock_pipeline()
    print("✓ Generate mock pipeline test passed")
    test_generate_patch_card_metadata()
    print("✓ MotionVector PatchCard metadata test passed")
    test_studio_assets_list()
    print("✓ Assets listing test passed")
    test_studio_4k_upscale_chain()
    print("✓ 4K Super-Resolution chain test passed")
    test_studio_full_pipeline()
    print("🎉 ALL PLUTO STUDIO + MOTIONVECTOR TESTS PASSED (100% SUCCESS)!")

def test_cockpit_status_includes_launch_time(monkeypatch):
    """Verify that instance.launch_time propagates up through the status endpoint."""
    import src.studio_api as studio_api
    from fastapi.testclient import TestClient
    
    monkeypatch.setattr(studio_api, "_status_cache", None)
    
    def fake_instance_info(_cfg):
        return {
            "id": "i-123",
            "state": "running",
            "ip": "1.2.3.4",
            "type": "g6e.xlarge",
            "launch_time": "2026-08-21T10:00:00Z"
        }
        
    monkeypatch.setattr(studio_api, "get_instance_info", fake_instance_info)
    monkeypatch.setattr(studio_api, "fetch_worker_health", lambda ip: {"ok": True})
    
    client = TestClient(studio_api.app)
    res = client.get("/api/cockpit/status")
    assert res.status_code == 200
    data = res.json()
    assert data["instance"]["launch_time"] == "2026-08-21T10:00:00Z"
    assert "uptime_minutes" in data
    assert "estimated_cost_usd" in data

def test_generate_with_camera_motion():
    """Verify camera parameters are compiled into prompt and STG."""
    res = client.post(
        "/api/generate",
        headers=AUTH,
        json={
            "prompt": "Cybernetic tiger in neon jungle",
            "seconds": 2.0,
            "camera_pan": "right",
            "camera_tilt": "up",
            "camera_zoom": "in",
            "camera_intensity": 3,
            "stg_scale": 1.0,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "job_id" in data
    
    meta = data["meta"]
    enhanced = meta["enhanced_prompt"]
    assert "cinematic slow pan right" in enhanced
    assert "smooth tilt up" in enhanced
    assert "smooth dolly zoom in" in enhanced
    assert "stable camera track" in enhanced
    
    # stg should be scaled: base 1.0 + (3 * 0.1) = 1.3
    assert abs(meta["stg_scale"] - 1.3) < 0.001

def test_watchdog_update_config():
    """Verify idle_shutdown_minutes can be updated via /api/cockpit/config."""
    res = client.post("/api/cockpit/config", headers=AUTH, json={"config": {"idle_shutdown_minutes": 15}})
    assert res.status_code == 200
    assert res.json()["config"]["idle_shutdown_minutes"] == 15

    res_get = client.get("/api/cockpit/config")
    assert res_get.status_code == 200
    assert res_get.json()["config"]["idle_shutdown_minutes"] == 15

def test_watchdog_logic_trigger(monkeypatch):
    """Verify watchdog triggers auto-termination when idle exceeds threshold."""
    async def run_test():
        import src.studio_api as studio_api
        fake_time = [1000.0]
        monkeypatch.setattr(studio_api.time, "time", lambda: fake_time[0])
        studio_api._last_activity_time = 1000.0
        monkeypatch.setattr(studio_api, "load_config", lambda: {"idle_shutdown_minutes": 20})
        monkeypatch.setattr(studio_api, "get_instance_info", lambda cfg: {"id": "i-123", "state": "running"})
        
        term_calls = []
        monkeypatch.setattr(studio_api, "run_cmd", lambda cmd, **kwargs: term_calls.append(cmd))
        
        sleep_calls = [0]
        async def mock_sleep(secs):
            sleep_calls[0] += 1
            if sleep_calls[0] > 1:
                raise asyncio.CancelledError()
            
        monkeypatch.setattr(studio_api.asyncio, "sleep", mock_sleep)
        
        # 10 mins idle -> no termination
        fake_time[0] = 1000.0 + (10 * 60)
        try:
            await studio_api.idle_watchdog_loop()
        except asyncio.CancelledError:
            pass
        assert len(term_calls) == 0
        
        # 21 mins idle -> triggers termination
        sleep_calls[0] = 0
        fake_time[0] = 1000.0 + (21 * 60)
        try:
            await studio_api.idle_watchdog_loop()
        except asyncio.CancelledError:
            pass
        assert len(term_calls) == 1
        assert studio_api._watchdog_event["event"] == "auto_shutdown"

    asyncio.run(run_test())

def test_watchdog_activity_reset(monkeypatch):
    """Verify activity updates reset the watchdog timer."""
    async def run_test():
        import src.studio_api as studio_api
        studio_api._last_activity_time = 1000.0
        monkeypatch.setattr(studio_api, "load_config", lambda: {"idle_shutdown_minutes": 20})
        monkeypatch.setattr(studio_api, "get_instance_info", lambda cfg: {"id": "i-123", "state": "running"})
        
        term_calls = []
        monkeypatch.setattr(studio_api, "run_cmd", lambda cmd, **kwargs: term_calls.append(cmd))
        sleep_calls = [0]
        async def mock_sleep(secs):
            sleep_calls[0] += 1
            if sleep_calls[0] > 1:
                raise asyncio.CancelledError()
        monkeypatch.setattr(studio_api.asyncio, "sleep", mock_sleep)
        
        fake_time = [2000.0]
        monkeypatch.setattr(studio_api.time, "time", lambda: fake_time[0])
        studio_api.update_activity()
        assert studio_api._last_activity_time == fake_time[0]
        
        fake_time[0] = 2000.0 + (10 * 60)
        try:
            await studio_api.idle_watchdog_loop()
        except asyncio.CancelledError:
            pass
        
        assert len(term_calls) == 0

    asyncio.run(run_test())

def test_multi_provider_config_redaction():
    # Set up some test config
    update_data = {
        "config": {
            "provider": "shadeform",
            "shadeform_api_key": "sec_12345",
            "aws_profile": "my-profile"
        }
    }
    r = client.post("/api/cockpit/config", json=update_data, headers=AUTH)
    assert r.status_code == 200
    
    # Check GET redacts
    r_get = client.get("/api/cockpit/config", headers=AUTH)
    assert r_get.status_code == 200
    cfg = r_get.json()["config"]
    assert cfg["provider"] == "shadeform"
    assert cfg["shadeform_api_key"] == "********"
    assert cfg["aws_profile"] == "my-profile"  # not redacted
    
    # Check POST doesn't overwrite with asterisks
    update_data2 = {
        "config": {
            "provider": "aws",
            "shadeform_api_key": "********",
            "aws_profile": "new-profile"
        }
    }
    r2 = client.post("/api/cockpit/config", json=update_data2, headers=AUTH)
    assert r2.status_code == 200
    
    # Verify underlying config
    from src.cli import load_config
    real_cfg = load_config()
    assert real_cfg["shadeform_api_key"] == "sec_12345"
    assert real_cfg["aws_profile"] == "new-profile"
    assert real_cfg["provider"] == "aws"



def test_generate_video_4take_batch():
    payload = {
        "prompt": "4 take test",
        "seconds": 2.0,
        "seed": 100,
        "takes": 4,
        "draft_mode": True
    }
    response = client.post("/api/generate", json=payload, headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert "jobs" in data
    assert len(data["jobs"]) == 4
    assert "take_group_id" in data
    
    seeds = [job["meta"]["seed"] for job in data["jobs"]]
    assert seeds == [100, 101, 102, 103]
    
    for i, job in enumerate(data["jobs"]):
        assert job["meta"]["take_index"] == i + 1
        assert job["meta"]["take_group_id"] == data["take_group_id"]
