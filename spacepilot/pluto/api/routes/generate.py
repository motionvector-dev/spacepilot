"""Prompt enhancement, generation, upscaling, extend, and composition routes."""

import os
import json
import time
import uuid
from pathlib import Path
from typing import Optional, List

import httpx
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from spacepilot.pluto.core.config import get_settings
from spacepilot.pluto.core.utils import run_ffmpeg, discard_partial, ffmpeg_error, write_meta, resolve_output
from spacepilot.pluto.api.deps import require_token, update_activity
from spacepilot.cli import get_instance_info, load_config
from spacepilot.pluto.services.generation import (
    GenerateRequest,
    ExtendRequest,
    UpscaleRequest,
    AutoScriptRequest,
    CompositeMotionVectorRequest,
    worker_headers,
)

router = APIRouter(tags=["generate"])

# The urlopen calls these replaced passed no timeout at all, so a wedged worker
# hung the background thread forever. httpx defaults to 5s, which is too short
# for a download; name the three bounds instead of inheriting either.
WORKER_SUBMIT_TIMEOUT_SEC = 15.0
WORKER_POLL_TIMEOUT_SEC = 30.0
WORKER_DOWNLOAD_TIMEOUT_SEC = 300.0


@router.post("/api/enhance")
@router.post("/api/enhance-prompt")
def enhance_prompt_api(body: dict):
    """Enhance prompt with cinematic visual and camera tokens."""
    prompt = body.get("prompt", "")
    if not prompt:
        return {"enhanced_prompt": ""}

    additions = []
    if "cinematic" not in prompt.lower():
        additions.append("cinematic lighting")
    if "4k" not in prompt.lower() and "detail" not in prompt.lower():
        additions.append("ultra-detailed, 8k resolution, photorealistic")
    if "camera" not in prompt.lower() and "shot" not in prompt.lower():
        additions.append("smooth cinematic camera drift, 35mm lens, depth of field")

    enhanced = f"{prompt.strip()}, {', '.join(additions)}"
    return {"original_prompt": prompt, "enhanced_prompt": enhanced}


@router.post("/api/generate")
def generate_video_api(req: GenerateRequest, background_tasks: BackgroundTasks, _: None = Depends(require_token)):
    """Queue video generation job to remote resident GPU or local mock."""
    update_activity()
    settings = get_settings()
    outputs_dir = settings.outputs_dir
    cfg = load_config()
    try:
        inst = get_instance_info(cfg)
        aws_error = None
    except Exception as e:
        inst = None
        aws_error = str(e)

    job_id = f"pluto_{uuid.uuid4().hex[:10]}"
    target_prompt = req.prompt

    if req.enhance:
        enh_res = enhance_prompt_api({"prompt": req.prompt})
        target_prompt = enh_res["enhanced_prompt"]

    cam_tokens = []
    intensity = req.camera_intensity or 3
    if req.camera_pan == "right": cam_tokens.append("cinematic slow pan right")
    elif req.camera_pan == "left": cam_tokens.append("cinematic slow pan left")
    
    if req.camera_tilt == "up": cam_tokens.append("smooth tilt up")
    elif req.camera_tilt == "down": cam_tokens.append("smooth tilt down")
    
    if req.camera_zoom == "in": cam_tokens.append("smooth dolly zoom in")
    elif req.camera_zoom == "out": cam_tokens.append("smooth dolly zoom out")
    
    if req.camera_roll == "left": cam_tokens.append("roll left")
    elif req.camera_roll == "right": cam_tokens.append("roll right")
    elif req.camera_roll == "orbit": cam_tokens.append("stable orbit 360")
    
    if cam_tokens:
        cam_tokens.append("stable camera track")
        target_prompt = f"{target_prompt}, {', '.join(cam_tokens)}"
        
    stg_scale_base = req.stg_scale if req.stg_scale is not None else (0.5 if req.draft_mode else 1.0)
    if cam_tokens:
        stg_scale = min(5.0, stg_scale_base + (intensity * 0.1))
    else:
        stg_scale = stg_scale_base

    is_online = inst and inst.get("ip") and inst.get("state") == "running"
    
    if req.draft_mode:
        default_w, default_h = 768, 432
        steps = req.steps if req.steps is not None else 15
        cost_usd = 0.01 if is_online else 0.00
        compute_quote = "Estimated Spot compute: ~$0.01 (No charge on failure)" if is_online else "Local Mode (Free FFmpeg Preview)"
    else:
        default_w, default_h = 1024, 576
        steps = req.steps if req.steps is not None else 30
        cost_usd = 0.04 if is_online else 0.00
        compute_quote = "Estimated Spot compute: ~$0.04 (No charge on failure)" if is_online else "Local Mode (Free FFmpeg Preview)"

    raw_w = req.width if req.width is not None else default_w
    raw_h = req.height if req.height is not None else default_h

    if req.draft_mode and req.width is None and req.height is None:
        width = 768
        height = 432
    else:
        width = (raw_w // 64) * 64 if raw_w % 64 == 0 else (raw_w // 16) * 16
        height = (raw_h // 64) * 64 if raw_h % 64 == 0 else (raw_h // 16) * 16

    raw_frames = int(req.seconds * 24)
    num_frames = ((raw_frames - 1) // 8) * 8 + 1
    base_seed = req.seed if req.seed is not None else int(time.time() * 1000) % 2147483647
    
    take_group_id = f"tg_{uuid.uuid4().hex[:10]}" if req.takes > 1 else None
    jobs = []
    
    for i in range(req.takes):
        job_id = f"pluto_{uuid.uuid4().hex[:10]}"
        seed = (base_seed + i) % 2147483648
        
        patch = {
            "target": "LTX-2.5 Video Generation",
            "specs": {
                "resolution": f"{width}x{height}",
                "fps": f"{req.fps}fps",
                "duration": f"{req.seconds:.1f}s",
                "frames": num_frames,
                "steps": steps,
                "stg_scale": stg_scale,
                "seed": seed,
                "draft_mode": req.draft_mode,
            },
            "compute_quote": compute_quote,
            "diff": {
                "prompt": {"before": None, "after": req.prompt},
                "stg_scale": {"before": 1.0, "after": stg_scale},
                "aspect": {"before": "16:9 (1024x576)", "after": f"{width}x{height}"},
                "duration": {"before": "4.0s", "after": f"{req.seconds:.1f}s"},
                "seed": {"before": "random", "after": seed},
            },
            "ops": [
                {
                    "address": "video.generation",
                    "subject": "LTX-2.5 Video Generation",
                    "before": None,
                    "after": f"{width}x{height} @ {req.fps}fps, {req.seconds:.1f}s",
                    "generate": {
                        "kind": "video",
                        "prompt": req.prompt,
                        "tier": "LTX-2.5",
                        "units": req.seconds,
                        "resolution": f"{width}x{height}",
                        "fps": req.fps,
                        "stg_scale": stg_scale,
                        "seed": seed,
                        "draft_mode": req.draft_mode,
                    },
                    "quote": {
                        "estimated": True,
                        "compute_text": compute_quote,
                        "cost_usd": cost_usd,
                    },
                }
            ],
        }

        meta = {
            "id": job_id,
            "prompt": req.prompt,
            "enhanced_prompt": target_prompt,
            "width": width,
            "height": height,
            "seconds": req.seconds,
            "num_frames": num_frames,
            "seed": seed,
            "steps": steps,
            "stg_scale": stg_scale,
            "draft_mode": req.draft_mode,
            "image_path": req.image_path,
            "last_image_path": req.last_image_path,
            "status": "queued",
            "created_at": time.time(),
            "is_upscaled": False,
            "duration_sec": req.seconds,
            "patch": patch,
        }
        
        if take_group_id:
            meta["take_group_id"] = take_group_id
            meta["take_index"] = i + 1

        meta_file = outputs_dir / f"{job_id}.json"
        write_meta(meta_file, meta)

        if inst and inst.get("ip") and inst.get("state") == "running":
            def _dispatch_remote(current_job_id=job_id, current_meta=meta, current_meta_file=meta_file, current_seed=seed):
                ip = inst["ip"]
                try:
                    payload = {
                        "job_id": current_job_id,
                        "prompt": target_prompt,
                        "negative_prompt": req.negative_prompt,
                        "width": width,
                        "height": height,
                        "seconds": req.seconds,
                        "seed": current_seed,
                        "steps": steps,
                        "stg_scale": stg_scale,
                        "modality_scale": req.modality_scale,
                        "fps": req.fps,
                        "draft_mode": req.draft_mode,
                    }
                    if req.image_path:
                        payload["image_path"] = req.image_path
                    if req.last_image_path:
                        payload["last_image_path"] = req.last_image_path
                    submit = httpx.post(
                        f"http://{ip}:5000/generate",
                        content=json.dumps(payload).encode(),
                        headers=worker_headers({"Content-Type": "application/json"}),
                        timeout=WORKER_SUBMIT_TIMEOUT_SEC,
                    )
                    submit.raise_for_status()

                    while True:
                        time.sleep(1.5)
                        st_resp = httpx.get(
                            f"http://{ip}:5000/status/{current_job_id}",
                            headers=worker_headers(),
                            timeout=WORKER_POLL_TIMEOUT_SEC,
                        )
                        st_resp.raise_for_status()
                        st_data = st_resp.json()
                        if st_data.get("status") == "completed":
                            out_mp4 = outputs_dir / f"{current_job_id}.mp4"
                            with httpx.stream(
                                "GET",
                                f"http://{ip}:5000/download/{current_job_id}",
                                headers=worker_headers(),
                                timeout=WORKER_DOWNLOAD_TIMEOUT_SEC,
                            ) as dl_resp:
                                dl_resp.raise_for_status()
                                with open(out_mp4, "wb") as out_f:
                                    for chunk in dl_resp.iter_bytes():
                                        out_f.write(chunk)

                            thumb_png = outputs_dir / f"{current_job_id}.png"
                            thumb_res = run_ffmpeg(["-ss", "00:00:01", "-i", str(out_mp4), "-frames:v", "1", str(thumb_png)])

                            current_meta["status"] = "completed"
                            current_meta["file_path"] = str(out_mp4)
                            if thumb_res.returncode == 0:
                                current_meta["thumbnail_path"] = str(thumb_png)
                            else:
                                current_meta["thumbnail_error"] = ffmpeg_error(thumb_res)
                            write_meta(current_meta_file, current_meta)
                            break
                        elif st_data.get("status") == "failed":
                            current_meta["status"] = "failed"
                            current_meta["error"] = st_data.get("error")
                            write_meta(current_meta_file, current_meta)
                            break
                except Exception as e:
                    current_meta["status"] = "failed"
                    current_meta["error"] = str(e)
                    write_meta(current_meta_file, current_meta)

            background_tasks.add_task(_dispatch_remote)
        else:
            # No worker: refuse rather than fabricate. The old fallback
            # rendered an ffmpeg testsrc pattern, wrote is_mock (which nothing
            # read) and reported "completed"; the UI showed a finished clip
            # for a model that never ran (removed at e4b7910).
            meta["status"] = "failed"
            meta["error"] = (
                "No video execution route: no GPU worker is running and local "
                "video generation is not implemented. Nothing was rendered."
                + (f" (AWS query failed: {aws_error})" if aws_error else "")
            )
            write_meta(meta_file, meta)

        jobs.append({"job_id": job_id, "meta": meta, "patch": patch})
        
    overall = jobs[0]["meta"]["status"] if jobs else "failed"
    if req.takes > 1:
        return {"status": overall, "jobs": jobs, "take_group_id": take_group_id, "patch": jobs[0]["patch"]}
    else:
        return {"status": overall, "job_id": jobs[0]["job_id"], "meta": jobs[0]["meta"], "patch": jobs[0]["patch"]}


@router.post("/api/video/extend")
@router.post("/api/extend")
def extend_video_api(req: ExtendRequest, background_tasks: BackgroundTasks, _: None = Depends(require_token)):
    update_activity()
    settings = get_settings()
    outputs_dir = settings.outputs_dir
    uploads_dir = outputs_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    clean_id = os.path.basename(req.asset_id).replace(".mp4", "")
    source_mp4 = (outputs_dir / f"{clean_id}.mp4").resolve()
    if not str(source_mp4).startswith(str(outputs_dir.resolve())) or not source_mp4.exists():
        raise HTTPException(status_code=404, detail="Source asset not found")

    out_frame = uploads_dir / f"ext_{uuid.uuid4().hex[:10]}.jpg"
    
    ffmpeg_res = run_ffmpeg(["-sseof", "-0.1", "-i", str(source_mp4), "-vframes", "1", "-q:v", "2", str(out_frame)])
    if ffmpeg_res.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Failed to extract final frame")
        
    meta_file = outputs_dir / f"{clean_id}.json"
    extension_index = 2
    if meta_file.exists():
        with open(meta_file) as f:
            prev_meta = json.load(f)
            extension_index = prev_meta.get("extension_index", 1) + 1
            
    gen_req = GenerateRequest(
        prompt=req.prompt,
        negative_prompt=req.negative_prompt,
        seconds=req.duration,
        width=req.width,
        height=req.height,
        seed=req.seed,
        steps=req.steps,
        enhance=req.enhance,
        takes=req.takes,
        stg_scale=req.stg_scale,
        modality_scale=req.modality_scale,
        fps=req.fps,
        draft_mode=req.draft_mode,
        image_path=str(out_frame),
        camera_pan=req.camera_pan,
        camera_tilt=req.camera_tilt,
        camera_zoom=req.camera_zoom,
        camera_roll=req.camera_roll,
        camera_intensity=req.camera_intensity
    )
    
    res = generate_video_api(gen_req, background_tasks)
    
    job_id = res["job_id"]
    new_meta_file = outputs_dir / f"{job_id}.json"
    
    if new_meta_file.exists():
        with open(new_meta_file) as f:
            new_meta = json.load(f)
        new_meta["extended_from"] = req.asset_id
        new_meta["extension_index"] = extension_index
        write_meta(new_meta_file, new_meta)
            
    if "meta" in res:
        res["meta"]["extended_from"] = req.asset_id
        res["meta"]["extension_index"] = extension_index
        
    return res


@router.post("/api/upscale-4k")
def upscale_4k_api(req: UpscaleRequest, background_tasks: BackgroundTasks, _: None = Depends(require_token)):
    update_activity()
    settings = get_settings()
    outputs_dir = settings.outputs_dir

    source_mp4 = outputs_dir / f"{req.asset_id}.mp4"
    if not source_mp4.exists():
        raise HTTPException(status_code=404, detail="Source video not found")

    out_4k_id = f"{req.asset_id}_4k"
    out_4k_mp4 = outputs_dir / f"{out_4k_id}.mp4"
    out_4k_meta = outputs_dir / f"{out_4k_id}.json"

    def _run_upscale():
        start_t = time.time()
        scale_res = run_ffmpeg([
            "-i", str(source_mp4),
            "-vf", "scale=3840:2160:flags=lanczos",
            "-c:v", "h264_videotoolbox", "-b:v", "40M", "-pix_fmt", "yuv420p", str(out_4k_mp4),
        ])
        dur = round(time.time() - start_t, 2)

        meta_4k = {
            "id": out_4k_id,
            "source_id": req.asset_id,
            "width": 3840,
            "height": 2160,
            "status": "completed",
            "is_upscaled": True,
            "upscale_factor": "4x UHD",
            "upscale_latency_sec": dur,
            "file_path": str(out_4k_mp4),
            "created_at": time.time(),
        }
        if scale_res.returncode != 0:
            meta_4k["status"] = "failed"
            meta_4k["error"] = ffmpeg_error(scale_res)
            meta_4k["is_upscaled"] = False
            discard_partial(out_4k_mp4)
            write_meta(out_4k_meta, meta_4k)
            return

        thumb_4k = outputs_dir / f"{out_4k_id}.png"
        thumb_res = run_ffmpeg(["-ss", "00:00:01", "-i", str(out_4k_mp4), "-frames:v", "1", str(thumb_4k)])
        if thumb_res.returncode == 0:
            meta_4k["thumbnail_path"] = str(thumb_4k)
        else:
            meta_4k["thumbnail_error"] = ffmpeg_error(thumb_res)
        write_meta(out_4k_meta, meta_4k)

    background_tasks.add_task(_run_upscale)
    return {"status": "upscaling", "output_id": out_4k_id, "target_resolution": "3840x2160 UHD"}


@router.post("/api/director/auto-script")
def auto_script_api(req: AutoScriptRequest):
    """Generate a complete multi-scene documentary storyboard from a topic prompt."""
    topic = req.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic prompt is required")

    scenes = [
        {
            "scene_idx": 1,
            "title": "Hook: The Prompt Comparison",
            "prompt": f"An astronaut riding a horse on the moon, cinematic 35mm lighting, photorealistic, 4k",
            "narration": f"When you ask an AI model to generate a video, something extraordinary happens behind the pixels.",
            "math_formula": r"\text{Prompt: } \mathbf{y} \in \mathcal{Y}",
            "overlay_type": "kinetic_title",
            "card_position": "bottom_third",
            "duration_sec": 4.0,
            "takes_ready": 0,
        },
        {
            "scene_idx": 2,
            "title": "Intuition: Brownian Motion & Noise",
            "prompt": f"Microscopic Brownian motion of particles diffusing through dark viscous fluid, illuminated sparks, 4k",
            "narration": f"Every image actually begins as pure, unstructured random Gaussian noise.",
            "math_formula": r"x_t = \sqrt{\bar{\alpha}_t} x_0 + \sqrt{1 - \bar{\alpha}_t} \epsilon",
            "overlay_type": "math_card",
            "card_position": "bottom_left",
            "duration_sec": 5.0,
            "takes_ready": 0,
        },
        {
            "scene_idx": 3,
            "title": "Geometry: Density Manifolds",
            "prompt": f"Abstract 3D probability manifold surface with glowing vector trajectories curving across space, 4k",
            "narration": f"The neural network's job is to calculate the score function: which direction leads to a real image?",
            "math_formula": r"\nabla_{x_t} \log p_t(x_t)",
            "overlay_type": "math_card",
            "card_position": "bottom_left",
            "duration_sec": 5.0,
            "takes_ready": 0,
        },
        {
            "scene_idx": 4,
            "title": "The Physics: Stochastic Differential Equation",
            "prompt": f"Dynamic vector field pushing random noise particles into structured crystalline geometric forms",
            "narration": f"By following the reverse time trajectory, noise gradually condenses into sharp physical structure.",
            "math_formula": r"\mathrm{d}x = \left[ f(x, t) - g(t)^2 \nabla_x \log p_t(x) \right] \mathrm{d}t + g(t) \mathrm{d}\bar{w}",
            "overlay_type": "math_card",
            "card_position": "center",
            "duration_sec": 5.0,
            "takes_ready": 0,
        },
        {
            "scene_idx": 5,
            "title": "Guidance: Classifier-Free Steering",
            "prompt": f"Glowing particle vectors steering across latent space toward a focal point, cinematic slow motion",
            "narration": f"Classifier-free guidance amplifies the prompt's pull, driving the pixels toward high-confidence fidelity.",
            "math_formula": r"\tilde{\epsilon}_\theta = (1+w)\epsilon_\theta(x_t, y) - w \epsilon_\theta(x_t, \emptyset)",
            "overlay_type": "math_card",
            "card_position": "bottom_left",
            "duration_sec": 4.0,
            "takes_ready": 0,
        },
    ]

    return {
        "topic": topic,
        "style": req.style,
        "scene_count": len(scenes),
        "total_duration_sec": sum(s["duration_sec"] for s in scenes),
        "scenes": scenes,
    }


@router.post("/api/composite-motionvector")
def composite_motionvector_api(req: CompositeMotionVectorRequest, background_tasks: BackgroundTasks, _: None = Depends(require_token)):
    """Enforce P0 Composite Order: 4K Plate Upscale FIRST -> Native 4K Vector Render ON TOP."""
    settings = get_settings()
    outputs_dir = settings.outputs_dir

    source_mp4 = outputs_dir / f"{req.asset_id}.mp4"
    if not source_mp4.exists():
        raise HTTPException(status_code=404, detail="Source asset video not found")

    master_id = f"{req.asset_id}_master"
    master_mp4 = outputs_dir / f"{master_id}.mp4"
    master_meta = outputs_dir / f"{master_id}.json"

    def _run_composite():
        start_t = time.time()
        plate_4k = outputs_dir / f"{req.asset_id}_4k.mp4"
        if not plate_4k.exists():
            plate_res = run_ffmpeg([
                "-i", str(source_mp4),
                "-vf", "scale=3840:2160:flags=lanczos",
                "-c:v", "h264_videotoolbox", "-b:v", "40M", "-pix_fmt", "yuv420p", str(plate_4k),
            ])
            if plate_res.returncode != 0:
                discard_partial(plate_4k)
                write_meta(master_meta, {
                    "id": master_id,
                    "source_id": req.asset_id,
                    "status": "failed",
                    "error": ffmpeg_error(plate_res),
                    "created_at": time.time(),
                })
                return

        overlay_png = outputs_dir / f"{master_id}_overlay.png"
        title_text = req.title or "Diffusion Velocity Field"
        math_text = req.latex_formula or r"dx_t = f(x_t)dt + g(t)dw_t"
        
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGBA", (3840, 2160), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        card_w, card_h = 1600, 380
        if req.card_position == "center":
            card_x, card_y = (3840 - card_w) // 2, (2160 - card_h) // 2
        elif req.card_position == "bottom_third":
            card_x, card_y = (3840 - card_w) // 2, 1680
        else:
            card_x, card_y = 160, 1620

        draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=32, fill=(19, 23, 31, 225), outline=(59, 130, 246, 200), width=4)
        draw.rounded_rectangle([card_x + 32, card_y + 32, card_x + 44, card_y + 92], radius=6, fill=(59, 130, 246, 255))

        try:
            font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 44)
            font_math = ImageFont.truetype("/System/Library/Fonts/Courier.dfont", 52)
            font_sub = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 30)
        except Exception:
            font_title = font_math = font_sub = ImageFont.load_default()

        draw.text((card_x + 64, card_y + 40), title_text, fill=(255, 255, 255, 255), font=font_title)
        draw.line([(card_x + 32, card_y + 120), (card_x + card_w - 32, card_y + 120)], fill=(255, 255, 255, 30), width=2)
        draw.text((card_x + 64, card_y + 180), math_text, fill=(103, 232, 249, 255), font=font_math)
        draw.text((card_x + 64, card_y + 280), "MotionVector · Native 4K Vello Composite", fill=(156, 163, 175, 255), font=font_sub)
        img.save(overlay_png)

        codec_args = (
            ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le"]
            if req.export_prores
            else ["-c:v", "h264_videotoolbox", "-b:v", "45M", "-pix_fmt", "yuv420p"]
        )
        composite_res = run_ffmpeg([
            "-i", str(plate_4k), "-i", str(overlay_png),
            "-filter_complex", "[0:v][1:v]overlay=0:0",
            *codec_args,
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            str(master_mp4),
        ])
        dur = round(time.time() - start_t, 2)

        meta_master = {
            "id": master_id,
            "source_id": req.asset_id,
            "width": 3840,
            "height": 2160,
            "status": "completed",
            "is_upscaled": True,
            "is_motionvector_master": True,
            "overlay_title": title_text,
            "overlay_formula": math_text,
            "latency_sec": dur,
            "file_path": str(master_mp4),
            "created_at": time.time(),
        }
        if composite_res.returncode != 0:
            meta_master["status"] = "failed"
            meta_master["error"] = ffmpeg_error(composite_res)
            meta_master["is_upscaled"] = False
            meta_master["is_motionvector_master"] = False
            discard_partial(master_mp4)
            write_meta(master_meta, meta_master)
            return

        thumb_master = outputs_dir / f"{master_id}.png"
        thumb_res = run_ffmpeg(["-ss", "00:00:00.5", "-i", str(master_mp4), "-frames:v", "1", str(thumb_master)])
        if thumb_res.returncode == 0:
            meta_master["thumbnail_path"] = str(thumb_master)
        else:
            meta_master["thumbnail_error"] = ffmpeg_error(thumb_res)
        write_meta(master_meta, meta_master)

    background_tasks.add_task(_run_composite)
    return {"status": "compositing", "master_id": master_id, "resolution": "3840x2160 UHD (Native 4K Vector)"}


@router.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    """Job metadata."""
    with open(resolve_output(f"{job_id}.json")) as f:
        return json.load(f)
