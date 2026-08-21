#!/usr/bin/env python3
"""Pluto Studio Backend API.

Modular entrypoint delegating to src.pluto package layout while preserving
100% backwards compatibility for existing imports, monkeypatching, and tests.
"""

import os
import sys
import time
import json
import asyncio
import secrets
import threading
from pathlib import Path
from typing import Optional, List, Dict, Literal

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, Depends, Request, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# Core package layout
from src.pluto.core.config import Settings, get_settings, PLUTO_ROOT
from src.pluto.core.utils import (
    run_ffmpeg,
    discard_partial,
    ffmpeg_error,
    write_meta,
    resolve_output,
)
from src.pluto.services.audio import (
    CLOUD_NOT_READY,
    mlx_generate_audio,
    loudnorm_two_pass,
    peak_normalize,
    synthesize_voice,
    load_kokoro,
    kokoro_assets,
    get_kokoro_search_paths,
)
from src.pluto.services.image_utils import (
    MAX_IMAGE_SIZE,
    ALLOWED_IMAGE_MIMES,
    sanitize_upload_filename,
    parse_image_dimensions_fallback,
    get_image_info,
    get_aspect_ratio_str,
    parse_multipart_form_data,
)
from src.pluto.services.generation import (
    GenerateRequest,
    ExtendRequest,
    UpscaleRequest,
    AutoScriptRequest,
    CompositeMotionVectorRequest,
    worker_headers,
)
from src.pluto.api.routes.engines import MultiEngineGenerateRequest
from src.pluto.api.routes.lora import TrainLoRARequest
from src.pluto.api.routes.audio import (
    MusicRequest,
    VoiceRequest,
    MixDuckedAudioRequest,
    LocalSynthesizeAudioRequest,
)
from src.pluto.api.routes.storyboard import (
    StoryboardDecomposeRequest,
    LocalNarrativeDecomposeRequest,
)
from src.pluto.api.routes.gpu import (
    GpuActionRequest,
    InspectActionRequest,
    SkyScheduleRequest,
    SkyFailoverRequest,
)

from src.cli import (
    get_instance_info,
    fetch_worker_health,
    load_config,
    save_config,
    run_cmd,
)
from src.skypilot_orchestrator import sky_orchestrator, generate_skypilot_yaml
from src.storyboard_decomposer import decompose_storyboard
from src.pluto.app import create_app
from src.pluto.api.deps import require_token  # re-export for backward compat

# Settings & Directory Aliases
_settings = get_settings()
OUTPUTS_DIR = _settings.outputs_dir
UPLOADS_DIR = OUTPUTS_DIR / "uploads"
STUDIO_DIR = _settings.studio_dir
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

STUDIO_TOKEN = _settings.studio_token
WORKER_TOKEN = os.environ.get("LOCAL_WORKER_TOKEN", "")

# Telemetry & Status Cache
_STATUS_CACHE_TTL_SEC = 2.0
_status_cache_lock = threading.Lock()
_status_refresh_lock = threading.Lock()
_status_cache = None
_status_cache_at = 0.0

# Watchdog
_last_activity_time = time.time()
_watchdog_event = None


def update_activity() -> None:
    from src.pluto.api import deps
    deps.update_activity()
    global _last_activity_time
    _last_activity_time = deps.get_last_activity_time()



def _build_status(cfg: dict) -> dict:
    """Build one status snapshot; callers must enforce refresh single-flight."""
    api_mod = sys.modules.get("src.studio_api")
    gi_fn = getattr(api_mod, "get_instance_info", get_instance_info) if api_mod else get_instance_info
    inst = gi_fn(cfg)
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
        fh_fn = getattr(api_mod, "fetch_worker_health", fetch_worker_health) if api_mod else fetch_worker_health
        worker_health = fh_fn(inst["ip"])

    global _last_activity_time, _watchdog_event
    return {
        "instance": inst,
        "gpu_online": inst.get("state") == "running",
        "uptime_minutes": uptime_min,
        "estimated_cost_usd": cost,
        "worker": worker_health,
        "worker_ready": worker_health.get("ok", False) if worker_health else False,
        "watchdog": {
            "elapsed_mins": round((time.time() - _last_activity_time) / 60.0, 1),
            "last_event": _watchdog_event,
        },
    }


def get_status() -> dict:
    """Retrieve bounded, single-flight status of the GPU box and worker."""
    global _status_cache, _status_cache_at
    api_mod = sys.modules.get("src.studio_api")
    lc_fn = getattr(api_mod, "load_config", load_config) if api_mod else load_config
    cfg = lc_fn()
    now = time.monotonic()
    with _status_cache_lock:
        if _status_cache is not None and now - _status_cache_at < _STATUS_CACHE_TTL_SEC:
            import copy
            return copy.deepcopy(_status_cache)

    with _status_refresh_lock:
        now = time.monotonic()
        with _status_cache_lock:
            if _status_cache is not None and now - _status_cache_at < _STATUS_CACHE_TTL_SEC:
                import copy
                return copy.deepcopy(_status_cache)
        b_fn = getattr(api_mod, "_build_status", _build_status) if api_mod else _build_status
        snapshot = b_fn(cfg)
        with _status_cache_lock:
            _status_cache = snapshot
            _status_cache_at = time.monotonic()
        import copy
        return copy.deepcopy(snapshot)


def has_active_jobs() -> bool:
    try:
        if not OUTPUTS_DIR.exists():
            return False
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
    global _watchdog_event, _last_activity_time
    api_mod = sys.modules.get("src.studio_api")
    while True:
        try:
            sl_fn = getattr(api_mod.asyncio if api_mod else asyncio, "sleep", asyncio.sleep)
            await sl_fn(30)
            
            haj_fn = getattr(api_mod, "has_active_jobs", has_active_jobs) if api_mod else has_active_jobs
            if await asyncio.to_thread(haj_fn):
                up_fn = getattr(api_mod, "update_activity", update_activity) if api_mod else update_activity
                up_fn()
                
            lc_fn = getattr(api_mod, "load_config", load_config) if api_mod else load_config
            cfg = lc_fn()
            idle_mins = cfg.get("idle_shutdown_minutes", 20)
            if idle_mins <= 0:
                continue
                
            tm_fn = getattr(api_mod.time if api_mod else time, "time", time.time)
            now = tm_fn()
            lat = getattr(api_mod, "_last_activity_time", _last_activity_time)
            elapsed = now - lat
            if elapsed > (idle_mins * 60):
                gi_fn = getattr(api_mod, "get_instance_info", get_instance_info) if api_mod else get_instance_info
                inst = await asyncio.to_thread(gi_fn, cfg)
                if inst and inst.get("state") == "running":
                    print(f"[Watchdog] Auto-terminating GPU instance {inst.get('id')} after {idle_mins}m of inactivity to save cost.")
                    _watchdog_event = {"event": "auto_shutdown", "time": now, "idle_mins": idle_mins}
                    if api_mod:
                        api_mod._watchdog_event = _watchdog_event
                    infra_script = PLUTO_ROOT / "infra" / "gpu-box.sh"
                    if infra_script.exists():
                        try:
                            rc_fn = getattr(api_mod, "run_cmd", run_cmd) if api_mod else run_cmd
                            await asyncio.to_thread(rc_fn, ["bash", str(infra_script), "terminate"])
                        except Exception as e:
                            print(f"[Watchdog] Failed to auto-terminate: {e}")
                    up_fn = getattr(api_mod, "update_activity", update_activity) if api_mod else update_activity
                    up_fn()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Watchdog] Error in loop: {e}")


# Build application
app = create_app(_settings)

if __name__ == "__main__":
    host = os.environ.get("PLUTO_STUDIO_HOST", "0.0.0.0")
    port = int(os.environ.get("PLUTO_STUDIO_PORT", 8088))
    print(f"\n✨ SpacePilot Studio API running on http://{host}:{port} (and http://spacepilot.localhost:{port})")
    print(f"🔑 Studio Token: {STUDIO_TOKEN[:8]}...{STUDIO_TOKEN[-8:]}\n")
    uvicorn.run(app, host=host, port=port, log_level="info")
