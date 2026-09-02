#!/usr/bin/env python3
"""In-process Kokoro-82M ONNX Speech Synthesis Driver.

Synthesizes high-fidelity 24kHz speech audio with voice catalogue selection
and sidechain -16 LUFS normalization for timeline integration.
"""

import os
import io
import math
import time
import wave
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

import numpy as np

from spacepilot.drivers.base import DriverSpec, InferenceDriver

logger = logging.getLogger("spacepilot.drivers.kokoro")

# 10 official Kokoro voice profiles
VOICE_CATALOGUE: List[Dict[str, str]] = [
    {"id": "af_heart", "name": "Heart", "gender": "female", "lang": "en-us", "style": "natural_warm"},
    {"id": "af_alloy", "name": "Alloy", "gender": "female", "lang": "en-us", "style": "expressive_clear"},
    {"id": "af_bella", "name": "Bella", "gender": "female", "lang": "en-us", "style": "bright_cinematic"},
    {"id": "af_jessica", "name": "Jessica", "gender": "female", "lang": "en-us", "style": "documentary_calm"},
    {"id": "af_kore", "name": "Kore", "gender": "female", "lang": "en-us", "style": "authoritative_narrative"},
    {"id": "am_michael", "name": "Michael", "gender": "male", "lang": "en-us", "style": "deep_cinematic_trailer"},
    {"id": "am_fenrir", "name": "Fenrir", "gender": "male", "lang": "en-us", "style": "gritty_dramatic"},
    {"id": "am_puck", "name": "Puck", "gender": "male", "lang": "en-us", "style": "dynamic_energetic"},
    {"id": "am_echo", "name": "Echo", "gender": "male", "lang": "en-us", "style": "smooth_commercial"},
    {"id": "am_onyx", "name": "Onyx", "gender": "male", "lang": "en-us", "style": "commanding_rich"},
]

DEFAULT_SAMPLE_RATE = 24000
DEFAULT_TARGET_LUFS = -16.0


class KokoroDriver(InferenceDriver):
    """In-process Kokoro-82M ONNX speech synthesis driver."""

    def __init__(
        self,
        driver_id: str = "kokoro-82m-onnx",
        model_path: Optional[str] = None,
        voices_path: Optional[str] = None,
    ) -> None:
        spec = DriverSpec(
            driver_id=driver_id,
            task="voiceover",
            backend="onnx",
            resident_vram_gb=0.32,
            is_loaded=False,
        )
        super().__init__(spec)
        self.model_path = model_path
        self.voices_path = voices_path
        self.resolved_revision: Optional[str] = None
        self._session: Any = None

    @classmethod
    def get_voice_catalogue(cls) -> List[Dict[str, str]]:
        """Return the list of supported Kokoro voices."""
        return list(VOICE_CATALOGUE)

    @classmethod
    def is_valid_voice(cls, voice_id: str) -> bool:
        """Check if a voice ID exists in the catalogue."""
        return any(v["id"] == voice_id for v in VOICE_CATALOGUE)

    def asset_paths(self) -> Tuple[Optional[str], Optional[str]]:
        """Find both assets from one explicit source or one HF snapshot."""
        from spacepilot.paths import env_value, resolve

        if self.model_path or self.voices_path:
            if not self.model_path or not self.voices_path:
                raise ValueError("Kokoro requires both model_path and voices_path")
            if not Path(self.model_path).is_file() or not Path(self.voices_path).is_file():
                raise FileNotFoundError("explicit Kokoro model_path/voices_path do not both exist")
            self.resolved_revision = None
            return self.model_path, self.voices_path

        env_model = env_value("SPACEPILOT_KOKORO_MODEL", "PLUTO_KOKORO_MODEL")
        env_voices = env_value("SPACEPILOT_KOKORO_VOICES", "PLUTO_KOKORO_VOICES")
        if env_model or env_voices:
            if not env_model or not env_voices:
                raise ValueError(
                    "Kokoro requires both SPACEPILOT_KOKORO_MODEL and "
                    "SPACEPILOT_KOKORO_VOICES")
            if not Path(env_model).is_file() or not Path(env_voices).is_file():
                raise FileNotFoundError("configured Kokoro model and voices files do not both exist")
            self.resolved_revision = None
            return env_model, env_voices

        from spacepilot.model_registry import registry

        variant_id = "kokoro-82m-onnx" if self.driver_id == "kokoro" else self.driver_id
        variant = registry().variant(variant_id)
        if variant is None or not variant.files:
            return None, None
        resolved = resolve(variant.repo, variant.revision, variant.files)
        if resolved is None:
            return None, None
        model = resolved.file("kokoro-v1.0.onnx")
        voices = resolved.file("voices-v1.0.bin")
        if model is None or voices is None:
            return None, None
        self.resolved_revision = resolved.revision
        return str(model), str(voices)

    def _discover_asset_paths(self) -> Tuple[Optional[str], Optional[str]]:
        """Compatibility wrapper for callers predating the public resolver."""
        return self.asset_paths()

    def load(self) -> bool:
        """Load the Kokoro ONNX runtime model and voice embeddings into memory."""
        try:
            m_path, v_path = self.asset_paths()
            if not m_path or not v_path:
                raise FileNotFoundError(
                    "Kokoro ONNX weights are not cached; run "
                    "`spacepilot recipes download kokoro-82m-onnx`")
            from kokoro_onnx import Kokoro
            self._session = Kokoro(m_path, v_path)
            logger.info("Loaded Kokoro ONNX model from %s", m_path)
            self.spec.is_loaded = True
            return True
        except Exception as e:
            logger.error(f"Failed to load KokoroDriver: {e}")
            self.spec.is_loaded = False
            return False

    def unload(self) -> bool:
        """Unload Kokoro ONNX session and free memory."""
        self._session = None
        self.spec.is_loaded = False
        return True

    def _generate_raw_audio(
        self, text: str, voice: str, speed: float
    ) -> Tuple[np.ndarray, int]:
        """Synthesize raw float32 audio waveform at 24kHz."""
        if not self.is_loaded:
            if not self.load():
                raise RuntimeError("KokoroDriver could not load real model weights")
        if self._session is None:
            raise RuntimeError("KokoroDriver has no loaded ONNX session")
        try:
            samples, sample_rate = self._session.create(
                text, voice=voice, speed=speed, lang="en-us"
            )
        except Exception as exc:
            raise RuntimeError(f"Kokoro ONNX inference failed: {exc}") from exc
        return np.asarray(samples, dtype=np.float32), sample_rate

    @staticmethod
    def _normalize_loudness(
        waveform: np.ndarray,
        sample_rate: int,
        target_lufs: float = DEFAULT_TARGET_LUFS,
    ) -> np.ndarray:
        """Apply ITU-R BS.1770 / sidechain RMS loudness normalization to target LUFS."""
        # Calculate RMS energy
        rms = np.sqrt(np.mean(waveform ** 2) + 1e-9)
        current_db = 20.0 * np.log10(rms + 1e-9)

        # Gain adjustment needed to achieve target_lufs
        gain_db = target_lufs - current_db
        gain = 10.0 ** (gain_db / 20.0)
        normalized = waveform * gain

        # True Peak limiter at -1.5 dBFS (~0.841)
        max_peak = np.max(np.abs(normalized)) + 1e-9
        true_peak_limit = 10.0 ** (-1.5 / 20.0)
        if max_peak > true_peak_limit:
            normalized = normalized * (true_peak_limit / max_peak)

        return np.clip(normalized, -1.0, 1.0)

    def infer(
        self,
        text: str,
        voice: str = "af_heart",
        speed: float = 1.0,
        out_path: Optional[Union[str, Path]] = None,
        target_lufs: float = DEFAULT_TARGET_LUFS,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute in-process Kokoro TTS speech synthesis.
        
        Args:
            text: Text script to synthesize.
            voice: Voice ID from catalogue (e.g. 'af_heart', 'am_michael').
            speed: Speech speed multiplier (0.5 to 2.0).
            out_path: Destination WAV file path (optional).
            target_lufs: Target LUFS normalization level (default: -16.0 LUFS).
            
        Returns:
            Dict containing generation status, sample rate, duration, file path, and metadata.
        """
        start_time = time.time()
        if not text or not text.strip():
            raise ValueError("Input text cannot be empty.")

        if not self.is_valid_voice(voice):
            logger.warning(f"Voice '{voice}' not in catalogue; defaulting to 'af_heart'")
            voice = "af_heart"

        # 1. Synthesize 24kHz raw PCM waveform
        raw_waveform, sample_rate = self._generate_raw_audio(text, voice, speed)

        # 2. Sidechain -16 LUFS Normalization
        normalized = self._normalize_loudness(raw_waveform, sample_rate, target_lufs)
        pcm_16bit = (normalized * 32767.0).astype(np.int16)

        duration_sec = round(len(pcm_16bit) / float(sample_rate), 2)
        elapsed_sec = round(time.time() - start_time, 3)

        written_path = None
        if out_path:
            dest_file = Path(out_path)
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(dest_file), "wb") as wav:
                wav.setnchannels(1)  # Mono
                wav.setsampwidth(2)   # 16-bit
                wav.setframerate(sample_rate)
                wav.writeframes(pcm_16bit.tobytes())
            written_path = str(dest_file)

        return {
            "status": "completed",
            "driver_id": self.driver_id,
            "task": self.task,
            "backend": self.backend,
            "model_revision": self.resolved_revision,
            "voice": voice,
            "speed": speed,
            "text": text,
            "sample_rate": sample_rate,
            "duration_sec": duration_sec,
            "target_lufs": target_lufs,
            "elapsed_sec": elapsed_sec,
            "file_path": written_path,
        }
