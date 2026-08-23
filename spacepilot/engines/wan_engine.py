#!/usr/bin/env python3
"""Wan2.1 Video Engine Adapter for Pluto.

Implements the BaseVideoEngine interface for Wan2.1 (1.3B and 14B DiT).
Features 3D Causal VAE architecture with temporal compression factor 4x (4k + 1 frames)
and spatial compression factor 8x (multiples of 16), supporting Text-to-Video and Image-to-Video.
"""

from typing import Dict, Any, Optional, Tuple, Literal
from pathlib import Path
import time
import uuid

from spacepilot.engines.base import BaseVideoEngine, EngineSpec


class WanVideoEngine(BaseVideoEngine):
    """Adapter for Wan2.1 1.3B and 14B DiT video foundation models."""

    def __init__(
        self,
        model_size: Literal["1.3B", "14B", "1.3b", "14b"] = "14B",
        precision: str = "bf16",
        **kwargs,
    ):
        super().__init__(**kwargs)
        normalized_size = "1.3B" if "1.3" in str(model_size) else "14B"
        self.model_size = normalized_size
        self.precision = precision

        if self.model_size == "1.3B":
            self.spec = EngineSpec(
                engine_id="wan-2.1-1.3b",
                name="Wan2.1 1.3B",
                parameters="1.3B",
                min_vram_gb=8.0,
                supported_aspects=["16:9", "9:16", "1:1", "4:3"],
                supports_i2v=True,
                supports_extend=True,
                description="Wan2.1 1.3B lightweight 3D Causal VAE video diffusion model for edge and consumer GPUs.",
                default_resolution=(832, 480),
                fps_options=[16, 24],
                architecture="Wan DiT + 3D Causal VAE (4x Temporal, 8x Spatial)",
            )
        else:
            self.spec = EngineSpec(
                engine_id="wan-2.1-14b",
                name="Wan2.1 14B",
                parameters="14B",
                min_vram_gb=24.0,
                supported_aspects=["16:9", "9:16", "1:1", "4:3", "21:9"],
                supports_i2v=True,
                supports_extend=True,
                description="Wan2.1 14B high-fidelity cinematic 3D Causal VAE video foundation model.",
                default_resolution=(1280, 720),
                fps_options=[16, 24, 30],
                architecture="Wan DiT + 3D Causal VAE (4x Temporal, 8x Spatial)",
            )

    def get_spec(self) -> EngineSpec:
        return self.spec

    def adjust_dimensions(self, width: int, height: int) -> Tuple[int, int]:
        """Wan2.1 requires spatial dimensions to be multiples of 16 (8x VAE * 2x2 patch)."""
        adj_w = max(16, round(width / 16) * 16)
        adj_h = max(16, round(height / 16) * 16)
        return adj_w, adj_h

    def adjust_frame_count(self, num_frames: int, fps: int = 16) -> int:
        """Wan2.1 3D Causal VAE uses 4x temporal compression, requiring (4 * k + 1) frames."""
        if (num_frames - 1) % 4 == 0:
            return max(5, num_frames)
        k = max(1, round((num_frames - 1) / 4))
        return (4 * k) + 1

    def generate_video(
        self,
        prompt: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        seconds: float = 4.0,
        image_path: Optional[str] = None,
        seed: Optional[int] = None,
        steps: Optional[int] = None,
        guidance_scale: Optional[float] = None,
        fps: int = 16,
        draft_mode: bool = False,
        output_path: Optional[str] = None,
        mock: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        job_id = f"wan_{uuid.uuid4().hex[:10]}"
        default_res = self.spec.default_resolution
        raw_w = width if width is not None else (768 if draft_mode else default_res[0])
        raw_h = height if height is not None else (432 if draft_mode else default_res[1])
        w, h = self.adjust_dimensions(raw_w, raw_h)

        raw_frames = int(seconds * fps)
        num_frames = self.adjust_frame_count(raw_frames, fps=fps)

        inferred_steps = steps if steps is not None else (20 if draft_mode else 40)
        inferred_cfg = guidance_scale if guidance_scale is not None else 6.0
        inferred_seed = seed if seed is not None else int(time.time() * 1000) % 2147483647

        if output_path is None:
            output_dir = Path("/tmp/pluto_renders")
            output_dir.mkdir(parents=True, exist_ok=True)
            out_file = str(output_dir / f"{job_id}.mp4")
        else:
            out_file = output_path

        # Render mock video
        self._render_mock_video(
            output_path=out_file,
            width=w,
            height=h,
            seconds=seconds,
            fps=fps,
            image_path=image_path,
            engine_label=f"Wan2.1-{self.model_size}",
        )

        return {
            "job_id": job_id,
            "engine_id": self.spec.engine_id,
            "model_size": self.model_size,
            "status": "completed",
            "prompt": prompt,
            "image_path": image_path,
            "video_path": out_file,
            "width": w,
            "height": h,
            "seconds": seconds,
            "num_frames": num_frames,
            "fps": fps,
            "steps": inferred_steps,
            "guidance_scale": inferred_cfg,
            "seed": inferred_seed,
            "draft_mode": draft_mode,
            "is_i2v": bool(image_path),
            "metadata": {
                "engine": self.spec.name,
                "parameters": self.spec.parameters,
                "precision": self.precision,
                "temporal_compression": "4x",
                "spatial_compression": "8x",
                "frame_constraint": "4k+1",
            },
        }

    def extend_video(
        self,
        video_path: str,
        prompt: str,
        seconds: float = 4.0,
        output_path: Optional[str] = None,
        mock: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        job_id = f"wan_ext_{uuid.uuid4().hex[:10]}"
        if output_path is None:
            output_dir = Path("/tmp/pluto_renders")
            output_dir.mkdir(parents=True, exist_ok=True)
            out_file = str(output_dir / f"{job_id}.mp4")
        else:
            out_file = output_path

        self._render_mock_video(
            output_path=out_file,
            width=self.spec.default_resolution[0],
            height=self.spec.default_resolution[1],
            seconds=seconds,
            fps=16,
            engine_label=f"Wan2.1-{self.model_size}-Extend",
        )

        return {
            "job_id": job_id,
            "engine_id": self.spec.engine_id,
            "status": "completed",
            "base_video_path": video_path,
            "prompt": prompt,
            "extension_seconds": seconds,
            "video_path": out_file,
            "action": "extend_video",
            "metadata": {
                "engine": self.spec.name,
                "model_size": self.model_size,
                "extension_mode": "causal_vae_tail_conditioning",
            },
        }
