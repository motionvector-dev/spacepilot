#!/usr/bin/env python3
"""mflux subprocess driver for local FLUX image generation on Apple Silicon.

mflux (registry/runtimes/mflux.yaml) lives in its own conda environment,
`~/miniconda3/envs/mflux`, deliberately separate from the interpreter this
repo runs under — installing mflux into the repo env downgrades
opencv-python from 5.0 to 4.14. So this driver never imports mflux; it always
shells out to the mflux CLI as a subprocess, the same way the GPU worker
shells out to ffmpeg.

mflux ships a different CLI entry point per model family (`mflux-generate`
for the classic FLUX.1 line, `mflux-generate-flux2` for FLUX.2 Klein,
`mflux-generate-qwen` for Qwen-Image, `mflux-generate-z-image` for Z-Image),
not one binary with a --model flag that covers everything. _COMMAND_FOR_ALIAS
below is the map from model alias to CLI entry point, built by reading
`mflux-generate --help` / `mflux-generate-flux2 --help` output (mflux 0.19.0)
rather than guessed.
"""

import logging
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from spacepilot.drivers.base import DriverSpec, InferenceDriver

logger = logging.getLogger("pluto.drivers.mflux")

# Which mflux CLI entry point serves a given --model alias. Verified against
# `mflux-capabilities` and each command's --help in mflux 0.19.0; a
# family not listed here falls back to plain mflux-generate, which is right
# for schnell/dev/krea and wrong for anything mflux has split out (flux2-klein
# errors "not supported by mflux-generate. Use mflux-generate-flux2 instead" —
# confirmed by running it).
_COMMAND_FOR_ALIAS = {
    "flux2-klein-4b": "mflux-generate-flux2",
    "flux2-klein-9b": "mflux-generate-flux2",
    "flux2-klein-9b-kv": "mflux-generate-flux2",
    "flux2-klein-base-4b": "mflux-generate-flux2",
    "flux2-klein-base-9b": "mflux-generate-flux2",
    "qwen-image": "mflux-generate-qwen",
    "qwen-image-edit": "mflux-generate-qwen-edit",
    "z-image": "mflux-generate-z-image",
    "z-image-turbo": "mflux-generate-z-image-turbo",
}
_DEFAULT_COMMAND = "mflux-generate"

# One line of an mflux/tqdm progress bar during the denoising loop, e.g.
#   "100%|##########| 4/4 [00:12<00:00,  3.05s/it]"
# The first line matching this is the load/generate boundary: mflux downloads,
# loads and quantizes weights before the loop starts, then this bar runs once
# per sampling step. Nothing in mflux's own output names "load" or "generate"
# directly, so this is inferred from the progress bar's appearance, not
# reported by mflux itself — see the docstring on MfluxDriver.infer.
_STEP_PROGRESS_RE = re.compile(r"^\s*\d{1,3}%\|.*\|\s*\d+/\d+\s*\[")


class MfluxSubprocessError(RuntimeError):
    """mflux exited non-zero, or its output could not be timed. Never swallowed."""


def _default_bin_dir() -> str:
    return str(Path.home() / "miniconda3" / "envs" / "mflux" / "bin")


def mflux_bin_dir(cfg: Optional[Dict[str, Any]] = None) -> str:
    """Where the mflux CLI entry points live. Configurable because the path is
    this-machine-specific: env var wins, then .pluto_config.json, then the
    conda env layout this Mac actually uses."""
    from spacepilot.paths import env_value
    return (
        env_value("SPACEPILOT_MFLUX_BIN", "PLUTO_MFLUX_BIN")
        or (cfg or {}).get("mflux_bin_dir")
        or _default_bin_dir()
    )


def command_for_alias(alias: str) -> str:
    """The mflux CLI entry point that serves a --model alias."""
    return _COMMAND_FOR_ALIAS.get(alias, _DEFAULT_COMMAND)


class MfluxDriver(InferenceDriver):
    """Subprocess driver for mflux image generation.

    mflux is never imported in-process (see module docstring); every call to
    `infer` shells out to the right mflux-generate* entry point and waits for
    it to exit. `load()`/`unload()` are no-ops that only flip `is_loaded` —
    there is no resident session to hold, because a fresh subprocess loads its
    own weights on every invocation. That load cost is exactly what
    `infer()`'s `load_seconds` measures.
    """

    def __init__(
        self,
        driver_id: str = "mflux-metal",
        bin_dir: Optional[str] = None,
        resident_vram_gb: float = 0.0,
    ) -> None:
        spec = DriverSpec(
            driver_id=driver_id,
            task="image",
            backend="metal",
            resident_vram_gb=resident_vram_gb,
            is_loaded=False,
            requires_accelerator=True,
        )
        super().__init__(spec)
        self.bin_dir = bin_dir or mflux_bin_dir()

    def load(self) -> bool:
        """No persistent session to warm — mflux loads weights fresh inside its
        own subprocess on every `infer()` call. This only records readiness."""
        exe = Path(self.bin_dir) / _DEFAULT_COMMAND
        self.spec.is_loaded = exe.is_file()
        return self.spec.is_loaded

    def unload(self) -> bool:
        self.spec.is_loaded = False
        return True

    def _resolve_executable(self, model: str) -> str:
        exe = Path(self.bin_dir) / command_for_alias(model)
        if not exe.is_file():
            raise MfluxSubprocessError(
                f"mflux executable not found: {exe}. Set PLUTO_MFLUX_BIN or "
                f"\"mflux_bin_dir\" in .pluto_config.json to the bin/ directory "
                f"of the mflux conda env."
            )
        return str(exe)

    def infer(
        self,
        prompt: str,
        model: str = "schnell",
        quantize: Optional[int] = None,
        steps: Optional[int] = None,
        seed: Optional[int] = None,
        height: int = 512,
        width: int = 512,
        out_path: Optional[str] = None,
        extra_args: Optional[List[str]] = None,
        timeout: Optional[float] = None,
        env: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Run one real mflux generation and report load and generate time
        as separate numbers.

        **How the split is obtained, and how reliable it is** (this is the
        whole point of this driver — see the task this shipped for): mflux
        does not report a load/generate split in any machine-readable form.
        What it does print, to stderr, is a tqdm progress bar once per
        denoising step once the model is loaded and sampling has begun. This
        method starts a subprocess, reads its combined output line by line,
        and takes the wall-clock timestamp of the *first* line matching
        `_STEP_PROGRESS_RE` as the load/generate boundary:

            load_seconds     = first_progress_line_at - process_start
            generate_seconds = process_exit_at - first_progress_line_at

        This folds HF download time (if the weights were not already cached),
        weight quantization, and MLX graph construction into `load_seconds`,
        and folds the denoising loop plus VAE decode into `generate_seconds`.
        It is a real measurement of wall-clock phases, not a guess — but it
        is inferred from mflux's incidental progress-bar output, not a
        boundary mflux declares on purpose, so a future mflux release that
        changes its progress bar format could silently widen `load_seconds`
        to include part of the generation. If no progress line is ever seen,
        this method does NOT guess a split: `generate_seconds` comes back
        `None` and `timing_source` says so, rather than reporting a made-up
        number.

        Raises MfluxSubprocessError on a non-zero exit or a timeout. A failed
        run is never reported as "completed" — this repo has a documented
        history of swallowing subprocess failures (ffmpeg stderr sent to
        /dev/null while `"completed"` was returned anyway) and this driver
        does not repeat it.
        """
        if not prompt or not prompt.strip():
            raise ValueError("prompt cannot be empty")

        exe = self._resolve_executable(model)
        cmd: List[str] = [
            exe, "--model", model,
            "--height", str(height), "--width", str(width),
            "--prompt", prompt,
        ]
        if quantize is not None:
            cmd += ["--quantize", str(quantize)]
        if steps is not None:
            cmd += ["--steps", str(steps)]
        if seed is not None:
            cmd += ["--seed", str(seed)]
        if out_path:
            cmd += ["--output", str(out_path)]
        if extra_args is not None:
            # A caller passing "--low-ram" instead of ["--low-ram"] would silently
            # explode into one argv token per character via list(str) — reject it
            # outright, the same rule spacepilot.cli.run_cmd applies to the whole command.
            if isinstance(extra_args, str):
                raise TypeError("extra_args takes a list of argv tokens, not a string")
            cmd += list(extra_args)

        if not isinstance(cmd, list):  # belt and suspenders; run_cmd's own rule
            raise TypeError("mflux command must be an argv list, never a string")

        run_env = {**os.environ, **(env or {})}

        start = time.perf_counter()
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, env=run_env,
        )

        # `for line in proc.stdout` blocks on each read, so a plain
        # `proc.wait(timeout=...)` after the loop would never fire the
        # timeout if mflux hangs mid-generation without closing its pipe —
        # the loop itself would block forever first. A watchdog timer kills
        # the process (which closes its stdout, unblocking the read loop
        # with EOF) regardless of where the hang is.
        timed_out = threading.Event()
        watchdog: Optional[threading.Timer] = None
        if timeout:
            def _on_timeout():
                timed_out.set()
                proc.kill()
            watchdog = threading.Timer(timeout, _on_timeout)
            watchdog.start()

        first_progress_at: Optional[float] = None
        lines: List[str] = []
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                lines.append(line)
                if first_progress_at is None and _STEP_PROGRESS_RE.match(line):
                    first_progress_at = time.perf_counter()
            returncode = proc.wait()
        finally:
            if watchdog is not None:
                watchdog.cancel()
        end = time.perf_counter()

        if timed_out.is_set():
            raise MfluxSubprocessError(f"mflux timed out after {timeout}s: {' '.join(cmd)}")

        if returncode != 0:
            tail = "".join(lines[-40:])
            raise MfluxSubprocessError(
                f"mflux exited {returncode}: {' '.join(cmd)}\n{tail}"
            )

        wall_seconds = end - start
        if first_progress_at is not None:
            load_seconds = first_progress_at - start
            generate_seconds = end - first_progress_at
            timing_source = "first-progress-line"
        else:
            # We cannot see a step boundary at all — do not fabricate one.
            load_seconds = None
            generate_seconds = None
            timing_source = "no-progress-line-observed"

        return {
            "status": "completed",
            "driver_id": self.driver_id,
            "task": self.task,
            "backend": self.backend,
            "model": model,
            "quantize": quantize,
            "steps": steps,
            "seed": seed,
            "height": height,
            "width": width,
            "wall_seconds": round(wall_seconds, 3),
            "load_seconds": round(load_seconds, 3) if load_seconds is not None else None,
            "generate_seconds": round(generate_seconds, 3) if generate_seconds is not None else None,
            "timing_source": timing_source,
            "out_path": out_path,
            "command": cmd,
        }
