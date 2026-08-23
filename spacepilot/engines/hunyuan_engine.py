#!/usr/bin/env python3
"""HunyuanVideo Engine Adapter for Pluto.

Implements the BaseVideoEngine interface for Tencent HunyuanVideo (13B Dual-Stream DiT).
Features separate visual and text streams that interact via cross-attention,
producing 720p / 1080p cinematic video with high semantic alignment.
"""

from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import time
import uuid

from spacepilot.engines.base import BaseVideoEngine, EngineSpec


class HunyuanVideoEngine(BaseVideoEngine):
    """Adapter for Tencent HunyuanVideo 13B Dual-Stream DiT."""

    def __init__(
        self,
        precision: str = "bf16",
        resolution: str = "720p",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.precision = precision
        self.resolution = resolution
        default_res = (1280, 720) if resolution == "720p" else (1920, 1080)

        self.spec = EngineSpec(
            engine_id="hunyuan-video",
            name="HunyuanVideo",
            parameters="13B dual-stream DiT",
            min_vram_gb=32.0,
            supported_aspects=["16:9", "9:16", "4:3", "1:1", "21:9"],
            supports_i2v=True,
            supports_extend=True,
            description="Tencent HunyuanVideo 13B dual-stream DiT high-fidelity 720p cinematic foundation model.",
            default_resolution=default_res,
            fps_options=[24, 30],
            architecture="Dual-Stream Diffusion Transformer (DiT)",
        )

    def get_spec(self) -> EngineSpec:
        return self.spec

    def adjust_dimensions(self, width: int, height: int) -> Tuple[int, int]:
        """HunyuanVideo requires spatial dimensions to be multiples of 16."""
        adj_w = max(16, round(width / 16) * 16)
        adj_h = max(16, round(height / 16) * 16)
        return adj_w, adj_h

    def adjust_frame_count(self, num_frames: int, fps: int = 24) -> int:
        """HunyuanVideo requires (4 * k + 1) frames."""
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
        fps: int = 24,
        draft_mode: bool = False,
        output_path: Optional[str] = None,
        mock: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        job_id = f"hunyuan_{uuid.uuid4().hex[:10]}"
        default_res = self.spec.default_resolution
        raw_w = width if width is not None else (960 if draft_mode else default_res[0])
        raw_h = height if height is not None else (544 if draft_mode else default_res[1])
        w, h = self.adjust_dimensions(raw_w, raw_h)

        raw_frames = int(seconds * fps)
        num_frames = self.adjust_frame_count(raw_frames, fps=fps)

        inferred_steps = steps if steps is not None else (25 if draft_mode else 50)
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
            engine_label="HunyuanVideo-720p",
        )

        return {
            "job_id": job_id,
            "engine_id": self.spec.engine_id,
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
                "stream_architecture": "dual-stream (text+visual)",
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
        job_id = f"hunyuan_ext_{uuid.uuid4().hex[:10]}"
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
            fps=24,
            engine_label="HunyuanVideo-Extend",
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
                "extension_mode": "dual_stream_latent_concatenation",
            },
        }
