try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    class FastMCP:
        def __init__(self, name):
            self.name = name
        def tool(self):
            return lambda f: f
        def resource(self, path):
            return lambda f: f
        def run(self):
            pass

from typing import Optional, Dict, Any, List

mcp = FastMCP("Pluto Studio")

@mcp.tool()
def pluto_generate_video(prompt: str, seconds: float = 4.0, camera_pan: str = None, camera_tilt: str = None, camera_zoom: str = None, camera_intensity: int = 3, draft_mode: bool = False) -> Dict[str, Any]:
    """Generate a video using Pluto.
    
    Args:
        prompt (str): The prompt describing the video to generate.
        seconds (float, optional): Length of the video in seconds. Defaults to 4.0.
        camera_pan (str, optional): Horizontal camera movement (e.g., "left", "right"). Defaults to None.
        camera_tilt (str, optional): Vertical camera movement (e.g., "up", "down"). Defaults to None.
        camera_zoom (str, optional): Zoom direction (e.g., "in", "out"). Defaults to None.
        camera_intensity (int, optional): The intensity of the camera movement, from 1 to 5. Defaults to 3.
        draft_mode (bool, optional): Whether to use draft mode ($0.012/gen) or cinema mode ($0.04/gen). Defaults to False.
        
    Returns:
        Dict[str, Any]: A dictionary containing the job_id and status.
    """
    return {"job_id": "vid-12345", "status": "processing"}

@mcp.tool()
def pluto_extend_video(asset_id: str, prompt: str, seconds: float = 4.0) -> Dict[str, Any]:
    """Extend an existing video.
    
    Args:
        asset_id (str): The ID of the video asset to extend.
        prompt (str): The prompt describing how to extend the video.
        seconds (float, optional): How many seconds to add to the video. Defaults to 4.0.
        
    Returns:
        Dict[str, Any]: A dictionary containing the new job_id and status.
    """
    return {"job_id": "vid-67890", "status": "processing"}

@mcp.tool()
def pluto_generate_audio(text: str, voice: str = "af_heart", speed: float = 1.0) -> Dict[str, Any]:
    """Generate audio using Kokoro TTS.
    
    Args:
        text (str): The text to synthesize into speech.
        voice (str, optional): The voice to use from the catalogue (e.g., "af_heart"). Defaults to "af_heart".
        speed (float, optional): The speech rate multiplier. Defaults to 1.0.
        
    Returns:
        Dict[str, Any]: A dictionary containing the job_id and status.
    """
    return {"job_id": "aud-12345", "status": "processing"}

@mcp.tool()
def pluto_generate_music(prompt: str, lyrics: str, duration_seconds: float = 30.0) -> Dict[str, Any]:
    """Generate music.
    
    Args:
        prompt (str): A description of the musical style.
        lyrics (str): The lyrics to sing.
        duration_seconds (float, optional): The duration of the generated track. Defaults to 30.0.
        
    Returns:
        Dict[str, Any]: A dictionary containing the job_id and status.
    """
    return {"job_id": "mus-12345", "status": "processing"}

@mcp.tool()
def pluto_get_render_status(job_id: str) -> Dict[str, Any]:
    """Get the status of a render job.
    
    Args:
        job_id (str): The unique ID of the render job.
        
    Returns:
        Dict[str, Any]: A dictionary containing the job_id and its current status.
    """
    return {"job_id": job_id, "status": "completed"}

@mcp.tool()
def pluto_get_fleet_status() -> Dict[str, Any]:
    """Get the status of the GPU fleet.
    
    Returns:
        Dict[str, Any]: Information about vram_usage, active instances, and health status.
    """
    return {"vram_usage": 0.5, "instances": 10, "status": "healthy"}

@mcp.tool()
def pluto_skypilot_arbitrage(sort_by: str = "spot_price") -> Dict[str, Any]:
    """Query real-time spot GPU prices and preemption rates across 12+ cloud providers via SkyPilot.
    
    Args:
        sort_by (str, optional): Metric to sort by ("spot_price", "preemption_rate", "vram"). Defaults to "spot_price".
        
    Returns:
        Dict[str, Any]: 12+ cloud arbitrage rankings and recommended spot instance.
    """
    try:
        from src.skypilot_orchestrator import sky_orchestrator
        return {
            "status": "ok",
            "arbitrage_matrix": sky_orchestrator.get_arbitrage_matrix(sort_by=sort_by),
            "best_option": sky_orchestrator.get_cheapest_cloud(),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def pluto_decompose_storyboard(script: str, scene_count: int = 6, target_duration_sec: float = 60.0, style: str = "cinematic") -> Dict[str, Any]:
    """Decompose a high-level narrative script into 6-8 cinematic storyboard scenes with 3D camera vectors.
    
    Args:
        script (str): The narrative story or high-level video prompt.
        scene_count (int, optional): Number of scenes (4-10). Defaults to 6.
        target_duration_sec (float, optional): Total duration in seconds. Defaults to 60.0.
        style (str, optional): Visual directing style. Defaults to "cinematic".
        
    Returns:
        Dict[str, Any]: Structured scenes with locked character seed and 3D camera trajectory tokens.
    """
    try:
        from src.storyboard_decomposer import decompose_storyboard
        return decompose_storyboard(
            script=script,
            target_duration_sec=target_duration_sec,
            scene_count=scene_count,
            style=style,
        )
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def pluto_probe_hardware() -> Dict[str, Any]:
    """Probe host hardware capabilities and VRAM headroom for local inference.
    
    Returns:
        Dict[str, Any]: Device telemetry including backend (MPS/CUDA/CPU), total VRAM, and usable headroom.
    """
    try:
        from src.device_probe import probe_local_device
        profile = probe_local_device()
        return {"status": "success", "profile": profile.to_dict()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def pluto_recommend_models() -> Dict[str, Any]:
    """Recommend task-based models (TTS, Storyboard, Video Diffusion) matched to host hardware.
    
    Returns:
        Dict[str, Any]: Recommended models with fit scores, quantization levels, and local cache status.
    """
    try:
        from src.model_recommender import recommend_models_for_device
        return {"status": "success", **recommend_models_for_device()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def pluto_download_model(model_id: str) -> Dict[str, Any]:
    """Download a model from the recommended catalog to the local cache.
    
    Args:
        model_id (str): The ID of the model to download (e.g. 'kokoro-82m-tts', 'qwen2.5-3b-instruct-gguf').
        
    Returns:
        Dict[str, Any]: Download status and destination path.
    """
    try:
        from src.model_recommender import download_model_mock
        return download_model_mock(model_id)
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def pluto_get_local_status() -> Dict[str, Any]:
    """Get live status of local inference workers and loaded models.
    
    Returns:
        Dict[str, Any]: Loaded model weights, current VRAM allocation, and worker availability.
    """
    try:
        from src.device_probe import probe_local_device
        from src.model_recommender import PLUTO_MODELS_CACHE
        profile = probe_local_device()
        downloaded = []
        if PLUTO_MODELS_CACHE.exists():
            downloaded = [f.name for f in PLUTO_MODELS_CACHE.iterdir() if f.is_file()]
        return {
            "status": "online",
            "backend": profile.backend,
            "vram_usable_gb": profile.vram_usable_gb,
            "loaded_models": downloaded,
            "is_local_capable": profile.is_local_capable,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.resource("pluto://models/ltx25")
def get_ltx25_model_info() -> str:
    """Get information about the LTX25 model.
    
    Returns:
        str: A markdown-formatted summary of the LTX25 model specifications.
    """
    return (
        "# LTX25 Model Specifications\n"
        "- **Format:** Float8\n"
        "- **VRAM Requirement:** 48GB\n"
        "- **Output Framerate:** 24fps\n"
        "- **Description:** Advanced spatio-temporal generative model for cinematic video creation.\n"
    )

@mcp.resource("pluto://voices/catalogue")
def get_voice_catalogue() -> str:
    """Get the Kokoro voice catalogue.
    
    Returns:
        str: A JSON-formatted string detailing the 10 available Kokoro voices.
    """
    import json
    voices = [
        {"id": "af_heart", "name": "Heart", "gender": "female"},
        {"id": "af_alloy", "name": "Alloy", "gender": "female"},
        {"id": "af_bella", "name": "Bella", "gender": "female"},
        {"id": "af_jessica", "name": "Jessica", "gender": "female"},
        {"id": "af_kore", "name": "Kore", "gender": "female"},
        {"id": "am_michael", "name": "Michael", "gender": "male"},
        {"id": "am_fenrir", "name": "Fenrir", "gender": "male"},
        {"id": "am_puck", "name": "Puck", "gender": "male"},
        {"id": "am_echo", "name": "Echo", "gender": "male"},
        {"id": "am_onyx", "name": "Onyx", "gender": "male"}
    ]
    return json.dumps(voices, indent=2)

if __name__ == "__main__":
    mcp.run()

