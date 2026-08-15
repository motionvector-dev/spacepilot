#!/usr/bin/env python3
"""Pluto CLI - Remote GPU Box & Video Generation Tool

Controls remote AWS Spot GPU instances, monitors real-time VRAM / GPU metrics,
streams live worker logs, and triggers remote LTX-2.5 video generations
directly from your Mac terminal.
"""

import os
import sys
import time
import json
import argparse
import shutil
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

# Paths
PLUTO_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = PLUTO_ROOT / "outputs"
CONFIG_FILE = PLUTO_ROOT / ".pluto_config.json"
KEY_FILE_DEFAULT = Path.home() / ".ssh" / "pluto-gpu-key-2026-07-26.pem"

DEFAULT_CONFIG = {
    "aws_profile": "antigravity-dev-user",
    "aws_region": "us-east-1",
    "instance_type": "g6e.2xlarge",
    "key_name": "pluto-gpu-key-2026-07-26",
    "key_file": str(KEY_FILE_DEFAULT),
    "security_group": "pluto-gpu-sg",
    "market_type": "spot",
    "spot_hourly_rate": 0.75,
    "default_resolution": [1024, 576],
    "default_seconds": 4.0,
    "default_steps": 30,
}


WORKER_TOKEN = os.environ.get("LOCAL_WORKER_TOKEN", "")


def worker_headers(extra=None):
    """Auth headers for the remote LTX worker; refuses to call it unauthenticated."""
    if not WORKER_TOKEN:
        raise RuntimeError("LOCAL_WORKER_TOKEN is not set; export the GPU worker token first")
    headers = {"Authorization": f"Bearer {WORKER_TOKEN}"}
    if extra:
        headers.update(extra)
    return headers


def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
                return {**DEFAULT_CONFIG, **cfg}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def run_cmd(cmd, check=True, capture=False, stdin_text=None):
    """Run an argv list. Strings are rejected so no caller can reintroduce a shell."""
    if isinstance(cmd, str):
        raise TypeError("run_cmd takes an argv list, not a shell string")
    if capture:
        res = subprocess.run(cmd, text=True, input=stdin_text, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check and res.returncode != 0:
            raise RuntimeError(f"Command failed ({res.returncode}): {' '.join(cmd)}\n{res.stderr}")
        return res.stdout.strip()
    return subprocess.run(cmd, check=check, text=True, input=stdin_text)


def get_instance_info(cfg):
    cmd = [
        "aws", "--profile", cfg["aws_profile"], "--region", cfg["aws_region"],
        "ec2", "describe-instances",
        "--filters",
        "Name=tag:Name,Values=pluto-gpu-research,ltx-spot-ec2,ltx-ec2",
        "Name=instance-state-name,Values=pending,running,stopping,stopped",
        "--query", "Reservations[].Instances[][InstanceId,State.Name,PublicIpAddress,InstanceType,LaunchTime]",
        "--output", "json",
    ]
    try:
        raw = run_cmd(cmd, capture=True)
        items = json.loads(raw) if raw else []
        if items and len(items) > 0:
            item = items[0]
            return {
                "id": item[0],
                "state": item[1],
                "ip": item[2] if len(item) > 2 else None,
                "type": item[3] if len(item) > 3 else cfg["instance_type"],
                "launch_time": item[4] if len(item) > 4 else None,
            }
    except Exception as e:
        pass
    return None


def fetch_worker_health(ip):
    if not ip:
        return None
    url = f"http://{ip}:5000/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PlutoCLI/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"ok": False, "status": "http_error", "code": e.code}
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# COMMAND HANDLERS
# ─────────────────────────────────────────────────────────────────────────────

def cmd_status(args, cfg):
    print("──────────────────────────────────────────────────────────────────────────")
    print("  PLUTO GPU BOX & WORKER STATUS")
    print("──────────────────────────────────────────────────────────────────────────")
    inst = get_instance_info(cfg)
    if not inst:
        print("  AWS Instance : [STOPPED / NONE] No active GPU instance found.")
        print("  Launch with  : pluto launch")
        print("──────────────────────────────────────────────────────────────────────────")
        return

    print(f"  Instance ID  : {inst['id']} ({inst['type']})")
    print(f"  AWS State    : {inst['state'].upper()}")
    print(f"  Public IP    : {inst['ip'] or 'Assigning...'}")

    # Calculate runtime cost estimate
    if inst.get("launch_time"):
        try:
            # Parse ISO timestamp
            import datetime
            lt = datetime.datetime.fromisoformat(inst["launch_time"].replace("Z", "+00:00"))
            uptime_min = (datetime.datetime.now(datetime.timezone.utc) - lt).total_seconds() / 60.0
            cost = (uptime_min / 60.0) * cfg["spot_hourly_rate"]
            print(f"  Uptime       : {uptime_min:.1f} mins (Estimated Cost: ${cost:.2f})")
        except Exception:
            pass

    print("──────────────────────────────────────────────────────────────────────────")
    if inst["ip"] and inst["state"] == "running":
        health = fetch_worker_health(inst["ip"])
        if health and health.get("ok"):
            print(f"  Worker State : [READY] Model resident in VRAM")
            print(f"  VRAM Allocated: {health.get('vram_allocated_gib', 'N/A')} GiB")
            print(f"  VRAM Reserved : {health.get('vram_reserved_gib', 'N/A')} GiB")
            print(f"  Active Jobs   : {health.get('active_jobs', 0)}")
            print(f"  HTTP Endpoint : http://{inst['ip']}:5000")
        elif health and health.get("status") == "warming_up":
            print(f"  Worker State : [WARMING UP] Loading 78 GB model into VRAM (~170s)...")
        else:
            print(f"  Worker State : [OFFLINE / STARTING] Server not responding on port 5000.")
            print(f"                 Check logs with: pluto logs")
    print("──────────────────────────────────────────────────────────────────────────")


def cmd_launch(args, cfg):
    print("──────────────────────────────────────────────────────────────────────────")
    print("  LAUNCHING PLUTO GPU BOX (AWS SPOT L40S)")
    print("──────────────────────────────────────────────────────────────────────────")
    inst = get_instance_info(cfg)
    if inst and inst["state"] in ("running", "pending"):
        print(f"  Already running: {inst['id']} ({inst['ip']})")
        return

    # Trigger launch script
    infra_script = PLUTO_ROOT / "infra" / "gpu-box.sh"
    if not infra_script.exists():
        print(f"  Error: {infra_script} not found.")
        return

    run_cmd(["bash", str(infra_script), "launch"])
    time.sleep(2)
    inst = get_instance_info(cfg)
    if inst and inst["ip"]:
        print(f"\n  Box ready at IP: {inst['ip']}")
        print("  Deploying worker code to /scratch/worker...")
        cmd_deploy(args, cfg)


def cmd_deploy(args, cfg):
    inst = get_instance_info(cfg)
    if not inst or not inst["ip"]:
        print("  Error: No running instance found to deploy to.")
        return

    ip = inst["ip"]
    key = cfg["key_file"]
    if not WORKER_TOKEN:
        print("  Error: LOCAL_WORKER_TOKEN is not set; the worker would start unauthenticated.")
        return

    print(f"  Syncing worker files to {ip}...")
    run_cmd(["ssh", "-o", "StrictHostKeyChecking=accept-new", "-i", key, f"ubuntu@{ip}",
             "sudo mkdir -p /scratch/worker && sudo chown -R ubuntu:ubuntu /scratch"])
    run_cmd(["scp", "-i", key, f"{PLUTO_ROOT}/src/ltx_worker.py", f"ubuntu@{ip}:/scratch/worker/ltx_worker.py"])
    run_cmd(["scp", "-i", key, f"{PLUTO_ROOT}/infra/setup_ltx_ec2.sh", f"ubuntu@{ip}:/scratch/worker/setup.sh"])
    print("  Starting setup & warmup in background...")
    # Token arrives on stdin so it never lands in the remote process list.
    run_cmd(["ssh", "-i", key, f"ubuntu@{ip}",
             "cd /scratch/worker && export LOCAL_WORKER_TOKEN=$(cat) && bash setup.sh"],
            stdin_text=WORKER_TOKEN)
    print("\n  Deployment complete! Check status with: pluto status")


def cmd_ssh(args, cfg):
    inst = get_instance_info(cfg)
    if not inst or not inst["ip"]:
        print("  Error: No running instance found.")
        return
    key = cfg["key_file"]
    ip = inst["ip"]
    print(f"Connecting to ubuntu@{ip}...")
    subprocess.run(["ssh", "-i", key, f"ubuntu@{ip}"])


def cmd_logs(args, cfg):
    inst = get_instance_info(cfg)
    if not inst or not inst["ip"]:
        print("  Error: No running instance found.")
        return
    key = cfg["key_file"]
    ip = inst["ip"]
    print(f"Streaming worker logs from {ip} (Ctrl+C to stop)...")
    subprocess.run(["ssh", "-i", key, f"ubuntu@{ip}",
                    "tail -f /scratch/worker/worker.log 2>/dev/null || tail -f /tmp/worker.log"])


def cmd_generate(args, cfg):
    inst = get_instance_info(cfg)
    if not inst or not inst["ip"]:
        print("  Error: No running GPU box. Run 'pluto launch' first.")
        return

    ip = inst["ip"]
    prompt = args.prompt
    seconds = args.seconds or cfg["default_seconds"]
    width, height = args.resolution or cfg["default_resolution"]
    seed = args.seed
    steps = args.steps or cfg["default_steps"]

    print("──────────────────────────────────────────────────────────────────────────")
    print("  PLUTO VIDEO GENERATION")
    print("──────────────────────────────────────────────────────────────────────────")
    print(f"  Prompt     : \"{prompt}\"")
    print(f"  Resolution : {width}x{height} | Duration: {seconds}s | Steps: {steps}")
    print(f"  Target Box : http://{ip}:5000")
    print("──────────────────────────────────────────────────────────────────────────")

    payload = {
        "prompt": prompt,
        "seconds": seconds,
        "width": width,
        "height": height,
        "steps": steps,
    }
    if seed is not None:
        payload["seed"] = seed

    data = json.dumps(payload).encode()
    try:
        headers = worker_headers({"Content-Type": "application/json"})
    except RuntimeError as e:
        print(f"  Error: {e}")
        return
    req = urllib.request.Request(
        f"http://{ip}:5000/generate",
        data=data,
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode())
            job_id = res.get("job_id")
            print(f"  Job Queued : {job_id} (ETA: {res.get('eta_seconds', 12)}s)")
    except Exception as e:
        print(f"  Error submitting job: {e}")
        return

    # Poll status with progress bar
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    start_t = time.time()
    print("  Rendering  : [", end="", flush=True)

    while True:
        time.sleep(1.5)
        print("█", end="", flush=True)
        try:
            st_req = urllib.request.Request(f"http://{ip}:5000/status/{job_id}", headers=worker_headers())
            with urllib.request.urlopen(st_req) as st_resp:
                st_data = json.loads(st_resp.read().decode())
                if st_data.get("status") == "completed":
                    dur = time.time() - start_t
                    print(f"] Done in {dur:.1f}s!")

                    # Download MP4
                    dl_req = urllib.request.Request(f"http://{ip}:5000/download/{job_id}", headers=worker_headers())
                    out_path = OUTPUTS_DIR / f"{job_id}.mp4"
                    with urllib.request.urlopen(dl_req) as dl_resp, open(out_path, "wb") as out_f:
                        shutil.copyfileobj(dl_resp, out_f)
                    print(f"  Output MP4 : {out_path} ({out_path.stat().st_size / (1024*1024):.2f} MB)")
                    
                    if args.open:
                        subprocess.run(["open", str(out_path)])
                    break
                elif st_data.get("status") == "failed":
                    print(f"\n  Error: Job failed: {st_data.get('error')}")
                    break
        except Exception as e:
            pass


def cmd_sync(args, cfg):
    inst = get_instance_info(cfg)
    if not inst or not inst["ip"]:
        print("  Error: No running instance found.")
        return
    key = cfg["key_file"]
    ip = inst["ip"]
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Syncing /scratch/out/ from {ip} to {OUTPUTS_DIR}...")
    subprocess.run(["rsync", "-avz", "-e", f"ssh -i {key}", f"ubuntu@{ip}:/scratch/out/", f"{OUTPUTS_DIR}/"])
    print("Sync complete!")


def cmd_studio(args, cfg):
    port = args.port or 8088
    print("──────────────────────────────────────────────────────────────────────────")
    print(f"  🎬 LAUNCHING PLUTO STUDIO ON http://localhost:{port}")
    print("──────────────────────────────────────────────────────────────────────────")
    studio_script = PLUTO_ROOT / "src" / "studio_api.py"
    if args.open:
        import webbrowser
        time.sleep(1.0)
        webbrowser.open(f"http://localhost:{port}")
    subprocess.run([sys.executable, str(studio_script)], env={**os.environ, "PLUTO_STUDIO_PORT": str(port)})


def cmd_terminate(args, cfg):
    inst = get_instance_info(cfg)
    if not inst:
        print("  No active instance found to terminate.")
        return

    print("──────────────────────────────────────────────────────────────────────────")
    print(f"  TERMINATING GPU INSTANCE {inst['id']} ({inst.get('ip')})")
    print("──────────────────────────────────────────────────────────────────────────")
    if not args.yes:
        confirm = input("  Are you sure you want to terminate this instance? (y/N): ").strip().lower()
        if confirm != "y":
            print("  Cancelled.")
            return

    infra_script = PLUTO_ROOT / "infra" / "gpu-box.sh"
    run_cmd(["bash", str(infra_script), "terminate"])
    print("  Instance terminated cleanly. Zero ongoing billing.")


# ─────────────────────────────────────────────────────────────────────────────
# CLI ENTRYPOINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    cfg = load_config()
    parser = argparse.ArgumentParser(description="Pluto Remote GPU Box & Video Generation Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # studio
    studio_p = subparsers.add_parser("studio", help="Launch interactive Pluto Studio Web UI")
    studio_p.add_argument("--port", type=int, default=8088, help="Port to bind (default: 8088)")
    studio_p.add_argument("--open", action="store_true", help="Open in default browser")

    # status
    subparsers.add_parser("status", help="Show instance state, VRAM, and worker health")

    # launch
    subparsers.add_parser("launch", help="Launch AWS Spot GPU instance and deploy worker")

    # deploy
    subparsers.add_parser("deploy", help="Deploy latest worker code to running box")

    # ssh
    subparsers.add_parser("ssh", help="Open SSH terminal to GPU box")

    # logs
    subparsers.add_parser("logs", help="Stream live worker inference logs")

    # generate
    gen_p = subparsers.add_parser("generate", help="Generate a video from prompt")
    gen_p.add_argument("prompt", type=str, help="Text description of the scene")
    gen_p.add_argument("--seconds", type=float, default=4.0, help="Duration in seconds (default: 4.0)")
    gen_p.add_argument("--resolution", type=int, nargs=2, default=[1024, 576], help="Width Height (e.g. 1024 576)")
    gen_p.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    gen_p.add_argument("--steps", type=int, default=30, help="Inference steps (default: 30)")
    gen_p.add_argument("--open", action="store_true", help="Open downloaded MP4 in macOS player")

    # sync
    subparsers.add_parser("sync", help="Sync all generated videos from box to local outputs/")

    # terminate
    term_p = subparsers.add_parser("terminate", help="Terminate EC2 instance to stop billing")
    term_p.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()

    dispatch = {
        "studio": cmd_studio,
        "status": cmd_status,
        "launch": cmd_launch,
        "deploy": cmd_deploy,
        "ssh": cmd_ssh,
        "logs": cmd_logs,
        "generate": cmd_generate,
        "sync": cmd_sync,
        "terminate": cmd_terminate,
    }

    handler = dispatch.get(args.command)
    if handler:
        handler(args, cfg)


if __name__ == "__main__":
    main()
