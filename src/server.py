import os
import time

# Enable MPS fallback to CPU for unsupported ops (must be set before torch import)
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

import sys
# Add current directory to path to ensure relative/local imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


import uuid
import base64
import re
import tempfile
import torch
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from transformers import AutoModelForCausalLM, AutoTokenizer
from diffusers import LTXPipeline, LTXImageToVideoPipeline
from diffusers.utils import export_to_video, load_image
from generate_video import adjust_dimension, adjust_frame_count

import asyncio
from fastapi.concurrency import run_in_threadpool

# ── Device Detection ──────────────────────────────────────────────
# Priority: DEVICE env var > CUDA > MPS > CPU
def detect_device() -> str:
    """Auto-detect the best available compute device."""
    override = os.environ.get("DEVICE", "").strip().lower()
    if override in ("cuda", "mps", "cpu"):
        return override
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"

DEVICE = detect_device()
SERVER_START_TIME = time.time()

app = FastAPI(title="LTX-Video Local API Bridge")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global lock to serialize heavy GPU inference
generation_lock = asyncio.Lock()

MOCK_VIDEO = os.environ.get("MOCK_VIDEO", "true").lower() == "true"

# Choose model size: "2b" (fast, ~4 GB) or "13b" (quality, ~39 GB)
LTX_MODEL = os.environ.get("LTX_MODEL", "2b").lower()

MODEL_REGISTRY = {
    "2b": "Lightricks/LTX-Video-0.9.7-distilled",
    "13b": "Lightricks/LTX-Video-0.9.8-13B-distilled",
}

txt2vid_pipe = None
img2vid_pipe = None

if not MOCK_VIDEO:
    ltx_model_id = MODEL_REGISTRY.get(LTX_MODEL)
    if not ltx_model_id:
        print(f"[Server] Unknown LTX_MODEL='{LTX_MODEL}'. Valid options: {list(MODEL_REGISTRY.keys())}")
        print("[Server] Falling back to MOCK mode.")
        MOCK_VIDEO = True
    else:
        print("\n===========================================")
        print(f"[Server] INITIALIZING LTX-Video ({LTX_MODEL.upper()}) on device: {DEVICE}")
        print("===========================================")
        try:
            print(f"[Server] Loading {ltx_model_id}...")
            dtype = torch.float16 if DEVICE == "cuda" else torch.bfloat16
            txt2vid_pipe = LTXPipeline.from_pretrained(ltx_model_id, torch_dtype=dtype)

            # For small models on devices with enough VRAM, load directly.
            # For large models or CPU-offload scenarios, use enable_model_cpu_offload.
            if LTX_MODEL == "2b" and DEVICE in ("cuda", "mps"):
                txt2vid_pipe.to(DEVICE)
            elif DEVICE in ("cuda", "mps"):
                txt2vid_pipe.enable_model_cpu_offload(device=DEVICE)
            # else: stays on CPU

            # Create the Image-to-Video pipeline sharing the exact same weights in memory
            img2vid_pipe = LTXImageToVideoPipeline(**txt2vid_pipe.components)
            if LTX_MODEL == "2b" and DEVICE in ("cuda", "mps"):
                img2vid_pipe.to(DEVICE)
            elif DEVICE in ("cuda", "mps"):
                img2vid_pipe.enable_model_cpu_offload(device=DEVICE)

            print("===========================================")
            print(f"[Server] {LTX_MODEL.upper()} MODEL LOADED on {DEVICE.upper()}! API IS READY.")
            print("===========================================\n")
        except Exception as e:
            print(f"[Server] Failed to load {LTX_MODEL.upper()} model: {e}")
            print("[Server] Falling back to MOCK mode.")
            MOCK_VIDEO = True

if MOCK_VIDEO:
    print("\n===========================================")
    print("[Server] RUNNING IN MOCK VIDEO MODE (Fast Startup)")
    print("===========================================\n")


@app.get("/health")
async def health_check():
    """Health check endpoint for frontend connectivity and status monitoring."""
    gpu_name = None
    if DEVICE == "cuda" and torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
    elif DEVICE == "mps":
        gpu_name = "Apple Silicon (MPS)"
    return {
        "status": "ok",
        "device": DEVICE,
        "gpu_name": gpu_name,
        "model": LTX_MODEL if not MOCK_VIDEO else None,
        "mock_mode": MOCK_VIDEO,
        "uptime_seconds": round(time.time() - SERVER_START_TIME, 1),
    }


class EnhanceRequest(BaseModel):
    prompt: str

class GenerateRequest(BaseModel):
    prompt: str
    image: Optional[str] = None
    width: int = 512
    height: int = 288
    num_frames: int = 49
    steps: int = 25

def process_image(image_str: str) -> str:
    if image_str.startswith("http://") or image_str.startswith("https://") or os.path.exists(image_str):
        return image_str
    if image_str.startswith("data:image"):
        image_str = re.sub('^data:image/.+;base64,', '', image_str)
    try:
        image_data = base64.b64decode(image_str)
        fd, temp_path = tempfile.mkstemp(suffix=".png")
        with os.fdopen(fd, 'wb') as f:
            f.write(image_data)
        return temp_path
    except Exception as e:
        raise ValueError(f"Invalid image format: {e}")

def cleanup_file(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print(f"Failed to clean up {path}: {e}")

@app.post("/enhance")
async def enhance_prompt_api(req: EnhanceRequest):
    try:
        import json
        import urllib.request
        import urllib.error
        
        prompt = req.prompt.strip()
        system_prompt = (
            "You are an expert AI video generation prompt engineer. "
            "Your job is to expand and enhance the user's short description into a highly detailed cinematic video prompt. "
            "Describe rich visual details, lighting, motion, camera angle, and atmosphere. "
            "Respond ONLY with the final enhanced prompt. Do NOT write any introduction, quotes, or explanation."
        )
        
        # Try local Ollama over SSH tunnel
        ollama_url = "http://localhost:11434/api/generate"
        data = {
            "model": "gemma3:4b",  # Using fast 4B model
            "prompt": f"{system_prompt}\n\nUser prompt: {prompt}\n\nEnhanced cinematic prompt:",
            "stream": False
        }
        
        try:
            req_data = json.dumps(data).encode("utf-8")
            url_req = urllib.request.Request(
                ollama_url,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(url_req, timeout=6.0) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                enhanced = resp_data.get("response", "").strip()
                if enhanced:
                    # Clean up quotes
                    enhanced = re.sub(r'^["\']|["\']$', '', enhanced).strip()
                    print(f"[Server] Successfully enhanced prompt using Lenovo Ollama (gemma3:4b)")
                    return {"enhanced_prompt": enhanced}
        except Exception as ollama_err:
            print(f"[Server] Ollama enhancement failed ({str(ollama_err)}), falling back to rule-based enhancement.")
            
        # Fallback Mock enhancement
        enhanced = prompt
        if not any(word in enhanced.lower() for word in ["cinematic", "photorealistic", "ultra"]):
            enhanced += ", cinematic, photorealistic, 8k resolution, highly detailed"
        return {"enhanced_prompt": enhanced}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate")
async def generate_video(req: GenerateRequest, background_tasks: BackgroundTasks):
    try:
        width = adjust_dimension(req.width, "width")
        height = adjust_dimension(req.height, "height")
        num_frames = adjust_frame_count(req.num_frames)
        
        temp_image_path = None
        source_image = None
        
        if req.image:
            temp_image_path = process_image(req.image)
            source_image = load_image(temp_image_path)
            
        # Generate random seed
        seed_device = "cpu"  # Seeds are always generated on CPU for reproducibility
        generator = torch.Generator(device=seed_device).manual_seed(torch.randint(0, 1000000, (1,)).item())
        
        output_filename = f"output_{uuid.uuid4().hex}.mp4"
        output_path = os.path.abspath(output_filename)
        
        if MOCK_VIDEO:
            # Simulate generation delay for realistic frontend loading feedback
            print(f"[Server] Generatively rendering mock video...")
            await asyncio.sleep(3.0)
            
            # Try multiple demo video URLs
            demo_urls = [
                "https://download.samplelib.com/mp4/sample-5s.mp4",
                "https://www.w3schools.com/html/mov_bbb.mp4",
            ]
            downloaded = False
            for url in demo_urls:
                try:
                    import urllib.request
                    print(f"[Server] Trying mock video from: {url}")
                    urllib.request.urlretrieve(url, output_path)
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                        downloaded = True
                        print(f"[Server] Successfully downloaded mock video.")
                        break
                except Exception as dl_err:
                    print(f"[Server] Download failed: {dl_err}")
            
            if not downloaded:
                # Generate a minimal valid MP4 using ffmpeg (available on macOS)
                print(f"[Server] Generating local test pattern MP4 via ffmpeg...")
                try:
                    import subprocess
                    subprocess.run([
                        "ffmpeg", "-y", "-f", "lavfi", "-i",
                        "color=c=purple:s=512x288:d=3",
                        "-vf", "drawtext=text='Katana Mock':fontsize=48:fontcolor=white:x=(w-tw)/2:y=(h-th)/2",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        output_path
                    ], capture_output=True, timeout=10)
                except Exception as ffmpeg_err:
                    print(f"[Server] ffmpeg fallback also failed: {ffmpeg_err}")
                    # Ultimate fallback: create a tiny but valid MP4 container
                    # ftyp box + mdat box only (browsers will show error but won't crash)
                    ftyp = b'\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41'
                    mdat = b'\x00\x00\x00\x08mdat'
                    with open(output_path, "wb") as f:
                        f.write(ftyp + mdat)
        else:
            # Serialize access to GPU and run in threadpool to prevent blocking the async loop
            async with generation_lock:
                def run_generation():
                    if source_image is not None:
                        return img2vid_pipe(
                            image=source_image,
                            prompt=req.prompt,
                            width=width,
                            height=height,
                            num_frames=num_frames,
                            num_inference_steps=req.steps,
                            guidance_scale=3.0,
                            generator=generator,
                        )
                    else:
                        return txt2vid_pipe(
                            prompt=req.prompt,
                            width=width,
                            height=height,
                            num_frames=num_frames,
                            num_inference_steps=req.steps,
                            guidance_scale=3.0,
                            generator=generator,
                        )
                
                output = await run_in_threadpool(run_generation)
                
            export_to_video(output.frames[0], output_path, fps=16)
            
        if temp_image_path and not req.image.startswith("http"):
            cleanup_file(temp_image_path)
            
        # Cleanup video file after returning it to Vue
        background_tasks.add_task(cleanup_file, output_path)
        
        return FileResponse(path=output_path, media_type="video/mp4", filename="generated_video.mp4")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
