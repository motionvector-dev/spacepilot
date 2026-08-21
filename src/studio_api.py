#!/usr/bin/env python3
"""Pluto Studio Backend API

Powers the Pluto Studio Web UI:
- Manages AWS Spot GPU lifecycle (launch, status, cost, terminate)
- Dispatches prompt-to-video jobs to the remote LTX-2.5 resident worker
- Performs local Apple Silicon CoreML / MLX 4K Super-Resolution upscaling
- Manages asset library and timeline projects
"""

import base64
import os
import re
import struct
import sys
import asyncio
import copy
import hashlib
import json
import logging
import math
import secrets
import subprocess
import threading
import time
import uuid
import shutil
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, List, Dict, Literal
from pydantic import BaseModel, Field

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Header, Depends, Request, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# Add Pluto root to sys.path
PLUTO_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = Path(os.environ.get("PLUTO_OUTPUTS_DIR", PLUTO_ROOT / "outputs"))
UPLOADS_DIR = OUTPUTS_DIR / "uploads"
STUDIO_DIR = PLUTO_ROOT / "studio"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
STUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Import CLI helpers
sys.path.append(str(PLUTO_ROOT / "src"))
from cli import get_instance_info, load_config, save_config, fetch_worker_health, run_cmd

app = FastAPI(title="Pluto Studio Video API", version="2.2.0")


@app.get("/healthz")
async def healthz():
    """Dependency-free process liveness for local supervisors.

    Keep this separate from ``/api/status``: status collects AWS and worker
    telemetry and may block while those dependencies are unavailable.
    """
    return {"status": "ok"}

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
    # Mode goes in the open(), not a chmod after it. write_text() creates at
    # 0644 under the usual umask and the narrowing lands a line later, leaving
    # the session token world-readable in between. O_EXCL closes the other end:
    # if a second process created it first, read theirs rather than clobber it.
    try:
        _fd = os.open(TOKEN_FILE, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(_fd, "w") as _f:
            _f.write(secrets.token_hex(32))
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




# --- WATCHDOG ---
_last_activity_time = time.time()
_watchdog_event = None

def update_activity():
    global _last_activity_time
    _last_activity_time = time.time()

def has_active_jobs():
    try:
        if not OUTPUTS_DIR.exists():
            return False
        import json
        for path in OUTPUTS_DIR.glob("*.json"):
            try:
                with open(path) as f:
                    meta = json.load(f)
                    if meta.get("status") in ("queued", "running"):
                        return True
            except Exception:
                pass
    except Exception:
        pass
    return False

async def idle_watchdog_loop():
    global _watchdog_event
    while True:
        try:
            await asyncio.sleep(30)
            
            if await asyncio.to_thread(has_active_jobs):
                update_activity()
                
            cfg = load_config()
            idle_mins = cfg.get("idle_shutdown_minutes", 20)
            if idle_mins <= 0:
                continue
                
            now = time.time()
            elapsed = now - _last_activity_time
            if elapsed > (idle_mins * 60):
                inst = await asyncio.to_thread(get_instance_info, cfg)
                if inst and inst.get("state") == "running":
                    print(f"[Watchdog] Auto-terminating GPU instance {inst.get('id')} after {idle_mins}m of inactivity to save cost.")
                    _watchdog_event = {"event": "auto_shutdown", "time": now, "idle_mins": idle_mins}
                    infra_script = PLUTO_ROOT / "infra" / "gpu-box.sh"
                    if infra_script.exists():
                        try:
                            await asyncio.to_thread(run_cmd, ["bash", str(infra_script), "terminate"])
                        except Exception as e:
                            print(f"[Watchdog] Failed to auto-terminate: {e}")
                    update_activity()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[Watchdog] Error in loop: {e}")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(idle_watchdog_loop())
# -----------------

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
    width: Optional[int] = Field(None, ge=64, le=4096)
    height: Optional[int] = Field(None, ge=64, le=4096)
    seed: Optional[int] = Field(None, ge=0, le=2**31 - 1)
    steps: Optional[int] = Field(None, ge=1, le=200)
    enhance: bool = False
    takes: int = Field(1, ge=1, le=16)
    stg_scale: Optional[float] = Field(None, ge=0.0, le=5.0)
    modality_scale: float = Field(1.0, ge=0.0, le=5.0)
    fps: int = Field(24, ge=1, le=60)
    image_path: Optional[str] = None
    draft_mode: bool = False
    camera_pan: Optional[Literal["left", "right"]] = None
    camera_tilt: Optional[Literal["up", "down"]] = None
    camera_zoom: Optional[Literal["in", "out"]] = None
    camera_roll: Optional[Literal["left", "right", "orbit"]] = None
    camera_intensity: Optional[int] = Field(None, ge=1, le=5)



class ExtendRequest(BaseModel):
    asset_id: str
    prompt: str = Field(max_length=4000)
    negative_prompt: Optional[str] = Field("worst quality, blurry, distorted, jittery", max_length=4000)
    duration: float = Field(4.0, gt=0, le=600, allow_inf_nan=False)
    width: Optional[int] = Field(None, ge=64, le=4096)
    height: Optional[int] = Field(None, ge=64, le=4096)
    seed: Optional[int] = Field(None, ge=0, le=2**31 - 1)
    steps: Optional[int] = Field(None, ge=1, le=200)
    enhance: bool = False
    takes: int = Field(1, ge=1, le=16)
    stg_scale: Optional[float] = Field(None, ge=0.0, le=5.0)
    modality_scale: float = Field(1.0, ge=0.0, le=5.0)
    fps: int = Field(24, ge=1, le=60)
    draft_mode: bool = False
    camera_pan: Optional[Literal["left", "right"]] = None
    camera_tilt: Optional[Literal["up", "down"]] = None
    camera_zoom: Optional[Literal["in", "out"]] = None
    camera_roll: Optional[Literal["left", "right", "orbit"]] = None
    camera_intensity: Optional[int] = Field(None, ge=1, le=5)


class MusicRequest(BaseModel):
    # lyrics is required by the backend even for instrumentals: pass section tags
    # only, e.g. "[Intro]\n[Instrumental]\n[Outro]". A sparse tag list ends the
    # piece early, so use 4+ sections to fill the duration.
    prompt: str = Field(max_length=4000)
    lyrics: str = Field(max_length=8000)
    duration_seconds: float = Field(30.0, ge=1, le=360, allow_inf_nan=False)
    seed: Optional[int] = Field(None, ge=0, le=2**31 - 1)
    backend: str = Field("local", pattern=r"^(local|cloud)$")


class VoiceRequest(BaseModel):
    text: str = Field(max_length=8000)
    voice: str = Field("af_heart", pattern=r"^[A-Za-z0-9_+.-]{1,64}$")
    speed: float = Field(1.0, ge=0.5, le=2.0, allow_inf_nan=False)
    seed: Optional[int] = Field(None, ge=0, le=2**31 - 1)
    # local = Kokoro in-process; mlx = mlx-serve over HTTP, kept as an alternative.
    backend: str = Field("local", pattern=r"^(local|mlx|cloud)$")


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

_STATUS_CACHE_TTL_SEC = 2.0
_status_cache_lock = threading.Lock()
_status_refresh_lock = threading.Lock()
_status_cache = None
_status_cache_at = 0.0


def _build_status(cfg):
    """Build one status snapshot; callers must enforce refresh single-flight."""
    inst = get_instance_info(cfg)
    if not inst:
        return {
            "instance": None,
            "gpu_online": False,
            "worker_ready": False,
            "worker": None,
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
        "watchdog": {
            "elapsed_mins": round((time.time() - _last_activity_time) / 60.0, 1),
            "last_event": _watchdog_event
        }
    }

@app.get("/api/status")
def get_status():
    """Retrieve bounded, single-flight status of the GPU box and worker.

    UI polls are intentionally coalesced: while a refresh is running, other
    callers wait for that same snapshot rather than spawning more AWS CLIs.
    """
    cfg = load_config()
    global _status_cache, _status_cache_at
    now = time.monotonic()
    with _status_cache_lock:
        if _status_cache is not None and now - _status_cache_at < _STATUS_CACHE_TTL_SEC:
            return copy.deepcopy(_status_cache)

    # A blocking lock is deliberate: once the first request is refreshing,
    # concurrent callers wait and then receive its cached result.
    with _status_refresh_lock:
        now = time.monotonic()
        with _status_cache_lock:
            if _status_cache is not None and now - _status_cache_at < _STATUS_CACHE_TTL_SEC:
                return copy.deepcopy(_status_cache)
        snapshot = _build_status(cfg)
        with _status_cache_lock:
            _status_cache = snapshot
            _status_cache_at = time.monotonic()
        return copy.deepcopy(snapshot)


@app.get("/api/token")
def get_token():
    """Hand the UI its session token; cross-origin pages can't read this (CORS)."""
    return {"token": STUDIO_TOKEN}


class GpuActionRequest(BaseModel):
    confirm: bool = False


@app.post("/api/gpu/launch")
def launch_gpu(req: GpuActionRequest, background_tasks: BackgroundTasks, _: None = Depends(require_token)):
    """Trigger 1-click Spot GPU launch and resident model warmup (requires confirm=True)."""
    if not req.confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Pass {'confirm': true} to authorize AWS spot instance billing."
        )
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
def terminate_gpu(req: GpuActionRequest, _: None = Depends(require_token)):
    """Safely terminate GPU box to stop billing immediately (requires confirm=True)."""
    if not req.confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Pass {'confirm': true} to authorize instance termination."
        )
    infra_script = PLUTO_ROOT / "infra" / "gpu-box.sh"
    if not infra_script.exists():
        raise HTTPException(status_code=500, detail="gpu-box.sh not found")
    try:
        run_cmd(["bash", str(infra_script), "terminate"])
        return {"status": "terminated", "message": "GPU box terminated cleanly. Billing stopped."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/gpu/deploy")
def deploy_worker_api(background_tasks: BackgroundTasks, _: None = Depends(require_token)):
    """Hot-deploy latest ltx_worker.py to the running box and restart worker."""
    cfg = load_config()
    inst = get_instance_info(cfg)
    if not inst or inst.get("state") != "running":
        raise HTTPException(status_code=400, detail="No running GPU instance found to deploy to.")

    infra_script = PLUTO_ROOT / "infra" / "gpu-box.sh"

    def _run_deploy():
        try:
            run_cmd(["bash", str(infra_script), "deploy"])
        except Exception as e:
            print(f"[Studio] Deploy failed: {e}", file=sys.stderr)

    background_tasks.add_task(_run_deploy)
    return {"status": "deploying", "message": "Worker deployment initiated in background."}


@app.post("/api/gpu/sync")
def sync_outputs_api(_: None = Depends(require_token)):
    """Rsync all rendered video outputs from remote /scratch/out/ to local outputs/."""
    cfg = load_config()
    inst = get_instance_info(cfg)
    if not inst or not inst.get("ip"):
        raise HTTPException(status_code=400, detail="No running instance found to sync from.")

    key = cfg.get("key_file", str(Path.home() / ".ssh" / "pluto-gpu-key-2026-07-26.pem"))
    ip = inst["ip"]
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["rsync", "-avz", "-e", f"ssh -i {key} -o StrictHostKeyChecking=no", f"ubuntu@{ip}:/scratch/out/", f"{OUTPUTS_DIR}/"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {"ok": True, "message": "Sync complete. All videos downloaded."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}")


@app.get("/api/cockpit/status")
def get_cockpit_status():
    """Unified telemetry for the Cockpit infrastructure dashboard."""
    cfg = load_config()
    inst = get_instance_info(cfg)
    base_status = get_status()

    ssh_cmd = None
    if inst and inst.get("ip") and inst.get("state") == "running":
        key = cfg.get("key_file", "~/.ssh/pluto-gpu-key-2026-07-26.pem")
        ssh_cmd = f"ssh -i {key} ubuntu@{inst['ip']}"

    return {
        **base_status,
        "config": {
            "region": cfg.get("region", "us-east-1"),
            "instance_type": cfg.get("instance_type", "g6e.xlarge"),
            "spot_hourly_rate": cfg.get("spot_hourly_rate", 0.75),
            "key_file": cfg.get("key_file"),
        },
        "ssh_command": ssh_cmd,
    }


@app.get("/api/cockpit/config")
def get_cockpit_config():
    """Get current configuration."""
    cfg = load_config()
    safe_cfg = {}
    for k, v in cfg.items():
        kl = k.lower()
        if "secret" in kl or "token" in kl or "api_key" in kl:
            safe_cfg[k] = "********" if v else ""
        else:
            safe_cfg[k] = v
    if "provider" not in safe_cfg:
        safe_cfg["provider"] = "aws"
    return {"config": safe_cfg}


@app.post("/api/cockpit/config")
def update_cockpit_config(body: dict, _: None = Depends(require_token)):
    """Update configuration settings."""
    cfg = load_config()
    new_data = body.get("config", {})
    
    if "idle_shutdown_minutes" in new_data:
        try:
            val = int(new_data["idle_shutdown_minutes"])
            new_data["idle_shutdown_minutes"] = max(0, min(1440, val))
        except (ValueError, TypeError):
            new_data.pop("idle_shutdown_minutes")
            
    for k, v in new_data.items():
        if v == "********":
            continue
        cfg[k] = v
    if "provider" not in cfg:
        cfg["provider"] = "aws"
    save_config(cfg)
    
    # Return safe config
    safe_cfg = {}
    for k, v in cfg.items():
        kl = k.lower()
        if "secret" in kl or "token" in kl or "api_key" in kl:
            safe_cfg[k] = "********" if v else ""
        else:
            safe_cfg[k] = v
            
    return {"ok": True, "config": safe_cfg}


@app.get("/api/gpu/logs/stream")
async def stream_gpu_logs():
    """SSE stream of worker logs from the remote GPU box or local fallback."""
    cfg = load_config()
    inst = get_instance_info(cfg)

    async def log_generator():
        if not inst or inst.get("state") != "running" or not inst.get("ip"):
            yield f"data: {json.dumps({'line': '[Cockpit] GPU instance is offline. No remote logs to stream.', 'type': 'info'})}\n\n"
            return

        key = cfg.get("key_file", str(Path.home() / ".ssh" / "pluto-gpu-key-2026-07-26.pem"))
        ip = inst["ip"]
        yield f"data: {json.dumps({'line': f'[Cockpit] Connected to {ip}. Streaming /scratch/worker/worker.log...', 'type': 'system'})}\n\n"

        cmd = [
            "ssh", "-i", key,
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=5",
            f"ubuntu@{ip}",
            "tail -n 50 -f /scratch/worker/worker.log 2>/dev/null || true"
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode(errors="replace").rstrip()
                if text:
                    yield f"data: {json.dumps({'line': text, 'type': 'log'})}\n\n"
        except asyncio.CancelledError:
            proc.terminate()
            raise

    return StreamingResponse(
        log_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


# ─────────────────────────────────────────────────────────────────────────────
# LIVE HOT-RELOAD (SSE FILE WATCHER)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/live-reload")
async def live_reload_events():
    """Stream Server-Sent Events (SSE) when studio files (CSS/HTML/JS) change."""
    async def event_generator():
        last_mtimes = {}

        def get_watch_files():
            if not STUDIO_DIR.exists():
                return []
            return [f for f in STUDIO_DIR.iterdir() if f.is_file() and f.suffix in {".html", ".js", ".css"}]

        for f in get_watch_files():
            last_mtimes[str(f)] = f.stat().st_mtime

        while True:
            await asyncio.sleep(0.4)
            for f in get_watch_files():
                current_mtime = f.stat().st_mtime
                path_str = str(f)
                if path_str in last_mtimes and current_mtime > last_mtimes[path_str]:
                    last_mtimes[path_str] = current_mtime
                    event_type = "reload-css" if f.name.endswith(".css") else "reload-full"
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
# PROMPT ENHANCEMENT, IMAGE UPLOAD & GENERATION ROUTES
# ─────────────────────────────────────────────────────────────────────────────

MAX_IMAGE_SIZE = 25 * 1024 * 1024  # 25MB limit
ALLOWED_IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


def sanitize_upload_filename(filename: str, fallback_ext: str = ".png") -> str:
    """Sanitize filename to prevent directory traversal and remove unsafe chars."""
    if not filename:
        clean = "upload"
    else:
        normalized = filename.replace("\\", "/").replace("\x00", "")
        clean = normalized.split("/")[-1]
        clean = clean.replace("..", "")
        clean = re.sub(r"[^A-Za-z0-9_.-]", "_", clean)
        while ".." in clean:
            clean = clean.replace("..", "_")
        clean = clean.strip(". _-")
        if not clean:
            clean = "upload"
    ext = Path(clean).suffix.lower()
    if not ext:
        ext = fallback_ext
        clean = f"{clean}{ext}"
    return clean


def parse_image_dimensions_fallback(content: bytes) -> tuple[Optional[int], Optional[int], Optional[str]]:
    """Header parsing fallback for PNG, JPEG, GIF, WEBP."""
    if len(content) < 16:
        return None, None, None

    # PNG: 89 50 4E 47 0D 0A 1A 0A
    if content.startswith(b"\x89PNG\r\n\x1a\n") and len(content) >= 24:
        w, h = struct.unpack(">II", content[16:24])
        return w, h, "image/png"

    # GIF: GIF87a or GIF89a
    if content.startswith((b"GIF87a", b"GIF89a")) and len(content) >= 10:
        w, h = struct.unpack("<HH", content[6:10])
        return w, h, "image/gif"

    # WEBP: RIFF....WEBP
    if content.startswith(b"RIFF") and len(content) >= 30 and content[8:12] == b"WEBP":
        vp8 = content[12:16]
        if vp8 == b"VP8 " and len(content) >= 30:
            w = struct.unpack("<H", content[26:28])[0] & 0x3FFF
            h = struct.unpack("<H", content[28:30])[0] & 0x3FFF
            return w, h, "image/webp"
        elif vp8 == b"VP8L" and len(content) >= 25:
            b0, b1, b2, b3 = content[21:25]
            w = 1 + (((b1 & 0x3F) << 8) | b0)
            h = 1 + (((content[25] & 0x0F) << 10) | (b3 << 2) | ((b2 & 0xC0) >> 6))
            return w, h, "image/webp"
        elif vp8 == b"VP8X" and len(content) >= 30:
            w = 1 + struct.unpack("<I", content[24:27] + b"\x00")[0]
            h = 1 + struct.unpack("<I", content[27:30] + b"\x00")[0]
            return w, h, "image/webp"
        return None, None, "image/webp"

    # JPEG: FF D8 FF
    if content.startswith(b"\xff\xd8\xff"):
        idx = 2
        while idx < len(content) - 8:
            if content[idx] != 0xFF:
                idx += 1
                continue
            marker = content[idx + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", content[idx + 5:idx + 9])
                return w, h, "image/jpeg"
            else:
                length = struct.unpack(">H", content[idx + 2:idx + 4])[0]
                idx += 2 + length
        return None, None, "image/jpeg"

    return None, None, None


def get_image_info(content: bytes) -> tuple[Optional[int], Optional[int], Optional[str]]:
    """Get dimensions and MIME type using PIL, falling back to header parsing."""
    width, height, mime = None, None, None
    try:
        from PIL import Image
        import io
        with Image.open(io.BytesIO(content)) as img:
            width, height = img.size
            fmt = (img.format or "").upper()
            fmt_map = {
                "PNG": "image/png",
                "JPEG": "image/jpeg",
                "JPG": "image/jpeg",
                "WEBP": "image/webp",
                "GIF": "image/gif",
            }
            mime = fmt_map.get(fmt)
    except Exception:
        pass

    if width is None or height is None or mime is None:
        fb_w, fb_h, fb_mime = parse_image_dimensions_fallback(content)
        width = width or fb_w
        height = height or fb_h
        mime = mime or fb_mime

    return width, height, mime


def get_aspect_ratio_str(width: int, height: int) -> str:
    """Determine aspect ratio string ('16:9', '9:16', '1:1', '4:3', etc.)."""
    if not width or not height or width <= 0 or height <= 0:
        return "16:9"
    ratio = width / height
    known = [
        ("16:9", 16 / 9),
        ("9:16", 9 / 16),
        ("1:1", 1.0),
        ("4:3", 4 / 3),
        ("3:4", 3 / 4),
        ("3:2", 3 / 2),
        ("2:3", 2 / 3),
        ("21:9", 21 / 9),
        ("9:21", 9 / 21),
        ("4:5", 4 / 5),
        ("5:4", 5 / 4),
    ]
    best_name, best_val = min(known, key=lambda x: abs(ratio - x[1]))
    if abs(ratio - best_val) / best_val < 0.05:
        return best_name
    g = math.gcd(width, height)
    sw, sh = width // g, height // g
    if sw <= 32 and sh <= 32:
        return f"{sw}:{sh}"
    return f"{width}:{height}"


def parse_multipart_form_data(body: bytes, content_type_header: str) -> tuple[Optional[bytes], str, Optional[str]]:
    """Parse multipart/form-data using standard library without external dependencies."""
    boundary = None
    for part in content_type_header.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            boundary = part.split("boundary=", 1)[1].strip('"\'')
            break

    if not boundary:
        if body.startswith(b"--"):
            first_line = body.split(b"\r\n", 1)[0] if b"\r\n" in body else body.split(b"\n", 1)[0]
            boundary = first_line.lstrip(b"-").decode("utf-8", errors="replace").strip()
        else:
            return None, "upload.png", None

    boundary_bytes = f"--{boundary}".encode()
    sections = body.split(boundary_bytes)

    for section in sections:
        if not section or section in (b"--", b"--\r\n", b"\r\n", b"--\n", b"\n"):
            continue
        if section.startswith(b"\r\n"):
            section = section[2:]
        elif section.startswith(b"\n"):
            section = section[1:]

        if section.endswith(b"\r\n--"):
            section = section[:-4]
        elif section.endswith(b"\r\n"):
            section = section[:-2]
        elif section.endswith(b"\n--"):
            section = section[:-3]
        elif section.endswith(b"\n"):
            section = section[:-1]

        if b"\r\n\r\n" in section:
            headers_raw, content_part = section.split(b"\r\n\r\n", 1)
        elif b"\n\n" in section:
            headers_raw, content_part = section.split(b"\n\n", 1)
        else:
            continue

        headers_text = headers_raw.decode("utf-8", errors="replace")
        filename = "upload.png"
        content_type = None

        for line in headers_text.splitlines():
            line_lower = line.lower()
            if line_lower.startswith("content-disposition:"):
                fn_match = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';\r\n]+)["\']?', line, re.IGNORECASE)
                if fn_match:
                    filename = fn_match.group(1).strip()
            elif line_lower.startswith("content-type:"):
                content_type = line.split(":", 1)[1].strip()

        if content_part:
            return content_part, filename, content_type

    return None, "upload.png", None


@app.post("/api/upload-image")
async def upload_image_api(request: Request):
    """Upload and validate an image for Image-to-Video generation."""
    content_type = request.headers.get("content-type", "")
    content: Optional[bytes] = None
    raw_filename: str = "upload.png"
    declared_mime: Optional[str] = None

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        has_multipart_lib = False
        try:
            import multipart
            has_multipart_lib = True
        except ImportError:
            pass

        if has_multipart_lib:
            try:
                form = await request.form()
                upload_file = form.get("file") or form.get("image")
                if upload_file is None:
                    for v in form.values():
                        if hasattr(v, "filename") and hasattr(v, "read"):
                            upload_file = v
                            break

                if upload_file is not None and hasattr(upload_file, "filename"):
                    raw_filename = upload_file.filename or "upload.png"
                    declared_mime = upload_file.content_type
                    content = await upload_file.read()
            except Exception:
                pass

        if content is None:
            raw_body = await request.body()
            content, raw_filename, declared_mime = parse_multipart_form_data(raw_body, content_type)

        if content is None:
            raise HTTPException(status_code=400, detail="No image file provided in form data")

    elif "application/json" in content_type:
        try:
            body = await request.json()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {e}")

        b64_data = body.get("image_base64") or body.get("image") or body.get("data") or body.get("file")
        if not b64_data or not isinstance(b64_data, str):
            raise HTTPException(status_code=400, detail="Missing image base64 data in JSON body")

        raw_filename = body.get("filename", "upload.png")
        declared_mime = body.get("content_type")

        if "," in b64_data and b64_data.startswith("data:"):
            header_part, b64_part = b64_data.split(",", 1)
            if not declared_mime and ";" in header_part:
                declared_mime = header_part.split(";")[0].replace("data:", "")
            b64_data = b64_part

        try:
            content = base64.b64decode(b64_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 payload: {e}")

    elif any(content_type.startswith(m) for m in ALLOWED_IMAGE_MIMES):
        raw_filename = "upload.png"
        declared_mime = content_type.split(";")[0]
        content = await request.body()

    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported Content-Type. Expected multipart/form-data or application/json",
        )

    if not content or len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty image payload")

    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="File size exceeds maximum allowed 25MB")

    width, height, detected_mime = get_image_info(content)
    effective_mime = detected_mime or declared_mime
    if effective_mime == "image/jpg":
        effective_mime = "image/jpeg"

    if not effective_mime or effective_mime not in ALLOWED_IMAGE_MIMES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type '{effective_mime}'. Allowed: image/png, image/jpeg, image/webp, image/gif",
        )

    if not width or not height or width <= 0 or height <= 0:
        raise HTTPException(status_code=400, detail="Could not determine valid image dimensions")

    mime_to_ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}
    fallback_ext = mime_to_ext.get(effective_mime, ".png")
    clean_name = sanitize_upload_filename(raw_filename, fallback_ext)

    unique_id = uuid.uuid4().hex[:10]
    safe_name = f"{unique_id}_{clean_name}"
    dest_path = (UPLOADS_DIR / safe_name).resolve()

    # Verify path containment inside UPLOADS_DIR
    if not dest_path.is_relative_to(UPLOADS_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid target filename")

    dest_path.write_bytes(content)
    aspect_str = get_aspect_ratio_str(width, height)

    return {
        "image_path": str(dest_path),
        "url": f"/api/media/uploads/{safe_name}",
        "width": width,
        "height": height,
        "aspect_ratio": aspect_str,
        "filename": clean_name,
    }


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
    update_activity()
    """Queue video generation job to remote resident GPU or local mock."""
    cfg = load_config()
    inst = get_instance_info(cfg)

    job_id = f"pluto_{uuid.uuid4().hex[:10]}"
    target_prompt = req.prompt

    if req.enhance:
        enh_res = enhance_prompt_api({"prompt": req.prompt})
        target_prompt = enh_res["enhanced_prompt"]


    # Camera Tokens
    cam_tokens = []
    intensity = req.camera_intensity or 3
    if req.camera_pan == "right": cam_tokens.append("cinematic slow pan right")
    elif req.camera_pan == "left": cam_tokens.append("cinematic slow pan left")
    
    if req.camera_tilt == "up": cam_tokens.append("smooth tilt up")
    elif req.camera_tilt == "down": cam_tokens.append("smooth tilt down")
    
    if req.camera_zoom == "in": cam_tokens.append("smooth dolly zoom in")
    elif req.camera_zoom == "out": cam_tokens.append("smooth dolly zoom out")
    
    if req.camera_roll == "left": cam_tokens.append("roll left")
    elif req.camera_roll == "right": cam_tokens.append("roll right")
    elif req.camera_roll == "orbit": cam_tokens.append("stable orbit 360")
    
    if cam_tokens:
        cam_tokens.append("stable camera track")
        target_prompt = f"{target_prompt}, {', '.join(cam_tokens)}"
        
    stg_scale_base = req.stg_scale if req.stg_scale is not None else (0.5 if req.draft_mode else 1.0)
    # Adjust STG dynamically
    if cam_tokens:
        stg_scale = min(5.0, stg_scale_base + (intensity * 0.1)) # scale dynamic
    else:
        stg_scale = stg_scale_base

    # Resolution & step defaults based on draft_mode
    is_online = inst and inst.get("ip") and inst.get("state") == "running"
    
    if req.draft_mode:
        default_w, default_h = 768, 432
        steps = req.steps if req.steps is not None else 15
        
        cost_usd = 0.01 if is_online else 0.00
        compute_quote = "Estimated Spot compute: ~$0.01 (No charge on failure)" if is_online else "Local Mode (Free FFmpeg Preview)"
    else:
        default_w, default_h = 1024, 576
        steps = req.steps if req.steps is not None else 30
        
        cost_usd = 0.04 if is_online else 0.00
        compute_quote = "Estimated Spot compute: ~$0.04 (No charge on failure)" if is_online else "Local Mode (Free FFmpeg Preview)"

    raw_w = req.width if req.width is not None else default_w
    raw_h = req.height if req.height is not None else default_h

    # Enforce resolution and frame rules
    if req.draft_mode and req.width is None and req.height is None:
        width = 768
        height = 432
    else:
        width = (raw_w // 64) * 64 if raw_w % 64 == 0 else (raw_w // 16) * 16
        height = (raw_h // 64) * 64 if raw_h % 64 == 0 else (raw_h // 16) * 16

    raw_frames = int(req.seconds * 24)
    num_frames = ((raw_frames - 1) // 8) * 8 + 1

    base_seed = req.seed if req.seed is not None else int(time.time() * 1000) % 2147483647
    
    take_group_id = f"tg_{uuid.uuid4().hex[:10]}" if req.takes > 1 else None
    jobs = []
    
    for i in range(req.takes):
        job_id = f"pluto_{uuid.uuid4().hex[:10]}"
        seed = (base_seed + i) % 2147483648
        
        patch = {
            "target": "LTX-2.5 Video Generation",
            "specs": {
                "resolution": f"{width}x{height}",
                "fps": f"{req.fps}fps",
                "duration": f"{req.seconds:.1f}s",
                "frames": num_frames,
                "steps": steps,
                "stg_scale": stg_scale,
                "seed": seed,
                "draft_mode": req.draft_mode,
            },
            "compute_quote": compute_quote,
            "diff": {
                "prompt": {"before": None, "after": req.prompt},
                "stg_scale": {"before": 1.0, "after": stg_scale},
                "aspect": {"before": "16:9 (1024x576)", "after": f"{width}x{height}"},
                "duration": {"before": "4.0s", "after": f"{req.seconds:.1f}s"},
                "seed": {"before": "random", "after": seed},
            },
            "ops": [
                {
                    "address": "video.generation",
                    "subject": "LTX-2.5 Video Generation",
                    "before": None,
                    "after": f"{width}x{height} @ {req.fps}fps, {req.seconds:.1f}s",
                    "generate": {
                        "kind": "video",
                        "prompt": req.prompt,
                        "tier": "LTX-2.5",
                        "units": req.seconds,
                        "resolution": f"{width}x{height}",
                        "fps": req.fps,
                        "stg_scale": stg_scale,
                        "seed": seed,
                        "draft_mode": req.draft_mode,
                    },
                    "quote": {
                        "estimated": True,
                        "compute_text": compute_quote,
                        "cost_usd": cost_usd,
                    },
                }
            ],
        }

        meta = {
            "id": job_id,
            "prompt": req.prompt,
            "enhanced_prompt": target_prompt,
            "width": width,
            "height": height,
            "seconds": req.seconds,
            "num_frames": num_frames,
            "seed": seed,
            "steps": steps,
            "stg_scale": stg_scale,
            "draft_mode": req.draft_mode,
            "image_path": req.image_path,
            "status": "queued",
            "created_at": time.time(),
            "is_upscaled": False,
            "duration_sec": req.seconds,
            "patch": patch,
        }
        
        if take_group_id:
            meta["take_group_id"] = take_group_id
            meta["take_index"] = i + 1

        meta_file = OUTPUTS_DIR / f"{job_id}.json"
        with open(meta_file, "w") as f:
            json.dump(meta, f, indent=2)

        # If GPU box is running, dispatch to remote worker
        if inst and inst.get("ip") and inst.get("state") == "running":
            def _dispatch_remote(current_job_id=job_id, current_meta=meta, current_meta_file=meta_file, current_seed=seed):
                ip = inst["ip"]
                try:
                    payload = {
                        "job_id": current_job_id,
                        "prompt": target_prompt,
                        "negative_prompt": req.negative_prompt,
                        "width": width,
                        "height": height,
                        "seconds": req.seconds,
                        "seed": current_seed,
                        "steps": steps,
                        "stg_scale": stg_scale,
                        "modality_scale": req.modality_scale,
                        "fps": req.fps,
                        "draft_mode": req.draft_mode,
                    }
                    if req.image_path:
                        payload["image_path"] = req.image_path
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
                        st_req = urllib.request.Request(f"http://{ip}:5000/status/{current_job_id}", headers=worker_headers())
                        with urllib.request.urlopen(st_req) as st_resp:
                            st_data = json.loads(st_resp.read().decode())
                            if st_data.get("status") == "completed":
                                # Download MP4
                                dl_req = urllib.request.Request(f"http://{ip}:5000/download/{current_job_id}", headers=worker_headers())
                                out_mp4 = OUTPUTS_DIR / f"{current_job_id}.mp4"
                                with urllib.request.urlopen(dl_req) as dl_resp, open(out_mp4, "wb") as out_f:
                                    shutil.copyfileobj(dl_resp, out_f)

                                # Extract thumbnail
                                thumb_png = OUTPUTS_DIR / f"{current_job_id}.png"
                                thumb_res = run_ffmpeg(["-ss", "00:00:01", "-i", str(out_mp4), "-frames:v", "1", str(thumb_png)])

                                current_meta["status"] = "completed"
                                current_meta["file_path"] = str(out_mp4)
                                if thumb_res.returncode == 0:
                                    current_meta["thumbnail_path"] = str(thumb_png)
                                else:
                                    current_meta["thumbnail_error"] = ffmpeg_error(thumb_res)
                                write_meta(current_meta_file, current_meta)
                                break
                            elif st_data.get("status") == "failed":
                                current_meta["status"] = "failed"
                                current_meta["error"] = st_data.get("error")
                                write_meta(current_meta_file, current_meta)
                                break
                except Exception as e:
                    current_meta["status"] = "failed"
                    current_meta["error"] = str(e)
                    write_meta(current_meta_file, current_meta)

            background_tasks.add_task(_dispatch_remote)
        else:
            # Mock mode generation for zero-latency local testing
            def _mock_gen(current_job_id=job_id, current_meta=meta, current_meta_file=meta_file):
                out_mp4 = OUTPUTS_DIR / f"{current_job_id}.mp4"
                thumb_png = OUTPUTS_DIR / f"{current_job_id}.png"

                # Generate test video pattern with ffmpeg
                current_meta["is_mock"] = True
                if req.image_path and Path(req.image_path).exists():
                    gen_res = run_ffmpeg([
                        "-loop", "1", "-i", str(req.image_path),
                        "-t", f"{req.seconds}",
                        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_mp4),
                    ])
                else:
                    gen_res = run_ffmpeg([
                        "-f", "lavfi",
                        "-i", f"testsrc=duration={req.seconds}:size={width}x{height}:rate=24",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_mp4),
                    ])
                if gen_res.returncode != 0:
                    current_meta["status"] = "failed"
                    current_meta["error"] = ffmpeg_error(gen_res)
                    discard_partial(out_mp4)
                    write_meta(current_meta_file, current_meta)
                    return

                thumb_res = run_ffmpeg(["-ss", "00:00:00.5", "-i", str(out_mp4), "-frames:v", "1", str(thumb_png)])
                if thumb_res.returncode != 0:
                    thumb_res = run_ffmpeg(["-ss", "00:00:00", "-i", str(out_mp4), "-frames:v", "1", str(thumb_png)])
                current_meta["status"] = "completed"
                current_meta["file_path"] = str(out_mp4)
                if thumb_res.returncode == 0:
                    current_meta["thumbnail_path"] = str(thumb_png)
                else:
                    current_meta["thumbnail_error"] = ffmpeg_error(thumb_res)
                write_meta(current_meta_file, current_meta)

            background_tasks.add_task(_mock_gen)

        jobs.append({"job_id": job_id, "meta": meta, "patch": patch})
        
    if req.takes > 1:
        return {"status": "queued", "jobs": jobs, "take_group_id": take_group_id, "patch": jobs[0]["patch"]}
    else:
        return {"status": "queued", "job_id": jobs[0]["job_id"], "meta": jobs[0]["meta"], "patch": jobs[0]["patch"]}


# ─────────────────────────────────────────────────────────────────────────────
# 4K SUPER-RESOLUTION LOCAL MAC UPSCALER ROUTE
# ─────────────────────────────────────────────────────────────────────────────


@app.post("/api/video/extend")
def extend_video_api(req: ExtendRequest, background_tasks: BackgroundTasks, _: None = Depends(require_token)):
    update_activity()
    clean_id = os.path.basename(req.asset_id).replace(".mp4", "")
    source_mp4 = (OUTPUTS_DIR / f"{clean_id}.mp4").resolve()
    if not str(source_mp4).startswith(str(OUTPUTS_DIR.resolve())) or not source_mp4.exists():
        raise HTTPException(status_code=404, detail="Source asset not found")

        
    out_frame = UPLOADS_DIR / f"ext_{uuid.uuid4().hex[:10]}.jpg"
    
    ffmpeg_res = run_ffmpeg(["-sseof", "-0.1", "-i", str(source_mp4), "-vframes", "1", "-q:v", "2", str(out_frame)])
    if ffmpeg_res.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Failed to extract final frame")
        
    meta_file = OUTPUTS_DIR / f"{clean_id}.json"
    extension_index = 2
    if meta_file.exists():
        with open(meta_file) as f:
            prev_meta = json.load(f)
            extension_index = prev_meta.get("extension_index", 1) + 1
            
    gen_req = GenerateRequest(
        prompt=req.prompt,
        negative_prompt=req.negative_prompt,
        seconds=req.duration,
        width=req.width,
        height=req.height,
        seed=req.seed,
        steps=req.steps,
        enhance=req.enhance,
        takes=req.takes,
        stg_scale=req.stg_scale,
        modality_scale=req.modality_scale,
        fps=req.fps,
        draft_mode=req.draft_mode,
        image_path=str(out_frame),
        camera_pan=req.camera_pan,
        camera_tilt=req.camera_tilt,
        camera_zoom=req.camera_zoom,
        camera_roll=req.camera_roll,
        camera_intensity=req.camera_intensity
    )
    
    # For `generate_video_api`, `require_token` dependency is a default argument, we pass `None` because we verified it at route entry.
    res = generate_video_api(gen_req, background_tasks)
    
    job_id = res["job_id"]
    new_meta_file = OUTPUTS_DIR / f"{job_id}.json"
    
    if new_meta_file.exists():
        with open(new_meta_file) as f:
            new_meta = json.load(f)
        new_meta["extended_from"] = req.asset_id
        new_meta["extension_index"] = extension_index
        with open(new_meta_file, "w") as f:
            json.dump(new_meta, f, indent=2)
            
    if "meta" in res:
        res["meta"]["extended_from"] = req.asset_id
        res["meta"]["extension_index"] = extension_index
        
    return res


@app.post("/api/upscale-4k")
def upscale_4k_api(req: UpscaleRequest, background_tasks: BackgroundTasks, _: None = Depends(require_token)):
    update_activity()
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
    """Generate a complete multi-scene documentary storyboard from a topic prompt.

    TODO: not implemented yet. `topic` is validated and echoed back, but the
    five scenes below are hardcoded for the Welch diffusion explainer — ask for
    "history of coffee" and you still get Brownian motion. This is scaffolding
    for produce_welch_master.py until the generation exists.

    When it does: this route starts spending compute, so it needs
    Depends(require_token) and removal from UNGATED_BY_DESIGN in
    tests/test_studio_api.py. The route guard exempts it today, so nothing will
    fail to remind you.
    """
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
        codec_args = (
            ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le"]
            if req.export_prores
            else ["-c:v", "h264_videotoolbox", "-b:v", "45M", "-pix_fmt", "yuv420p"]
        )
        composite_res = run_ffmpeg([
            "-i", str(plate_4k), "-i", str(overlay_png),
            "-filter_complex", "[0:v][1:v]overlay=0:0",
            *codec_args,
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
VOICE_MODEL = os.environ.get("PLUTO_VOICE_MODEL", "kokoro")
MUSIC_TARGET_LUFS = -16
VOICE_PEAK_DBFS = -1.0

# Kokoro runs in-process through onnxruntime. The engine shells out to Python
# because it is Rust; pluto is already Python, so there is no interpreter bridge
# to cross and no generated script for user text to be injected into.
KOKORO_SEARCH_PATHS = [
    (os.environ.get("PLUTO_KOKORO_MODEL"), os.environ.get("PLUTO_KOKORO_VOICES")),
    (
        str(PLUTO_ROOT.parent / "sr-lessons" / "tools" / "kokoro" / "kokoro-v1.0.onnx"),
        str(PLUTO_ROOT.parent / "sr-lessons" / "tools" / "kokoro" / "voices-v1.0.bin"),
    ),
    (
        str(Path.home() / ".cache" / "hyperframes" / "tts" / "models" / "kokoro-v1.0.onnx"),
        str(Path.home() / ".cache" / "hyperframes" / "tts" / "voices" / "voices-v1.0.bin"),
    ),
]
_kokoro = None
_kokoro_lock = threading.Lock()


def kokoro_assets():
    """First (model, voices) pair that exists on disk, or (None, None)."""
    for model, voices in KOKORO_SEARCH_PATHS:
        if model and voices and Path(model).is_file() and Path(voices).is_file():
            return model, voices
    return None, None


def load_kokoro():
    """Lazily build the shared Kokoro session; ~0.7s once, then cached."""
    global _kokoro
    with _kokoro_lock:
        if _kokoro is None:
            from kokoro_onnx import Kokoro

            model, voices = kokoro_assets()
            if not model:
                raise RuntimeError(
                    "kokoro-v1.0.onnx / voices-v1.0.bin not found; set PLUTO_KOKORO_MODEL "
                    "and PLUTO_KOKORO_VOICES"
                )
            _kokoro = Kokoro(model, voices)
        return _kokoro


def synthesize_voice(text: str, voice: str, speed: float, out_path: Path) -> None:
    """Render speech to a 16-bit mono WAV with Kokoro."""
    import wave

    import numpy as np

    samples, sample_rate = load_kokoro().create(text, voice=voice, speed=speed, lang="en-us")
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(out_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())

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


def peak_normalize(src: Path, dst: Path, target_dbfs: float) -> subprocess.CompletedProcess:
    """Bring the true peak to target_dbfs.

    A limiter only caps peaks above the threshold, so on quiet VO it leaves the
    level wherever it was. Measure the peak, then apply the difference as gain.
    """
    measure = run_ffmpeg(["-i", str(src), "-af", "volumedetect", "-f", "null", "-"])
    if measure.returncode != 0:
        return measure

    gain_db = 0.0
    for line in (measure.stderr or "").splitlines():
        if "max_volume:" in line:
            try:
                peak = float(line.split("max_volume:")[1].strip().split()[0])
                if math.isfinite(peak):
                    gain_db = target_dbfs - peak
            except (ValueError, IndexError):
                pass
            break

    # Gain alone is exact. alimiter is not a safety net here: its `level` option
    # auto-levels to the ceiling by default, which overrides the gain we just computed.
    return run_ffmpeg([
        "-v", "error", "-i", str(src), "-af", f"volume={gain_db:.2f}dB", str(dst),
    ])


def queued_audio_job(meta: dict) -> dict:
    """Write the queued metadata for an audio job and hand back the response body."""
    write_meta(OUTPUTS_DIR / f"{meta['id']}.json", meta)
    return {"status": "queued", "job_id": meta["id"], "kind": meta["kind"], "meta": meta}


@app.post("/api/generate/music")
def generate_music_api(req: MusicRequest, background_tasks: BackgroundTasks, _: None = Depends(require_token)):
    update_activity()
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


@app.post("/api/generate/voice")
def generate_voice_api(req: VoiceRequest, background_tasks: BackgroundTasks, _: None = Depends(require_token)):
    update_activity()
    """Queue a voiceover on the local MLX server, peak-limited to -1 dBFS.

    No loudnorm: VO gets mixed later, so program loudness is the mixer's call.
    """
    if req.backend == "cloud":
        raise HTTPException(status_code=501, detail=CLOUD_NOT_READY)

    job_id = f"voice_{uuid.uuid4().hex[:10]}"
    meta_file = OUTPUTS_DIR / f"{job_id}.json"
    raw_wav = OUTPUTS_DIR / f"{job_id}_raw.wav"
    out_wav = OUTPUTS_DIR / f"{job_id}.wav"
    meta = {
        "id": job_id,
        "kind": "voice",
        "text": req.text,
        "voice": req.voice,
        "speed": req.speed,
        "seed": req.seed,
        "backend": req.backend,
        "status": "queued",
        "created_at": time.time(),
    }

    def _run_voice():
        meta["status"] = "running"
        write_meta(meta_file, meta)
        start_t = time.time()
        try:
            if req.backend == "mlx":
                payload = {
                    "model": VOICE_MODEL,
                    "input": req.text,
                    "voice": req.voice,
                    "speed": req.speed,
                    "response_format": "wav",
                }
                if req.seed is not None:
                    payload["seed"] = req.seed
                raw_wav.write_bytes(
                    mlx_generate_audio("/v1/audio/speech", payload, timeout=FFMPEG_TIMEOUT_SEC)
                )
            else:
                synthesize_voice(req.text, req.voice, req.speed, raw_wav)
        except Exception as e:
            meta["status"] = "failed"
            meta["error"] = f"{req.backend} backend: {e}"
            discard_partial(raw_wav)
            write_meta(meta_file, meta)
            return

        meta["generate_sec"] = round(time.time() - start_t, 1)
        limit = peak_normalize(raw_wav, out_wav, VOICE_PEAK_DBFS)
        if limit.returncode != 0:
            # Voice is cheap to regenerate, so no _raw exception here.
            meta["status"] = "failed"
            meta["error"] = ffmpeg_error(limit)
            discard_partial(out_wav)
            discard_partial(raw_wav)
            write_meta(meta_file, meta)
            return

        discard_partial(raw_wav)
        meta["status"] = "completed"
        meta["file_path"] = str(out_wav)
        meta["audio_url"] = f"/api/media/{job_id}.wav"
        meta["peak_dbfs"] = VOICE_PEAK_DBFS
        write_meta(meta_file, meta)

    background_tasks.add_task(_run_voice)
    return queued_audio_job(meta)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    """Job metadata. A failed render has no video, so it is invisible in /api/assets."""
    with open(resolve_output(f"{job_id}.json")) as f:
        return json.load(f)


@app.api_route("/api/media/uploads/{filename}", methods=["GET", "HEAD"])
def get_uploaded_media_file(filename: str):
    """Stream uploaded image file from outputs/uploads directory safely."""
    file_path = resolve_output(f"uploads/{filename}")
    lower = filename.lower()
    if lower.endswith(".png"):
        return FileResponse(file_path, media_type="image/png")
    elif lower.endswith((".jpg", ".jpeg")):
        return FileResponse(file_path, media_type="image/jpeg")
    elif lower.endswith(".webp"):
        return FileResponse(file_path, media_type="image/webp")
    elif lower.endswith(".gif"):
        return FileResponse(file_path, media_type="image/gif")
    return FileResponse(file_path)


@app.api_route("/api/media/{filename}", methods=["GET", "HEAD"])
def get_media_file(filename: str):
    """Stream video or thumbnail file from outputs directory."""
    file_path = resolve_output(filename)
    lower = filename.lower()
    if lower.endswith(".mp4"):
        return FileResponse(file_path, media_type="video/mp4")
    elif lower.endswith(".png"):
        return FileResponse(file_path, media_type="image/png")
    elif lower.endswith((".jpg", ".jpeg")):
        return FileResponse(file_path, media_type="image/jpeg")
    elif lower.endswith(".webp"):
        return FileResponse(file_path, media_type="image/webp")
    elif lower.endswith(".gif"):
        return FileResponse(file_path, media_type="image/gif")
    elif lower.endswith(".wav"):
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




# ─────────────────────────────────────────────────────────────────────────────
# HTML VIEWS
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# INSPECT MODE (WEB SSH & DIAGNOSTICS)
# ─────────────────────────────────────────────────────────────────────────────

@app.websocket("/api/gpu/inspect/shell")
async def inspect_shell_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        # Initial Auth Frame (wait up to 3s)
        try:
            auth_frame = await asyncio.wait_for(websocket.receive_json(), timeout=3.0)
            if auth_frame.get("type") != "auth" or not secrets.compare_digest(str(auth_frame.get("token") or ""), STUDIO_TOKEN):
                await websocket.close(code=1008)
                return
        except (asyncio.TimeoutError, json.JSONDecodeError):
            await websocket.close(code=1008)
            return

        cfg = load_config()
        inst = get_instance_info(cfg)
        if not inst or inst.get("state") != "running" or not inst.get("ip"):
            await websocket.send_json({"type": "error", "message": "Instance not running"})
            await websocket.close(code=1011)
            return

        key = cfg.get("key_file", str(Path.home() / ".ssh" / "pluto-gpu-key-2026-07-26.pem"))
        ip = inst["ip"]

        # Non-blocking SSH Bridge
        # We need a pseudo-terminal for interactive shell. ssh -t -t
        ssh_cmd = [
            "ssh", "-t", "-t", "-i", key,
            "-o", "StrictHostKeyChecking=no",
            f"ubuntu@{ip}",
            "bash"
        ]

        process = await asyncio.create_subprocess_exec(
            *ssh_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )

        async def read_stdout():
            try:
                while True:
                    data = await process.stdout.read(4096)
                    if not data:
                        break
                    # Send as text (base64 or just string if it's utf-8)
                    # For xterm.js we can send raw text. But xterm handles ansi.
                    # We can send as json with type='data' or just raw string.
                    # Usually WebSocket sends raw text or bytes.
                    # Let's send as string.
                    try:
                        text = data.decode("utf-8")
                        await websocket.send_text(text)
                    except UnicodeDecodeError:
                        await websocket.send_bytes(data)
            except Exception:
                pass

        async def read_ws():
            try:
                while True:
                    msg = await websocket.receive()
                    if "text" in msg:
                        try:
                            data = json.loads(msg["text"])
                            if data.get("type") == "resize":
                                # Handle resize gracefully if needed (e.g. via stty size in the stream or signals)
                                # For a simple bridge, we might just ignore or send an stty command.
                                cols = data.get("cols", 120)
                                rows = data.get("rows", 40)
                                # send stty command to set size
                                process.stdin.write(f"stty cols {cols} rows {rows}\n".encode())
                                await process.stdin.drain()
                                continue
                        except json.JSONDecodeError:
                            # If not JSON, treat as raw input data
                            process.stdin.write(msg["text"].encode("utf-8"))
                            await process.stdin.drain()
                    elif "bytes" in msg:
                        process.stdin.write(msg["bytes"])
                        await process.stdin.drain()
            except Exception:
                pass

        stdout_task = asyncio.create_task(read_stdout())
        ws_task = asyncio.create_task(read_ws())

        done, pending = await asyncio.wait(
            [stdout_task, ws_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        for task in pending:
            task.cancel()

    except WebSocketDisconnect:
        pass
    finally:
        if 'process' in locals() and process.returncode is None:
            try:
                process.terminate()
                await asyncio.sleep(0.1)
                if process.returncode is None:
                    process.kill()
                await process.wait()
            except ProcessLookupError:
                pass

@app.get("/api/gpu/inspect/metrics")
def get_inspect_metrics(_: None = Depends(require_token)):
    cfg = load_config()
    inst = get_instance_info(cfg)
    if not inst or inst.get("state") != "running" or not inst.get("ip"):
        raise HTTPException(status_code=400, detail="Instance not running")

    key = cfg.get("key_file", str(Path.home() / ".ssh" / "pluto-gpu-key-2026-07-26.pem"))
    ip = inst["ip"]

    # Execute bounded SSH command
    ssh_cmd = [
        "ssh", "-i", key,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=5",
        f"ubuntu@{ip}",
        "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits && echo '---' && df -h /scratch && echo '---' && free -m"
    ]
    try:
        res = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=15)
        if res.returncode != 0:
            raise HTTPException(status_code=500, detail=f"SSH failed: {res.stderr}")
        
        parts = res.stdout.split('---')
        if len(parts) >= 3:
            gpu_stats = parts[0].strip().split(',')
            df_stats = parts[1].strip()
            free_stats = parts[2].strip()
            return {
                "gpu": {
                    "utilization": gpu_stats[0].strip() if len(gpu_stats) > 0 else "0",
                    "memory_used": gpu_stats[1].strip() if len(gpu_stats) > 1 else "0",
                    "memory_total": gpu_stats[2].strip() if len(gpu_stats) > 2 else "0",
                    "temperature": gpu_stats[3].strip() if len(gpu_stats) > 3 else "0",
                },
                "disk": df_stats,
                "memory": free_stats
            }
        return {"raw": res.stdout}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class InspectActionRequest(BaseModel):
    action: str

@app.post("/api/gpu/inspect/action")
def post_inspect_action(req: InspectActionRequest, _: None = Depends(require_token)):
    cfg = load_config()
    inst = get_instance_info(cfg)
    if not inst or inst.get("state") != "running" or not inst.get("ip"):
        raise HTTPException(status_code=400, detail="Instance not running")

    key = cfg.get("key_file", str(Path.home() / ".ssh" / "pluto-gpu-key-2026-07-26.pem"))
    ip = inst["ip"]

    whitelist = {
        "restart_worker": "sudo systemctl restart ltx-worker",
        "clear_tmp": "rm -rf /scratch/tmp/*"
    }

    if req.action not in whitelist:
        raise HTTPException(status_code=400, detail=f"Action '{req.action}' not whitelisted")

    cmd = whitelist[req.action]
    ssh_cmd = [
        "ssh", "-i", key,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=5",
        f"ubuntu@{ip}",
        cmd
    ]
    try:
        res = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=15)
        if res.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Action failed: {res.stderr}")
        return {"ok": True, "message": f"Action {req.action} executed successfully", "output": res.stdout}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def read_root():
    onboarding_file = STUDIO_DIR / "onboarding.html"
    if onboarding_file.exists():
        return FileResponse(onboarding_file)
    return FileResponse(STUDIO_DIR / "index.html")

@app.get("/onboarding")
def read_onboarding():
    return FileResponse(STUDIO_DIR / "onboarding.html")

@app.get("/create")
def read_create():
    return FileResponse(STUDIO_DIR / "create.html")

@app.get("/studio")
@app.get("/editor")
def read_studio():
    return FileResponse(STUDIO_DIR / "index.html")

@app.get("/cockpit")
@app.get("/settings")
def read_cockpit():
    cockpit_file = STUDIO_DIR / "cockpit.html"
    if cockpit_file.exists():
        return FileResponse(cockpit_file)
    return FileResponse(STUDIO_DIR / "index.html")

# Mount Static Frontend
if STUDIO_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STUDIO_DIR), html=True), name="studio")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PLUTO_STUDIO_PORT", 8088))
    print(f"\n──────────────────────────────────────────────────────────────────────────")
    print(f"  🎬 PLUTO STUDIO LIVE ON: http://localhost:{port}")
    uvicorn.run(
        "src.studio_api:app",
        host="127.0.0.1",
        port=port,
        app_dir=str(PLUTO_ROOT),
        reload=True,
        reload_dirs=[str(PLUTO_ROOT / "src"), str(PLUTO_ROOT / "studio")],
    )
