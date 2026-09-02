"""Video generation models and processing services."""

import os
import json
import time
import uuid
import shutil
import urllib.request
from pathlib import Path
from typing import Optional, List, Dict, Literal
from pydantic import BaseModel, Field, model_validator

from spacepilot.core.config import get_settings
from spacepilot.core.utils import run_ffmpeg, discard_partial, ffmpeg_error, write_meta
from spacepilot.cli import get_instance_info, load_config

ASSET_ID_PATTERN = r"^[A-Za-z0-9_-]+$"


class GenerateRequest(BaseModel):
    prompt: str = Field(max_length=4000)
    negative_prompt: Optional[str] = Field("worst quality, blurry, distorted, jittery", max_length=4000)
    seconds: float = Field(4.0, gt=0, le=600, allow_inf_nan=False)
    width: Optional[int] = Field(None, ge=64, le=4096)
    height: Optional[int] = Field(None, ge=64, le=4096)
    seed: Optional[int] = Field(None, ge=0, le=2**31 - 1)
    steps: Optional[int] = Field(None, ge=1, le=200)
    enhance: bool = False
    takes: int = Field(1, ge=1, le=16)
    stg_scale: Optional[float] = Field(None, ge=0.0, le=5.0)
    modality_scale: float = Field(1.0, ge=0.0, le=5.0)
    fps: int = Field(24, ge=1, le=60)
    image_path: Optional[str] = None
    last_image_path: Optional[str] = None
    draft_mode: bool = False
    camera_pan: Optional[Literal["left", "right"]] = None
    camera_tilt: Optional[Literal["up", "down"]] = None
    camera_zoom: Optional[Literal["in", "out"]] = None
    camera_roll: Optional[Literal["left", "right", "orbit"]] = None
    camera_intensity: Optional[int] = Field(None, ge=1, le=5)

    @model_validator(mode="after")
    def validate_dual_keyframe(self) -> "GenerateRequest":
        if self.last_image_path is not None and self.image_path is None:
            raise ValueError("last_image_path requires image_path to be present")
        return self


class ExtendRequest(BaseModel):
    asset_id: str
    prompt: str = Field(max_length=4000)
    negative_prompt: Optional[str] = Field("worst quality, blurry, distorted, jittery", max_length=4000)
    duration: float = Field(4.0, gt=0, le=600, allow_inf_nan=False)
    width: Optional[int] = Field(None, ge=64, le=4096)
    height: Optional[int] = Field(None, ge=64, le=4096)
    seed: Optional[int] = Field(None, ge=0, le=2**31 - 1)
    steps: Optional[int] = Field(None, ge=1, le=200)
    enhance: bool = False
    takes: int = Field(1, ge=1, le=16)
    stg_scale: Optional[float] = Field(None, ge=0.0, le=5.0)
    modality_scale: float = Field(1.0, ge=0.0, le=5.0)
    fps: int = Field(24, ge=1, le=60)
    draft_mode: bool = False
    camera_pan: Optional[Literal["left", "right"]] = None
    camera_tilt: Optional[Literal["up", "down"]] = None
    camera_zoom: Optional[Literal["in", "out"]] = None
    camera_roll: Optional[Literal["left", "right", "orbit"]] = None
    camera_intensity: Optional[int] = Field(None, ge=1, le=5)


class UpscaleRequest(BaseModel):
    asset_id: str = Field(pattern=ASSET_ID_PATTERN)
    scale: int = 4
    engine: str = "coreml"


class AutoScriptRequest(BaseModel):
    topic: str
    target_duration: Optional[int] = 60
    style: Optional[str] = "3blue1brown"


class CompositeMotionVectorRequest(BaseModel):
    asset_id: str = Field(pattern=ASSET_ID_PATTERN)
    overlay_type: str = "math_card"
    title: Optional[str] = None
    subtitle: Optional[str] = None
    latex_formula: Optional[str] = None
    speech_text: Optional[str] = None
    accent_color: Optional[str] = "#3b82f6"
    card_position: Optional[str] = "bottom_left"
    export_4k: bool = True
    export_prores: bool = False


def worker_headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Auth headers for the remote LTX worker; refuses to call it unauthenticated."""
    import spacepilot.web_api as web_api
    token = getattr(web_api, "WORKER_TOKEN", os.environ.get("LOCAL_WORKER_TOKEN", ""))
    if not token:
        raise RuntimeError("LOCAL_WORKER_TOKEN is not set; cannot talk to the GPU worker")
    headers = {"Authorization": f"Bearer {token}"}
    if extra:
        headers.update(extra)
    return headers
