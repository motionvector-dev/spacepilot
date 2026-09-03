"""GPU spot lifecycle and Cockpit telemetry routes."""

import sys
import json
import asyncio
import subprocess
from pathlib import Path
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
import secrets

from spacepilot.core.config import get_settings
from spacepilot.api.deps import require_token
from spacepilot.services.gpu_lifecycle import get_cached_status
from spacepilot.cli import get_instance_info, load_config, save_config, run_cmd

router = APIRouter(tags=["gpu"])


class GpuActionRequest(BaseModel):
    confirm: bool = False


class InspectActionRequest(BaseModel):
    action: str


def _get_api_attr(name, default):
    api_mod = sys.modules.get("spacepilot.web_api")
    return getattr(api_mod, name, default) if api_mod else default


@router.post("/api/gpu/launch")
def launch_gpu(req: GpuActionRequest, background_tasks: BackgroundTasks, _: None = Depends(require_token)):
    """Trigger 1-click Spot GPU launch and resident model warmup (requires confirm=True)."""
    if not req.confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Pass {'confirm': true} to authorize AWS spot instance billing."
        )
    settings = get_settings()
    lc_fn = _get_api_attr("load_config", load_config)
    gi_fn = _get_api_attr("get_instance_info", get_instance_info)
    rc_fn = _get_api_attr("run_cmd", run_cmd)
    
    cfg = lc_fn()
    try:
        inst = gi_fn(cfg)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AWS query failed; instance state unknown: {e}")
    if inst and inst.get("state") in ("running", "pending"):
        return {"status": "already_running", "instance_id": inst["id"], "ip": inst.get("ip")}

    infra_script = settings.root_dir / "infra" / "gpu-box.sh"
    if not infra_script.exists():
        raise HTTPException(status_code=500, detail="gpu-box.sh not found")

    def _run_launch():
        try:
            rc_fn(["bash", str(infra_script), "launch"])
        except Exception as e:
            print(f"[Studio] Launch failed: {e}", file=sys.stderr)

    background_tasks.add_task(_run_launch)
    return {"status": "launching", "message": "GPU instance launch initiated. Takes ~2 mins to boot and warm VRAM."}


@router.post("/api/gpu/terminate")
def terminate_gpu(req: GpuActionRequest, _: None = Depends(require_token)):
    """Safely terminate GPU box to stop billing immediately (requires confirm=True)."""
    if not req.confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Pass {'confirm': true} to authorize instance termination."
        )
    settings = get_settings()
    rc_fn = _get_api_attr("run_cmd", run_cmd)
    infra_script = settings.root_dir / "infra" / "gpu-box.sh"
    if not infra_script.exists():
        raise HTTPException(status_code=500, detail="gpu-box.sh not found")
    try:
        rc_fn(["bash", str(infra_script), "terminate"])
        return {"status": "terminated", "message": "GPU box terminated cleanly. Billing stopped."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/gpu/deploy")
def deploy_worker_api(background_tasks: BackgroundTasks, _: None = Depends(require_token)):
    """Hot-deploy latest ltx_worker.py to the running box and restart worker."""
    lc_fn = _get_api_attr("load_config", load_config)
    gi_fn = _get_api_attr("get_instance_info", get_instance_info)
    rc_fn = _get_api_attr("run_cmd", run_cmd)
    
    cfg = lc_fn()
    try:
        inst = gi_fn(cfg)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AWS query failed; instance state unknown: {e}")
    if not inst or inst.get("state") != "running":
        raise HTTPException(status_code=400, detail="No running GPU instance found to deploy to.")

    settings = get_settings()
    infra_script = settings.root_dir / "infra" / "gpu-box.sh"

    def _run_deploy():
        try:
            rc_fn(["bash", str(infra_script), "deploy"])
        except Exception as e:
            print(f"[Studio] Deploy failed: {e}", file=sys.stderr)

    background_tasks.add_task(_run_deploy)
    return {"status": "deploying", "message": "Worker deployment initiated in background."}


@router.post("/api/gpu/sync")
def sync_outputs_api(_: None = Depends(require_token)):
    """Rsync all rendered video outputs from remote /scratch/out/ to local outputs/."""
    lc_fn = _get_api_attr("load_config", load_config)
    gi_fn = _get_api_attr("get_instance_info", get_instance_info)
    
    cfg = lc_fn()
    inst = gi_fn(cfg)
    if not inst or not inst.get("ip"):
        raise HTTPException(status_code=400, detail="No running instance found to sync from.")

    key = cfg.get("key_file", str(Path.home() / ".ssh" / "pluto-gpu-key-2026-07-26.pem"))
    ip = inst["ip"]
    settings = get_settings()
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["rsync", "-avz", "-e", f"ssh -i {key} -o StrictHostKeyChecking=no", f"ubuntu@{ip}:/scratch/out/", f"{settings.outputs_dir}/"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {"ok": True, "message": "Sync complete. All videos downloaded."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}")


@router.get("/api/cockpit/status")
def get_cockpit_status():
    """Unified telemetry for the Cockpit infrastructure dashboard.

    The snapshot owns the AWS lookup.  Do not query the instance separately for
    the SSH hint: cockpit polling would otherwise bypass the status cache.
    """
    lc_fn = _get_api_attr("load_config", load_config)
    gs_fn = _get_api_attr("get_status", get_cached_status)

    cfg = lc_fn()
    base_status = gs_fn()
    inst = base_status.get("instance")

    ssh_cmd = None
    if inst and inst.get("ip") and inst.get("state") == "running":
        key = cfg.get("key_file", "~/.ssh/pluto-gpu-key-2026-07-26.pem")
        ssh_cmd = f"ssh -i {key} ubuntu@{inst['ip']}"

    return {
        **base_status,
        "config": {
            "region": cfg.get("aws_region", "us-east-1"),
            "instance_type": cfg.get("instance_type", "g6e.2xlarge"),
            "spot_hourly_rate": cfg.get("spot_hourly_rate", 0.75),
            "key_file": cfg.get("key_file"),
        },
        "ssh_command": ssh_cmd,
    }


@router.get("/api/cockpit/config")
def get_cockpit_config():
    """Get current configuration."""
    lc_fn = _get_api_attr("load_config", load_config)
    cfg = lc_fn()
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


@router.post("/api/cockpit/config")
def update_cockpit_config(body: dict, _: None = Depends(require_token)):
    """Update configuration settings."""
    lc_fn = _get_api_attr("load_config", load_config)
    sc_fn = _get_api_attr("save_config", save_config)
    
    cfg = lc_fn()
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
    sc_fn(cfg)
    
    safe_cfg = {}
    for k, v in cfg.items():
        kl = k.lower()
        if "secret" in kl or "token" in kl or "api_key" in kl:
            safe_cfg[k] = "********" if v else ""
        else:
            safe_cfg[k] = v
            
    return {"ok": True, "config": safe_cfg}


@router.get("/api/gpu/logs/stream")
async def stream_gpu_logs():
    """SSE stream of worker logs from the remote GPU box or local fallback."""
    lc_fn = _get_api_attr("load_config", load_config)
    gi_fn = _get_api_attr("get_instance_info", get_instance_info)
    
    cfg = lc_fn()
    inst = gi_fn(cfg)

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


@router.websocket("/api/gpu/inspect/shell")
async def inspect_shell_ws(websocket: WebSocket):
    settings = get_settings()

    # Before accepting anything. CORS does not apply to websockets, so a page on
    # any origin may reach this handler; the token frame below is the only other
    # gate, and a rebinding attack can read that token.
    from spacepilot.api.security import websocket_is_local

    if settings.local_only and not await websocket_is_local(websocket, settings.cors_origins):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    try:
        try:
            auth_frame = await asyncio.wait_for(websocket.receive_json(), timeout=3.0)
            if auth_frame.get("type") != "auth" or not secrets.compare_digest(str(auth_frame.get("token") or ""), settings.studio_token):
                await websocket.close(code=1008)
                return
        except (asyncio.TimeoutError, json.JSONDecodeError):
            await websocket.close(code=1008)
            return

        lc_fn = _get_api_attr("load_config", load_config)
        gi_fn = _get_api_attr("get_instance_info", get_instance_info)
        cfg = lc_fn()
        inst = gi_fn(cfg)
        if not inst or inst.get("state") != "running" or not inst.get("ip"):
            await websocket.send_json({"type": "error", "message": "Instance not running"})
            await websocket.close(code=1011)
            return

        key = cfg.get("key_file", str(Path.home() / ".ssh" / "pluto-gpu-key-2026-07-26.pem"))
        ip = inst["ip"]

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
                                cols = data.get("cols", 120)
                                rows = data.get("rows", 40)
                                process.stdin.write(f"stty cols {cols} rows {rows}\n".encode())
                                await process.stdin.drain()
                                continue
                        except json.JSONDecodeError:
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


@router.get("/api/gpu/inspect/metrics")
def get_inspect_metrics(_: None = Depends(require_token)):
    lc_fn = _get_api_attr("load_config", load_config)
    gi_fn = _get_api_attr("get_instance_info", get_instance_info)
    
    cfg = lc_fn()
    inst = gi_fn(cfg)
    if not inst or inst.get("state") != "running" or not inst.get("ip"):
        raise HTTPException(status_code=400, detail="Instance not running")

    key = cfg.get("key_file", str(Path.home() / ".ssh" / "pluto-gpu-key-2026-07-26.pem"))
    ip = inst["ip"]

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


@router.post("/api/gpu/inspect/action")
def post_inspect_action(req: InspectActionRequest, _: None = Depends(require_token)):
    lc_fn = _get_api_attr("load_config", load_config)
    gi_fn = _get_api_attr("get_instance_info", get_instance_info)
    
    cfg = lc_fn()
    inst = gi_fn(cfg)
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
