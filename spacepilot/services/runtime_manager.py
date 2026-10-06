"""Runtime process and resident model management for local/remote inference nodes.

Coordinates model server processes (e.g. SGLang, vLLM), tracks active process
PIDs, ports, and model paths in a persistent resident registry file
(~/.spacepilot/resident.json), and provides health check verification.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import httpx

logger = logging.getLogger(__name__)

DEFAULT_RESIDENT_PATH = Path.home() / ".spacepilot" / "resident.json"


def _read_resident_state(state_path: Path) -> List[Dict[str, Any]]:
    """Read the resident models list from state_path."""
    if not state_path.exists():
        return []
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            data = json.loads(content)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "resident" in data:
                return data["resident"]
    except Exception as exc:
        logger.warning("Failed to read resident state from %s: %s", state_path, exc)
    return []


def _write_resident_state(state_path: Path, models: List[Dict[str, Any]]) -> None:
    """Atomically write the resident models list to state_path."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = state_path.parent / f".{state_path.name}.tmp.{os.getpid()}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(models, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, state_path)


def _is_pid_alive(pid: int) -> bool:
    """Check if process with PID is alive."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _check_http_health(port: int, host: str = "127.0.0.1", timeout_sec: float = 1.0) -> bool:
    """Perform healthcheck against http://<host>:<port>/health."""
    url = f"http://{host}:{port}/health"
    try:
        with httpx.Client(timeout=timeout_sec) as client:
            resp = client.get(url)
            return resp.status_code == 200
    except Exception:
        return False


def wait_for_healthcheck(
    port: int,
    host: str = "127.0.0.1",
    timeout: float = 30.0,
    interval: float = 0.5,
    health_checker: Optional[Callable[[int, str], bool]] = None,
) -> bool:
    """Poll health endpoint until healthy or timeout exceeded."""
    checker = health_checker or (lambda p, h: _check_http_health(p, h))
    start_time = time.time()
    while time.time() - start_time < timeout:
        if checker(port, host):
            return True
        time.sleep(interval)
    return False


def get_resident_models(
    state_path: Optional[Path] = None,
    verify_alive: bool = True,
) -> List[Dict[str, Any]]:
    """Get list of resident models, optionally pruning dead processes.

    Args:
        state_path: Path to resident state JSON. Defaults to ~/.spacepilot/resident.json.
        verify_alive: If True, checks if PIDs are alive and prunes defunct entries.

    Returns:
        List of resident model metadata dictionaries.
    """
    path = state_path or DEFAULT_RESIDENT_PATH
    records = _read_resident_state(path)
    if not verify_alive:
        return records

    alive_records = []
    modified = False
    for item in records:
        pid = item.get("pid")
        if pid and _is_pid_alive(pid):
            alive_records.append(item)
        else:
            modified = True

    if modified:
        _write_resident_state(path, alive_records)

    return alive_records


def build_backend_command(
    backend: str,
    weights_dir: Union[Path, str],
    port: int,
    tp: int = 1,
) -> List[str]:
    """Build the CLI command to launch the given inference backend."""
    weights_path = str(weights_dir)
    b = backend.lower()
    if b == "sglang":
        cmd = [
            "python", "-m", "sglang.launch_server",
            "--model-path", weights_path,
            "--port", str(port),
            "--tp", str(tp),
            "--host", "0.0.0.0",
        ]
    elif b == "vllm":
        cmd = [
            "python", "-m", "vllm.entrypoints.openai.api_server",
            "--model", weights_path,
            "--port", str(port),
            "--tensor-parallel-size", str(tp),
            "--host", "0.0.0.0",
        ]
    else:
        cmd = [
            "python", "-m", f"{b}.launch",
            "--model-path", weights_path,
            "--port", str(port),
            "--tp", str(tp),
            "--host", "0.0.0.0",
        ]
    return cmd


def load_model(
    model_id: str,
    weights_dir: Path,
    backend: str = "sglang",
    port: int = 30010,
    tp: int = 1,
    daemon: bool = True,
    state_path: Optional[Path] = None,
    runner: Optional[Callable[..., Any]] = None,
    health_timeout: float = 30.0,
    skip_healthcheck: bool = False,
    health_checker: Optional[Callable[[int, str], bool]] = None,
) -> Dict[str, Any]:
    """Launch a model inference server and record it in resident state.

    Args:
        model_id: Unique model identifier.
        weights_dir: Path to model checkpoint/weights.
        backend: Runtime backend (default: 'sglang').
        port: Listening port (default: 30010).
        tp: Tensor parallelism degree (default: 1).
        daemon: If True, spawn subprocess detached.
        state_path: Override path to resident.json.
        runner: Optional subprocess runner (defaults to subprocess.Popen).
        health_timeout: Max seconds to wait for /health endpoint.
        skip_healthcheck: If True, return immediately without polling health.
        health_checker: Optional callable taking (port, host) returning bool.

    Returns:
        Dict containing model metadata, pid, port, backend, and health status.
    """
    path = state_path or DEFAULT_RESIDENT_PATH
    residents = get_resident_models(path, verify_alive=True)

    # Check if model or port is already loaded
    for m in residents:
        if m.get("port") == port:
            raise RuntimeError(f"Port {port} is already in use by resident model {m.get('model_id')} (PID {m.get('pid')})")
        if m.get("model_id") == model_id:
            raise RuntimeError(f"Model {model_id} is already resident on port {m.get('port')} (PID {m.get('pid')})")

    cmd = build_backend_command(backend=backend, weights_dir=weights_dir, port=port, tp=tp)

    if runner is not None:
        proc = runner(cmd)
    else:
        popen_kwargs: Dict[str, Any] = {
            "stdout": subprocess.DEVNULL if daemon else None,
            "stderr": subprocess.DEVNULL if daemon else None,
        }
        if daemon and hasattr(os, "setpgrp"):
            popen_kwargs["preexec_fn"] = os.setpgrp

        proc = subprocess.Popen(cmd, **popen_kwargs)

    pid = getattr(proc, "pid", None)
    if pid is None:
        pid = -1

    healthy = True
    if not skip_healthcheck:
        healthy = wait_for_healthcheck(
            port=port,
            timeout=health_timeout,
            health_checker=health_checker,
        )
        if not healthy:
            # Clean up spawned process if healthcheck failed
            if pid > 0 and _is_pid_alive(pid):
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass
            raise TimeoutError(f"Healthcheck timed out for {model_id} on port {port} after {health_timeout}s")

    record: Dict[str, Any] = {
        "model_id": model_id,
        "weights_dir": str(weights_dir),
        "backend": backend,
        "port": port,
        "tp": tp,
        "pid": pid,
        "loaded_at": time.time(),
        "healthy": healthy,
    }

    residents.append(record)
    _write_resident_state(path, residents)

    return record


def unload_model(
    model_id: Optional[str] = None,
    port: Optional[int] = None,
    all_models: bool = False,
    state_path: Optional[Path] = None,
    sig: int = signal.SIGTERM,
) -> Dict[str, Any]:
    """Stop one or all resident model processes and remove from state registry.

    Args:
        model_id: Target model ID to unload.
        port: Target port to unload.
        all_models: If True, unload all resident models.
        state_path: Override path to resident.json.
        sig: Signal to send to process (default: SIGTERM).

    Returns:
        Dict with status, count of unloaded models, and details.
    """
    path = state_path or DEFAULT_RESIDENT_PATH
    residents = _read_resident_state(path)

    to_unload: List[Dict[str, Any]] = []
    retained: List[Dict[str, Any]] = []

    for item in residents:
        matches = False
        if all_models:
            matches = True
        elif model_id is not None and item.get("model_id") == model_id:
            matches = True
        elif port is not None and item.get("port") == port:
            matches = True

        if matches:
            to_unload.append(item)
        else:
            retained.append(item)

    unloaded_count = 0
    errors: List[str] = []

    for item in to_unload:
        pid = item.get("pid")
        if pid and _is_pid_alive(pid):
            try:
                os.kill(pid, sig)
                unloaded_count += 1
            except OSError as exc:
                errors.append(f"Failed to kill PID {pid} for {item.get('model_id')}: {exc}")
        else:
            # Already dead
            unloaded_count += 1

    _write_resident_state(path, retained)

    return {
        "unloaded_count": unloaded_count,
        "unloaded_models": to_unload,
        "remaining_count": len(retained),
        "errors": errors,
    }
