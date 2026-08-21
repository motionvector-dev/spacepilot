"""Multi-model video DiT engines API routes."""

import time
import uuid
from typing import Optional, Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from src.pluto.core.config import get_settings
from src.pluto.core.utils import write_meta
from src.pluto.api.deps import require_token, update_activity

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
    """List supported video diffusion engines and capabilities."""
    from src.engines import list_video_engines
    return {
        "status": "ok",
        "engines": [spec.to_dict() for spec in list_video_engines()]
    }


@router.post("/api/generate/multi-engine")
def generate_multi_engine_api(
    req: MultiEngineGenerateRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(require_token),
):
    """Queue polymorphic video generation job across LTX-2.5, Wan2.1, or HunyuanVideo."""
    update_activity()
    settings = get_settings()
    from src.engines import get_video_engine

    engine = get_video_engine(req.engine_id)
    spec = engine.get_spec()

    clean_engine_id = spec.engine_id.replace(".", "_").replace("-", "_")
    job_id = f"pluto_{clean_engine_id}_{uuid.uuid4().hex[:8]}"
    target_prompt = req.prompt

    if req.width is not None and req.height is not None:
        raw_w, raw_h = req.width, req.height
    else:
        if req.aspect_ratio == "9:16":
            raw_w, raw_h = (432, 768) if req.draft_mode else (720, 1280)
        elif req.aspect_ratio == "1:1":
            raw_w, raw_h = (512, 512) if req.draft_mode else (768, 768)
        elif req.aspect_ratio == "4:3":
            raw_w, raw_h = (640, 480) if req.draft_mode else (960, 720)
        else:  # 16:9
            raw_w, raw_h = (768, 432) if req.draft_mode else spec.default_resolution

    width, height = engine.adjust_dimensions(raw_w, raw_h)
    raw_frames = int(req.seconds * req.fps)
    num_frames = engine.adjust_frame_count(raw_frames, fps=req.fps)

    seed = req.seed if req.seed is not None else int(time.time() * 1000) % 2147483647
    steps = req.steps if req.steps is not None else (15 if req.draft_mode else 30)

    out_mp4 = settings.outputs_dir / f"{job_id}.mp4"
    thumb_png = settings.outputs_dir / f"{job_id}.png"
    meta_file = settings.outputs_dir / f"{job_id}.json"

    patch = {
        "target": f"{spec.name} Video Generation",
        "specs": {
            "engine": spec.engine_id,
            "resolution": f"{width}x{height}",
            "fps": f"{req.fps}fps",
            "duration": f"{req.seconds:.1f}s",
            "frames": num_frames,
            "steps": steps,
            "seed": seed,
            "draft_mode": req.draft_mode,
        },
        "diff": {
            "prompt": {"before": None, "after": req.prompt},
            "engine": {"before": "ltx-2.5", "after": spec.engine_id},
            "aspect": {"before": "16:9", "after": f"{width}x{height}"},
            "duration": {"before": "4.0s", "after": f"{req.seconds:.1f}s"},
        },
    }

    meta = {
        "id": job_id,
        "kind": "video",
        "engine": spec.engine_id,
        "engine_name": spec.name,
        "prompt": target_prompt,
        "original_prompt": req.prompt,
        "negative_prompt": req.negative_prompt,
        "seconds": req.seconds,
        "width": width,
        "height": height,
        "fps": req.fps,
        "frames": num_frames,
        "seed": seed,
        "steps": steps,
        "draft_mode": req.draft_mode,
        "status": "queued",
        "created_at": time.time(),
        "patch": patch,
    }

    def _run_render():
        meta["status"] = "running"
        write_meta(meta_file, meta)
        try:
            res = engine.generate_video(
                prompt=target_prompt,
                negative_prompt=req.negative_prompt,
                width=width,
                height=height,
                seconds=req.seconds,
                fps=req.fps,
                seed=seed,
                steps=steps,
                output_path=out_mp4,
                thumbnail_path=thumb_png,
                image_path=req.image_path,
            )
            meta["status"] = "completed"
            meta["file_path"] = str(out_mp4)
            meta["video_url"] = f"/api/media/{job_id}.mp4"
            meta["thumbnail_url"] = f"/api/media/{job_id}.png"
            meta["render_time_sec"] = res.get("render_time_sec", 1.0)
            write_meta(meta_file, meta)
        except Exception as e:
            meta["status"] = "failed"
            meta["error"] = str(e)
            write_meta(meta_file, meta)

    background_tasks.add_task(_run_render)
    write_meta(meta_file, meta)
    return {"status": "queued", "job_id": job_id, "meta": meta, "patch": patch}
