#!/usr/bin/env python3
"""SpacePilot CLI - local and remote inference tools.

Controls remote AWS Spot GPU instances, monitors real-time VRAM / GPU metrics,
streams live worker logs, and triggers remote LTX-2.5 video generations
directly from your Mac terminal.
"""

import os
import sys
import time
import json
import logging
import uuid
import argparse
import subprocess
from pathlib import Path
from typing import Any, Dict, Mapping, TextIO

import httpx

logger = logging.getLogger(__name__)

# Paths
PLUTO_ROOT = Path(__file__).resolve().parent.parent

# `python spacepilot/cli.py` puts spacepilot/ on sys.path, not the repo root, so
# every `from spacepilot.<module> import ...` below raises ModuleNotFoundError
# named 'spacepilot'. `python -m spacepilot.cli` does not have the problem. Support both,
# because the first form is what a path in a doc or a launch config looks like.
if str(PLUTO_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUTO_ROOT))
from spacepilot.paths import env_value

OUTPUTS_DIR = Path(env_value("SPACEPILOT_OUTPUTS_DIR", "PLUTO_OUTPUTS_DIR", default=str(PLUTO_ROOT / "outputs")))
CONFIG_FILE = PLUTO_ROOT / ".pluto_config.json"
KEY_FILE_DEFAULT = Path(
    env_value(
        "SPACEPILOT_SSH_KEY",
        "PLUTO_SSH_KEY",
        default=str(Path.home() / ".ssh" / "pluto-gpu-key-2026-07-26.pem"),
    )
)

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
    "idle_shutdown_minutes": 20,
    "default_steps": 30,
}

OUTPUT_MODES = frozenset({"live", "plain"})


def _valid_output_mode(value: object, source: str) -> str | None:
    """Normalise one configured output mode, rejecting a misleading typo."""
    if value is None:
        return None
    if not isinstance(value, str) or value.strip().lower() not in OUTPUT_MODES:
        raise ValueError(f"{source} must be one of: live, plain")
    return value.strip().lower()


def resolve_output_mode(
    explicit: object = None,
    cfg: Mapping[str, Any] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    stdout: TextIO | None = None,
) -> str:
    """Resolve rendering mode with invocation, env, config, then TTY precedence."""
    selected = _valid_output_mode(explicit, "--live/--plain")
    if selected:
        return selected

    env = os.environ if environ is None else environ
    if "SPACEPILOT_OUTPUT_MODE" in env:
        return _valid_output_mode(env["SPACEPILOT_OUTPUT_MODE"], "SPACEPILOT_OUTPUT_MODE")  # type: ignore[index]

    config = cfg or {}
    if "output_mode" in config:
        return _valid_output_mode(config["output_mode"], "output_mode in config")

    stream = sys.stdout if stdout is None else stdout
    return "live" if stream.isatty() else "plain"


class OutputRenderer:
    """Small mode boundary shared by present and future progress displays.

    The text after the label is deliberately assembled once, before choosing a
    renderer: mode may change presentation, never the operational facts.
    """

    def __init__(self, mode: str, *, stdout: TextIO | None = None,
                 environ: Mapping[str, str] | None = None) -> None:
        self.mode = mode
        self.stream = sys.stdout if stdout is None else stdout
        env = os.environ if environ is None else environ
        self.no_color = "NO_COLOR" in env
        self._console = None
        if mode == "live":
            # Rich is intentionally loaded only for live output: piping should
            # not add terminal control codes or a rendering-only import path.
            from rich.console import Console
            self._console = Console(file=self.stream, no_color=self.no_color)

    def progress(self, label: str, facts: str) -> None:
        line = f"  {label}: {facts}"
        if self.mode == "plain":
            print(line, file=self.stream)
        else:
            assert self._console is not None
            self._console.print(line, end="\r")

    def finish(self) -> None:
        if self.mode == "live":
            assert self._console is not None
            self._console.print()


def output_renderer(args: argparse.Namespace, cfg: Mapping[str, Any] | None = None) -> OutputRenderer:
    explicit = getattr(args, "output_mode", None)
    # Direct handler tests often use MagicMock args. Only a real string is an
    # invocation override; otherwise resolve from config/TTY as normal.
    if not isinstance(explicit, str):
        explicit = None
    return OutputRenderer(resolve_output_mode(explicit, cfg))


def _extract_output_mode_flags(argv: list[str]) -> tuple[list[str], str | None]:
    """Allow --plain/--live either side of a subcommand, but never after --."""
    selected: list[str] = []
    cleaned: list[str] = []
    passthrough = False
    for arg in argv:
        if arg == "--":
            passthrough = True
            cleaned.append(arg)
        elif not passthrough and arg in ("--live", "--plain"):
            selected.append(arg[2:])
        else:
            cleaned.append(arg)
    if len(set(selected)) > 1:
        raise ValueError("--live and --plain are mutually exclusive")
    return cleaned, (selected[0] if selected else None)


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
            logger.debug("Failed to load config", exc_info=True)
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def run_cmd(cmd, check=True, capture=False, stdin_text=None, timeout=None):
    """Run an argv list. Strings are rejected so no caller can reintroduce a shell."""
    if isinstance(cmd, str):
        raise TypeError("run_cmd takes an argv list, not a shell string")
    if capture:
        res = subprocess.run(
            cmd, text=True, input=stdin_text, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=timeout,
        )
        if check and res.returncode != 0:
            raise RuntimeError(f"Command failed ({res.returncode}): {' '.join(cmd)}\n{res.stderr}")
        return res.stdout.strip()
    return subprocess.run(cmd, check=check, text=True, input=stdin_text, timeout=timeout)


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
        # AWS is an external dependency and can leave a child behind when the
        # CLI or network wedges. Status polling must always have a hard bound.
        raw = run_cmd(cmd, capture=True, timeout=3.0)
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
    except Exception:
        logger.warning("Failed to get instance info", exc_info=True)
    return None


def fetch_worker_health(ip):
    if not ip:
        return None
    url = f"http://{ip}:5000/health"
    try:
        resp = httpx.get(url, headers={"User-Agent": "PlutoCLI/1.0"}, timeout=3)
        if resp.is_error:
            # urlopen raised HTTPError here and the body was still readable; an
            # unhealthy worker answers 503 with a JSON reason worth surfacing.
            try:
                return resp.json()
            except Exception:
                return {"ok": False, "status": "http_error", "code": resp.status_code}
        return resp.json()
    except Exception:
        logger.warning("Failed to fetch worker health", exc_info=True)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# COMMAND HANDLERS
# ─────────────────────────────────────────────────────────────────────────────

def cmd_status(args: argparse.Namespace, cfg: Dict[str, Any]) -> None:
    print("──────────────────────────────────────────────────────────────────────────")
    print("  PLUTO GPU BOX & WORKER STATUS")
    print("──────────────────────────────────────────────────────────────────────────")
    inst = get_instance_info(cfg)
    if not inst:
        print("  AWS Instance : [STOPPED / NONE] No active GPU instance found.")
        print("  Launch with  : spacepilot launch")
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
            logger.debug("Failed to calculate uptime/cost", exc_info=True)

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
            print("                 Check logs with: spacepilot logs")
    print("──────────────────────────────────────────────────────────────────────────")


def cmd_launch(args: argparse.Namespace, cfg: Dict[str, Any]) -> None:
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


def cmd_deploy(args: argparse.Namespace, cfg: Dict[str, Any]) -> None:
    inst = get_instance_info(cfg)
    if not inst or not inst["ip"]:
        print("  Error: No running instance found to deploy to.")
        return

    ip = inst["ip"]
    key = cfg["key_file"]
    worker_token = os.environ.get("LOCAL_WORKER_TOKEN", WORKER_TOKEN)
    if not worker_token:
        print("  Error: LOCAL_WORKER_TOKEN is not set; the worker would start unauthenticated.")
        return

    print(f"  Syncing worker files to {ip}...")
    run_cmd(["ssh", "-o", "StrictHostKeyChecking=accept-new", "-i", key, f"ubuntu@{ip}",
             "sudo mkdir -p /opt/dlami/nvme/worker && ([ -L /scratch ] || sudo rm -rf /scratch) && sudo ln -sfn /opt/dlami/nvme /scratch && sudo chown -R ubuntu:ubuntu /opt/dlami/nvme /scratch"])
    run_cmd(["scp", "-i", key, f"{PLUTO_ROOT}/spacepilot/ltx_worker.py", f"ubuntu@{ip}:/scratch/worker/ltx_worker.py"])
    run_cmd(["scp", "-i", key, f"{PLUTO_ROOT}/infra/setup_ltx_ec2.sh", f"ubuntu@{ip}:/scratch/worker/setup.sh"])
    print("  Starting setup & warmup in background...")
    # Tokens arrive on stdin so they never land in the remote command line or process list.
    hf_token = os.environ.get("HF_TOKEN", "")
    token_payload = f"LOCAL_WORKER_TOKEN={worker_token}\nHF_TOKEN={hf_token}\n"
    run_cmd(["ssh", "-i", key, f"ubuntu@{ip}",
             "cd /scratch/worker && while IFS= read -r line; do export \"$line\"; done && bash setup.sh"],
            stdin_text=token_payload)
    print("\n  Deployment complete! Check status with: spacepilot status")


def cmd_ssh(args: argparse.Namespace, cfg: Dict[str, Any]) -> None:
    inst = get_instance_info(cfg)
    if not inst or not inst["ip"]:
        print("  Error: No running instance found.")
        return
    key = cfg["key_file"]
    ip = inst["ip"]
    print(f"Connecting to ubuntu@{ip}...")
    subprocess.run(["ssh", "-i", key, f"ubuntu@{ip}"])


def cmd_logs(args: argparse.Namespace, cfg: Dict[str, Any]) -> None:
    inst = get_instance_info(cfg)
    if not inst or not inst["ip"]:
        print("  Error: No running instance found.")
        return
    key = cfg["key_file"]
    ip = inst["ip"]
    print(f"Streaming worker logs from {ip} (Ctrl+C to stop)...")
    subprocess.run(["ssh", "-i", key, f"ubuntu@{ip}",
                    "tail -f /scratch/worker/worker.log 2>/dev/null || tail -f /tmp/worker.log"])


def cmd_generate(args: argparse.Namespace, cfg: Dict[str, Any]) -> None:
    inst = get_instance_info(cfg)
    if not inst or not inst["ip"]:
        print("  Error: No running GPU box. Run 'spacepilot launch' first.")
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
    stg = getattr(args, "stg", 1.0)
    modality_scale = getattr(args, "modality_scale", 3.0)
    guidance_scale = getattr(args, "guidance_scale", 3.0)
    audio_guidance_scale = getattr(args, "audio_guidance_scale", 7.0)
    guidance_rescale = getattr(args, "guidance_rescale", 0.7)
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
            headers["Content-Length"] = str(len(body_bytes))
            conn = http.client.HTTPConnection(ip, 5000, timeout=120)
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
    try:
        resp = httpx.post(
            f"http://{ip}:5000/generate",
            content=data,
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        res = resp.json()
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
            st_resp = httpx.get(
                f"http://{ip}:5000/status/{job_id}", headers=worker_headers(), timeout=30
            )
            st_resp.raise_for_status()
            st_data = st_resp.json()
            retries = 0
            if st_data.get("status") == "completed":
                dur = time.time() - start_t
                print(f"] Done in {dur:.1f}s!")

                # Download MP4
                if getattr(args, "output", None):
                    out_path = Path(args.output).resolve()
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                else:
                    out_path = OUTPUTS_DIR / f"{job_id}.mp4"
                with httpx.stream(
                    "GET",
                    f"http://{ip}:5000/download/{job_id}",
                    headers=worker_headers(),
                    timeout=60,
                ) as dl_resp:
                    dl_resp.raise_for_status()
                    with open(out_path, "wb") as out_f:
                        for chunk in dl_resp.iter_bytes():
                            out_f.write(chunk)
                print(f"  Output MP4 : {out_path} ({out_path.stat().st_size / (1024*1024):.2f} MB)")
                
                if args.open:
                    subprocess.run(["open", str(out_path)])
                break
            elif st_data.get("status") == "failed":
                print(f"\n  Error: Job failed: {st_data.get('error')}")
                sys.exit(1)
        except Exception:
            logger.warning("Failed during worker status polling", exc_info=True)
            retries += 1
            if retries > 20:
                print(f"\n  Error: Connection lost while polling worker status.")
                break


def cmd_sync(args: argparse.Namespace, cfg: Dict[str, Any]) -> None:
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
        env_value("SPACEPILOT_PYTHON", "PLUTO_PYTHON"),
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


def cmd_studio(args: argparse.Namespace, cfg: Dict[str, Any]) -> None:
    port = args.port or 8088
    studio_script = PLUTO_ROOT / "spacepilot" / "web_api.py"

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


def cmd_terminate(args: argparse.Namespace, cfg: Dict[str, Any]) -> None:
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


def cmd_doctor(args: argparse.Namespace, cfg: Dict[str, Any]) -> None:
    sys.path.insert(0, str(PLUTO_ROOT))
    from spacepilot.device_probe import probe_local_device
    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│                        SPACEPILOT DOCTOR                        │")
    print("└─────────────────────────────────────────────────────────────────┘")
    
    # 1. Device Profile
    profile = probe_local_device()
    print("  [Hardware]")
    print(f"  OS/Arch  : {profile.os_type} / {profile.architecture}")
    print(f"  Backend  : {profile.backend.upper()}")
    if profile.device_name:
        print(f"  Device   : {profile.device_name}")
    from spacepilot.device_probe import ACCELERATED_BACKENDS
    if profile.accelerator_memory_bytes is None:
        # Never print system RAM on this line. A machine whose GPU we could not
        # read has unknown accelerator memory, and saying "12.5GB usable" there
        # is a number the user cannot check and we cannot defend.
        print("  VRAM     : unknown — not measured (system RAM is not a substitute)")
    elif profile.backend not in ACCELERATED_BACKENDS:
        print(f"  VRAM     : {profile.vram_total_gb:.1f}GB present, 0GB usable "
              "— no compute runtime can reach this card")
    else:
        print(f"  VRAM     : {profile.vram_usable_gb:.1f}GB usable / {profile.vram_total_gb:.1f}GB total (Safety Headroom: {profile.vram_total_gb - profile.vram_usable_gb:.1f}GB)")
    print(f"  RAM      : {profile.ram_free_gb:.1f}GB free / {profile.ram_total_gb:.1f}GB total")
    for gpu in (profile.gpus if isinstance(profile.gpus, list) else []):
        vram = f"{gpu['vram_total_bytes'] / (1024 ** 3):.2f}GB" if gpu.get("vram_total_bytes") else "VRAM unknown"
        print(f"  GPU      : {gpu.get('name') or gpu.get('node')} · {vram} · driver {gpu.get('driver') or 'unknown'}")
    print(f"  Status   : {profile.status}")
    unknown = profile.unknown if isinstance(profile.unknown, dict) else {}
    if unknown:
        print("")
        print("  [Not measured]")
        for key, reason in unknown.items():
            print(f"  {key}: {reason}")
    print("")

    # 2. FFmpeg check
    print("  [Dependencies]")
    try:
        ffmpeg_res = subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        ffmpeg_ver = ffmpeg_res.stdout.split('\n')[0].replace('ffmpeg version ', '').split(' ')[0]
        print(f"  FFmpeg   : ✅ Installed (v{ffmpeg_ver})")
    except Exception:
        print("  FFmpeg   : ❌ NOT FOUND (Required for video assembly)")

    # 3. Kokoro weights check — ask the driver where it actually looks, so this
    #    reflects what TTS will really find instead of a guessed path that the
    #    driver never checks.
    try:
        from spacepilot.drivers.kokoro_driver import KokoroDriver
        m_path, v_path = KokoroDriver()._discover_asset_paths()
        kokoro_found = bool(m_path and v_path)
    except Exception:
        m_path = None
        kokoro_found = False
    if kokoro_found:
        print(f"  Kokoro   : ✅ Found ONNX weights ({Path(m_path).name})")
    else:
        print("  Kokoro   : ❌ ONNX weights NOT FOUND (Required for TTS)")
        print("             Point PLUTO_KOKORO_MODEL / PLUTO_KOKORO_VOICES at a local")
        print("             kokoro-v1.0.onnx + voices-v1.0.bin (auto-fetch not built yet).")
        
    print("")

    # 4. AWS CLI check
    print("  [Cloud & Auth]")
    try:
        aws_res = subprocess.run(["aws", "sts", "get-caller-identity", "--profile", cfg.get("aws_profile", "default")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        aws_data = json.loads(aws_res.stdout)
        print(f"  AWS Auth : ✅ Valid (Profile: {cfg.get('aws_profile', 'default')})")
        print(f"  Identity : {aws_data.get('Arn')}")
    except Exception as e:
        print("  AWS Auth : ❌ NOT AUTHENTICATED or AWS CLI not installed")
        print("             Run 'aws configure' or check credentials")

    # 5. Studio Token check
    token_path = PLUTO_ROOT / ".studio_token"
    if token_path.exists():
        print(f"  Session  : ✅ Token found (.studio_token)")
    else:
        print(f"  Session  : ⚠️ No local session token found")

    print("─────────────────────────────────────────────────────────────────")


def cmd_serve(args: argparse.Namespace, cfg: Dict[str, Any]) -> None:
    import uvicorn
    print(f"Starting Pluto server on {args.host}:{args.port}")
    sys.path.insert(0, str(PLUTO_ROOT))
    uvicorn.run("spacepilot.pluto.app:create_app", host=args.host, port=args.port, reload=args.reload, factory=True)


def cmd_lora(args: argparse.Namespace, cfg: Dict[str, Any]) -> int:
    """List LoRA adapters. Training is gated — only the simulation existed.

    Listing is a real read and stays working, exactly as the API and MCP
    surfaces keep it: gating the whole command would have taken an honest
    read down with the dishonest write.
    """
    from spacepilot.pluto.services.lora import lora_manager

    action = getattr(args, "lora_action", None)

    if action == "list":
        adapters = lora_manager.list_adapters()
        if not adapters:
            print("  No LoRA adapters. Training is not implemented yet, so this")
            print("  list stays empty until real adapters can be produced.")
            return 0
        print(f"  {'ADAPTER':<24} {'BASE MODEL':<20} {'RANK':>5}  TRIGGER")
        for a in adapters:
            print(f"  {a.adapter_id:<24} {a.base_model:<20} {a.rank:>5}  {a.trigger_word}")
        return 0

    if action == "train":
        print("  LoRA training is not implemented.")
        print("  The previous service only simulated it — a fake loss curve and no")
        print("  real checkpoint — so it is gated rather than left to look real.")
        print("  Real training (an mflux/diffusers run producing a real adapter)")
        print("  is a separate, unbuilt feature.")
        return 1

    print("  Usage: spacepilot lora {list|train}")
    return 2


def _progress_bar(pct: float, width: int = 24) -> str:
    filled = int(width * max(0.0, min(100.0, pct)) / 100)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def cmd_recipes(args: argparse.Namespace, cfg: Dict[str, Any]) -> int:
    """List registry-backed model recipes and download their weights from the Hub.

    A recipe is a view over registry/models/*.yaml; downloading fetches the
    real weights via huggingface_hub, narrowed by the variant's allow_patterns
    and pinned to its revision when the registry records one.
    """
    from spacepilot.pluto.services.model_catalog import catalog_manager

    action = getattr(args, "recipes_action", None)

    if action == "list":
        recipes = catalog_manager.get_all_recipes()
        if not recipes:
            print("  No recipes in the registry.")
            return 0
        print(f"  {'RECIPE':<30} {'SIZE':>9}  {'RUNS HERE':<9} REPO")
        for r in sorted(recipes, key=lambda x: x.recipe_id):
            size = f"{r.size_gb:.1f} GB" if r.download_bytes else "—"
            runs = "yes" if r.is_local_runnable else "no"
            pin = "" if r.is_pinned else "  (unpinned)"
            print(f"  {r.recipe_id:<30} {size:>9}  {runs:<9} {r.hf_repo}{pin}")
        return 0

    if action == "download":
        rid = args.recipe_name
        recipe = catalog_manager.get_recipe(rid)
        if not recipe:
            print(f"  Recipe not found: {rid}")
            print("  Run 'spacepilot recipes list' to see what is available.")
            return 1
        if not recipe.hf_repo:
            print(f"  Recipe {rid} has no hf_repo to download from.")
            return 1

        rev = f" @ {recipe.revision}" if recipe.revision else " (unpinned — resolved SHA reported on completion)"
        print(f"  Downloading {rid} from {recipe.hf_repo}{rev}")

        import threading
        import time

        outcome: Dict[str, Any] = {}

        def _run() -> None:
            try:
                outcome["job"] = catalog_manager.download_recipe_blocking(rid)
            except Exception as exc:  # surfaced to the user below
                outcome["error"] = exc

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        while thread.is_alive():
            job = catalog_manager.get_download_progress(rid)
            if job:
                sys.stdout.write(
                    f"\r  {_progress_bar(job.progress_percent)} "
                    f"{job.progress_percent:5.1f}%  {job.speed_mb_s:6.1f} MB/s")
                sys.stdout.flush()
            time.sleep(0.5)
        thread.join()
        sys.stdout.write("\n")

        if "error" in outcome:
            print(f"  Download failed: {outcome['error']}")
            return 1
        job = outcome.get("job")
        if not job or job.status != "completed":
            reason = getattr(job, "error", None) or "unknown"
            print(f"  Download did not complete: {reason}")
            return 1
        print(f"  Done → {job.local_path}")
        if job.resolved_revision:
            print(f"  revision: {job.resolved_revision}")
        return 0

    print("  Usage: spacepilot recipes {list|download <recipe>}")
    return 2


# ─────────────────────────────────────────────────────────────────────────────
# CLI ENTRYPOINT
# ─────────────────────────────────────────────────────────────────────────────


def _gb(b) -> str:
    return f"{(b or 0) / 1024 ** 3:.1f} GB"


def cmd_models(args, cfg=None) -> int:
    """List the registry, or one variant, judged against this machine."""
    from spacepilot.device_probe import probe_local_device, usable_memory_bytes
    from spacepilot.pluto.registry import registry
    from spacepilot.pluto.services.compatibility import assess
    from spacepilot.pluto.services.model_catalog import catalog_manager

    reg = registry()
    profile = probe_local_device()

    # `list` is reserved, so this reads the same way as `runtimes list`; no
    # variant may be named that.
    model_id = getattr(args, "model_id", None)
    if model_id and model_id != "list":
        v = reg.variant(model_id)
        if not v:
            print(f"No variant '{model_id}'. Run `spacepilot models` to list them.")
            return 1
        verdict = assess(catalog_manager.recipes[v.id], profile)
        print(f"{v.name}  [{v.id}]")
        print(f"  {v.kind} · {v.params or '?'} · {v.precision or '?'} · runs on {', '.join(v.backends)}")
        print(f"  repo      {v.repo}" + (f"   files: {', '.join(v.files)}" if v.files else "   (whole repo)"))
        checked = f", checked {v.download.checked}" if v.download.checked else ""
        print(f"  download  {_gb(v.download.value)}   [{v.download.source}{checked}]")
        print(f"  needs     {_gb(v.working_set.value)}   [{v.working_set.source}]")
        if v.working_set.note:
            print(f"            {v.working_set.note}")
        print(f"  licence   {v.license.id}")
        for r in v.license.restrictions:
            print(f"            ! {r}")
        print(f"  here      {verdict.verdict} — {verdict.reason}")
        if v.speed:
            for sp in v.speed:
                print(f"  speed     {sp.value} {sp.metric} on {sp.device}   [{sp.source}]")
                if sp.note:
                    print(f"            {sp.note.strip()}")
        else:
            print("  speed     not measured on any machine yet")
        return 0

    usable = usable_memory_bytes(profile)
    src = profile.memory_limit_source or "unknown"
    print(f"{profile.chip or 'this machine'} · {_gb(profile.accelerator_memory_bytes)} "
          f"· {_gb(usable)} available to models [{src}]\n")
    print(f"  {'VERDICT':10s}{'MODEL':36s}{'DOWNLOAD':>10s}{'NEEDS':>9s}   {'SPEED':<11s}LICENCE")

    order = {"fits": 0, "tight": 1, "unknown": 2, "wont_fit": 3, "blocked": 4}
    rows = [(assess(catalog_manager.recipes[v.id], profile), v) for v in reg.variants]
    rows.sort(key=lambda rv: (order.get(rv[0].verdict, 9), -rv[1].working_set.value))

    for verdict, v in rows:
        speed = ("measured" if any(s.source == "measured" for s in v.speed)
                 else "published" if v.speed else "—")
        lic = v.license.id + ("" if v.license.is_permissive else "  !")
        print(f"  {verdict.verdict:10s}{v.id:36s}{_gb(v.download.value):>10s}"
              f"{_gb(v.working_set.value):>9s}   {speed:<11s}{lic}")
    print("\n  `spacepilot models <id>` for detail.  ! marks a licence with restrictions.")
    print("  SPEED is how the number was obtained, not how fast it is — most are unmeasured.")
    return 0


def cmd_runtimes(args, cfg=None) -> int:
    """List, check or install the packages that execute a model."""
    from spacepilot.device_probe import probe_local_device
    from spacepilot.pluto import runtimes as rt

    reg = rt.runtimes()
    action = getattr(args, "runtimes_action", None) or "list"

    if action == "list":
        profile = probe_local_device()
        backend = profile.backend
        print(f"{profile.chip or 'this machine'} · {backend or 'unknown backend'} "
              f"· {rt.interpreter()}\n")
        print(f"  {'STATE':11s}{'RUNTIME':20s}{'SERVES':16s}{'BACKENDS':20s}VERSION")
        for r in sorted(reg.values(), key=lambda x: x.id):
            st = rt.check(r)
            if not st.python_compatible:
                state = "unusable"
            elif st.below_minimum:
                state = "outdated"
            elif st.installed:
                state = "installed"
            elif backend and backend not in r.backends:
                state = "n/a here"
            else:
                state = "available"
            print(f"  {state:11s}{r.id:20s}{','.join(r.serves):16s}"
                  f"{','.join(r.backends):20s}{st.version or '-'}")
            if not st.python_compatible:
                print(f"  {'':11s}{'':20s}{st.python_note}")
        print("\n  `spacepilot runtimes check <id>` for detail, `install <id>` to add one.")
        print("  n/a here means it needs silicon this machine does not have.")
        return 0

    rid = getattr(args, "runtime_id", None)
    r = reg.get(rid)
    if not r:
        print(f"No runtime '{rid}'. Known: {', '.join(sorted(reg))}")
        return 1

    if action == "check":
        st = rt.check(r)
        print(f"{r.name}  [{r.id}]")
        print(f"  {r.summary}")
        print(f"  serves    {', '.join(r.serves)}")
        print(f"  backends  {', '.join(r.backends)}")
        print(f"  licence   {r.license}")
        print(f"  package   {r.install.package}"
              + (f" >= {r.install.min_version}" if r.install.min_version else "")
              + (f"   (checked {r.install.checked})" if r.install.checked else ""))
        print(f"  python    {r.python_requires or 'any'}")
        print(f"  runs      {', '.join(r.runs) or '-'}")
        print(f"  here      " + (
            f"installed, {st.version}" if st.installed and not st.below_minimum
            else f"installed but outdated — {st.reason}" if st.below_minimum
            else f"not installed — {st.reason}"))
        if not st.python_compatible:
            print(f"            {st.python_note}")
        if r.notes:
            print(f"  note      {r.notes}")
        return 0

    if action == "install":
        st = rt.check(r)
        if st.installed and not st.below_minimum:
            print(f"{r.name} is already installed ({st.version}).")
            return 0
        if not st.python_compatible:
            print(f"Cannot install {r.name}: {st.python_note}")
            return 1

        argv = rt.install_command(r)
        print(f"{r.name} — {r.summary}\n")
        print(f"  will run   {' '.join(argv)}")
        print(f"  into       {rt.interpreter()}")
        print(f"  licence    {r.license}")
        if r.notes:
            print(f"  note       {r.notes}")

        print("\n  resolving what this would change...")
        imp = rt.preview(r)
        if imp.error:
            print(f"  could not resolve: {imp.error}")
            return 1
        if imp.new:
            print(f"  new        {', '.join(n for n, _ in imp.new)}")
        for name, cur, ver in imp.upgrades:
            print(f"  upgrade    {name} {cur} -> {ver}")
        for name, cur, ver in imp.downgrades:
            print(f"  DOWNGRADE  {name} {cur} -> {ver}")
        if imp.is_disruptive:
            # A downgrade in a shared environment breaks whatever needed the
            # newer version, somewhere else, later. It is never implied by
            # "install this runtime", so it is never assumed here.
            print("\n  This lowers a package version other work in this environment may")
            print("  depend on. Consider a separate environment for this runtime.")
            if getattr(args, "yes", False):
                print("  --yes does not cover a downgrade. Re-run with --allow-downgrade.")
                if not getattr(args, "allow_downgrade", False):
                    return 1

        if not getattr(args, "yes", False):
            # Installing into the user's interpreter is a real mutation, so it
            # is confirmed rather than assumed, the same as a model download.
            try:
                if input("\n  Install? [y/N] ").strip().lower() not in ("y", "yes"):
                    print("  Nothing installed.")
                    return 1
            except EOFError:
                print("\n  No terminal to confirm on. Re-run with --yes to proceed.")
                return 1

        print(f"\n  installing {r.install.package}...")
        st = rt.install(r)
        if st.installed and not st.below_minimum:
            print(f"  {r.name} {st.version} installed and imports cleanly.")
            return 0
        print(f"  Install did not take: {st.reason}")
        return 1

    print(f"Unknown action '{action}'.")
    return 1


def cmd_measure(args, cfg=None) -> int:
    """Time a real command and write down what happened.

    Measurements gathered on purpose are rare and biased toward whatever the
    person wanted to prove. Measurements that fall out of ordinary use are
    neither, so this wraps the command you were going to run anyway.
    """
    import resource
    import time

    from spacepilot.device_probe import probe_local_device
    from spacepilot.pluto import measurements as ms

    command = list(getattr(args, "command_argv", []) or [])
    if command and command[0] == "--":   # REMAINDER keeps the separator
        command = command[1:]
    if not command:
        print("Nothing to measure. Put the command after --, e.g.")
        print("  pluto measure --model flux --metric seconds_per_image -- "
              "mflux-generate --model schnell --steps 4")
        return 1

    profile = probe_local_device()
    system = ms.system_from_profile(profile)

    before = ms.sample_contention()
    rss_before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    started = time.perf_counter()
    proc = subprocess.run(command)
    wall = time.perf_counter() - started
    after = ms.sample_contention()
    rss_after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss

    if proc.returncode != 0:
        print(f"\n  command exited {proc.returncode} after {wall:.1f}s — nothing recorded.")
        print("  A failed run is not a measurement of anything.")
        return proc.returncode

    # Written only once the run succeeded. Writing it up front left a system
    # record behind on every failed measure, which contradicts "nothing
    # recorded" and put the CI runner's own box into registry/systems/.
    ms.write_system(system)

    # Busy at either end means busy: a run that started idle and ended loaded
    # was contended for part of its life, and the solo stream must stay clean.
    contention = "solo" if before == after == "solo" else (
        "unknown" if "unknown" in (before, after) else "loaded")

    value = wall / args.units if getattr(args, "units", None) else wall
    # ru_maxrss is bytes on macOS and kibibytes on Linux.
    peak = (rss_after - rss_before) if rss_after > rss_before else None
    if peak and sys.platform != "darwin":
        peak *= 1024

    knobs = {}
    for pair in getattr(args, "knob", None) or []:
        key, _, val = pair.partition("=")
        knobs[key.strip()] = val.strip() if val else True
    if getattr(args, "units", None):
        knobs["units"] = args.units

    path = ms.record(
        system=system, model_id=args.model, metric=args.metric, value=value,
        contention=contention, runtime_id=getattr(args, "runtime", None),
        quantisation=getattr(args, "quantisation", None),
        interpreter=sys.executable, wall_seconds=wall,
        peak_memory_bytes=peak, knobs=knobs,
        note=" ".join(command)[:300],
    )

    print(f"\n  {args.metric.replace('_', ' ')}  {value:.3f}")
    print(f"  wall              {wall:.1f}s")
    if peak:
        print(f"  peak child RSS    {peak / 1024 ** 3:.2f} GB")
    print(f"  machine was       {contention}")
    if contention != "solo":
        print("  ↳ excluded from the solo ceiling; run again on an idle box for that")
    # Records land outside the repo on an installed copy (spacepilot.paths),
    # where relative_to raises rather than shortening anything.
    try:
        shown = path.relative_to(PLUTO_ROOT)
    except ValueError:
        shown = path
    print(f"  recorded          {shown}")
    return 0


def cmd_sweep(args, cfg=None) -> int:
    """Run (or dry-run) a declarative measurement sweep spec, unattended."""
    from spacepilot.pluto.sweep import load_spec, expand_jobs, run_sweep, SweepSpecError

    action = getattr(args, "sweep_action", None) or "run"
    if action != "run":
        print(f"Unknown action '{action}'.")
        return 1

    try:
        spec = load_spec(args.spec)
    except SweepSpecError as exc:
        print(f"Bad sweep spec: {exc}")
        return 1

    if getattr(args, "max_jobs", None) is not None:
        spec = replace_dataclass(spec, max_jobs=args.max_jobs)
    if getattr(args, "max_wall_seconds", None) is not None:
        spec = replace_dataclass(spec, max_wall_seconds=args.max_wall_seconds)

    jobs = expand_jobs(spec)
    print(f"{spec.id}  [{spec.model_id} via {spec.runtime_id}, model_alias={spec.model_alias}]")
    print(f"  {len(jobs)} jobs in the grid  ·  max_jobs={spec.max_jobs}  "
          f"max_wall_seconds={spec.max_wall_seconds:.0f}  disk_floor={spec.disk_free_floor_gb:.0f}GB")

    if getattr(args, "dry_run", False):
        for job in jobs:
            print(f"    {job.slug}")
        return 0

    record = run_sweep(
        spec,
        outputs_dir=Path(args.outputs_dir) if getattr(args, "outputs_dir", None) else None,
        caffeinate=not getattr(args, "no_caffeinate", False),
    )
    print(f"\n  stopped: {record.stopped_reason}")
    print(f"  ran {record.jobs_run} ({record.jobs_succeeded} ok, {record.jobs_failed} failed), "
          f"skipped {record.jobs_skipped} of {record.jobs_total}")
    if record.last_job_slug:
        print(f"  last job: {record.last_job_slug}")
    return 0 if record.stopped_reason in ("completed", "max_jobs", "max_wall_seconds",
                                           "human_returned") else 1


def replace_dataclass(instance, **changes):
    """dataclasses.replace, imported lazily so cmd_sweep stays self-contained
    next to the rest of this file's handler functions."""
    import dataclasses
    return dataclasses.replace(instance, **changes)


def cmd_probe(args: argparse.Namespace, cfg: Dict[str, Any]) -> int:
    """Detect this machine and print its system record.

    `measure` and `sweep` write a system record only as a side effect of a real
    run. `probe` is the direct way to see what SpacePilot detects, and — with
    --save — the honest way to add this box to registry/systems/. Read-only by
    default: it writes nothing unless you ask.
    """
    from spacepilot.device_probe import probe_local_device
    from spacepilot.pluto import measurements as ms

    profile = probe_local_device()
    system = ms.system_from_profile(profile)

    if getattr(args, "json", False):
        import json
        print(json.dumps({"schema": ms.SCHEMA_VERSION, **system.to_dict()}, indent=2))
    else:
        gib = lambda b: f"{b / (1024 ** 3):.2f} GiB"
        print(f"  system id : {system.id}")
        print(f"  chip      : {system.chip or system.machine_model or 'unknown'}")
        print(f"  backend   : {(system.backend or 'unknown').upper()}")
        os_line = f"{system.os_name or '?'} {system.os_version or ''}".rstrip()
        print(f"  os        : {os_line}")
        cores = []
        if system.cpu_cores:
            cores.append(f"{system.cpu_cores} cpu")
        if system.gpu_cores:
            cores.append(f"{system.gpu_cores} gpu")
        if cores:
            print(f"  cores     : {', '.join(cores)}")
        if system.memory_total_bytes:
            unified = " unified" if system.memory_unified else ""
            print(f"  memory    : {gib(system.memory_total_bytes)}{unified}")
        if system.memory_limit_bytes is not None:
            src = system.memory_limit_source or "unknown"
            print(f"  usable    : {gib(system.memory_limit_bytes)} (source: {src})")
        elif profile.accelerator_memory_bytes is None:
            print("  usable    : unknown — accelerator memory not measured")
        if system.vram_total_bytes:
            print(f"  vram      : {gib(system.vram_total_bytes)} present")
        if system.unknown:
            print("  not measured:")
            for key, reason in system.unknown.items():
                print(f"    {key}: {reason}")

    if getattr(args, "save", False):
        path = ms.write_system(system)
        print(f"\n  recorded → {path}")
    else:
        print("\n  (not saved; pass --save to write this to registry/systems/)")
    return 0


def main():
    cfg = load_config()
    parser = argparse.ArgumentParser(
        prog="spacepilot",
        description="SpacePilot — inference orchestration across the machines you can reach.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # doctor
    subparsers.add_parser("doctor", help="Check local environment and capabilities")

    # probe
    probe_p = subparsers.add_parser(
        "probe", help="Detect this machine and print its system record")
    probe_p.add_argument("--save", action="store_true",
                         help="Write the record to registry/systems/")
    probe_p.add_argument("--json", action="store_true",
                         help="Emit the record as JSON")

    # serve
    serve_p = subparsers.add_parser("serve", help="Start FastAPI app")
    serve_p.add_argument("--host", type=str, default="127.0.0.1",
                         help="Host (default: 127.0.0.1, this machine only)")
    serve_p.add_argument("--port", type=int, default=8088, help="Port (default: 8088)")
    serve_p.add_argument("--reload", action="store_true", help="Enable reload")

    # lora
    lora_p = subparsers.add_parser("lora", help="Manage LoRA models")
    lora_subparsers = lora_p.add_subparsers(dest="lora_action", required=True)
    lora_subparsers.add_parser("list", help="List LoRA models")
    lora_subparsers.add_parser("train", help="Train a new LoRA model")

    # recipes
    recipes_p = subparsers.add_parser("recipes", help="Manage recipes")
    recipes_subparsers = recipes_p.add_subparsers(dest="recipes_action", required=True)
    recipes_subparsers.add_parser("list", help="List recipes")
    recipe_download_p = recipes_subparsers.add_parser("download", help="Download a recipe")
    recipe_download_p.add_argument("recipe_name", type=str, help="Name of recipe to download")

    # studio
    studio_p = subparsers.add_parser("studio", help="Launch interactive Pluto Studio Web UI")
    studio_p.add_argument("--port", type=int, default=8088, help="Port to bind (default: 8088)")
    studio_p.add_argument("--open", action="store_true", help="Open in default browser")

    # status
    rt_p = subparsers.add_parser("runtimes", help="Packages that execute models")
    rt_sub = rt_p.add_subparsers(dest="runtimes_action")
    rt_sub.add_parser("list", help="What is installed and what is available")
    rt_check = rt_sub.add_parser("check", help="One runtime in detail")
    rt_check.add_argument("runtime_id")
    rt_inst = rt_sub.add_parser("install", help="Install a runtime")
    rt_inst.add_argument("runtime_id")
    rt_inst.add_argument("--yes", action="store_true", help="Skip the confirmation")
    rt_inst.add_argument("--allow-downgrade", action="store_true",
                         help="Proceed even if it lowers a package other work may need")

    models_p = subparsers.add_parser("models", help="List models and whether they run here")
    models_p.add_argument("model_id", nargs="?",
                          help="`list` for the table (the default), or a variant id for detail")

    meas_p = subparsers.add_parser("measure", help="Time a real run and record it")
    meas_p.add_argument("--model", required=True, help="Model id, e.g. flux")
    meas_p.add_argument("--metric", required=True,
                        help="seconds_per_image, tokens_per_second, realtime_factor, "
                             "seconds_per_second_of_video")
    meas_p.add_argument("--runtime", default=None, help="Runtime id, e.g. mflux")
    meas_p.add_argument("--quantisation", default=None, help="e.g. 4bit, 8bit, bf16")
    meas_p.add_argument("--units", type=float, default=None,
                        help="Divide wall time by this many units (images, seconds of "
                             "video) to get a per-unit rate")
    meas_p.add_argument("--knob", action="append", metavar="KEY=VALUE",
                        help="Record a setting that changes the number (repeatable)")
    meas_p.add_argument("command_argv", nargs=argparse.REMAINDER,
                        help="The command to run, after --")

    # sweep
    sweep_p = subparsers.add_parser("sweep", help="Run a declarative measurement sweep, unattended")
    sweep_sub = sweep_p.add_subparsers(dest="sweep_action")
    sweep_run = sweep_sub.add_parser("run", help="Run (or dry-run) a sweep spec")
    sweep_run.add_argument("spec", help="Path to a registry/sweeps/*.yaml spec")
    sweep_run.add_argument("--dry-run", action="store_true",
                           help="Print the job grid and exit without running anything")
    sweep_run.add_argument("--max-jobs", type=int, default=None,
                           help="Override the spec's runner.max_jobs")
    sweep_run.add_argument("--max-wall-seconds", type=float, default=None,
                           help="Override the spec's runner.max_wall_seconds")
    sweep_run.add_argument("--outputs-dir", default=None,
                           help="Override where generated images land (default: outputs/)")
    sweep_run.add_argument("--no-caffeinate", action="store_true",
                           help="Do not keep the Mac awake (for debugging only)")

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
    gen_p.add_argument("--output", "-o", type=str, default=None, help="Target path to save downloaded MP4")
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
        "doctor": cmd_doctor,
        "probe": cmd_probe,
        "serve": cmd_serve,
        "lora": cmd_lora,
        "recipes": cmd_recipes,
        "studio": cmd_studio,
        "models": cmd_models,
        "runtimes": cmd_runtimes,
        "measure": cmd_measure,
        "sweep": cmd_sweep,
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
    if not handler:
        parser.print_help()
        return 2
    # Return the handler's status. This used to be discarded, so every command
    # exited 0 — including ones that had just printed a refusal or an error,
    # which made pluto unusable from a script or a CI step.
    return handler(args, cfg) or 0


if __name__ == "__main__":
    raise SystemExit(main())
