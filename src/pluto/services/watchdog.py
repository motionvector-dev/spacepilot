"""Idle watchdog background monitor for GPU cost conservation."""

import time
import json
import asyncio
from src.pluto.core.config import get_settings
from src.pluto.api.deps import update_activity, get_last_activity_time
from src.pluto.services.gpu_lifecycle import set_watchdog_event
from src.cli import load_config, get_instance_info, run_cmd


def has_active_jobs() -> bool:
    settings = get_settings()
    try:
        if not settings.outputs_dir.exists():
            return False
        for path in settings.outputs_dir.glob("*.json"):
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
    settings = get_settings()
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
            elapsed = now - get_last_activity_time()
            if elapsed > (idle_mins * 60):
                inst = await asyncio.to_thread(get_instance_info, cfg)
                if inst and inst.get("state") == "running":
                    print(f"[Watchdog] Auto-terminating GPU instance {inst.get('id')} after {idle_mins}m of inactivity to save cost.")
                    set_watchdog_event({"event": "auto_shutdown", "time": now, "idle_mins": idle_mins})
                    infra_script = settings.root_dir / "infra" / "gpu-box.sh"
                    if infra_script.exists():
                        try:
                            await asyncio.to_thread(run_cmd, ["bash", str(infra_script), "terminate"])
                        except Exception as e:
                            print(f"[Watchdog] Failed to auto-terminate: {e}")
                    update_activity()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Watchdog] Error in loop: {e}")
