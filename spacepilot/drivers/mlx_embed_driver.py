"""Pinned, offline, subprocess-only MLX embedding driver."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from spacepilot.drivers.base import DriverSpec, InferenceDriver


RESULT_PREFIX = "SPACEPILOT_RESULT "


class MlxEmbedSubprocessError(RuntimeError):
    """The isolated MLX embedding worker failed or returned unverifiable output."""


class MlxEmbedDriver(InferenceDriver):
    def __init__(
        self,
        driver_id: str = "mlx-embed",
        variant_id: str = "qwen3-embedding-0-6b-8bit",
        python_bin: Optional[str] = None,
    ) -> None:
        super().__init__(DriverSpec(
            driver_id=driver_id, task="embedding", backend="metal",
            resident_vram_gb=0.7, is_loaded=False,
        ))
        from spacepilot.runtimes import runtime_python
        self.variant_id = variant_id
        # Embeddings come out of the same mlx-lm runtime, so they follow it
        # into its isolated venv.
        self.python_bin = python_bin or runtime_python("mlx-lm")
        self.resolved_revision: Optional[str] = None

    def load(self) -> bool:
        """Nothing to warm: weights load inside the runner on every call."""
        ready, _ = self.runtime_ready()
        self.spec.is_loaded = ready
        return ready

    def unload(self) -> bool:
        self.spec.is_loaded = False
        return True

    def asset_dir(self, variant_id: Optional[str] = None) -> Optional[tuple[str, str]]:
        from spacepilot.paths import resolve
        from spacepilot.model_registry import registry

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
        inputs: List[str],
        out_path: str,
        max_tokens: int,
        variant_id: Optional[str] = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        variant_id = variant_id or self.variant_id
        resolved = self.asset_dir(variant_id)
        if resolved is None:
            raise MlxEmbedSubprocessError(
                f"weights are not cached; run `spacepilot recipes download {variant_id}`")
        snapshot, revision = resolved
        from spacepilot.drivers import mlx_embed_runner
        # By file path for the same reason as the text runner: mlx-lm's
        # isolated venv has mlx_lm in it and nothing of SpacePilot's own.
        cmd = [
            self.python_bin, mlx_embed_runner.__file__,
            "--model", snapshot, "--output", out_path,
            "--max-tokens", str(max_tokens),
        ]
        env = os.environ.copy()
        env["HF_HUB_OFFLINE"] = "1"
        env["TRANSFORMERS_OFFLINE"] = "1"
        try:
            proc = subprocess.run(
                cmd, input=json.dumps({"inputs": list(inputs)}),
                capture_output=True, text=True, timeout=timeout, env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise MlxEmbedSubprocessError(
                f"MLX embedding timed out after {timeout}s") from exc
        except OSError as exc:
            raise MlxEmbedSubprocessError(f"could not start MLX embedding: {exc}") from exc
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "")[-3000:]
            raise MlxEmbedSubprocessError(f"MLX embedding exited {proc.returncode}: {tail}")
        line = next(
            (line for line in reversed(proc.stdout.splitlines())
             if line.startswith(RESULT_PREFIX)), None,
        )
        if line is None:
            raise MlxEmbedSubprocessError("MLX embedding returned no structured result")
        try:
            result = json.loads(line[len(RESULT_PREFIX):])
        except json.JSONDecodeError as exc:
            raise MlxEmbedSubprocessError(
                "MLX embedding returned malformed result metadata") from exc
        result["model_revision"] = revision
        result["weights"] = Path(snapshot).name
        result["command"] = cmd
        return result
