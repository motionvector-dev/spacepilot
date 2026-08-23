"""Common file, subprocess, and metadata helpers."""

import json
import subprocess
from pathlib import Path
from fastapi import HTTPException
from spacepilot.pluto.core.config import get_settings


def run_ffmpeg(args: list[str]) -> subprocess.CompletedProcess:
    settings = get_settings()
    try:
        return subprocess.run(
            ["ffmpeg", "-y", *args],
            capture_output=True,
            text=True,
            timeout=settings.ffmpeg_timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args, returncode=-1, stdout="", stderr=f"timed out after {settings.ffmpeg_timeout_sec}s",
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
    """Resolve a name to an existing file inside outputs_dir, or raise 404."""
    settings = get_settings()
    outputs_dir = settings.outputs_dir
    try:
        path = (outputs_dir / name).resolve()
        contained = path.is_relative_to(outputs_dir.resolve()) and path.is_file()
    except (ValueError, TypeError):
        contained = False
    if not contained:
        raise HTTPException(status_code=404, detail=f"'{name}' not found")
    return path
