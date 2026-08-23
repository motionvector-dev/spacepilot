"""Storyboard and narrative decomposition routes."""

from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException

from spacepilot.pluto.api.deps import require_token, update_activity
from spacepilot.storyboard_decomposer import decompose_storyboard

router = APIRouter(tags=["storyboard"])


class StoryboardDecomposeRequest(BaseModel):
    script: str
    target_duration_sec: float = Field(default=60.0, ge=10.0, le=300.0)
    scene_count: int = Field(default=6, ge=4, le=10)
    style: str = "cinematic"
    model: str = "gemini-3.7-flash"
    character_seed: Optional[int] = None


class LocalNarrativeDecomposeRequest(BaseModel):
    script: str
    target_duration_sec: float = Field(default=60.0, ge=10.0, le=300.0)
    scene_count: int = Field(default=6, ge=4, le=10)
    style: str = "cinematic"
    character_seed: Optional[int] = None


@router.post("/api/storyboard/decompose")
def post_storyboard_decompose_api(req: StoryboardDecomposeRequest, _: None = Depends(require_token)):
    """Deconstructs narrative into 6-8 cinematic storyboard scenes with 3D camera trajectory vectors."""
    script_text = req.script.strip()
    if not script_text:
        raise HTTPException(status_code=400, detail="Script or prompt text is required")
    
    update_activity()
    result = decompose_storyboard(
        script=script_text,
        target_duration_sec=req.target_duration_sec,
        scene_count=req.scene_count,
        style=req.style,
        model=req.model,
        character_seed=req.character_seed,
    )
    return result


@router.post("/api/narrative/decompose-local")
def decompose_local_narrative_api(req: LocalNarrativeDecomposeRequest, _: None = Depends(require_token)):
    """In-process GGUF narrative decomposition driver for screenplay and cinematic scene beats."""
    script_text = req.script.strip()
    if not script_text:
        raise HTTPException(status_code=400, detail="Script text cannot be empty")

    update_activity()
    try:
        from spacepilot.local_workers import local_worker_manager
        result = local_worker_manager.dispatch(
            "storyboard",
            script=script_text,
            scene_count=req.scene_count,
            target_duration_sec=req.target_duration_sec,
            style=req.style,
            character_seed=req.character_seed,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Local narrative decomposition failed: {str(e)}")
