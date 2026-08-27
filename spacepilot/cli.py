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
import tempfile
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
from spacepilot.paths import env_value, fleet_orders_path

OUTPUTS_DIR = Path(env_value("SPACEPILOT_OUTPUTS_DIR", "PLUTO_OUTPUTS_DIR", default=str(PLUTO_ROOT / "outputs")))
CONFIG_FILE = PLUTO_ROOT / ".spacepilot_config.json"
LEGACY_CONFIG_FILE = PLUTO_ROOT / ".pluto_config.json"
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
            self._console.print(line, end="\r", markup=False)

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
    # Canonical configuration wins whenever it exists. A malformed canonical
    # file must not silently fall through to a stale legacy file containing
    # different infrastructure settings or credentials.
    source = CONFIG_FILE if CONFIG_FILE.exists() else LEGACY_CONFIG_FILE
    if source.exists():
        try:
            with open(source, "r") as f:
                cfg = json.load(f)
                return {**DEFAULT_CONFIG, **cfg}
        except Exception:
            logger.debug("Failed to load config", exc_info=True)
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    """Atomically write only the canonical private config file.

    The config can carry provider credentials.  Writing through a private
    sibling and replacing it avoids partially-written JSON and makes the final
    file mode independent of the caller's umask.
    """
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{CONFIG_FILE.name}.", suffix=".tmp", dir=CONFIG_FILE.parent,
    )
    temp_path = Path(temp_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            fd = -1
            json.dump(cfg, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, CONFIG_FILE)
        CONFIG_FILE.chmod(0o600)
    finally:
        if fd != -1:
            os.close(fd)
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


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
    # AWS is an external dependency and can leave a child behind when the
    # CLI or network wedges. Status polling must always have a hard bound.
    # Errors propagate: a credential or network failure must never be
    # rendered as "no instance" — that made a billing box invisible. The one
    # exception is the hard timeout itself: the child was killed at the bound,
    # which is a safe "no answer yet" rather than a broken query.
    try:
        raw = run_cmd(cmd, capture=True, timeout=3.0)
    except (TimeoutError, subprocess.TimeoutExpired):
        return None
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
    return None


def fetch_worker_health(ip):
    if not ip:
        return None
    url = f"http://{ip}:5000/health"
    try:
        resp = httpx.get(url, headers={"User-Agent": "SpacePilotCLI/1.0"}, timeout=3)
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

def cmd_status(args: argparse.Namespace, cfg: Dict[str, Any]) -> int:
    print("──────────────────────────────────────────────────────────────────────────")
    print("  SPACEPILOT GPU BOX & WORKER STATUS")
    print("──────────────────────────────────────────────────────────────────────────")
    try:
        inst = get_instance_info(cfg)
    except Exception as e:
        # "Could not ask AWS" and "no instance" are different answers. The old
        # code rendered both as a confident negative, exit 0, on the verb the
        # docs call the free way to check a billing box.
        print("  AWS Instance : could not be determined — the AWS query failed.")
        print(f"  Error        : {e}")
        print("  This is a detection failure, not proof the account is empty.")
        print("──────────────────────────────────────────────────────────────────────────")
        return 1
    if not inst:
        print("  AWS Instance : [STOPPED / NONE] No active GPU instance found.")
        print("  Launch with  : spacepilot launch")
        print("──────────────────────────────────────────────────────────────────────────")
        return 0

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
            print(f"  Worker State : [WARMING UP] Worker is loading its model; not serving yet.")
        else:
            print(f"  Worker State : [OFFLINE / STARTING] Server not responding on port 5000.")
            print("                 Check logs with: spacepilot logs")
    print("──────────────────────────────────────────────────────────────────────────")
    return 0


def _refuse_legacy_aws(verb: str) -> int:
    """The retired single-box AWS path refuses instead of half-working.

    These verbs drove one hardcoded g6e.2xlarge spot instance. Their handlers
    exited 0 on every failure, `sync` printed "Sync complete!" regardless of
    rsync, and the numbers on screen (load time, rate) were never measured.
    They return as the docks surface (docs/BUILD-PLAN.md, Phase 4) with a
    spend ceiling; the old bodies are in git history at e4b7910.
    `status`, `ssh`, `logs` and `terminate` stay live so an already-running
    box can still be seen, reached, and stopped.
    """
    print(f"  `spacepilot {verb}` is retired. It drove a single hardcoded AWS")
    print("  spot instance and reported success regardless of what happened.")
    print("  Renting compute returns as the docks surface (docs/BUILD-PLAN.md,")
    print("  Phase 4). Nothing was started and nothing is billing.")
    print("  A box that is already running: `spacepilot status` / `terminate`.")
    return 2


def cmd_launch(args: argparse.Namespace, cfg: Dict[str, Any]) -> int:
    return _refuse_legacy_aws("launch")


def cmd_deploy(args: argparse.Namespace, cfg: Dict[str, Any]) -> int:
    return _refuse_legacy_aws("deploy")


def _live_instance_or_none(cfg):
    """Instance info, with AWS failures surfaced rather than swallowed."""
    try:
        return get_instance_info(cfg), None
    except Exception as e:
        return None, e


def cmd_ssh(args: argparse.Namespace, cfg: Dict[str, Any]) -> int:
    inst, err = _live_instance_or_none(cfg)
    if err is not None:
        print(f"  Error: the AWS query failed — {err}")
        return 1
    if not inst or not inst["ip"]:
        print("  Error: No running instance found.")
        return 1
    key = cfg["key_file"]
    ip = inst["ip"]
    print(f"Connecting to ubuntu@{ip}...")
    return subprocess.run(["ssh", "-i", key, f"ubuntu@{ip}"]).returncode


def cmd_logs(args: argparse.Namespace, cfg: Dict[str, Any]) -> int:
    inst, err = _live_instance_or_none(cfg)
    if err is not None:
        print(f"  Error: the AWS query failed — {err}")
        return 1
    if not inst or not inst["ip"]:
        print("  Error: No running instance found.")
        return 1
    key = cfg["key_file"]
    ip = inst["ip"]
    print(f"Streaming worker logs from {ip} (Ctrl+C to stop)...")
    return subprocess.run(["ssh", "-i", key, f"ubuntu@{ip}",
                    "tail -f /scratch/worker/worker.log 2>/dev/null || tail -f /tmp/worker.log"]).returncode


def cmd_generate(args: argparse.Namespace, cfg: Dict[str, Any]) -> int:
    return _refuse_legacy_aws("generate")


def cmd_sync(args: argparse.Namespace, cfg: Dict[str, Any]) -> int:
    return _refuse_legacy_aws("sync")


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
                    # Cached so the next launch skips this scan — probing every
                    # conda env costs a subprocess import each. Said out loud
                    # because a launch verb writing config silently is a trap.
                    cfg["python_bin"] = candidate
                    save_config(cfg)
                    print(f"  caching interpreter choice → .pluto_config.json "
                          f"(python_bin = {candidate})")
                return candidate
        except Exception:
            continue
    return None


def cmd_studio(args: argparse.Namespace, cfg: Dict[str, Any]) -> int:
    port = args.port or 8088
    studio_script = PLUTO_ROOT / "spacepilot" / "web_api.py"

    python_bin = studio_python(cfg)
    if not python_bin:
        print("  Error: no interpreter found with fastapi + uvicorn installed.")
        print("  Set SPACEPILOT_PYTHON, or add \"python_bin\" to .pluto_config.json,")
        print("  pointing at the environment where you ran: pip install -r requirements.txt")
        return 1

    print("──────────────────────────────────────────────────────────────────────────")
    print(f"  🎬 LAUNCHING SPACEPILOT STUDIO ON http://localhost:{port}")
    print("──────────────────────────────────────────────────────────────────────────")
    if args.open:
        import webbrowser
        time.sleep(1.0)
        webbrowser.open(f"http://localhost:{port}")
    return subprocess.run([python_bin, str(studio_script)], env={**os.environ, "SPACEPILOT_STUDIO_PORT": str(port)}).returncode


def cmd_terminate(args: argparse.Namespace, cfg: Dict[str, Any]) -> int:
    inst, err = _live_instance_or_none(cfg)
    if err is not None:
        print(f"  Error: the AWS query failed — {err}")
        print("  Could not confirm whether an instance is running. Nothing was terminated.")
        return 1
    if not inst:
        print("  No active instance found to terminate.")
        return 0

    print("──────────────────────────────────────────────────────────────────────────")
    print(f"  TERMINATING GPU INSTANCE {inst['id']} ({inst.get('ip')})")
    print("──────────────────────────────────────────────────────────────────────────")
    if not args.yes:
        confirm = input("  Are you sure you want to terminate this instance? (y/N): ").strip().lower()
        if confirm != "y":
            print("  Cancelled.")
            return 1

    infra_script = PLUTO_ROOT / "infra" / "gpu-box.sh"
    try:
        run_cmd(["bash", str(infra_script), "terminate"])
    except Exception as e:
        print(f"  Error: terminate did not complete — {e}")
        print("  The instance may still be running and billing. Check `spacepilot status`.")
        return 1
    print("  Instance terminated cleanly. Zero ongoing billing.")
    return 0


def cmd_doctor(args: argparse.Namespace, cfg: Dict[str, Any]) -> int:
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
              "— no compute runtime SpacePilot can use was detected")
        # "can reach this card" stated a negative detection as a fact about the
        # hardware. The probe only knows that it looked and found nothing it
        # can route through — which on the Lenovo is a card Vulkan reaches fine.
        if profile.compute_runtime and profile.compute_runtime_detail:
            print(f"  Runtime  : {profile.compute_runtime} present but unrouted "
                  f"— {profile.compute_runtime_detail}")
    else:
        source = getattr(profile, "memory_limit_source", None) or "unknown"
        print(f"  VRAM     : {profile.vram_usable_gb:.1f}GB usable / {profile.vram_total_gb:.1f}GB total "
              f"(limit source: {source}; Safety Headroom: {profile.vram_total_gb - profile.vram_usable_gb:.1f}GB)")
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
        m_path, v_path = KokoroDriver().asset_paths()
        kokoro_found = bool(m_path and v_path)
    except Exception:
        m_path = None
        kokoro_found = False
    if kokoro_found:
        print(f"  Kokoro   : ✅ Found ONNX weights ({Path(m_path).name})")
    else:
        print("  Kokoro   : ❌ ONNX weights NOT FOUND (Required for TTS)")
        print("             Run: spacepilot recipes download kokoro-82m-onnx")
        print("             or set SPACEPILOT_KOKORO_MODEL / SPACEPILOT_KOKORO_VOICES.")
        
    print("")

    # 4. AWS CLI check
    print("  [Cloud & Auth]")
    try:
        aws_res = subprocess.run(["aws", "sts", "get-caller-identity", "--profile", cfg.get("aws_profile", "default")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        aws_data = json.loads(aws_res.stdout)
        print(f"  AWS Auth : ✅ Valid (Profile: {cfg.get('aws_profile', 'default')})")
        print(f"  Identity : {aws_data.get('Arn')}")
    except FileNotFoundError:
        print("  AWS Auth : ❌ AWS CLI is not installed")
    except Exception as e:
        # The real error, not a guess: "profile not found", "expired token"
        # and "no network" have different fixes and used to print the same line.
        detail = (getattr(e, "stderr", "") or str(e)).strip().splitlines()
        print("  AWS Auth : ❌ NOT AUTHENTICATED")
        for line in detail[:3]:
            print(f"             {line}")

    # 5. Studio Token check
    token_path = PLUTO_ROOT / ".studio_token"
    if token_path.exists():
        print(f"  Session  : ✅ Token found (.studio_token)")
    else:
        print(f"  Session  : ⚠️ No local session token found")

    print("─────────────────────────────────────────────────────────────────")
    return 0


def cmd_serve(args: argparse.Namespace, cfg: Dict[str, Any]) -> int:
    import uvicorn
    print(f"Starting SpacePilot server on {args.host}:{args.port}")
    sys.path.insert(0, str(PLUTO_ROOT))
    uvicorn.run("spacepilot.pluto.app:create_app", host=args.host, port=args.port, reload=args.reload, factory=True)
    return 0


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
        if getattr(args, "json", False):
            print(json.dumps({"recipes": [
                {"id": r.recipe_id, "download_bytes": r.download_bytes,
                 "runs_here": r.is_local_runnable, "repo": r.hf_repo,
                 "pinned": r.is_pinned}
                for r in sorted(recipes, key=lambda x: x.recipe_id)
            ]}, indent=2, default=str))
            return 0
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
        renderer = output_renderer(args, cfg)
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
                renderer.progress(
                    "Downloading",
                    f"{_progress_bar(job.progress_percent)} "
                    f"{job.progress_percent:5.1f}%  {job.speed_mb_s:6.1f} MB/s",
                )
            time.sleep(0.5)
        thread.join()
        renderer.finish()

        if "error" in outcome:
            print(f"  Download failed: {outcome['error']}")
            return 1
        job = outcome.get("job")
        if not job or job.status != "completed":
            reason = getattr(job, "error", None) or "unknown"
            print(f"  Download did not complete: {reason}")
            return 1
        print("  Done:")
        for resolved_file in job.resolved_files:
            print(f"    {resolved_file}")
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


def _caveat_method(caveat, precision: str | None) -> str | None:
    """Render an absent compression method as an explicit unknown, not a blank."""
    if caveat.method:
        return caveat.method
    normalized = (precision or "").lower()
    uncompressed = {"f16", "fp16", "bf16", "fp32", "float16", "float32"}
    if normalized and normalized not in uncompressed:
        return "method unrecorded"
    return None


def _caveat_summary(variant) -> str:
    """A compact, factual table cell; no caveats remains deliberately blank."""
    return "; ".join(
        f"{c.capability} · {c.status} · {c.provenance}"
        for c in variant.caveats
    )


def _print_caveats(variant) -> None:
    """Print the full capability evidence for one model variant, when present."""
    if not variant.caveats:
        return
    print("  caveats")
    for caveat in variant.caveats:
        print(f"    {caveat.capability} — {caveat.status} · {caveat.provenance}")
        if caveat.metric:
            print(f"      metric  {caveat.metric}")
        method = _caveat_method(caveat, variant.precision)
        if method:
            print(f"      method  {method}")
        print(f"      {caveat.detail}")


def _load_declared_provider_rates():
    """Read the locally pinned, signed provider projection without network I/O.

    Returns (providers, failure). A failure is the signed-ORDERS design working
    — a bad signature, a rolled-back file, a foreign owner — and must reach the
    screen. This used to swallow every exception into an empty tuple and log at
    DEBUG, which rendered byte-identically to "this machine has no fleet": the
    detection fired and the user saw nothing.
    """
    from spacepilot.daemon.orders import OrdersError, OrdersStore

    try:
        orders = OrdersStore(fleet_orders_path()).load()
    except OrdersError as exc:
        logger.debug("Local ORDERS provider projection did not verify: %s", exc)
        return (), str(exc)
    return (orders.providers if orders is not None else ()), None


def _print_provider_rates(providers, failure=None) -> None:
    if failure:
        print("\n  PROVIDERS — unavailable")
        print(f"  The local ORDERS file did not verify: {failure}")
        print("  This is a detection, not an absence. Nothing below reflects a fleet.")
        return
    if not providers:
        return
    print("\n  PROVIDERS — on paper only")
    print("  Declared API pricing; no local fit verdict, no flown/unflown speed axis, and no execution support is implied.")
    print("  PROVIDER / VARIANT / MODEL                         INPUT USD/1M TOKENS  OUTPUT USD/1M TOKENS  SOURCE · CHECKED")
    for rate in providers:
        print(
            f"  {rate.provider_id} / {rate.variant_id} / {rate.provider_model}"
            f"  {rate.input_usd_per_1m_tokens}  {rate.output_usd_per_1m_tokens}"
            f"  {rate.source} · checked {rate.checked}"
        )


def cmd_models(args, cfg=None) -> int:
    """List the registry, or one variant, judged against this machine."""
    from spacepilot.device_probe import probe_local_device, usable_memory_bytes
    from spacepilot.pluto import measurements as ms
    from spacepilot.pluto.registry import registry
    from spacepilot.pluto.services.compatibility import assess
    from spacepilot.pluto.services.model_catalog import catalog_manager
    from spacepilot.pluto.services.provenance import (
        format_fact, format_local_speed, format_metric, local_speeds, primary_speed,
        speed_provenance,
    )

    reg = registry()
    profile = probe_local_device()
    system_id = ms.system_from_profile(profile).id
    measurements = ms.load_measurements()

    def local_speed(v):
        return primary_speed(local_speeds(measurements, system_id=system_id, variant_id=v.id))

    as_json = getattr(args, "json", False)

    def _variant_row(v):
        from dataclasses import asdict
        verdict = assess(catalog_manager.recipes[v.id], profile)
        summary = local_speed(v)
        return {
            **v.to_dict(),
            "verdict": asdict(verdict),
            "speed_here": asdict(summary) if summary is not None else None,
        }

    # `list` is reserved, so this reads the same way as `runtimes list`; no
    # variant may be named that.
    model_id = getattr(args, "model_id", None)
    if model_id and model_id != "list":
        v = reg.variant(model_id)
        if not v:
            print(f"No variant '{model_id}'. Run `spacepilot models` to list them.")
            return 1
        if as_json:
            print(json.dumps(_variant_row(v), indent=2, default=str))
            return 0
        verdict = assess(catalog_manager.recipes[v.id], profile)
        print(f"{v.name}  [{v.id}]")
        print(f"  {v.kind} · {v.params or '?'} · {v.precision or '?'} · runs on {', '.join(v.backends)}")
        print(f"  repo      {v.repo}" + (f"   files: {', '.join(v.files)}" if v.files else "   (whole repo)"))
        print(f"  download  {format_fact(v.download, _gb(v.download.value))}")
        print(f"  needs     {format_fact(v.working_set, _gb(v.working_set.value))}")
        if v.working_set.note:
            print(f"            {v.working_set.note}")
        print(f"  licence   {v.license.id}")
        for r in v.license.restrictions:
            print(f"            ! {r}")
        _print_caveats(v)
        # `assess` legitimately needs an estimated footprint to decide whether
        # a model can fit, but its numeric ratio is not a measured fact and
        # must not be rendered as one.
        if v.working_set.source == "estimated":
            here_reason = "fit assessment uses an unflown footprint"
        else:
            here_reason = verdict.reason
        print(f"  here      {verdict.verdict} — {here_reason}")
        here = local_speed(v)
        print(f"  speed here {format_local_speed(here)}")
        if v.speed:
            for sp in v.speed:
                evidence = speed_provenance(sp)
                if evidence.value is None:
                    shown = "unflown"
                else:
                    date = evidence.checked or "date unrecorded"
                    shown = (f"{format_metric(sp.metric, evidence.value)} · {evidence.state} · "
                             f"{evidence.source} · checked {date}")
                print(f"  speed     {shown} on {sp.device}")
                if sp.note:
                    print(f"            {sp.note.strip()}")
        return 0

    usable = usable_memory_bytes(profile)
    src = profile.memory_limit_source or "unknown"
    if as_json:
        doc = {
            "system": {
                "chip": profile.chip,
                "accelerator_memory_bytes": profile.accelerator_memory_bytes,
                "usable_memory_bytes": usable,
                "memory_limit_source": src,
            },
            "variants": [_variant_row(v) for v in reg.variants],
        }
        print(json.dumps(doc, indent=2, default=str))
        return 0
    print(f"{profile.chip or 'this machine'} · {_gb(profile.accelerator_memory_bytes)} "
          f"· {_gb(usable)} available to models [{src}]\n")
    print(f"  {'VERDICT':10s}{'MODEL':36s}DOWNLOAD / PROVENANCE                          SPEED HERE   CAVEATS")

    order = {"fits": 0, "tight": 1, "unknown": 2, "wont_fit": 3, "blocked": 4}
    rows = [(assess(catalog_manager.recipes[v.id], profile), v) for v in reg.variants]
    rows.sort(key=lambda rv: (order.get(rv[0].verdict, 9), -rv[1].working_set.value))

    for verdict, v in rows:
        download = format_fact(v.download, _gb(v.download.value))
        speed = format_local_speed(local_speed(v))
        lic = v.license.id + ("" if v.license.is_permissive else "  !")
        caveats = _caveat_summary(v)
        print(f"  {verdict.verdict:10s}{v.id:36s}{download}   {speed}   {lic}   {caveats}")
    print("\n  `spacepilot models <id>` for detail.  ! marks a licence with restrictions.")
    print("  SPEED HERE is measured on this machine configuration. unflown means no local run is recorded.")
    _print_provider_rates(*_load_declared_provider_rates())
    return 0


def _verdict_fit_text(verdict) -> str:
    fit = f"{verdict.verdict} — {verdict.reason}"
    if verdict.runnable_now is False:
        fit += f"; not runnable now, short {_gb(verdict.free_shortfall_bytes)}"
    if verdict.disk_ok is False:
        fit += f"; disk short {_gb(verdict.disk_shortfall_bytes)}"
    return fit


def _run_candidate_facts(candidate) -> tuple[str, str, str]:
    """One source of truth for both live and plain confirmation rows."""
    from spacepilot.pluto.services.provenance import format_local_speed

    fit = _verdict_fit_text(candidate.verdict)
    provenance = format_local_speed(candidate.speed)
    if candidate.executable_ready:
        route = f"ready — {candidate.route.model_alias} via {candidate.executable}"
    else:
        route = f"no route — executable missing or not executable: {candidate.executable}"
    return fit, provenance, route


def run_confirmation_lines(plan, output: Path) -> list[str]:
    """Stable facts shared by both output modes; only their renderer may vary."""
    lines = [
        f"  {'MODEL':27s} {'FIT':16s} {'PROVENANCE':24s} ROUTE",
    ]
    for candidate in plan.candidates:
        fit, provenance, route = _run_candidate_facts(candidate)
        lines.append(f"  {candidate.variant.id:27s} {fit} · {provenance} · {route}")

    selected = plan.selected
    if selected is None:
        lines.append("\n  No safe local route is available; nothing can execute.")
    else:
        lines.extend([
            f"\n  selected   {selected.variant.id} (exact alias {selected.route.model_alias})",
            f"  output     {output}",
            "  weights    mflux owns its cache; the exact loaded revision is unobserved",
            "  network    disabled for this run; a missing cached weight fails instead of downloading",
        ])

    unsafe = [
        (candidate.variant.id, caveat)
        for candidate in plan.candidates
        for caveat in candidate.non_safe_caveats
    ]
    if unsafe:
        lines.append("\n  capability caveats")
        for variant_id, caveat in unsafe:
            method = _caveat_method(caveat, next(
                c.variant.precision for c in plan.candidates if c.variant.id == variant_id
            ))
            detail = f"{variant_id}: {caveat.capability} — {caveat.status} · {caveat.provenance}"
            if method:
                detail += f" · {method}"
            lines.append(f"    {detail}")
            lines.append(f"      {caveat.detail}")
    return lines


def audio_run_confirmation_lines(plan, output: Path, extra: list[str] | None = None) -> list[str]:
    """Stable facts shared by both output modes for speech and transcribe."""
    from spacepilot.pluto.services.provenance import format_local_speed

    lines = [
        f"  {'MODEL':27s} {'FIT':16s} {'PROVENANCE':24s} ROUTE",
    ]
    for candidate in plan.candidates:
        fit = _verdict_fit_text(candidate.verdict)
        provenance = format_local_speed(candidate.speed)
        lines.append(
            f"  {candidate.variant.id:27s} {fit} · {provenance} · {candidate.route_detail}")

    selected = plan.selected
    if selected is None:
        lines.append("\n  No safe local route is available; nothing can execute.")
    else:
        lines.extend([
            f"\n  selected   {selected.variant.id} via {selected.route.runtime_id}",
            f"  output     {output}",
            "  network    local files only; a missing cached weight refuses instead of downloading",
        ])
        if extra:
            lines.extend(extra)

    unsafe = [
        (candidate.variant.id, candidate.variant.precision, caveat)
        for candidate in plan.candidates
        for caveat in candidate.non_safe_caveats
    ]
    if unsafe:
        lines.append("\n  capability caveats")
        for variant_id, precision, caveat in unsafe:
            method = _caveat_method(caveat, precision)
            detail = f"{variant_id}: {caveat.capability} — {caveat.status} · {caveat.provenance}"
            if method:
                detail += f" · {method}"
            lines.append(f"    {detail}")
            lines.append(f"      {caveat.detail}")
    return lines


def text_run_confirmation_lines(plan, output: Path, *, max_tokens: int,
                                max_kv_size: int, temperature: float) -> list[str]:
    """All material facts shown before a large local text-model allocation."""
    from spacepilot.pluto.services.provenance import format_local_speed

    lines = [f"  {'MODEL':27s} {'FIT':16s} {'PROVENANCE':24s} ROUTE"]
    for candidate in plan.candidates:
        lines.append(
            f"  {candidate.variant.id:27s} {_verdict_fit_text(candidate.verdict)} · "
            f"{format_local_speed(candidate.speed)} · {candidate.route_detail}")
    selected = plan.selected
    if selected is None:
        lines.append("\n  No safe local route is available; nothing can execute.")
    else:
        lines.extend([
            f"\n  selected   {selected.variant.id} via mlx-lm",
            f"  output     {output}",
            f"  bounds     max {max_tokens} output tokens · max {max_kv_size} KV tokens",
            f"  sampling   temperature {temperature}",
            "  memory     working set is an estimate, not a measured peak or ceiling",
            "  network    disabled; only the exact pinned local snapshot may load",
            "  system     one-shot child process; no iogpu.wired_limit_mb change",
        ])
    return lines


def _confirm_run(args) -> bool:
    """The shared execute gate: --yes, or an interactive yes on a real tty."""
    if getattr(args, "yes", False):
        return True
    if not sys.stdin.isatty():
        print("\n  No terminal to confirm on. Re-run with --yes to execute.")
        return False
    try:
        answer = input("\n  Run? [Y/n] ").strip().lower()
    except EOFError:
        print("\n  No terminal to confirm on. Re-run with --yes to execute.")
        return False
    if answer not in ("", "y", "yes"):
        print("  Nothing ran.")
        return False
    return True


def _cmd_run_speech(args, cfg=None) -> int:
    from spacepilot.pluto.services.audio_execution import (
        SpeechExecutionService, SpeechRequest, default_speech_output,
    )
    from spacepilot.pluto.services.execution import LocalExecutionError

    service = SpeechExecutionService()
    try:
        plan = service.plan("speech")
    except (ValueError, LocalExecutionError) as exc:
        print(f"  Cannot plan run: {exc}")
        return 1

    output_arg = getattr(args, "output", None)
    output = Path(output_arg).expanduser().resolve() if output_arg else default_speech_output()
    print("\n".join(audio_run_confirmation_lines(plan, output)))
    if plan.selected is None:
        return 1
    if not _confirm_run(args):
        return 1

    try:
        result = service.execute(plan, SpeechRequest(
            workload="speech",
            text=args.text,
            voice=args.voice,
            output=output,
        ))
    except Exception as exc:
        # Driver failures are user-facing route failures, not tracebacks or
        # synthetic artifacts. The service writes no speed record for them.
        print(f"\n  Run failed: {exc}")
        return 1

    print(f"\n  completed   {result.variant_id}")
    print(f"  artifact    {result.output}")
    print(f"  wall        {result.wall_seconds:.3f}s")
    print(f"  audio       {result.audio_seconds:.2f}s")
    print(f"  speed       {result.realtime_factor:.2f}× realtime")
    print(f"  measured    {result.measurement_path}")
    print(f"  revision    {result.resolved_revision or 'unknown (weights came from an explicit path)'}")
    return 0


def _cmd_run_transcribe(args, cfg=None) -> int:
    from spacepilot.pluto.services.audio_execution import (
        TranscribeExecutionService, TranscribeRequest, default_transcript_output,
    )
    from spacepilot.pluto.services.execution import LocalExecutionError

    service = TranscribeExecutionService()
    try:
        plan = service.plan("transcribe")
    except (ValueError, LocalExecutionError) as exc:
        print(f"  Cannot plan run: {exc}")
        return 1

    audio = Path(args.audio).expanduser().resolve()
    output_arg = getattr(args, "output", None)
    output = Path(output_arg).expanduser().resolve() if output_arg else default_transcript_output()
    print("\n".join(audio_run_confirmation_lines(
        plan, output, extra=[f"  input      {audio}"])))
    if plan.selected is None:
        return 1
    if not audio.is_file():
        print(f"\n  Cannot run: audio file does not exist: {audio}")
        return 1
    if not _confirm_run(args):
        return 1

    try:
        result = service.execute(plan, TranscribeRequest(
            workload="transcribe",
            audio=audio,
            output=output,
        ))
    except Exception as exc:
        print(f"\n  Run failed: {exc}")
        return 1

    print(f"\n  completed   {result.variant_id}")
    print(f"  artifact    {result.output}")
    print(f"  wall        {result.wall_seconds:.3f}s")
    if result.realtime_factor is None:
        print("  speed       unrecorded — audio duration unknown (only PCM wav can be timed)")
    else:
        print(f"  audio       {result.audio_seconds:.2f}s")
        print(f"  speed       {result.realtime_factor:.2f}× realtime")
        print(f"  measured    {result.measurement_path}")
    print(f"  revision    {result.resolved_revision or 'unknown (weights came from an explicit path)'}")
    return 0


def _cmd_run_text(args, cfg=None) -> int:
    from spacepilot.drivers.mlx_lm_driver import MlxLmDriver
    from spacepilot.pluto import runtimes as rt
    from spacepilot.pluto.services.execution import LocalExecutionError
    from spacepilot.pluto.services.text_execution import (
        TextExecutionService, TextRequest, default_text_output,
    )

    driver = MlxLmDriver(python_bin=rt.interpreter(cfg))
    service = TextExecutionService(driver=driver)
    try:
        plan = service.plan("text")
    except (ValueError, LocalExecutionError) as exc:
        print(f"  Cannot plan run: {exc}")
        return 1
    output_arg = getattr(args, "output", None)
    output = Path(output_arg).expanduser().resolve() if output_arg else default_text_output()
    print("\n".join(text_run_confirmation_lines(
        plan, output, max_tokens=args.max_tokens,
        max_kv_size=args.max_kv_size, temperature=args.temperature,
    )))
    if plan.selected is None:
        return 1
    if not _confirm_run(args):
        return 1
    try:
        result = service.execute(plan, TextRequest(
            workload="text", prompt=args.prompt, output=output,
            max_tokens=args.max_tokens, max_kv_size=args.max_kv_size,
            temperature=args.temperature,
        ))
    except Exception as exc:
        print(f"\n  Run failed: {exc}")
        return 1
    print(f"\n  completed   {result.variant_id}")
    print(f"  artifact    {result.output}")
    print(f"  wall        {result.wall_seconds:.3f}s ({result.load_seconds:.3f}s load)")
    print(f"  tokens      {result.prompt_tokens} prompt + {result.generation_tokens} generated")
    print(f"  speed       {result.generation_tps:.3f} tokens/s")
    print(f"  peak memory {result.peak_memory_gb:.3f} GB (reported by MLX-LM)")
    print(f"  measured    {result.measurement_path}")
    print(f"  revision    {result.resolved_revision or 'unknown'}")
    return 0


def cmd_run(args, cfg=None) -> int:
    """Plan, confirm and execute one real local workload."""
    from spacepilot.drivers.mflux_driver import MfluxDriver, mflux_bin_dir
    from spacepilot.pluto.services.execution import (
        LocalExecutionError, LocalExecutionService, RunRequest, default_image_output,
    )

    workload = getattr(args, "run_workload", None)
    if workload == "speech":
        return _cmd_run_speech(args, cfg)
    if workload == "transcribe":
        return _cmd_run_transcribe(args, cfg)
    if workload == "text":
        return _cmd_run_text(args, cfg)
    service = LocalExecutionService(driver=MfluxDriver(bin_dir=mflux_bin_dir(cfg)))
    try:
        plan = service.plan(workload)
    except (ValueError, LocalExecutionError) as exc:
        print(f"  Cannot plan run: {exc}")
        return 1

    output_arg = getattr(args, "output", None)
    output = Path(output_arg).expanduser().resolve() if output_arg else default_image_output()
    # Deliberately identical fact strings in live and plain modes. This is a
    # confirmation snapshot, not progress animation; terminal mode cannot
    # make a refusal, caveat or provenance mark disappear.
    print("\n".join(run_confirmation_lines(plan, output)))
    if plan.selected is None:
        return 1

    if not _confirm_run(args):
        return 1

    try:
        result = service.execute(plan, RunRequest(
            workload=workload,
            prompt=args.prompt,
            output=output,
        ))
    except Exception as exc:
        # Driver failures are user-facing route failures, not tracebacks or
        # synthetic artifacts. The service writes no speed record for them.
        print(f"\n  Run failed: {exc}")
        return 1

    print(f"\n  completed   {result.variant_id}")
    print(f"  artifact    {result.output}")
    print(f"  wall        {result.wall_seconds:.3f}s")
    if result.seconds_per_image is None:
        print("  speed       unrecorded — mflux exposed no generation boundary")
    else:
        print(f"  speed       {result.seconds_per_image:.3f} s/image")
        print(f"  measured    {result.measurement_path}")
    print(f"  revision    {result.resolved_revision or 'unknown (mflux did not expose it)'}")
    return 0


def cmd_daemon(args: argparse.Namespace, cfg: Dict[str, Any] | None = None) -> int:
    """Manage the local daemon through its OS user-service supervisor."""
    from spacepilot.daemon import service

    action = getattr(args, "daemon_action", None)
    try:
        if action == "install":
            path = service.install_daemon()
            print(f"  daemon installed: {path}")
            if sys.platform.startswith("linux"):
                state = service.daemon_status()
                if state.lingering is False:
                    print("  lingering is off; the daemon stops when this user logs out.")
                elif state.lingering is None:
                    print("  lingering could not be checked; it was not changed.")
            return 0
        if action == "run":
            return service.run_foreground()
        if action == "status":
            state = service.daemon_status()
            if getattr(args, "json", False):
                from dataclasses import asdict
                print(json.dumps(asdict(state), indent=2, default=str))
                return 0 if state.installed and state.reachable else 1
            print(f"  definition  {state.definition}")
            print(f"  installed   {'yes' if state.installed else 'no'}")
            if state.active is None:
                print("  state       unknown")
            else:
                print(f"  state       {'active' if state.active else 'inactive'}")
            if state.platform == "linux":
                if state.lingering is True:
                    print("  lingering   on")
                elif state.lingering is False:
                    print("  lingering   off (daemon stops at logout)")
                else:
                    print("  lingering   unknown")
            print(f"  local door  {'reachable' if state.reachable else 'unreachable'}")
            if state.reachable:
                print(f"  picture     {_daemon_age_suffix(state.picture_age_seconds).removeprefix(' · ')}")
                if state.peer_state:
                    peer = state.peer_state
                    if state.peer_address:
                        peer += f" ({state.peer_address})"
                    print(f"  peer        {peer}{_daemon_age_suffix(state.peer_age_seconds)}")
                else:
                    print("  peer        unknown")
                if state.key_id:
                    print(f"  key         {state.key_id}{_daemon_age_suffix(state.key_age_seconds)}")
                else:
                    print("  key         unknown")
            elif state.reachability_detail:
                print(f"  local error {state.reachability_detail}")
            if state.detail:
                print(f"  supervisor  {state.detail}")
            return 0 if state.installed or state.reachable else 1
        if action == "stop":
            service.stop_daemon()
            print("  daemon stopped")
            return 0
    except service.ServiceError as exc:
        print(f"  daemon: {exc}")
        return 1
    except (OSError, RuntimeError) as exc:
        # Supervisor failures are real state failures, not an invitation to
        # guess a PID and kill it ourselves.
        print(f"  daemon supervisor error: {exc}")
        return 1
    print(f"  Unknown daemon action {action!r}.")
    return 2


def _daemon_age_suffix(seconds: float | None) -> str:
    """Render an observed age without pretending a missing timestamp is fresh."""
    if seconds is None:
        return " · checked unknown"
    if seconds < 60:
        return f" · checked {seconds:.0f}s ago"
    if seconds < 3600:
        return f" · checked {seconds / 60:.0f}m ago"
    return f" · checked {seconds / 3600:.1f}h ago"


def _fleet_admin_client():
    """The CLI's only fleet door is the local daemon's UDS admin contract."""
    from spacepilot.daemon.fleet import local_fleet_admin
    return local_fleet_admin()


def _fleet_snapshot(admin):
    from spacepilot.daemon.fleet import FleetSnapshot
    return FleetSnapshot.from_wire(admin.list())


def _fleet_frame_lines(admin) -> list[str]:
    """One fact frame shared unchanged by plain and Rich Live presentations."""
    from spacepilot.daemon.fleet import render_fleet_snapshot, utc_now
    return render_fleet_snapshot(_fleet_snapshot(admin), now=utc_now())


def _render_fleet_snapshot(snapshot) -> None:
    """Render a single non-watch fleet snapshot."""
    from spacepilot.daemon.fleet import render_fleet_snapshot, utc_now
    print("\n".join(render_fleet_snapshot(snapshot, now=utc_now())))


def _watch_fleet(
    admin,
    *,
    interval: float,
    output_mode: str = "plain",
    sleep=time.sleep,
    max_frames: int | None = None,
    live_factory=None,
    console_factory=None,
) -> int:
    """Refresh daemon-produced facts while recomputing ages at every frame."""
    frames = 0
    if output_mode == "live":
        from rich.console import Console
        from rich.live import Live
        from rich.text import Text

        # screen=False keeps this a compact updating table, not an alternate
        # screen TUI. The actual rows come exclusively from `_fleet_frame_lines`.
        make_console = console_factory or Console
        make_live = live_factory or Live
        console = make_console(no_color="NO_COLOR" in os.environ)
        try:
            with make_live(Text(""), console=console, screen=False, transient=False) as live:
                while max_frames is None or frames < max_frames:
                    lines = _fleet_frame_lines(admin)
                    live.update(Text("\n".join(lines)))
                    frames += 1
                    sleep(interval)
        except KeyboardInterrupt:
            console.print("\n  fleet watch stopped")
        return 0

    try:
        while max_frames is None or frames < max_frames:
            # Timestamping each printed snapshot makes an old block visibly
            # old when plain output is redirected to a log or CI artifact.
            from spacepilot.daemon.fleet import utc_now
            print(f"  snapshot   {utc_now().isoformat(timespec='seconds')}")
            print("\n".join(_fleet_frame_lines(admin)))
            frames += 1
            sleep(interval)
    except KeyboardInterrupt:
        print("\n  fleet watch stopped")
    return 0


def cmd_fleet(args: argparse.Namespace, cfg: Dict[str, Any] | None = None) -> int:
    """Send fleet requests to the local daemon; never poll peers from the CLI."""
    from spacepilot.daemon.fleet import FleetError

    # No subcommand reads as `list`, like models/silicon/runtimes. This used
    # to print "Unknown fleet action None." — Python's None, on screen.
    action = getattr(args, "fleet_action", None) or "list"
    watch = bool(getattr(args, "watch", False))
    if action is None and watch:
        action = "list"
    try:
        admin = _fleet_admin_client()
        if action == "init":
            result = admin.init(args.name)
            version = result.get("orders_version", "unknown")
            print(f"  fleet initialized · ORDERS v{version}")
            return 0
        if action == "add":
            result = admin.add(args.selector)
            print(f"  fleet member added · ORDERS v{result.get('orders_version', 'unknown')}")
            return 0
        if action == "join":
            result = admin.join(args.author_key_id, args.author_selector, args.fleet_id)
            print(f"  joined fleet · ORDERS v{result.get('orders_version', 'unknown')}")
            return 0
        if action == "list":
            if getattr(args, "json", False):
                print(json.dumps(dict(admin.list()), indent=2, default=str))
                return 0
            interval = float(getattr(args, "interval", 2.0))
            if interval <= 0:
                print("  --interval must be greater than zero")
                return 2
            if watch:
                mode = getattr(args, "output_mode", "plain")
                return _watch_fleet(admin, interval=interval, output_mode=mode)
            _render_fleet_snapshot(_fleet_snapshot(admin))
            return 0
    except (FleetError, OSError, RuntimeError) as exc:
        print(f"  fleet: {exc}")
        return 1
    print(f"  Unknown fleet action {action!r}.")
    return 2


def cmd_runtimes(args, cfg=None) -> int:
    """List, check or install the packages that execute a model."""
    from spacepilot.device_probe import probe_local_device
    from spacepilot.pluto import runtimes as rt

    reg = rt.runtimes()
    runtime_python = rt.interpreter(cfg)
    action = getattr(args, "runtimes_action", None) or "list"

    if action == "list":
        profile = probe_local_device()
        backend = profile.backend

        def _state_of(r, st):
            if not st.python_compatible:
                return "unusable"
            if st.below_minimum:
                return "outdated"
            if st.installed and st.external:
                return "installed (external env)"
            if st.installed:
                return "installed"
            if backend and backend not in r.backends:
                return "n/a here"
            return "available"

        checked = [(r, rt.check(r, cfg=cfg)) for r in
                   sorted(reg.values(), key=lambda x: x.id)]

        if getattr(args, "json", False):
            rows = []
            for r, st in checked:
                rows.append({
                    "id": r.id, "state": _state_of(r, st),
                    "serves": r.serves, "backends": r.backends,
                    "runs": r.runs, "version": st.version,
                    "python_note": st.python_note or None,
                    "external": st.external,
                    "external_path": st.external_path,
                })
            print(json.dumps({
                "system": {"chip": profile.chip, "backend": backend,
                           "interpreter": runtime_python},
                "runtimes": rows,
            }, indent=2, default=str))
            return 0

        print(f"{profile.chip or 'this machine'} · {backend or 'unknown backend'} "
              f"· {runtime_python}\n")
        width = max(11, max(len(_state_of(r, st)) for r, st in checked) + 2)
        print(f"  {'STATE':{width}s}{'RUNTIME':20s}{'SERVES':16s}{'BACKENDS':20s}VERSION")
        for r, st in checked:
            state = _state_of(r, st)
            print(f"  {state:{width}s}{r.id:20s}{','.join(r.serves):16s}"
                  f"{','.join(r.backends):20s}{st.version or '-'}")
            if not st.python_compatible:
                print(f"  {'':{width}s}{'':20s}{st.python_note}")
        print("\n  `spacepilot runtimes check <id>` for detail, `install <id>` to add one.")
        print("  n/a here means it needs silicon this machine does not have.")
        return 0

    rid = getattr(args, "runtime_id", None)
    r = reg.get(rid)
    if not r:
        print(f"No runtime '{rid}'. Known: {', '.join(sorted(reg))}")
        return 1

    if action == "check":
        st = rt.check(r, cfg=cfg)
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
            f"installed (external env), {st.version}" if st.installed and st.external and not st.below_minimum
            else f"installed, {st.version}" if st.installed and not st.below_minimum
            else f"installed but outdated — {st.reason}" if st.below_minimum
            else f"not installed — {st.reason}"))
        if st.external and st.external_path:
            print(f"  binary    {st.external_path}")
        if not st.python_compatible:
            print(f"            {st.python_note}")
        if r.notes:
            print(f"  note      {r.notes}")
        return 0

    if action == "install":
        st = rt.check(r, cfg=cfg)
        if st.installed and not st.below_minimum:
            if st.external:
                print(f"{r.name} is already installed in its own environment "
                      f"({st.version}) — {st.external_path}")
            else:
                print(f"{r.name} is already installed ({st.version}).")
            return 0
        if not st.python_compatible:
            print(f"Cannot install {r.name}: {st.python_note}")
            return 1

        argv = rt.install_command(r, py=runtime_python)
        print(f"{r.name} — {r.summary}\n")
        print(f"  will run   {' '.join(argv)}")
        print(f"  into       {runtime_python}")
        print(f"  licence    {r.license}")
        if r.notes:
            print(f"  note       {r.notes}")

        print("\n  resolving what this would change...")
        imp = rt.preview(r, py=runtime_python)
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
        st = rt.install(r, py=runtime_python)
        if st.installed and not st.below_minimum:
            print(f"  {r.name} {st.version} installed and imports cleanly.")
            return 0
        print(f"  Install did not take: {st.reason}")
        return 1

    print(f"Unknown action '{action}'.")
    return 1


# An absent figure is a fact about the vendor, not about the part. Printing it
# as 0, or as an empty cell, turns "nobody published this" into "this is zero" —
# the one reading the silicon registry exists to prevent.
NOT_PUBLISHED = "not published"

# A figure the vendor did not publish itself is marked, everywhere it appears.
# `declared` and `reported` are both claims, but only one of them is the claim
# of the party that built the thing.
REPORTED_MARK = "*"


def _bandwidth(v: float) -> str:
    """Bandwidth in the decimal units every vendor quotes it in.

    Memory uses `_gb` and its 1024s because that is how a machine reports its
    own capacity; bandwidth does not, and converting one with the other's base
    silently moves 819 GB/s to 763.
    """
    return f"{v / 1e12:.2f} TB/s" if v >= 1e12 else f"{v / 1e9:.0f} GB/s"


FIGURES = (
    ("memory", "memory_bytes", _gb),
    ("bandwidth", "bandwidth_bytes_per_sec", _bandwidth),
    ("npu", "npu_tops", lambda v: f"{v:.0f} TOPS"),
    ("power", "power_watts", lambda v: f"{v:.0f} W"),
    ("price", "price_usd", lambda v: f"${v:,.0f}"),
)


def _figure(claim, render) -> tuple:
    """One figure as (text, provenance mark), kept as two fields.

    The mark travels outside the value so the numbers still line up under one
    another. A reported figure that shifts its column by a character is a
    figure nobody compares against the one above it.
    """
    if claim is None:
        return NOT_PUBLISHED, " "
    return render(claim.value), (" " if claim.is_vendor else REPORTED_MARK)


def _source_kind(part) -> str:
    kinds = {c.source for c in (getattr(part, f) for _, f, _ in FIGURES) if c}
    if not kinds:
        return "nothing published"
    return kinds.pop() if len(kinds) == 1 else "mixed"


def _wrapped(text: str, indent: str, first: str = None) -> str:
    import textwrap
    return textwrap.fill(" ".join(text.split()), width=88,
                         initial_indent=first if first is not None else indent,
                         subsequent_indent=indent)


def cmd_silicon(args, cfg=None) -> int:
    """The parts that exist, as opposed to the machines this project has probed.

    Nothing here is measured, so nothing here is printed without its source.
    """
    from spacepilot.pluto import silicon as si

    parts = si.silicon()
    ordered = sorted(parts.values(), key=lambda p: (p.kind, p.id))
    as_json = getattr(args, "json", False)

    # `list` is reserved so this reads the same way as `models list`, and no
    # part may be named that.
    part_id = getattr(args, "part_id", None)
    if part_id and part_id != "list":
        part = parts.get(part_id)
        if not part:
            print(f"No part '{part_id}'. Run `spacepilot silicon` to list them.")
            return 1
        if as_json:
            print(json.dumps({"schema": si.SCHEMA_VERSION, **part.to_dict()}, indent=2))
            return 0

        buyable = "buyable today" if part.is_buyable else "not buyable"
        print(f"{part.name}  [{part.id}]")
        print(f"  {part.kind} · {part.vendor} · {part.availability} ({buyable})")
        mem = f" · {part.memory_model} memory" if part.memory_model else ""
        print(f"  reached by {', '.join(part.compute_paths)}{mem}" if part.compute_paths
              else f"  no compute path — a component, not a machine you run on{mem}")
        print(_wrapped(part.summary, "  "))
        print()

        for label, field, render in FIGURES:
            claim = getattr(part, field)
            if claim is None:
                print(f"  {label:11s}{NOT_PUBLISHED}")
                continue
            print(f"  {label:11s}{render(claim.value):<13s}"
                  f"[{claim.source}, checked {claim.checked}]")
            print(f"  {'':11s}{claim.url}")
            if claim.note:
                print(_wrapped(claim.note, " " * 13))
        if part.note:
            print()
            print(_wrapped(part.note, " " * 13, f"  {'note':11s}"))
        print(f"\n  {NOT_PUBLISHED} means the vendor publishes no such figure. It is not zero.")
        return 0

    if as_json:
        print(json.dumps({"schema": si.SCHEMA_VERSION,
                          "parts": [p.to_dict() for p in ordered]}, indent=2))
        return 0

    print(f"{len(ordered)} parts · nothing here is measured — every figure is "
          f"somebody's claim, dated\n")
    # Widths come from the data, not from constants. A hardcoded column pays no
    # dividend when an id gets shorter, and silently truncates when one grows.
    kind_w = max(len("KIND"), *(len(p.kind) for p in ordered)) + 2
    part_w = max(len("PART"), *(len(p.id) for p in ordered)) + 2
    avail_w = max(len("AVAILABILITY"), *(len(p.availability) for p in ordered)) + 1

    print(f"  {'KIND':{kind_w}s}{'PART':{part_w}s}{'AVAILABILITY':{avail_w}s}"
          f"{'MEMORY':>13s}    {'BANDWIDTH':>13s}    SOURCE")

    for p in ordered:
        mem, mem_mark = _figure(p.memory_bytes, _gb)
        bw, bw_mark = _figure(p.bandwidth_bytes_per_sec, _bandwidth)
        print(f"  {p.kind:{kind_w}s}{p.id:{part_w}s}{p.availability:{avail_w}s}"
              f"{mem:>13s} {mem_mark}  {bw:>13s} {bw_mark}  {_source_kind(p)}")

    print("\n  `spacepilot silicon <id>` for detail, with every claim's date and link.")
    print(f"  {REPORTED_MARK} marks a figure a publication reported, not one the vendor "
          f"published.")
    print("    SOURCE reads every figure a part carries, including ones with no column here.")
    print(f"  {NOT_PUBLISHED} means the vendor publishes no such figure. It is not zero.")
    return 0


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
        print("  spacepilot measure --model flux --metric seconds_per_image -- "
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

    as_json = getattr(args, "json", False)
    out = sys.stderr if as_json else sys.stdout
    if getattr(args, "save", False):
        path = ms.write_system(system)
        print(f"\n  recorded → {path}", file=out)
    else:
        # Under --json this trailer made stdout unparseable (`probe --json | jq`
        # failed on "Extra data"); stdout carries only the JSON object.
        print("\n  (not saved; pass --save to write this to registry/systems/)", file=out)
    return 0


def main(argv: list[str] | None = None):
    cfg = load_config()
    parser = argparse.ArgumentParser(
        prog="spacepilot",
        description="SpacePilot — inference orchestration across the machines you can reach.",
    )
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--live", dest="output_mode", action="store_const", const="live",
                              help="Render live terminal updates")
    output_group.add_argument("--plain", dest="output_mode", action="store_const", const="plain",
                              help="Render plain newline-delimited output")
    subparsers = parser.add_subparsers(dest="command")

    # doctor/check
    subparsers.add_parser("doctor", help="Check local environment and capabilities")
    subparsers.add_parser("check", help="Alias for doctor")

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

    # daemon
    daemon_p = subparsers.add_parser("daemon", help="Run and supervise this machine's local daemon")
    daemon_sub = daemon_p.add_subparsers(dest="daemon_action", required=True)
    daemon_sub.add_parser("install", help="Install and start the per-user daemon service")
    daemon_sub.add_parser("run", help="Run the daemon in this foreground terminal")
    daemon_status_p = daemon_sub.add_parser("status", help="Ask the OS supervisor for daemon status")
    daemon_status_p.add_argument("--json", action="store_true", help="Machine-readable output; stdout carries only JSON")
    daemon_sub.add_parser("stop", help="Stop the daemon through its OS supervisor")

    # fleet
    fleet_p = subparsers.add_parser("fleet", help="Manage ships through the local daemon")
    fleet_p.add_argument("--watch", action="store_true", help="Continuously render daemon fleet facts")
    fleet_p.add_argument("--interval", type=float, default=2.0,
                         help="Seconds between daemon snapshot requests (default: 2)")
    fleet_sub = fleet_p.add_subparsers(dest="fleet_action")
    fleet_init = fleet_sub.add_parser("init", help="Create this fleet's signed ORDERS")
    fleet_init.add_argument("name", help="This ship's real name")
    fleet_add = fleet_sub.add_parser("add", help="Add a signed ship member")
    fleet_add.add_argument("selector", help="One live Tailscale peer selector")
    fleet_join = fleet_sub.add_parser("join", help="Join with a signed fleet invitation")
    fleet_join.add_argument("--author-key-id", required=True,
                            help="Pinned permanent author Ed25519 key id")
    fleet_join.add_argument("--author-selector", required=True,
                            help="Live Tailscale selector for the pinned author")
    fleet_join.add_argument("--fleet-id", default=None, help="Optional pinned fleet UUID")
    fleet_list = fleet_sub.add_parser("list", help="Render the daemon's current fleet facts")
    fleet_list.add_argument("--json", action="store_true", help="Machine-readable output; stdout carries only JSON")
    # SUPPRESS, not a default: argparse writes a subparser default over whatever
    # the parent already parsed, so `fleet --watch --interval 5 list` silently
    # became a single snapshot at 2s. With SUPPRESS the attribute is only set
    # when the flag is actually given after the subcommand.
    fleet_list.add_argument("--watch", action="store_true", default=argparse.SUPPRESS,
                            help="Continuously render fleet facts")
    fleet_list.add_argument("--interval", type=float, default=argparse.SUPPRESS,
                            help="Seconds between daemon snapshot requests (default: 2)")

    # lora
    lora_p = subparsers.add_parser("lora", help="Manage LoRA models")
    lora_subparsers = lora_p.add_subparsers(dest="lora_action", required=True)
    lora_subparsers.add_parser("list", help="List LoRA models")
    lora_subparsers.add_parser("train", help="Train a new LoRA model")

    # recipes
    recipes_p = subparsers.add_parser("recipes", help="Manage recipes")
    recipes_subparsers = recipes_p.add_subparsers(dest="recipes_action", required=True)
    recipes_list_p = recipes_subparsers.add_parser("list", help="List recipes")
    recipes_list_p.add_argument("--json", action="store_true", help="Machine-readable output; stdout carries only JSON")
    recipe_download_p = recipes_subparsers.add_parser("download", help="Download a recipe")
    recipe_download_p.add_argument("recipe_name", type=str, help="Name of recipe to download")

    # studio
    studio_p = subparsers.add_parser("studio", help="Launch interactive SpacePilot Studio Web UI")
    studio_p.add_argument("--port", type=int, default=8088, help="Port to bind (default: 8088)")
    studio_p.add_argument("--open", action="store_true", help="Open in default browser")

    # status
    rt_p = subparsers.add_parser("runtimes", help="Packages that execute models")
    rt_sub = rt_p.add_subparsers(dest="runtimes_action")
    rt_list_p = rt_sub.add_parser("list", help="What is installed and what is available")
    rt_list_p.add_argument("--json", action="store_true", help="Machine-readable output; stdout carries only JSON")
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
    models_p.add_argument("--json", action="store_true", help="Machine-readable output; stdout carries only JSON")

    sil_p = subparsers.add_parser(
        "silicon", help="Parts that exist, whether or not this project has one")
    sil_p.add_argument("part_id", nargs="?",
                       help="`list` for the table (the default), or a part id for detail")
    sil_p.add_argument("--json", action="store_true",
                       help="Print the registry as JSON, sources and dates included")
    run_p = subparsers.add_parser("run", help="Run a real workload on this machine")
    run_sub = run_p.add_subparsers(dest="run_workload", required=True)
    run_image = run_sub.add_parser("image", help="Generate one image through an exact local route")
    run_image.add_argument("--prompt", required=True, help="Text prompt for the image")
    run_image.add_argument("--output", "-o", default=None, help="Output image path")
    run_image.add_argument("--yes", action="store_true", help="Execute after printing the plan")
    run_speech = run_sub.add_parser(
        "speech", help="Synthesize speech through an exact local route")
    run_speech.add_argument("--text", required=True, help="Text to synthesize")
    run_speech.add_argument("--voice", default="af_heart",
                            help="Kokoro voice id (default af_heart)")
    run_speech.add_argument("--output", "--out", "-o", dest="output", default=None,
                            help="Output wav path")
    run_speech.add_argument("--yes", action="store_true",
                            help="Execute after printing the plan")
    run_tr = run_sub.add_parser(
        "transcribe", help="Transcribe an audio file through an exact local route")
    run_tr.add_argument("audio", help="Audio file to transcribe (wav, mp3, flac, ogg)")
    run_tr.add_argument("--output", "--out", "-o", dest="output", default=None,
                        help="Output transcript path (.txt)")
    run_tr.add_argument("--yes", action="store_true",
                        help="Execute after printing the plan")
    run_text = run_sub.add_parser(
        "text", help="Generate text through the conservative pinned MLX-LM route")
    run_text.add_argument("--prompt", required=True, help="Prompt for the model")
    run_text.add_argument("--output", "--out", "-o", dest="output", default=None,
                          help="Output text path (.txt)")
    run_text.add_argument("--max-tokens", type=int, default=256,
                          help="Maximum generated tokens (safe route limit: 256)")
    run_text.add_argument("--max-kv-size", type=int, default=4096,
                          help="Maximum KV-cache tokens (safe route limit: 4096)")
    run_text.add_argument("--temperature", type=float, default=0.0,
                          help="Sampling temperature, 0.0..2.0 (default 0)")
    run_text.add_argument("--yes", action="store_true",
                          help="Execute after printing the plan")

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
    sweep_run.add_argument("spec", help="Path to a spec, e.g. spacepilot/registry/sweeps/flux-schnell-4bit.yaml")
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

    raw_argv = list(sys.argv[1:] if argv is None else argv)
    try:
        parse_argv, explicit_mode = _extract_output_mode_flags(raw_argv)
    except ValueError as exc:
        parser.error(str(exc))

    if not parse_argv:
        parser.print_help()
        return 0

    args = parser.parse_args(parse_argv)
    args.output_mode = resolve_output_mode(explicit_mode or args.output_mode, cfg)

    dispatch = {
        "doctor": cmd_doctor,
        "check": cmd_doctor,
        "probe": cmd_probe,
        "serve": cmd_serve,
        "daemon": cmd_daemon,
        "fleet": cmd_fleet,
        "lora": cmd_lora,
        "recipes": cmd_recipes,
        "studio": cmd_studio,
        "models": cmd_models,
        "silicon": cmd_silicon,
        "run": cmd_run,
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


def pluto_main() -> int:
    """Compatibility executable retained for one deprecation window."""
    print("pluto is deprecated; use spacepilot", file=sys.stderr)
    return main()


if __name__ == "__main__":
    raise SystemExit(main())
