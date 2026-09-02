#!/usr/bin/env python3
"""whisper.cpp subprocess driver for local speech-to-text.

Like mflux, whisper.cpp is never imported: the `whisper-cli` binary (Homebrew,
or a source build) is invoked as a subprocess with an argv list. Weights are
GGML files; the registry pins `ggerganov/whisper.cpp` revisions, and an
explicit `SPACEPILOT_WHISPER_MODEL` path wins over the cache the same way the
Kokoro driver's explicit paths do — an explicit path has no observed revision,
and the record says so rather than copying the registry pin onto it.
"""

import os
import shutil
import subprocess
import time
import wave
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from spacepilot.drivers.base import DriverSpec, InferenceDriver


class WhisperSubprocessError(RuntimeError):
    """whisper-cli exited non-zero or produced no transcript. Never swallowed."""


def whisper_bin(cfg: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Where whisper-cli lives: env var, then config, then PATH. None if absent."""
    from spacepilot.paths import env_value
    return (
        env_value("SPACEPILOT_WHISPER_BIN", "PLUTO_WHISPER_BIN")
        or (cfg or {}).get("whisper_bin")
        or shutil.which("whisper-cli")
    )


def audio_duration_seconds(path: Path) -> Optional[float]:
    """Duration of a PCM wav, or None. Never guessed for formats wave cannot read."""
    try:
        with wave.open(str(path), "rb") as handle:
            rate = handle.getframerate()
            frames = handle.getnframes()
    except (wave.Error, EOFError, OSError):
        return None
    if rate <= 0 or frames <= 0:
        return None
    return frames / float(rate)


class WhisperCppDriver(InferenceDriver):
    """Subprocess driver for whisper.cpp transcription."""

    def __init__(
        self,
        driver_id: str = "whisper-cpp",
        variant_id: str = "whisper-base-en",
        bin_path: Optional[str] = None,
        model_path: Optional[str] = None,
    ) -> None:
        spec = DriverSpec(
            driver_id=driver_id,
            task="transcription",
            backend="cpu",
            resident_vram_gb=0.36,
            is_loaded=False,
        )
        super().__init__(spec)
        self.variant_id = variant_id
        self.bin_path = bin_path
        self.model_path = model_path
        self.resolved_revision: Optional[str] = None

    def executable(self) -> Optional[str]:
        path = self.bin_path or whisper_bin()
        if path and Path(path).is_file() and os.access(path, os.X_OK):
            return str(path)
        return None

    def asset_path(self, variant_id: Optional[str] = None) -> Optional[str]:
        """The GGML weights file for one exact variant: explicit path, env
        override, or pinned cache.

        An explicit path must be named like the variant's registry file
        (`ggml-base.en.bin` and so on). Without that check a small.en file
        handed to the base.en route would run and be recorded under the wrong
        variant id — a measurement describing weights that never ran.
        """
        from spacepilot.paths import env_value, resolve
        from spacepilot.model_registry import registry

        variant_id = variant_id or self.variant_id
        variant = registry().variant(variant_id)
        if variant is None or not variant.files:
            return None
        expected = variant.files[0]

        explicit = self.model_path or env_value(
            "SPACEPILOT_WHISPER_MODEL", "PLUTO_WHISPER_MODEL")
        if explicit:
            if not Path(explicit).is_file():
                raise FileNotFoundError(
                    f"configured whisper model path does not exist: {explicit}")
            if Path(explicit).name != expected:
                raise FileNotFoundError(
                    f"configured whisper model is {Path(explicit).name}, but "
                    f"{variant_id} needs {expected}")
            self.resolved_revision = None
            return str(explicit)

        resolved = resolve(variant.repo, variant.revision, variant.files)
        if resolved is None:
            return None
        weights = resolved.file(expected)
        if weights is None:
            return None
        self.resolved_revision = resolved.revision
        return str(weights)

    def load(self) -> bool:
        try:
            self.spec.is_loaded = bool(self.executable() and self.asset_path())
        except FileNotFoundError:
            self.spec.is_loaded = False
        return self.spec.is_loaded

    def unload(self) -> bool:
        self.spec.is_loaded = False
        return True

    def infer(
        self,
        audio_path: str,
        out_path: str,
        variant_id: Optional[str] = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Transcribe one file to text and report measured wall time.

        `out_path` is the final .txt artifact; whisper-cli's `-of` takes the
        path without extension and appends `.txt` itself.
        """
        variant_id = variant_id or self.variant_id
        exe = self.executable()
        if exe is None:
            raise WhisperSubprocessError(
                "whisper-cli not found or not executable; install whisper-cpp "
                "or set SPACEPILOT_WHISPER_BIN")
        model = self.asset_path(variant_id)
        if model is None:
            raise WhisperSubprocessError(
                f"whisper weights are not cached; run "
                f"`spacepilot recipes download {variant_id}` "
                f"or set SPACEPILOT_WHISPER_MODEL")
        audio = Path(audio_path)
        if not audio.is_file() or audio.stat().st_size == 0:
            raise WhisperSubprocessError(f"audio file is missing or empty: {audio}")

        final = Path(out_path)
        prefix = str(final)[:-4] if final.suffix == ".txt" else str(final)
        cmd = [exe, "-m", model, "-f", str(audio), "-otxt", "-of", prefix, "-np"]

        start = time.perf_counter()
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise WhisperSubprocessError(
                f"whisper-cli timed out after {timeout}s: {' '.join(cmd)}") from exc
        wall_seconds = time.perf_counter() - start

        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "")[-2000:]
            raise WhisperSubprocessError(
                f"whisper-cli exited {proc.returncode}: {' '.join(cmd)}\n{tail}")

        transcript = Path(prefix + ".txt")
        if not transcript.is_file():
            raise WhisperSubprocessError(
                f"whisper-cli exited 0 but wrote no transcript at {transcript}")

        return {
            "status": "completed",
            "driver_id": self.driver_id,
            "task": self.task,
            "backend": self.backend,
            "model_revision": self.resolved_revision,
            "weights": Path(model).name,
            "audio_path": str(audio),
            "audio_seconds": audio_duration_seconds(audio),
            "wall_seconds": round(wall_seconds, 3),
            "out_path": str(transcript),
            "command": cmd,
        }
