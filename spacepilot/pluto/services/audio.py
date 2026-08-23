"""Audio synthesis, normalization, and ducking service."""

import math
import json
import time
import uuid
import subprocess
import threading
from pathlib import Path
from typing import Optional
from fastapi import HTTPException

import httpx

from spacepilot.pluto.core.config import get_settings
from spacepilot.pluto.core.http import require_http_url
from spacepilot.pluto.core.utils import run_ffmpeg, discard_partial, ffmpeg_error, write_meta

_kokoro = None
_kokoro_lock = threading.Lock()

CLOUD_NOT_READY = (
    "backend='cloud' is not implemented. MLX does not run on CUDA, so the spot box "
    "needs MiniMaxAI/MiniMax-Music3 (music) or a Qwen3-TTS build (voice) served via "
    "SGLang-Omni or the diffusers ModularPipeline. Neither is provisioned."
)


def get_kokoro_search_paths() -> list[tuple[Optional[str], Optional[str]]]:
    settings = get_settings()
    return [
        (settings.kokoro_model_path, settings.kokoro_voices_path),
        (
            str(settings.root_dir.parent / "sr-lessons" / "tools" / "kokoro" / "kokoro-v1.0.onnx"),
            str(settings.root_dir.parent / "sr-lessons" / "tools" / "kokoro" / "voices-v1.0.bin"),
        ),
        (
            str(Path.home() / ".cache" / "hyperframes" / "tts" / "models" / "kokoro-v1.0.onnx"),
            str(Path.home() / ".cache" / "hyperframes" / "tts" / "voices" / "voices-v1.0.bin"),
        ),
    ]


def kokoro_assets() -> tuple[Optional[str], Optional[str]]:
    """First (model, voices) pair that exists on disk, or (None, None)."""
    for model, voices in get_kokoro_search_paths():
        if model and voices and Path(model).is_file() and Path(voices).is_file():
            return model, voices
    return None, None


def load_kokoro():
    """Lazily build the shared Kokoro session; ~0.7s once, then cached."""
    global _kokoro
    with _kokoro_lock:
        if _kokoro is None:
            from kokoro_onnx import Kokoro

            model, voices = kokoro_assets()
            if not model:
                raise RuntimeError(
                    "kokoro-v1.0.onnx / voices-v1.0.bin not found; set PLUTO_KOKORO_MODEL "
                    "and PLUTO_KOKORO_VOICES"
                )
            _kokoro = Kokoro(model, voices)
        return _kokoro


def synthesize_voice(text: str, voice: str, speed: float, out_path: Path) -> None:
    """Render speech to a 16-bit mono WAV with Kokoro."""
    import wave
    import numpy as np

    samples, sample_rate = load_kokoro().create(text, voice=voice, speed=speed, lang="en-us")
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(out_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())


def mlx_generate_audio(path: str, payload: dict, timeout: int) -> bytes:
    """POST to mlx-serve and return the WAV bytes it responds with.

    `mlx_serve_url` comes from the MLX_SERVE_URL environment variable, so the
    scheme is attacker-shaped input in any deployment where the environment is
    not fully trusted. require_http_url rejects file:// and friends before the
    request is built.
    """
    settings = get_settings()
    url = require_http_url(f"{settings.mlx_serve_url}{path}")
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        return resp.content


def loudnorm_two_pass(src: Path, dst: Path, target_lufs: int) -> subprocess.CompletedProcess:
    """Normalize to target_lufs.

    Single-pass loudnorm is a live estimator and lands 1-2 LU off, which misses
    the studio's -14..-18 gate. Measure first, then apply the measurement.
    """
    measure = run_ffmpeg([
        "-i", str(src),
        "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:print_format=json",
        "-f", "null", "-",
    ])
    if measure.returncode != 0:
        return measure

    single_pass = f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11"
    try:
        blob = measure.stderr[measure.stderr.rindex("{"):measure.stderr.rindex("}") + 1]
        m = json.loads(blob)
        fields = {k: float(m[f"input_{k}"]) for k in ("i", "tp", "lra", "thresh")}
        offset = float(m["target_offset"])
        if not all(math.isfinite(v) for v in (*fields.values(), offset)) or fields["i"] < -70:
            applied = single_pass
        else:
            applied = (
                f"{single_pass}:measured_I={fields['i']}:measured_TP={fields['tp']}"
                f":measured_LRA={fields['lra']}:measured_thresh={fields['thresh']}"
                f":offset={offset}:linear=true"
            )
    except (ValueError, KeyError):
        applied = single_pass

    return run_ffmpeg(["-v", "error", "-i", str(src), "-af", applied, "-ar", "44100", str(dst)])


def peak_normalize(src: Path, dst: Path, target_dbfs: float) -> subprocess.CompletedProcess:
    """Bring the true peak to target_dbfs."""
    measure = run_ffmpeg(["-i", str(src), "-af", "volumedetect", "-f", "null", "-"])
    if measure.returncode != 0:
        return measure

    gain_db = 0.0
    for line in (measure.stderr or "").splitlines():
        if "max_volume:" in line:
            try:
                peak = float(line.split("max_volume:")[1].strip().split()[0])
                if math.isfinite(peak):
                    gain_db = target_dbfs - peak
            except (ValueError, IndexError):
                pass
            break

    return run_ffmpeg([
        "-v", "error", "-i", str(src), "-af", f"volume={gain_db:.2f}dB", str(dst),
    ])
