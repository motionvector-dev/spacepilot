#!/usr/bin/env python3
"""LTX-2.5 Resident GPU Flask Worker

Holds the quantized LTX-2.5 model warm in VRAM on a single GPU (L40S / A100).
Serves HTTP requests for video generation with zero per-request cold start.

Endpoints:
  POST /generate          - Queue and run video generation (202 accepted or 409 busy)
  GET  /health            - 503 while warming up VRAM, 200 when resident
  GET  /status/<job_id>   - Check job progress and retrieve video path / URL
  GET  /download/<job_id> - Download completed MP4 video directly
  GET  /queue             - Current queue depth and VRAM stats
"""

import os
import re
import secrets
import sys
import time
import uuid
import threading
import gc
import tempfile
from pathlib import Path
from flask import Flask, request, jsonify, send_file

# Ensure HuggingFace cache and temp directories point to the 230GB NVMe scratch drive
if "HF_HOME" not in os.environ:
    os.environ["HF_HOME"] = "/scratch/hf"
if "TMPDIR" not in os.environ:
    os.environ["TMPDIR"] = "/scratch/tmp"

# Enforce expandable segments before torch is imported to prevent fragmentation OOM
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import torch
import torch.nn.functional as F
if not hasattr(F, "ScalingType") and hasattr(torch._C, "_ScalingType"):
    F.ScalingType = torch._C._ScalingType

from diffusers import LTX2Pipeline, LTX2ImageToVideoPipeline, PipelineQuantizationConfig
from diffusers import TorchAoConfig as DTAO
from transformers import TorchAoConfig as TTAO
from torchao.quantization import Float8DynamicActivationFloat8WeightConfig as F8
from diffusers.utils import export_to_video, load_image
from diffusers.utils.export_utils import encode_video

# Configuration
PORT = int(os.environ.get("LTX_WORKER_PORT", "5000"))
HOST = os.environ.get("LTX_WORKER_HOST", "0.0.0.0")
TOKEN = os.environ.get("LOCAL_WORKER_TOKEN", "")
OUTPUT_DIR = Path(os.environ.get("LTX_OUTPUT_DIR", "/scratch/out"))
HF_TOKEN = os.environ.get("HF_TOKEN", "")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB image upload limit
_lock = threading.Lock()
_active = 0
_model_ready = False
_pipe = None               # t2v pipeline (always loaded)
_pipe_i2v = None           # i2v pipeline (loaded lazily on first i2v request sharing resident weights)
_jobs = {}

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _authed():
    if not TOKEN:
        return False
    header = request.headers.get("Authorization", "")
    try:
        return secrets.compare_digest(header, f"Bearer {TOKEN}")
    except TypeError:
        # Headers decode as latin-1, and compare_digest rejects non-ASCII str.
        return False


def load_model():
    """Load and quantize LTX-2.5 into GPU VRAM (runs once at boot)."""
    global _pipe, _model_ready
    print("[ltx_worker] Starting VRAM warmup for LTX-2.5 (takes ~170s)...", flush=True)
    start_t = time.time()

    quant_config = PipelineQuantizationConfig(
        quant_mapping={
            "transformer": DTAO(F8()),
            "text_encoder": TTAO(F8()),
        }
    )

    _pipe = LTX2Pipeline.from_pretrained(
        "Lightricks/LTX-2.5-Diffusers",
        token=HF_TOKEN or True,
        torch_dtype=torch.bfloat16,
        quantization_config=quant_config,
    ).to("cuda")

    _pipe.vae.enable_tiling()
    _model_ready = True
    load_dur = time.time() - start_t
    print(f"[ltx_worker] LTX-2.5 t2v model is RESIDENT in VRAM (loaded in {load_dur:.1f}s)!", flush=True)


def load_i2v_model():
    """Lazily instantiate the LTX-2.5 image-to-video pipeline by sharing resident VRAM weights."""
    global _pipe_i2v, _pipe
    if _pipe_i2v is not None:
        return
    if _pipe is None:
        load_model()
    print("[ltx_worker] Instantiating LTX-2.5 i2v pipeline sharing resident VRAM weights...", flush=True)
    start_t = time.time()

    # Reuse the exact resident quantized transformer, text encoder, VAE, and vocoder
    _pipe_i2v = LTX2ImageToVideoPipeline(
        transformer=_pipe.transformer,
        text_encoder=_pipe.text_encoder,
        tokenizer=_pipe.tokenizer,
        vae=_pipe.vae,
        scheduler=_pipe.scheduler,
        vocoder=getattr(_pipe, "vocoder", None),
    )
    _pipe_i2v.vae.enable_tiling()
    load_dur = time.time() - start_t
    print(f"[ltx_worker] LTX-2.5 i2v pipeline READY in {load_dur:.2f}s (zero duplicate VRAM overhead)!", flush=True)


def _generate_thread(job_id, params):
    """Worker thread running inference for a single video job."""
    global _active, _jobs
    try:
        prompt = params.get("prompt", "")
        negative_prompt = params.get("negative_prompt", "worst quality, inconsistent motion, blurry, jittery, distorted")
        width = int(params.get("width", 1024))
        height = int(params.get("height", 576))
        seconds = float(params.get("seconds", 4.0))
        fps = int(params.get("fps", 24))
        seed = int(params.get("seed", int(time.time() * 1000) % 2147483647))
        steps = int(params.get("steps", 30))

        # Advanced Guidance & Multi-Modal Controls
        guidance_scale = float(params.get("guidance_scale", 1.0))
        audio_guidance_scale = float(params.get("audio_guidance_scale", 1.0))
        stg_scale = float(params.get("stg_scale", 0.0))
        audio_stg_scale = float(params.get("audio_stg_scale", 0.0))
        modality_scale = float(params.get("modality_scale", 1.0))
        audio_modality_scale = float(params.get("audio_modality_scale", 1.0))
        guidance_rescale = float(params.get("guidance_rescale", 0.0))
        audio_guidance_rescale = float(params.get("audio_guidance_rescale", 0.0))
        conditioning_scale = float(params.get("conditioning_scale", 1.0))
        image_noise_scale = float(params.get("image_noise_scale", 0.0))

        # Image-to-video: if an image path is provided, load it and use the i2v pipeline
        image_path = params.get("image_path", "")
        use_i2v = bool(image_path)

        # Enforce mechanical constraints
        # 1. num_frames % 8 == 1
        raw_frames = int(seconds * fps)
        num_frames = ((raw_frames - 1) // 8) * 8 + 1
        if num_frames < 9:
            num_frames = 9

        # 2. Dimensions divisible by 64
        width = (width // 64) * 64
        height = (height // 64) * 64

        out_file = OUTPUT_DIR / f"{job_id}.mp4"
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["num_frames"] = num_frames
        _jobs[job_id]["seed"] = seed
        _jobs[job_id]["resolution"] = f"{width}x{height}"
        _jobs[job_id]["fps"] = fps

        print(f"[ltx_worker] Executing {job_id}: '{prompt[:60]}...' ({width}x{height}, {num_frames}f @ {fps}fps, stg={stg_scale}, mod={modality_scale}, seed={seed})", flush=True)

        generator = torch.Generator("cuda").manual_seed(seed)

        # Load the image if doing i2v
        source_image = None
        if use_i2v:
            load_i2v_model()
            print(f"[ltx_worker] Loading source image from: {image_path}", flush=True)
            source_image = load_image(image_path)

        pipe_kwargs = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "num_frames": num_frames,
            "num_inference_steps": steps,
            "guidance_scale": guidance_scale,
            "audio_guidance_scale": audio_guidance_scale,
            "stg_scale": stg_scale,
            "audio_stg_scale": audio_stg_scale,
            "modality_scale": modality_scale,
            "audio_modality_scale": audio_modality_scale,
            "guidance_rescale": guidance_rescale,
            "audio_guidance_rescale": audio_guidance_rescale,
            "generator": generator,
            "output_type": "np",
            "return_dict": False,
        }
        if stg_scale > 0:
            pipe_kwargs["spatio_temporal_guidance_blocks"] = [28]

        with torch.inference_mode():
            if use_i2v:
                pipe_kwargs["image"] = source_image
                if hasattr(_pipe_i2v, "conditioning_scale"):
                    pipe_kwargs["conditioning_scale"] = conditioning_scale
                video, audio = _pipe_i2v(**pipe_kwargs)
            else:
                video, audio = _pipe(**pipe_kwargs)

            frames = video[0]
            audio_tensor = audio[0].float().cpu()
            audio_sr = _pipe.vocoder.config.output_sampling_rate if _pipe_i2v is None else _pipe_i2v.vocoder.config.output_sampling_rate
            encode_video(
                video=frames,
                fps=fps,
                output_path=str(out_file),
                audio=audio_tensor,
                audio_sample_rate=audio_sr,
            )

        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["output_path"] = str(out_file)
        _jobs[job_id]["download_url"] = f"/download/{job_id}"
        _jobs[job_id]["duration_sec"] = num_frames / float(fps)
        print(f"[ltx_worker] Completed {job_id} -> {out_file}", flush=True)

    except Exception as e:
        print(f"[ltx_worker] Error running {job_id}: {e}", file=sys.stderr, flush=True)
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)

    finally:
        # Crucial invariant: free intermediates immediately to prevent memory fragmentation
        gc.collect()
        torch.cuda.empty_cache()
        with _lock:
            _active -= 1


@app.get("/health")
def health():
    if not _model_ready:
        return jsonify(ok=False, status="warming_up", message="Model loading into VRAM (takes ~170s)"), 503
    vram_alloc = torch.cuda.memory_allocated() / (1024**3)
    vram_res = torch.cuda.memory_reserved() / (1024**3)
    return jsonify(
        ok=True,
        model_resident=True,
        active_jobs=_active,
        vram_allocated_gib=round(vram_alloc, 2),
        vram_reserved_gib=round(vram_res, 2),
    )


@app.get("/queue")
def queue():
    vram_free = (torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_reserved()) / (1024**3)
    return jsonify(
        depth=_active,
        model_resident=_model_ready,
        vram_free_gib=round(vram_free, 2),
        active_jobs=_active,
    )


@app.post("/generate")
def generate():
    if not _authed():
        return jsonify(error="unauthorized"), 401
    if not _model_ready:
        return jsonify(error="model_not_ready", message="Worker is still warming up model"), 503

    body = request.get_json(silent=True) or {}
    job_id = body.get("job_id") or f"ltx_{uuid.uuid4().hex[:12]}"
    # job_id becomes a filename below; without this it can escape OUTPUT_DIR.
    if not JOB_ID_RE.match(str(job_id)):
        return jsonify(error="invalid_job_id", message="job_id must match [A-Za-z0-9_-]{1,128}"), 400
    params = body.get("params") or body

    global _active, _jobs
    with _lock:
        if _active >= 1:
            return jsonify(status="busy", message="Worker concurrency capped to 1", active=_active), 409
        _active += 1

    _jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "created_at": time.time(),
        "params": params,
    }

    t = threading.Thread(target=_generate_thread, args=(job_id, params), daemon=True)
    t.start()

    return jsonify(
        status="accepted",
        job_id=job_id,
        message="Generation started in resident VRAM",
        eta_seconds=12,
    ), 202


@app.post("/upload")
def upload_image():
    """Upload an image to the worker for use in image-to-video generation.

    Accepts multipart/form-data with a 'file' field. Saves to /scratch/images/
    and returns the path. The path should then be passed as 'image_path' in the
    /generate request params.
    """
    if not _authed():
        return jsonify(error="unauthorized"), 401

    if "file" not in request.files:
        return jsonify(error="no_file", message="POST multipart with a 'file' field"), 400

    upload_dir = Path("/scratch/images")
    upload_dir.mkdir(parents=True, exist_ok=True)

    file = request.files["file"]
    # Sanitize the filename — alphanumeric + dot + dash only, no leading dots (prevent path traversal)
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "", file.filename or "upload.png")
    safe_name = safe_name.lstrip(".")  # prevent hidden files / traversal
    if not safe_name or safe_name.startswith("."):
        safe_name = f"upload_{uuid.uuid4().hex[:8]}.png"
    dest = upload_dir / safe_name
    # Resolve and verify containment (prevent path traversal via crafted names)
    if not dest.resolve().parent == upload_dir.resolve():
        return jsonify(error="invalid_filename", message="Filename must not escape upload directory"), 400
    file.save(str(dest))

    return jsonify(
        status="uploaded",
        path=str(dest),
        filename=safe_name,
        size_bytes=dest.stat().st_size,
    )


@app.get("/status/<job_id>")
def status(job_id):
    if not _authed():
        return jsonify(error="unauthorized"), 401
    if job_id not in _jobs:
        disk_file = OUTPUT_DIR / f"{job_id}.mp4"
        if disk_file.exists():
            return jsonify(job_id=job_id, status="completed", output_path=str(disk_file), download_url=f"/download/{job_id}")
        return jsonify(error="not_found"), 404
    return jsonify(_jobs[job_id])


@app.get("/download/<job_id>")
def download(job_id):
    if not _authed():
        return jsonify(error="unauthorized"), 401
    disk_file = OUTPUT_DIR / f"{job_id}.mp4"
    if not disk_file.exists():
        return jsonify(error="file_not_found"), 404
    return send_file(disk_file, mimetype="video/mp4", as_attachment=True, download_name=f"{job_id}.mp4")


if __name__ == "__main__":
    if not TOKEN:
        sys.exit("[ltx_worker] LOCAL_WORKER_TOKEN is not set; refusing to start an unauthenticated worker.")
    threading.Thread(target=load_model, daemon=True).start()
    print(f"[ltx_worker] Starting Flask server on {HOST}:{PORT}...", flush=True)
    app.run(host=HOST, port=PORT, threaded=True)
