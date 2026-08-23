#!/usr/bin/env python3
"""Polymorphic Base Video Engine Architecture for Pluto.

Defines the EngineSpec dataclass and BaseVideoEngine abstract class
for multi-model DiT adapters (LTX-Video 2.5, Wan2.1 1.3B/14B, HunyuanVideo).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import subprocess
import uuid
import time
import os
import shutil


@dataclass
class EngineSpec:
    """Specification and capability metadata for a video generation engine."""
    engine_id: str
    name: str
    parameters: str
    min_vram_gb: float
    supported_aspects: List[str]
    supports_i2v: bool
    supports_extend: bool
    description: str = ""
    default_resolution: Tuple[int, int] = (768, 432)
    fps_options: List[int] = field(default_factory=lambda: [16, 24, 25, 30])
    architecture: str = "Diffusion Transformer (DiT)"

    def to_dict(self) -> Dict[str, Any]:
        """Convert engine specification to dictionary."""
        return asdict(self)


class BaseVideoEngine(ABC):
    """Abstract Base Class for Video Generation Engines."""

    def __init__(self, **kwargs):
        self.config = kwargs

    @abstractmethod
    def get_spec(self) -> EngineSpec:
        """Return the engine specifications and capabilities."""
        pass

    @abstractmethod
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
        """Generate a video clip from text prompt or image conditioning.

        Args:
            prompt: Text prompt describing the video.
            width: Output width in pixels (adjusted per engine constraints if needed).
            height: Output height in pixels.
            seconds: Duration in seconds.
            image_path: Optional source image for Image-to-Video.
            seed: Random generator seed.
            steps: Denoising inference steps.
            guidance_scale: Classifier-free guidance scale.
            fps: Frame rate.
            draft_mode: Fast draft mode flag.
            output_path: Output file path.
            mock: Run in mock mode producing test pattern.
            **kwargs: Extra engine-specific parameters.

        Returns:
            Dict[str, Any] containing job metadata, status, output video path.
        """
        pass

    @abstractmethod
    def extend_video(
        self,
        video_path: str,
        prompt: str,
        seconds: float = 4.0,
        output_path: Optional[str] = None,
        mock: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Extend an existing video sequentially.

        Args:
            video_path: Path to existing video file.
            prompt: Prompt describing continuation.
            seconds: Additional duration in seconds.
            output_path: Output file path.
            mock: Run in mock mode.
            **kwargs: Extra parameters.

        Returns:
            Dict[str, Any] containing status and output path.
        """
        pass

    def adjust_dimensions(self, width: int, height: int) -> Tuple[int, int]:
        """Adjust width and height to satisfy engine architectural constraints."""
        return width, height

    def adjust_frame_count(self, num_frames: int, fps: int = 24) -> int:
        """Adjust total frame count to satisfy temporal compression constraints."""
        return num_frames

    def is_available(self) -> bool:
        """Check whether local/remote dependencies or model weights are available."""
        return True

    def _render_mock_video(
        self,
        output_path: str,
        width: int,
        height: int,
        seconds: float,
        fps: int = 24,
        image_path: Optional[str] = None,
        engine_label: str = "DiT Engine",
    ) -> bool:
        """Helper to create a test video using ffmpeg or fallback dummy file."""
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        # Check if ffmpeg is available
        if shutil.which("ffmpeg"):
            try:
                if image_path and Path(image_path).exists():
                    cmd = [
                        "ffmpeg", "-y",
                        "-loop", "1", "-i", str(image_path),
                        "-t", str(seconds),
                        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
                        str(out_p)
                    ]
                else:
                    cmd = [
                        "ffmpeg", "-y",
                        "-f", "lavfi",
                        "-i", f"testsrc=duration={seconds}:size={width}x{height}:rate={fps}",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(out_p)
                    ]
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30)
                if res.returncode == 0 and out_p.exists() and out_p.stat().st_size > 0:
                    return True
            except Exception:
                pass

        # Fallback dummy write
        with open(out_p, "wb") as f:
            f.write(f"MOCK_VIDEO_DATA_{engine_label}_{width}x{height}_{seconds}s".encode())
        return True
