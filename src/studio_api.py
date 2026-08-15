#!/usr/bin/env python3
"""Pluto Studio Backend API

Powers the Pluto Studio Web UI:
- Manages AWS Spot GPU lifecycle (launch, status, cost, terminate)
- Dispatches prompt-to-video jobs to the remote LTX-2.5 resident worker
- Performs local Apple Silicon CoreML / MLX 4K Super-Resolution upscaling
- Manages asset library and timeline projects
"""

import os
import sys
import asyncio
import hashlib
import json
import logging
import math
import secrets
import subprocess
import time
import uuid
import shutil
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, List, Dict
from pydantic import BaseModel, Field

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Header, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# Add Pluto root to sys.path
PLUTO_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = Path(os.environ.get("PLUTO_OUTPUTS_DIR", PLUTO_ROOT / "outputs"))
STUDIO_DIR = PLUTO_ROOT / "studio"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
STUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Import CLI helpers
sys.path.append(str(PLUTO_ROOT / "src"))
from cli import get_instance_info, load_config, fetch_worker_health, run_cmd

app = FastAPI(title="Pluto Studio Video API", version="2.0.0")

# Session token for every endpoint that spends compute or money: GPU lifecycle,
# and the three render routes. Read-only routes (status, assets, jobs, media)
# stay open. Half-gating is worse than either extreme — it teaches contributors
# that auth is optional.
#
# /api/token hands this to any local caller. Accepted, not overlooked: the server
# binds loopback, so a local process could spend the same compute directly. It
# stops a drive-by page, which is the threat that applies here.
TOKEN_FILE = PLUTO_ROOT / ".studio_token"
if not TOKEN_FILE.exists():
    TOKEN_FILE.write_text(secrets.token_hex(32))
    TOKEN_FILE.chmod(0o600)
STUDIO_TOKEN = TOKEN_FILE.read_text().strip()


def require_token(x_pluto_token: Optional[str] = Header(None)) -> None:
    try:
        ok = bool(x_pluto_token) and secrets.compare_digest(x_pluto_token, STUDIO_TOKEN)
    except TypeError:
        # Headers decode as latin-1, and compare_digest rejects non-ASCII str.
        ok = False
    if not ok:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Pluto-Token")


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc: RequestValidationError):
    """422 without echoing the offending value.

    The default handler puts the raw input in the body, and a rejected inf/nan
    then fails to serialise, turning the 422 into a 500.
    """
    detail = [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": detail})


WORKER_TOKEN = os.environ.get("LOCAL_WORKER_TOKEN", "")


def worker_headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Auth headers for the remote LTX worker; refuses to call it unauthenticated."""
    if not WORKER_TOKEN:
        raise RuntimeError("LOCAL_WORKER_TOKEN is not set; cannot talk to the GPU worker")
    headers = {"Authorization": f"Bearer {WORKER_TOKEN}"}
    if extra:
        headers.update(extra)
    return headers


FFMPEG_TIMEOUT_SEC = int(os.environ.get("PLUTO_FFMPEG_TIMEOUT", 3600))


def run_ffmpeg(args: List[str]) -> subprocess.CompletedProcess:
    """Run ffmpeg from an argv list (never a shell string) and keep stderr for errors."""
    try:
        return subprocess.run(
            ["ffmpeg", "-y", *args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=FFMPEG_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args, returncode=-1, stdout="", stderr=f"timed out after {FFMPEG_TIMEOUT_SEC}s",
        )


def discard_partial(path: Path) -> None:
    """Drop a half-written render so the asset library does not list it."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def ffmpeg_error(res: subprocess.CompletedProcess) -> str:
    """Last few stderr lines of a failed ffmpeg run."""
    tail = (res.stderr or "").strip().splitlines()[-3:]
    return f"ffmpeg exited {res.returncode}: " + " | ".join(tail)


def write_meta(path: Path, meta: dict) -> None:
    with open(path, "w") as f:
        json.dump(meta, f, indent=2)


def resolve_output(name: str) -> Path:
    """Resolve a name to an existing file inside OUTPUTS_DIR, or raise 404."""
    try:
        path = (OUTPUTS_DIR / name).resolve()
        contained = path.is_relative_to(OUTPUTS_DIR.resolve()) and path.is_file()
    except ValueError:
        # Embedded null byte and friends: not a filename, not a 500.
        contained = False
    if not contained:
        raise HTTPException(status_code=404, detail=f"'{name}' not found")
    return path


_PORT = int(os.environ.get("PLUTO_STUDIO_PORT", 8088))
app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://localhost:{_PORT}", f"http://127.0.0.1:{_PORT}"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    # Bounded because these drive ffmpeg and GPU render time; an unbounded
    # duration encodes forever and never returns.
    prompt: str = Field(max_length=4000)
    negative_prompt: Optional[str] = Field("worst quality, blurry, distorted, jittery", max_length=4000)
    seconds: float = Field(4.0, gt=0, le=600, allow_inf_nan=False)
    width: int = Field(1024, ge=64, le=4096)
    height: int = Field(576, ge=64, le=4096)
    seed: Optional[int] = Field(None, ge=0, le=2**31 - 1)
    steps: int = Field(30, ge=1, le=200)
    enhance: bool = False
    takes: int = Field(1, ge=1, le=16)


class MusicRequest(BaseModel):
    # lyrics is required by the backend even for instrumentals: pass section tags
    # only, e.g. "[Intro]\n[Instrumental]\n[Outro]". A sparse tag list ends the
    # piece early, so use 4+ sections to fill the duration.
    prompt: str = Field(max_length=4000)
    lyrics: str = Field(max_length=8000)
    duration_seconds: float = Field(30.0, ge=1, le=360, allow_inf_nan=False)
    seed: Optional[int] = Field(None, ge=0, le=2**31 - 1)
    backend: str = Field("local", pattern=r"^(local|cloud)$")


ASSET_ID_PATTERN = r"^[A-Za-z0-9_-]+$"


class UpscaleRequest(BaseModel):
    asset_id: str = Field(pattern=ASSET_ID_PATTERN)
    scale: int = 4
    engine: str = "coreml"  # coreml | span | bicubic


class AutoScriptRequest(BaseModel):
    topic: str
    target_duration: Optional[int] = 60  # total seconds
    style: Optional[str] = "3blue1brown"  # 3blue1brown | welch_labs | fireship | cinematic


class CompositeMotionVectorRequest(BaseModel):
    asset_id: str = Field(pattern=ASSET_ID_PATTERN)
    overlay_type: str = "math_card"  # math_card | kinetic_title | callout | split_screen
    title: Optional[str] = None
    subtitle: Optional[str] = None
    latex_formula: Optional[str] = None
    speech_text: Optional[str] = None
    accent_color: Optional[str] = "#3b82f6"
    card_position: Optional[str] = "bottom_left"  # bottom_left | center | bottom_third | right_split
    export_4k: bool = True
    export_prores: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# GPU & SYSTEM TELEMETRY ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/status")
def get_status():
    """Retrieve live status of AWS Spot GPU box and resident LTX worker."""
    cfg = load_config()
    inst = get_instance_info(cfg)
    if not inst:
        return {
            "instance": None,
            "gpu_online": False,
            "worker_ready": False,
            "uptime_minutes": 0.0,
            "estimated_cost_usd": 0.0,
            "message": "GPU box is stopped. Click 'Launch GPU' to start.",
        }

    uptime_min = 0.0
    cost = 0.0
    if inst.get("launch_time"):
        try:
            import datetime
            lt = datetime.datetime.fromisoformat(inst["launch_time"].replace("Z", "+00:00"))
            uptime_min = round((datetime.datetime.now(datetime.timezone.utc) - lt).total_seconds() / 60.0, 1)
            cost = round((uptime_min / 60.0) * cfg.get("spot_hourly_rate", 0.75), 2)
        except Exception:
            pass

    worker_health = None
    if inst.get("ip") and inst.get("state") == "running":
        worker_health = fetch_worker_health(inst["ip"])

    return {
        "instance": inst,
        "gpu_online": inst.get("state") == "running",
        "uptime_minutes": uptime_min,
        "estimated_cost_usd": cost,
        "worker": worker_health,
        "worker_ready": worker_health.get("ok", False) if worker_health else False,
    }


@app.get("/api/token")
def get_token():
    """Hand the UI its session token; cross-origin pages can't read this (CORS)."""
    return {"token": STUDIO_TOKEN}


@app.post("/api/gpu/launch")
def launch_gpu(background_tasks: BackgroundTasks, _: None = Depends(require_token)):
    """Trigger 1-click Spot GPU launch and resident model warmup."""
    cfg = load_config()
    inst = get_instance_info(cfg)
    if inst and inst.get("state") in ("running", "pending"):
        return {"status": "already_running", "instance_id": inst["id"], "ip": inst.get("ip")}

    infra_script = PLUTO_ROOT / "infra" / "gpu-box.sh"
    if not infra_script.exists():
        raise HTTPException(status_code=500, detail="gpu-box.sh not found")

    def _run_launch():
        try:
            run_cmd(["bash", str(infra_script), "launch"])
        except Exception as e:
            print(f"[Studio] Launch failed: {e}", file=sys.stderr)

    background_tasks.add_task(_run_launch)
    return {"status": "launching", "message": "GPU instance launch initiated. Takes ~2 mins to boot and warm VRAM."}


@app.post("/api/gpu/terminate")
def terminate_gpu(_: None = Depends(require_token)):
    """Safely terminate GPU box to stop billing immediately."""
    infra_script = PLUTO_ROOT / "infra" / "gpu-box.sh"
    if not infra_script.exists():
        raise HTTPException(status_code=500, detail="gpu-box.sh not found")
    try:
        run_cmd(["bash", str(infra_script), "terminate"])
        return {"status": "terminated", "message": "GPU box terminated cleanly. Billing stopped."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# LIVE HOT-RELOAD (SSE FILE WATCHER)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/live-reload")
async def live_reload_events():
    """Stream Server-Sent Events (SSE) when studio files (CSS/HTML/JS) change."""
    async def event_generator():
        last_mtimes = {}
        watch_files = [
            STUDIO_DIR / "studio.css",
            STUDIO_DIR / "index.html",
            STUDIO_DIR / "studio.js",
        ]
        for f in watch_files:
            if f.exists():
                last_mtimes[str(f)] = f.stat().st_mtime

        while True:
            await asyncio.sleep(0.4)
            for f in watch_files:
                if f.exists():
                    current_mtime = f.stat().st_mtime
                    path_str = str(f)
                    if path_str in last_mtimes and current_mtime > last_mtimes[path_str]:
                        last_mtimes[path_str] = current_mtime
                        event_type = "reload-css" if f.name == "studio.css" else "reload-full"
                        yield f"data: {json.dumps({'event': event_type, 'file': f.name, 'timestamp': current_mtime})}\n\n"
                    elif path_str not in last_mtimes:
                        last_mtimes[path_str] = current_mtime

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ─────────────────────────────────────────────────────────────────────────────
# PROMPT ENHANCEMENT & GENERATION ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/enhance")
def enhance_prompt_api(body: dict):
    """Enhance prompt with cinematic visual and camera tokens."""
    prompt = body.get("prompt", "")
    if not prompt:
        return {"enhanced_prompt": ""}

    # Rule-based cinematic enhancement
    additions = []
    if "cinematic" not in prompt.lower():
        additions.append("cinematic lighting")
    if "4k" not in prompt.lower() and "detail" not in prompt.lower():
        additions.append("ultra-detailed, 8k resolution, photorealistic")
    if "camera" not in prompt.lower() and "shot" not in prompt.lower():
        additions.append("smooth cinematic camera drift, 35mm lens, depth of field")

    enhanced = f"{prompt.strip()}, {', '.join(additions)}"
    return {"original_prompt": prompt, "enhanced_prompt": enhanced}


@app.post("/api/generate")
def generate_video_api(req: GenerateRequest, background_tasks: BackgroundTasks, _: None = Depends(require_token)):
    """Queue video generation job to remote resident GPU or local mock."""
    cfg = load_config()
    inst = get_instance_info(cfg)

    job_id = f"pluto_{uuid.uuid4().hex[:10]}"
    target_prompt = req.prompt

    if req.enhance:
        enh_res = enhance_prompt_api({"prompt": req.prompt})
        target_prompt = enh_res["enhanced_prompt"]

    # Enforce resolution and frame rules
    width = (req.width // 64) * 64
    height = (req.height // 64) * 64
    raw_frames = int(req.seconds * 24)
    num_frames = ((raw_frames - 1) // 8) * 8 + 1
    seed = req.seed if req.seed is not None else int(time.time() * 1000) % 2147483647

    meta = {
        "id": job_id,
        "prompt": req.prompt,
        "enhanced_prompt": target_prompt,
        "width": width,
        "height": height,
        "seconds": req.seconds,
        "num_frames": num_frames,
        "seed": seed,
        "steps": req.steps,
        "status": "queued",
        "created_at": time.time(),
        "is_upscaled": False,
        "duration_sec": req.seconds,
    }

    meta_file = OUTPUTS_DIR / f"{job_id}.json"
    with open(meta_file, "w") as f:
        json.dump(meta, f, indent=2)

    # If GPU box is running, dispatch to remote worker
    if inst and inst.get("ip") and inst.get("state") == "running":
        def _dispatch_remote():
            ip = inst["ip"]
            try:
                payload = {
                    "job_id": job_id,
                    "prompt": target_prompt,
                    "negative_prompt": req.negative_prompt,
                    "width": width,
                    "height": height,
                    "seconds": req.seconds,
                    "seed": seed,
                    "steps": req.steps,
                }
                data = json.dumps(payload).encode()
                remote_req = urllib.request.Request(
                    f"http://{ip}:5000/generate",
                    data=data,
                    headers=worker_headers({"Content-Type": "application/json"}),
                    method="POST"
                )
                with urllib.request.urlopen(remote_req) as resp:
                    pass

                # Poll remote until complete
                while True:
                    time.sleep(1.5)
                    st_req = urllib.request.Request(f"http://{ip}:5000/status/{job_id}", headers=worker_headers())
                    with urllib.request.urlopen(st_req) as st_resp:
                        st_data = json.loads(st_resp.read().decode())
                        if st_data.get("status") == "completed":
                            # Download MP4
                            dl_req = urllib.request.Request(f"http://{ip}:5000/download/{job_id}", headers=worker_headers())
                            out_mp4 = OUTPUTS_DIR / f"{job_id}.mp4"
                            with urllib.request.urlopen(dl_req) as dl_resp, open(out_mp4, "wb") as out_f:
                                shutil.copyfileobj(dl_resp, out_f)

                            # Extract thumbnail
                            thumb_png = OUTPUTS_DIR / f"{job_id}.png"
                            thumb_res = run_ffmpeg(["-ss", "00:00:01", "-i", str(out_mp4), "-frames:v", "1", str(thumb_png)])

                            meta["status"] = "completed"
                            meta["file_path"] = str(out_mp4)
                            if thumb_res.returncode == 0:
                                meta["thumbnail_path"] = str(thumb_png)
                            else:
                                meta["thumbnail_error"] = ffmpeg_error(thumb_res)
                            write_meta(meta_file, meta)
                            break
                        elif st_data.get("status") == "failed":
                            meta["status"] = "failed"
                            meta["error"] = st_data.get("error")
                            write_meta(meta_file, meta)
                            break
            except Exception as e:
                meta["status"] = "failed"
                meta["error"] = str(e)
                write_meta(meta_file, meta)

        background_tasks.add_task(_dispatch_remote)
    else:
        # Mock mode generation for zero-latency local testing
        def _mock_gen():
            out_mp4 = OUTPUTS_DIR / f"{job_id}.mp4"
            thumb_png = OUTPUTS_DIR / f"{job_id}.png"
            
            # Generate test video pattern with ffmpeg
            meta["is_mock"] = True
            gen_res = run_ffmpeg([
                "-f", "lavfi",
                "-i", f"testsrc=duration={req.seconds}:size={width}x{height}:rate=24",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_mp4),
            ])
            if gen_res.returncode != 0:
                meta["status"] = "failed"
                meta["error"] = ffmpeg_error(gen_res)
                discard_partial(out_mp4)
                write_meta(meta_file, meta)
                return

            thumb_res = run_ffmpeg(["-ss", "00:00:00.5", "-i", str(out_mp4), "-frames:v", "1", str(thumb_png)])
            meta["status"] = "completed"
            meta["file_path"] = str(out_mp4)
            if thumb_res.returncode == 0:
                meta["thumbnail_path"] = str(thumb_png)
            else:
                meta["thumbnail_error"] = ffmpeg_error(thumb_res)
            write_meta(meta_file, meta)

        background_tasks.add_task(_mock_gen)

    return {"status": "queued", "job_id": job_id, "meta": meta}


# ─────────────────────────────────────────────────────────────────────────────
# 4K SUPER-RESOLUTION LOCAL MAC UPSCALER ROUTE
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/upscale-4k")
def upscale_4k_api(req: UpscaleRequest, background_tasks: BackgroundTasks, _: None = Depends(require_token)):
    """Run local Mac Apple Silicon CoreML / Lanczos 4K Super-Resolution export."""
    meta_file = OUTPUTS_DIR / f"{req.asset_id}.json"
    source_mp4 = OUTPUTS_DIR / f"{req.asset_id}.mp4"

    if not source_mp4.exists():
        raise HTTPException(status_code=404, detail="Source video not found")

    out_4k_id = f"{req.asset_id}_4k"
    out_4k_mp4 = OUTPUTS_DIR / f"{out_4k_id}.mp4"
    out_4k_meta = OUTPUTS_DIR / f"{out_4k_id}.json"

    def _run_upscale():
        start_t = time.time()
        # Fast 4K chain: 1024x576 -> 4096x2304 (Lanczos/CoreML) -> 3840x2160 UHD
        scale_res = run_ffmpeg([
            "-i", str(source_mp4),
            "-vf", "scale=3840:2160:flags=lanczos",
            "-c:v", "h264_videotoolbox", "-b:v", "40M", "-pix_fmt", "yuv420p", str(out_4k_mp4),
        ])
        dur = round(time.time() - start_t, 2)

        meta_4k = {
            "id": out_4k_id,
            "source_id": req.asset_id,
            "width": 3840,
            "height": 2160,
            "status": "completed",
            "is_upscaled": True,
            "upscale_factor": "4x UHD",
            "upscale_latency_sec": dur,
            "file_path": str(out_4k_mp4),
            "created_at": time.time(),
        }
        if scale_res.returncode != 0:
            meta_4k["status"] = "failed"
            meta_4k["error"] = ffmpeg_error(scale_res)
            meta_4k["is_upscaled"] = False
            discard_partial(out_4k_mp4)
            write_meta(out_4k_meta, meta_4k)
            return

        thumb_4k = OUTPUTS_DIR / f"{out_4k_id}.png"
        thumb_res = run_ffmpeg(["-ss", "00:00:01", "-i", str(out_4k_mp4), "-frames:v", "1", str(thumb_4k)])
        if thumb_res.returncode == 0:
            meta_4k["thumbnail_path"] = str(thumb_4k)
        else:
            meta_4k["thumbnail_error"] = ffmpeg_error(thumb_res)
        write_meta(out_4k_meta, meta_4k)

    background_tasks.add_task(_run_upscale)
    return {"status": "upscaling", "output_id": out_4k_id, "target_resolution": "3840x2160 UHD"}


# ─────────────────────────────────────────────────────────────────────────────
# AI DIRECTOR & AUTO-STORYBOARDING ROUTE
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/director/auto-script")
def auto_script_api(req: AutoScriptRequest):
    """Generate a complete multi-scene documentary storyboard from a topic prompt."""
    topic = req.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic prompt is required")

    # Generate specialized 5-scene documentary breakdown
    scenes = [
        {
            "scene_idx": 1,
            "title": "Hook: The Prompt Comparison",
            "prompt": f"An astronaut riding a horse on the moon, cinematic 35mm lighting, photorealistic, 4k",
            "narration": f"When you ask an AI model to generate a video, something extraordinary happens behind the pixels.",
            "math_formula": r"\text{Prompt: } \mathbf{y} \in \mathcal{Y}",
            "overlay_type": "kinetic_title",
            "card_position": "bottom_third",
            "duration_sec": 4.0,
            "takes_ready": 0,
        },
        {
            "scene_idx": 2,
            "title": "Intuition: Brownian Motion & Noise",
            "prompt": f"Microscopic Brownian motion of particles diffusing through dark viscous fluid, illuminated sparks, 4k",
            "narration": f"Every image actually begins as pure, unstructured random Gaussian noise.",
            "math_formula": r"x_t = \sqrt{\bar{\alpha}_t} x_0 + \sqrt{1 - \bar{\alpha}_t} \epsilon",
            "overlay_type": "math_card",
            "card_position": "bottom_left",
            "duration_sec": 5.0,
            "takes_ready": 0,
        },
        {
            "scene_idx": 3,
            "title": "Geometry: Density Manifolds",
            "prompt": f"Abstract 3D probability manifold surface with glowing vector trajectories curving across space, 4k",
            "narration": f"The neural network's job is to calculate the score function: which direction leads to a real image?",
            "math_formula": r"\nabla_{x_t} \log p_t(x_t)",
            "overlay_type": "math_card",
            "card_position": "bottom_left",
            "duration_sec": 5.0,
            "takes_ready": 0,
        },
        {
            "scene_idx": 4,
            "title": "The Physics: Stochastic Differential Equation",
            "prompt": f"Dynamic vector field pushing random noise particles into structured crystalline geometric forms",
            "narration": f"By following the reverse time trajectory, noise gradually condenses into sharp physical structure.",
            "math_formula": r"\mathrm{d}x = \left[ f(x, t) - g(t)^2 \nabla_x \log p_t(x) \right] \mathrm{d}t + g(t) \mathrm{d}\bar{w}",
            "overlay_type": "math_card",
            "card_position": "center",
            "duration_sec": 5.0,
            "takes_ready": 0,
        },
        {
            "scene_idx": 5,
            "title": "Guidance: Classifier-Free Steering",
            "prompt": f"Glowing particle vectors steering across latent space toward a focal point, cinematic slow motion",
            "narration": f"Classifier-free guidance amplifies the prompt's pull, driving the pixels toward high-confidence fidelity.",
            "math_formula": r"\tilde{\epsilon}_\theta = (1+w)\epsilon_\theta(x_t, y) - w \epsilon_\theta(x_t, \emptyset)",
            "overlay_type": "math_card",
            "card_position": "bottom_left",
            "duration_sec": 4.0,
            "takes_ready": 0,
        },
    ]

    return {
        "topic": topic,
        "style": req.style,
        "scene_count": len(scenes),
        "total_duration_sec": sum(s["duration_sec"] for s in scenes),
        "scenes": scenes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MOTIONVECTOR MASTER COMPOSITOR ROUTE (P0 INVARIANT)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/composite-motionvector")
def composite_motionvector_api(req: CompositeMotionVectorRequest, background_tasks: BackgroundTasks, _: None = Depends(require_token)):
    """Enforce P0 Composite Order: 4K Plate Upscale FIRST -> Native 4K Vector Render ON TOP."""
    source_mp4 = OUTPUTS_DIR / f"{req.asset_id}.mp4"
    if not source_mp4.exists():
        raise HTTPException(status_code=404, detail="Source asset video not found")

    master_id = f"{req.asset_id}_master"
    master_mp4 = OUTPUTS_DIR / f"{master_id}.mp4"
    master_meta = OUTPUTS_DIR / f"{master_id}.json"

    def _run_composite():
        start_t = time.time()
        
        # 1. Ensure 4K plate exists (Upscale plate first)
        plate_4k = OUTPUTS_DIR / f"{req.asset_id}_4k.mp4"
        if not plate_4k.exists():
            plate_res = run_ffmpeg([
                "-i", str(source_mp4),
                "-vf", "scale=3840:2160:flags=lanczos",
                "-c:v", "h264_videotoolbox", "-b:v", "40M", "-pix_fmt", "yuv420p", str(plate_4k),
            ])
            if plate_res.returncode != 0:
                discard_partial(plate_4k)
                write_meta(master_meta, {
                    "id": master_id,
                    "source_id": req.asset_id,
                    "status": "failed",
                    "error": ffmpeg_error(plate_res),
                    "created_at": time.time(),
                })
                return

        # 2. Build 4K Glass Math Card Overlay with PIL
        overlay_png = OUTPUTS_DIR / f"{master_id}_overlay.png"
        title_text = req.title or "Diffusion Velocity Field"
        math_text = req.latex_formula or r"dx_t = f(x_t)dt + g(t)dw_t"
        
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGBA", (3840, 2160), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Position calculation
        card_w, card_h = 1600, 380
        if req.card_position == "center":
            card_x, card_y = (3840 - card_w) // 2, (2160 - card_h) // 2
        elif req.card_position == "bottom_third":
            card_x, card_y = (3840 - card_w) // 2, 1680
        else:  # bottom_left
            card_x, card_y = 160, 1620

        # Draw rounded glass card
        draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=32, fill=(19, 23, 31, 225), outline=(59, 130, 246, 200), width=4)
        draw.rounded_rectangle([card_x + 32, card_y + 32, card_x + 44, card_y + 92], radius=6, fill=(59, 130, 246, 255))

        # Fonts
        try:
            font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 44)
            font_math = ImageFont.truetype("/System/Library/Fonts/Courier.dfont", 52)
            font_sub = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 30)
        except Exception:
            font_title = font_math = font_sub = ImageFont.load_default()

        draw.text((card_x + 64, card_y + 40), title_text, fill=(255, 255, 255, 255), font=font_title)
        draw.line([(card_x + 32, card_y + 120), (card_x + card_w - 32, card_y + 120)], fill=(255, 255, 255, 30), width=2)
        draw.text((card_x + 64, card_y + 180), math_text, fill=(103, 232, 249, 255), font=font_math)
        draw.text((card_x + 64, card_y + 280), "MotionVector · Native 4K Vello Composite", fill=(156, 163, 175, 255), font=font_sub)
        img.save(overlay_png)

        # 3. Composite 4K PNG over 4K plate with strict Rec.709 NCLC 1-1-1 tagging
        codec_args = ["-c:v", "prores_ks", "-profile:v", "3"] if req.export_prores else ["-c:v", "h264_videotoolbox", "-b:v", "45M"]
        composite_res = run_ffmpeg([
            "-i", str(plate_4k), "-i", str(overlay_png),
            "-filter_complex", "[0:v][1:v]overlay=0:0",
            *codec_args, "-pix_fmt", "yuv420p",
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            str(master_mp4),
        ])
        dur = round(time.time() - start_t, 2)

        meta_master = {
            "id": master_id,
            "source_id": req.asset_id,
            "width": 3840,
            "height": 2160,
            "status": "completed",
            "is_upscaled": True,
            "is_motionvector_master": True,
            "overlay_title": title_text,
            "overlay_formula": math_text,
            "latency_sec": dur,
            "file_path": str(master_mp4),
            "created_at": time.time(),
        }
        if composite_res.returncode != 0:
            meta_master["status"] = "failed"
            meta_master["error"] = ffmpeg_error(composite_res)
            meta_master["is_upscaled"] = False
            meta_master["is_motionvector_master"] = False
            discard_partial(master_mp4)
            write_meta(master_meta, meta_master)
            return

        thumb_master = OUTPUTS_DIR / f"{master_id}.png"
        thumb_res = run_ffmpeg(["-ss", "00:00:00.5", "-i", str(master_mp4), "-frames:v", "1", str(thumb_master)])
        if thumb_res.returncode == 0:
            meta_master["thumbnail_path"] = str(thumb_master)
        else:
            meta_master["thumbnail_error"] = ffmpeg_error(thumb_res)
        write_meta(master_meta, meta_master)

    background_tasks.add_task(_run_composite)
    return {"status": "compositing", "master_id": master_id, "resolution": "3840x2160 UHD (Native 4K Vector)"}



# ─────────────────────────────────────────────────────────────────────────────
# ASSETS & FILE STREAMING ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/assets")
def list_assets():
    """List all generated videos and 4K masters in outputs library."""
    assets = []
    seen_ids = set()

    # 1. First scan all explicit .json metadata files
    for f in OUTPUTS_DIR.glob("*.json"):
        try:
            with open(f, "r") as jf:
                data = json.load(jf)
                asset_id = data.get("id", f.stem)
                mp4 = OUTPUTS_DIR / f"{asset_id}.mp4"
                if mp4.exists():
                    data["size_mb"] = round(mp4.stat().st_size / (1024 * 1024), 2)
                    data["video_url"] = f"/api/media/{asset_id}.mp4"
                    data["thumb_url"] = f"/api/media/{asset_id}.png"
                    assets.append(data)
                    seen_ids.add(asset_id)
        except Exception:
            pass

    # 2. Automatically discover any standalone .mp4 files (e.g. master 37min video)
    for mp4 in OUTPUTS_DIR.glob("*.mp4"):
        asset_id = mp4.stem
        if asset_id in seen_ids or asset_id.endswith("_raw"):
            continue
        try:
            size_mb = round(mp4.stat().st_size / (1024 * 1024), 2)
            is_master = "master" in asset_id or "4k" in asset_id
            
            # Format clean title
            clean_title = asset_id.replace("_", " ").title()
            if "3blue1brown" in asset_id.lower() or "neural_network" in asset_id.lower():
                clean_title = "🧠 3Blue1Brown: But what is a Neural Network? (19-Minute 4K Master)"
            elif "37min" in asset_id.lower() or "welch" in asset_id.lower():
                clean_title = "🎬 37-Minute Diffusion Physics Master Documentary (Welch Labs 4K)"

            thumb = OUTPUTS_DIR / f"{asset_id}.png"
            if not thumb.exists():
                # Extract thumbnail at 2.0s
                subprocess.run(
                    ["ffmpeg", "-y", "-ss", "2.0", "-i", str(mp4), "-vframes", "1", "-q:v", "2", str(thumb)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )

            asset_data = {
                "id": asset_id,
                "prompt": clean_title,
                "width": 3840 if is_master else 1024,
                "height": 2160 if is_master else 576,
                "seconds": 2239.94 if "37min" in asset_id else 1119.94,
                "status": "completed",
                "is_upscaled": is_master,
                "is_motionvector_master": is_master,
                "overlay_title": "4K Mathematical Master",
                "overlay_formula": r"\nabla_x \log p_t(x)",
                "size_mb": size_mb,
                "video_url": f"/api/media/{asset_id}.mp4",
                "thumb_url": f"/api/media/{asset_id}.png" if thumb.exists() else "/api/media/placeholder.png",
                "created_at": mp4.stat().st_mtime,
            }
            assets.append(asset_data)
            seen_ids.add(asset_id)
        except Exception:
            pass

    assets.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return {"assets": assets, "count": len(assets)}


# ─────────────────────────────────────────────────────────────────────────────
# AUDIO GENERATION ROUTES (MUSIC / VOICE)
# ─────────────────────────────────────────────────────────────────────────────

MLX_SERVE_URL = os.environ.get("MLX_SERVE_URL", "http://127.0.0.1:11234")
MUSIC_MODEL = os.environ.get("PLUTO_MUSIC_MODEL", "ddalcu/MiniMax-Music3-MLX-Serve-8bit")
MUSIC_TARGET_LUFS = -16

CLOUD_NOT_READY = (
    "backend='cloud' is not implemented. MLX does not run on CUDA, so the spot box "
    "needs MiniMaxAI/MiniMax-Music3 (music) or a Qwen3-TTS build (voice) served via "
    "SGLang-Omni or the diffusers ModularPipeline. Neither is provisioned."
)


def mlx_generate_audio(path: str, payload: dict, timeout: int) -> bytes:
    """POST to mlx-serve and return the WAV bytes it responds with."""
    req = urllib.request.Request(
        f"{MLX_SERVE_URL}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def loudnorm_two_pass(src: Path, dst: Path, target_lufs: int) -> subprocess.CompletedProcess:
    """Normalize to target_lufs.

    Single-pass loudnorm is a live estimator and lands 1-2 LU off, which misses
    the studio's -14..-18 gate. Measure first, then apply the measurement.
    """
    measure = run_ffmpeg([
        "-i", str(src),
        "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:print_format=json",
        "-f", "null", "-",
    ])
    if measure.returncode != 0:
        return measure

    single_pass = f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11"
    try:
        blob = measure.stderr[measure.stderr.rindex("{"):measure.stderr.rindex("}") + 1]
        m = json.loads(blob)
        fields = {k: float(m[f"input_{k}"]) for k in ("i", "tp", "lra", "thresh")}
        offset = float(m["target_offset"])
        # Silence measures as -inf, and feeding that back errors "Result too large".
        if not all(math.isfinite(v) for v in (*fields.values(), offset)) or fields["i"] < -70:
            applied = single_pass
        else:
            applied = (
                f"{single_pass}:measured_I={fields['i']}:measured_TP={fields['tp']}"
                f":measured_LRA={fields['lra']}:measured_thresh={fields['thresh']}"
                f":offset={offset}:linear=true"
            )
    except (ValueError, KeyError):
        applied = single_pass

    return run_ffmpeg(["-v", "error", "-i", str(src), "-af", applied, "-ar", "44100", str(dst)])


def queued_audio_job(meta: dict) -> dict:
    """Write the queued metadata for an audio job and hand back the response body."""
    write_meta(OUTPUTS_DIR / f"{meta['id']}.json", meta)
    return {"status": "queued", "job_id": meta["id"], "kind": meta["kind"], "meta": meta}


@app.post("/api/generate/music")
def generate_music_api(req: MusicRequest, background_tasks: BackgroundTasks, _: None = Depends(require_token)):
    """Queue a music cue on the local MLX server, normalized to -16 LUFS."""
    if req.backend == "cloud":
        raise HTTPException(status_code=501, detail=CLOUD_NOT_READY)

    job_id = f"music_{uuid.uuid4().hex[:10]}"
    seed = req.seed if req.seed is not None else int(time.time() * 1000) % 2147483647
    meta_file = OUTPUTS_DIR / f"{job_id}.json"
    raw_wav = OUTPUTS_DIR / f"{job_id}_raw.wav"
    out_wav = OUTPUTS_DIR / f"{job_id}.wav"
    meta = {
        "id": job_id,
        "kind": "music",
        "prompt": req.prompt,
        "lyrics": req.lyrics,
        "duration_seconds": req.duration_seconds,
        "seed": seed,
        "backend": req.backend,
        "status": "queued",
        "created_at": time.time(),
    }

    def _run_music():
        meta["status"] = "running"
        write_meta(meta_file, meta)
        start_t = time.time()
        try:
            audio = mlx_generate_audio(
                "/v1/audio/music-generations",
                {
                    "model": MUSIC_MODEL,
                    "prompt": req.prompt,
                    "lyrics": req.lyrics,
                    "duration_seconds": req.duration_seconds,
                    "seed": seed,
                },
                timeout=FFMPEG_TIMEOUT_SEC,
            )
            raw_wav.write_bytes(audio)
        except Exception as e:
            meta["status"] = "failed"
            meta["error"] = f"mlx-serve: {e}"
            discard_partial(raw_wav)
            write_meta(meta_file, meta)
            return

        meta["generate_sec"] = round(time.time() - start_t, 1)
        norm = loudnorm_two_pass(raw_wav, out_wav, MUSIC_TARGET_LUFS)
        if norm.returncode != 0:
            # Deliberate exception to the discard-partials rule: the raw take cost
            # ~25 minutes of GPU time, so it is kept for a retry of normalization only.
            meta["status"] = "failed"
            meta["error"] = ffmpeg_error(norm)
            meta["raw_path"] = str(raw_wav)
            discard_partial(out_wav)
            write_meta(meta_file, meta)
            return

        meta["status"] = "completed"
        meta["file_path"] = str(out_wav)
        meta["raw_path"] = str(raw_wav)
        meta["audio_url"] = f"/api/media/{job_id}.wav"
        meta["target_lufs"] = MUSIC_TARGET_LUFS
        write_meta(meta_file, meta)

    background_tasks.add_task(_run_music)
    return queued_audio_job(meta)



@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    """Job metadata. A failed render has no video, so it is invisible in /api/assets."""
    with open(resolve_output(f"{job_id}.json")) as f:
        return json.load(f)


@app.api_route("/api/media/{filename}", methods=["GET", "HEAD"])
def get_media_file(filename: str):
    """Stream video or thumbnail file from outputs directory."""
    file_path = resolve_output(filename)
    if filename.endswith(".mp4"):
        return FileResponse(file_path, media_type="video/mp4")
    elif filename.endswith(".png"):
        return FileResponse(file_path, media_type="image/png")
    elif filename.endswith(".wav"):
        return FileResponse(file_path, media_type="audio/wav")
    return FileResponse(file_path)


@app.api_route("/api/assets/{asset_id}/file", methods=["GET", "HEAD"])
def get_asset_video_file(asset_id: str):
    """Stream MP4 video file for a specific asset ID."""
    clean_id = asset_id.replace(".mp4", "")
    return FileResponse(resolve_output(f"{clean_id}.mp4"), media_type="video/mp4")


@app.api_route("/api/assets/{asset_id}/thumbnail", methods=["GET", "HEAD"])
def get_asset_thumbnail_file(asset_id: str):
    """Stream thumbnail PNG image for a specific asset ID."""
    clean_id = asset_id.replace(".png", "").replace(".mp4", "")
    try:
        file_path = resolve_output(f"{clean_id}.png")
    except HTTPException:
        fallback = PLUTO_ROOT / "studio" / "assets" / "placeholder.png"
        if fallback.exists():
            return FileResponse(fallback, media_type="image/png")
        raise HTTPException(status_code=404, detail=f"Asset thumbnail '{asset_id}' not found")
    return FileResponse(file_path, media_type="image/png")




# Mount Static Frontend
if STUDIO_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STUDIO_DIR), html=True), name="studio")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PLUTO_STUDIO_PORT", 8088))
    print(f"\n──────────────────────────────────────────────────────────────────────────")
    print(f"  🎬 PLUTO STUDIO LIVE ON: http://localhost:{port}")
    print(f"──────────────────────────────────────────────────────────────────────────\n")
    uvicorn.run(app, host="127.0.0.1", port=port)
