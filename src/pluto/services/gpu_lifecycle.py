"""GPU spot instance lifecycle and telemetry service."""

import time
import copy
import threading
from typing import Optional, Dict, Any

from src.cli import get_instance_info, load_config, save_config, fetch_worker_health, run_cmd
from src.pluto.api.deps import get_last_activity_time

_STATUS_CACHE_TTL_SEC = 2.0
_status_cache_lock = threading.Lock()
_status_refresh_lock = threading.Lock()
_status_cache = None
_status_cache_at = 0.0

_watchdog_event = None


def set_watchdog_event(event: Optional[Dict[str, Any]]) -> None:
    global _watchdog_event
    _watchdog_event = event


def get_watchdog_event() -> Optional[Dict[str, Any]]:
    return _watchdog_event


def build_status(cfg: dict) -> dict:
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
            "elapsed_mins": round((time.time() - get_last_activity_time()) / 60.0, 1),
            "last_event": _watchdog_event,
        },
    }


def get_cached_status() -> dict:
    """Retrieve bounded, single-flight status of the GPU box and worker."""
    global _status_cache, _status_cache_at
    cfg = load_config()
    now = time.monotonic()
    with _status_cache_lock:
        if _status_cache is not None and now - _status_cache_at < _STATUS_CACHE_TTL_SEC:
            return copy.deepcopy(_status_cache)

    with _status_refresh_lock:
        now = time.monotonic()
        with _status_cache_lock:
            if _status_cache is not None and now - _status_cache_at < _STATUS_CACHE_TTL_SEC:
                return copy.deepcopy(_status_cache)
        snapshot = build_status(cfg)
        with _status_cache_lock:
            _status_cache = snapshot
            _status_cache_at = time.monotonic()
        return copy.deepcopy(snapshot)
