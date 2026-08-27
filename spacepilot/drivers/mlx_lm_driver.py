"""Pinned, offline, subprocess-only MLX-LM text driver."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from spacepilot.drivers.base import DriverSpec, InferenceDriver


RESULT_PREFIX = "SPACEPILOT_RESULT "


class MlxLmSubprocessError(RuntimeError):
    """The isolated MLX-LM worker failed or returned unverifiable output."""


class MlxLmDriver(InferenceDriver):
    def __init__(
        self,
        driver_id: str = "mlx-lm",
        variant_id: str = "qwen3-8-27b-4bit",
        python_bin: Optional[str] = None,
    ) -> None:
        super().__init__(DriverSpec(
            driver_id=driver_id, task="text", backend="metal",
            resident_vram_gb=18.0, is_loaded=False,
        ))
        from spacepilot.pluto.runtimes import interpreter
        self.variant_id = variant_id
        self.python_bin = python_bin or interpreter()
        self.resolved_revision: Optional[str] = None

    def load(self) -> bool:
        """No persistent session to warm — mlx-lm loads weights inside the
        runner subprocess on every `infer()` call. This only records readiness."""
        ready, _ = self.runtime_ready()
        self.spec.is_loaded = ready
        return ready

    def unload(self) -> bool:
        self.spec.is_loaded = False
        return True

    def asset_dir(self, variant_id: Optional[str] = None) -> Optional[tuple[str, str]]:
        from spacepilot.paths import resolve
        from spacepilot.pluto.registry import registry

        variant_id = variant_id or self.variant_id
        variant = registry().variant(variant_id)
        if variant is None or not variant.files or not variant.revision:
            return None
        resolved = resolve(variant.repo, variant.revision, variant.files)
        if resolved is None:
            return None
        self.resolved_revision = resolved.revision
        return str(resolved.snapshot), resolved.revision

    def runtime_ready(self) -> tuple[bool, str]:
        try:
            proc = subprocess.run(
                [self.python_bin, "-c", "import mlx_lm"],
                capture_output=True, text=True, timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, f"mlx-lm import check failed: {exc}"
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "import failed").strip().splitlines()[-1]
            return False, f"mlx-lm is unavailable in {self.python_bin}: {detail}"
        return True, f"mlx-lm importable in {self.python_bin}"

    def route_status(self, variant_id: Optional[str] = None) -> tuple[bool, str]:
        variant_id = variant_id or self.variant_id
        ready, detail = self.runtime_ready()
        if not ready:
            return False, f"no route — {detail}"
        resolved = self.asset_dir(variant_id)
        if resolved is None:
            return False, (
                f"no route — weights are not cached; run `spacepilot recipes "
                f"download {variant_id}`")
        snapshot, revision = resolved
        return True, f"ready — {Path(snapshot).name} at {revision[:12]} via mlx-lm"

    def infer(
        self,
        prompt: str,
        out_path: str,
        max_tokens: int,
        max_kv_size: int,
        temperature: float,
        variant_id: Optional[str] = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        variant_id = variant_id or self.variant_id
        resolved = self.asset_dir(variant_id)
        if resolved is None:
            raise MlxLmSubprocessError(
                f"weights are not cached; run `spacepilot recipes download {variant_id}`")
        snapshot, revision = resolved
        cmd = [
            self.python_bin, "-m", "spacepilot.drivers.mlx_lm_runner",
            "--model", snapshot, "--output", out_path,
            "--max-tokens", str(max_tokens), "--max-kv-size", str(max_kv_size),
            "--temperature", str(temperature),
        ]
        env = os.environ.copy()
        env["HF_HUB_OFFLINE"] = "1"
        env["TRANSFORMERS_OFFLINE"] = "1"
        try:
            proc = subprocess.run(
                cmd, input=prompt, capture_output=True, text=True,
                timeout=timeout, env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise MlxLmSubprocessError(
                f"MLX-LM timed out after {timeout}s") from exc
        except OSError as exc:
            raise MlxLmSubprocessError(f"could not start MLX-LM: {exc}") from exc
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "")[-3000:]
            raise MlxLmSubprocessError(
                f"MLX-LM exited {proc.returncode}: {tail}")
        line = next(
            (line for line in reversed(proc.stdout.splitlines())
             if line.startswith(RESULT_PREFIX)), None,
        )
        if line is None:
            raise MlxLmSubprocessError("MLX-LM returned no structured result")
        try:
            result = json.loads(line[len(RESULT_PREFIX):])
        except json.JSONDecodeError as exc:
            raise MlxLmSubprocessError("MLX-LM returned malformed result metadata") from exc
        result["model_revision"] = revision
        result["weights"] = Path(snapshot).name
        result["command"] = cmd
        return result
