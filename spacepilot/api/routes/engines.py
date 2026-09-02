"""Multi-model video DiT engines API routes."""

from typing import Optional, Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException

from spacepilot.api.deps import require_token, update_activity

router = APIRouter(tags=["engines"])


class MultiEngineGenerateRequest(BaseModel):
    prompt: str = Field(max_length=4000)
    engine_id: str = Field("ltx-2.5", max_length=100)
    negative_prompt: Optional[str] = Field("worst quality, blurry, distorted, jittery", max_length=4000)
    seconds: float = Field(4.0, gt=0, le=600, allow_inf_nan=False)
    width: Optional[int] = Field(None, ge=64, le=4096)
    height: Optional[int] = Field(None, ge=64, le=4096)
    aspect_ratio: Optional[str] = Field("16:9", max_length=32)
    seed: Optional[int] = Field(None, ge=0, le=2**31 - 1)
    steps: Optional[int] = Field(None, ge=1, le=200)
    enhance: bool = False
    draft_mode: bool = False
    fps: int = Field(24, ge=1, le=60)
    image_path: Optional[str] = None
    camera_pan: Optional[Literal["left", "right"]] = None
    camera_tilt: Optional[Literal["up", "down"]] = None
    camera_zoom: Optional[Literal["in", "out"]] = None
    camera_roll: Optional[Literal["left", "right", "orbit"]] = None
    camera_intensity: Optional[int] = Field(None, ge=1, le=5)


@router.get("/api/engines")
def list_engines_api():
    """List video engine SPECS. None of them can run inference."""
    from spacepilot.engines import list_video_engines
    return {
        "status": "ok",
        "implemented": False,
        "note": (
            "These are paper specs. No engine here runs a model; generation "
            "refuses with 501 until a real inference path exists."
        ),
        "engines": [spec.to_dict() for spec in list_video_engines()],
    }


@router.post("/api/generate/multi-engine")
def generate_multi_engine_api(
    req: MultiEngineGenerateRequest,
    _: None = Depends(require_token),
):
    """Refuses. The three "DiT engines" behind this route never ran a model.

    The previous body queued a job whose engine rendered an ffmpeg testsrc
    colour-bar pattern (or, without ffmpeg, a text file named .mp4) and wrote
    `status: "completed"` with invented inference parameters — the same
    fabrication the seven MCP tools were deleted for in PRs #67/#68. The full
    implementation is in git history at e4b7910. `require_token` stays so
    re-enabling a body cannot silently re-open the gate.
    """
    update_activity()
    raise HTTPException(
        status_code=501,
        detail=(
            "Video generation through the multi-engine route is not "
            "implemented. The engines behind it rendered test patterns and "
            "reported success; they now refuse. Nothing was queued."
        ),
    )
