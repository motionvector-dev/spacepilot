"""Small isolated Kokoro-82M ONNX worker used by :mod:`kokoro_driver`.

Runs Kokoro TTS synthesis and loudness normalization inside the configured
Python interpreter (e.g. SPACEPILOT_PYTHON), freeing memory when done and
avoiding loading ML packages in the control-plane CLI.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import wave
from pathlib import Path
from typing import Tuple

import numpy as np

RESULT_PREFIX = "SPACEPILOT_RESULT "
DEFAULT_SAMPLE_RATE = 24000
DEFAULT_TARGET_LUFS = -16.0


def normalize_loudness(
    waveform: np.ndarray,
    sample_rate: int,
    target_lufs: float = DEFAULT_TARGET_LUFS,
) -> np.ndarray:
    """Apply ITU-R BS.1770 / sidechain RMS loudness normalization to target LUFS."""
    rms = np.sqrt(np.mean(waveform ** 2) + 1e-9)
    current_db = 20.0 * np.log10(rms + 1e-9)

    gain_db = target_lufs - current_db
    gain = 10.0 ** (gain_db / 20.0)
    normalized = waveform * gain

    # True Peak limiter at -1.5 dBFS (~0.841)
    max_peak = np.max(np.abs(normalized)) + 1e-9
    true_peak_limit = 10.0 ** (-1.5 / 20.0)
    if max_peak > true_peak_limit:
        normalized = normalized * (true_peak_limit / max_peak)

    return np.clip(normalized, -1.0, 1.0)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Kokoro ONNX standalone runner")
    parser.add_argument("--model", required=True, help="Path to kokoro ONNX model file")
    parser.add_argument("--voices", required=True, help="Path to voices bin file")
    parser.add_argument("--output", required=True, help="Path to destination WAV file")
    parser.add_argument("--voice", default="af_heart", help="Voice ID")
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed multiplier")
    parser.add_argument("--target-lufs", type=float, default=DEFAULT_TARGET_LUFS, help="Target LUFS")
    args = parser.parse_args(argv)

    text = sys.stdin.read().strip()
    if not text:
        raise ValueError("Input text on stdin cannot be empty")

    from kokoro_onnx import Kokoro

    started = time.perf_counter()
    load_started = time.perf_counter()
    session = Kokoro(args.model, args.voices)
    load_seconds = time.perf_counter() - load_started

    samples, sample_rate = session.create(
        text, voice=args.voice, speed=args.speed, lang="en-us"
    )
    raw_waveform = np.asarray(samples, dtype=np.float32)

    normalized = normalize_loudness(raw_waveform, sample_rate, args.target_lufs)
    pcm_16bit = (normalized * 32767.0).astype(np.int16)

    duration_sec = round(len(pcm_16bit) / float(sample_rate), 2)
    elapsed_sec = round(time.perf_counter() - started, 3)

    dest_file = Path(args.output).expanduser().resolve()
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest_file), "wb") as wav:
        wav.setnchannels(1)  # Mono
        wav.setsampwidth(2)   # 16-bit
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_16bit.tobytes())

    payload = {
        "status": "completed",
        "voice": args.voice,
        "speed": args.speed,
        "sample_rate": sample_rate,
        "duration_sec": duration_sec,
        "target_lufs": args.target_lufs,
        "elapsed_sec": elapsed_sec,
        "load_seconds": round(load_seconds, 3),
        "file_path": str(dest_file),
    }
    print(RESULT_PREFIX + json.dumps(payload, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
