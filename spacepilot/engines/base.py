#!/usr/bin/env python3
"""Polymorphic Base Video Engine Architecture for SpacePilot.

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

from spacepilot.core.utils import allocate_output


def default_render_path(job_id: str) -> str:
    """Where a render lands when the caller names no output file."""
    return str(allocate_output(f"{job_id}.mp4", subdir="renders"))


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
        """Refuses. This helper was the whole engine.

        Every engine's generate_video/extend_video called this unconditionally
        (the mock= argument was never branched on), rendered an ffmpeg testsrc
        pattern — or, without ffmpeg, wrote a text file with an .mp4 name — and
        reported status "completed" with invented inference parameters. Same
        failure class as the seven MCP tools deleted in PRs #67/#68. It raises
        until a real inference path exists.
        """
        raise NotImplementedError(
            f"{engine_label}: video inference is not implemented. This engine "
            "never ran a model; it rendered an ffmpeg test pattern and "
            "reported success. It now refuses instead."
        )
