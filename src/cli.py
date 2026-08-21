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
import uuid
import argparse
import shutil
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

# Paths
PLUTO_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = Path(os.environ.get("PLUTO_OUTPUTS_DIR", PLUTO_ROOT / "outputs"))
CONFIG_FILE = PLUTO_ROOT / ".pluto_config.json"
KEY_FILE_DEFAULT = Path.home() / ".ssh" / "pluto-gpu-key-2026-07-26.pem"

DEFAULT_CONFIG = {
    "aws_profile": "default",
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

    # Checked before launch: a box we cannot deploy to still bills by the hour.
    if not WORKER_TOKEN:
        print("  Error: LOCAL_WORKER_TOKEN is not set; the worker would start unauthenticated.")
        print("  Export it before launching so the GPU box is not left billing idle.")
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
    image_path = getattr(args, "image", None)
    fps = getattr(args, "fps", 24) or 24
    negative_prompt = getattr(args, "negative_prompt", None)
    stg = getattr(args, "stg", 0.0)
    modality_scale = getattr(args, "modality_scale", 1.0)
    guidance_scale = getattr(args, "guidance_scale", 1.0)
    audio_guidance_scale = getattr(args, "audio_guidance_scale", 1.0)
    guidance_rescale = getattr(args, "guidance_rescale", 0.0)
    conditioning_scale = getattr(args, "conditioning_scale", 1.0)
    image_noise_scale = getattr(args, "image_noise_scale", 0.0)

    print("──────────────────────────────────────────────────────────────────────────")
    print("  PLUTO VIDEO GENERATION (LTX-2.5)")
    print("──────────────────────────────────────────────────────────────────────────")
    print(f"  Prompt     : \"{prompt}\"")
    print(f"  Resolution : {width}x{height} | Duration: {seconds}s ({fps} fps) | Steps: {steps}")
    if stg > 0:
        print(f"  Guidance   : CFG={guidance_scale} | STG={stg} (blocks=[28]) | ModalitySync={modality_scale}")
    if image_path:
        print(f"  Image      : {image_path} (I2V mode, cond={conditioning_scale}, noise={image_noise_scale})")
    print(f"  Target Box : http://{ip}:5000")
    print("──────────────────────────────────────────────────────────────────────────")

    remote_image_path = None
    if image_path:
        if not os.path.exists(image_path):
            print(f"  Error: Image not found: {image_path}")
            return
        try:
            headers = worker_headers({})
        except RuntimeError as e:
            print(f"  Error: {e}")
            return
        # Upload the image to the worker
        import mimetypes
        mime = mimetypes.guess_type(image_path)[0] or "image/png"
        filename = os.path.basename(image_path)
        print(f"  Uploading image to worker...")
        with open(image_path, "rb") as f:
            files = {"file": (filename, f, mime)}
            import http.client
            import io
            boundary = f"----pluto{uuid.uuid4().hex}"
            body = io.BytesIO()
            for name, (fname, fobj, ftype) in files.items():
                body.write(f"--{boundary}\r\n".encode())
                body.write(f'Content-Disposition: form-data; name="{name}"; filename="{fname}"\r\n'.encode())
                body.write(f"Content-Type: {ftype}\r\n\r\n".encode())
                body.write(fobj.read())
                body.write(b"\r\n")
            body.write(f"--{boundary}--\r\n".encode())
            body_bytes = body.getvalue()
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
            conn = http.client.HTTPConnection(ip, 5000, timeout=30)
            conn.request("POST", "/upload", body=body_bytes, headers=headers)
            resp = conn.getresponse()
            data = resp.read().decode()
            conn.close()
            if resp.status != 200:
                print(f"  Error uploading image: {resp.status} {data}")
                return
            upload_resp = json.loads(data)
            remote_image_path = upload_resp["path"]
            print(f"  Image uploaded: {remote_image_path}")

    payload = {
        "prompt": prompt,
        "seconds": seconds,
        "fps": fps,
        "width": width,
        "height": height,
        "steps": steps,
        "guidance_scale": guidance_scale,
        "audio_guidance_scale": audio_guidance_scale,
        "stg_scale": stg,
        "modality_scale": modality_scale,
        "guidance_rescale": guidance_rescale,
        "conditioning_scale": conditioning_scale,
        "image_noise_scale": image_noise_scale,
    }
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt
    if seed is not None:
        payload["seed"] = seed
    if remote_image_path:
        payload["image_path"] = remote_image_path

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
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode())
            job_id = res.get("job_id")
            print(f"  Job Queued : {job_id} (ETA: {res.get('eta_seconds', 15)}s)")
    except Exception as e:
        print(f"  Error submitting job: {e}")
        return

    # Poll status with progress bar
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    start_t = time.time()
    print("  Rendering  : [", end="", flush=True)

    retries = 0
    while True:
        time.sleep(1.5)
        print("█", end="", flush=True)
        try:
            st_req = urllib.request.Request(f"http://{ip}:5000/status/{job_id}", headers=worker_headers())
            with urllib.request.urlopen(st_req, timeout=10) as st_resp:
                st_data = json.loads(st_resp.read().decode())
                retries = 0
                if st_data.get("status") == "completed":
                    dur = time.time() - start_t
                    print(f"] Done in {dur:.1f}s!")

                    # Download MP4
                    dl_req = urllib.request.Request(f"http://{ip}:5000/download/{job_id}", headers=worker_headers())
                    out_path = OUTPUTS_DIR / f"{job_id}.mp4"
                    with urllib.request.urlopen(dl_req, timeout=60) as dl_resp, open(out_path, "wb") as out_f:
                        shutil.copyfileobj(dl_resp, out_f)
                    print(f"  Output MP4 : {out_path} ({out_path.stat().st_size / (1024*1024):.2f} MB)")
                    
                    if args.open:
                        subprocess.run(["open", str(out_path)])
                    break
                elif st_data.get("status") == "failed":
                    print(f"\n  Error: Job failed: {st_data.get('error')}")
                    break
        except Exception:
            retries += 1
            if retries > 20:
                print(f"\n  Error: Connection lost while polling worker status.")
                break


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


def studio_python(cfg):
    """Interpreter that can serve the studio.

    Scans configured interpreter, active sys.executable, Conda envs, and virtualenvs
    for a Python environment with fastapi and uvicorn installed.
    """
    candidates = [
        os.environ.get("PLUTO_PYTHON"),
        cfg.get("python_bin"),
        sys.executable,
        str(Path.home() / "miniconda3" / "envs" / "py312" / "bin" / "python"),
        str(Path.home() / "miniconda3" / "envs" / "local-ml-py311" / "bin" / "python"),
    ]

    # Dynamically scan user Conda environments
    conda_envs_dir = Path.home() / "miniconda3" / "envs"
    if conda_envs_dir.exists():
        for env_dir in conda_envs_dir.iterdir():
            py_bin = env_dir / "bin" / "python"
            if py_bin.exists():
                candidates.append(str(py_bin))

    # Scan local project virtualenvs
    for venv_name in (".venv", "venv", "env"):
        py_bin = PLUTO_ROOT / venv_name / "bin" / "python"
        if py_bin.exists():
            candidates.append(str(py_bin))

    # Standard Homebrew and system paths
    candidates.extend(["/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"])

    for candidate in candidates:
        if not candidate:
            continue
        try:
            probe = subprocess.run(
                [candidate, "-c", "import fastapi, uvicorn"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            if probe.returncode == 0:
                if cfg.get("python_bin") != candidate:
                    cfg["python_bin"] = candidate
                    save_config(cfg)
                return candidate
        except Exception:
            continue
    return None


def cmd_studio(args, cfg):
    port = args.port or 8088
    studio_script = PLUTO_ROOT / "src" / "studio_api.py"

    python_bin = studio_python(cfg)
    if not python_bin:
        print("  Error: no interpreter found with fastapi + uvicorn installed.")
        print("  Set PLUTO_PYTHON, or add \"python_bin\" to .pluto_config.json,")
        print("  pointing at the environment where you ran: pip install -r requirements.txt")
        return

    print("──────────────────────────────────────────────────────────────────────────")
    print(f"  🎬 LAUNCHING PLUTO STUDIO ON http://localhost:{port}")
    print("──────────────────────────────────────────────────────────────────────────")
    if args.open:
        import webbrowser
        time.sleep(1.0)
        webbrowser.open(f"http://localhost:{port}")
    subprocess.run([python_bin, str(studio_script)], env={**os.environ, "PLUTO_STUDIO_PORT": str(port)})


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
    parser = argparse.ArgumentParser(prog="pluto", description="Pluto Remote GPU Box & Video Generation Tool")
    subparsers = parser.add_subparsers(dest="command")

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
    gen_p.add_argument("--fps", type=int, default=24, help="Frame rate (default: 24)")
    gen_p.add_argument("--resolution", type=int, nargs=2, default=[1024, 576], help="Width Height (e.g. 1024 576)")
    gen_p.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    gen_p.add_argument("--steps", type=int, default=30, help="Inference steps (default: 30)")
    gen_p.add_argument("--image", type=str, default=None, help="Path to local image for image-to-video generation")
    gen_p.add_argument("--negative-prompt", type=str, default=None, help="Negative prompt")
    gen_p.add_argument("--stg", type=float, default=0.0, help="Spatio-Temporal Guidance scale (0.0 - 2.0, default: 0.0)")
    gen_p.add_argument("--modality-scale", type=float, default=1.0, help="Audio-Visual synchronization scale (default: 1.0)")
    gen_p.add_argument("--guidance-scale", type=float, default=1.0, help="Classifier-Free Guidance scale (default: 1.0)")
    gen_p.add_argument("--audio-guidance-scale", type=float, default=1.0, help="Audio CFG scale (default: 1.0)")
    gen_p.add_argument("--guidance-rescale", type=float, default=0.0, help="Guidance rescale factor (default: 0.0)")
    gen_p.add_argument("--conditioning-scale", type=float, default=1.0, help="I2V anchor scale (default: 1.0)")
    gen_p.add_argument("--image-noise-scale", type=float, default=0.0, help="I2V initial frame noise (default: 0.0)")
    gen_p.add_argument("--open", action="store_true", help="Open downloaded MP4 in macOS player")

    # sync
    subparsers.add_parser("sync", help="Sync all generated videos from box to local outputs/")

    # terminate
    term_p = subparsers.add_parser("terminate", help="Terminate EC2 instance to stop billing")
    term_p.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

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
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
