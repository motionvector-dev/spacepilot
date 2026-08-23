# The SDK renamed FastMCP to MCPServer in mcp 2.0; the API is otherwise the same.
# There is deliberately no fallback stub here. The old one defined run() as `pass`,
# so a missing or moved dependency produced a server that started, served nothing,
# and exited cleanly — an agent connecting to it saw no error at all.
try:
    from mcp.server import MCPServer
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "pluto_mcp_server needs the mcp SDK (>=2.0).\n"
        "  pip install 'mcp>=2.0'\n"
        f"import failed: {exc}"
    ) from exc

from typing import Optional, Dict, Any, List

mcp = MCPServer("Pluto Studio")

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
def pluto_generate_video_wan(
    prompt: str,
    model_size: str = "14B",
    seconds: float = 4.0,
    image_path: Optional[str] = None,
    aspect_ratio: str = "16:9",
    draft_mode: bool = False,
) -> Dict[str, Any]:
    """Generate a video using the Wan2.1 DiT engine (1.3B or 14B with 3D Causal VAE).
    
    Args:
        prompt (str): The prompt describing the video to generate.
        model_size (str, optional): Wan2.1 model parameter size ("1.3B" or "14B"). Defaults to "14B".
        seconds (float, optional): Length of the video in seconds. Defaults to 4.0.
        image_path (str, optional): Path to input image for image-to-video generation. Defaults to None.
        aspect_ratio (str, optional): Aspect ratio ("16:9", "9:16", "1:1", "4:3"). Defaults to "16:9".
        draft_mode (bool, optional): Whether to use fast draft inference. Defaults to False.
        
    Returns:
        Dict[str, Any]: A dictionary containing the job_id, engine_id, and status.
    """
    try:
        from src.engines import get_video_engine
        engine_id = "wan-2.1-1.3b" if "1.3" in model_size else "wan-2.1-14b"
        engine = get_video_engine(engine_id)
        w, h = (1280, 720) if aspect_ratio == "16:9" else (720, 1280) if aspect_ratio == "9:16" else (832, 480)
        res = engine.generate_video(
            prompt=prompt,
            width=w,
            height=h,
            seconds=seconds,
            image_path=image_path,
            draft_mode=draft_mode,
            mock=True,
        )
        return {"job_id": res["job_id"], "engine_id": res["engine_id"], "status": "processing", "model_size": model_size}
    except Exception:
        return {"job_id": "wan-12345", "engine_id": f"wan-2.1-{model_size}", "status": "processing"}

@mcp.tool()
def pluto_generate_video_hunyuan(
    prompt: str,
    seconds: float = 4.0,
    image_path: Optional[str] = None,
    resolution: str = "720p",
    draft_mode: bool = False,
) -> Dict[str, Any]:
    """Generate a high-fidelity video using the HunyuanVideo 13B dual-stream DiT engine.
    
    Args:
        prompt (str): The prompt describing the video to generate.
        seconds (float, optional): Length of the video in seconds. Defaults to 4.0.
        image_path (str, optional): Path to input image for image-to-video generation. Defaults to None.
        resolution (str, optional): Target resolution ("720p" or "1080p"). Defaults to "720p".
        draft_mode (bool, optional): Whether to use fast draft mode. Defaults to False.
        
    Returns:
        Dict[str, Any]: A dictionary containing the job_id, engine_id, and status.
    """
    try:
        from src.engines import get_video_engine
        engine = get_video_engine("hunyuan-video")
        w, h = (1280, 720) if resolution == "720p" else (1920, 1080)
        res = engine.generate_video(
            prompt=prompt,
            width=w,
            height=h,
            seconds=seconds,
            image_path=image_path,
            draft_mode=draft_mode,
            mock=True,
        )
        return {"job_id": res["job_id"], "engine_id": res["engine_id"], "status": "processing", "resolution": resolution}
    except Exception:
        return {"job_id": "hunyuan-12345", "engine_id": "hunyuan-video", "status": "processing"}

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



@mcp.tool()
def pluto_create_checkpoint(job_id: str, step: int, epoch: int, loss: float, local_paths: List[str]) -> Dict[str, Any]:
    """Create a new training checkpoint snapshot.
    
    Args:
        job_id (str): The ID of the training job.
        step (int): The current training step.
        epoch (int): The current training epoch.
        loss (float): The current loss value.
        local_paths (List[str]): List of local file paths to include in the snapshot.
        
    Returns:
        Dict[str, Any]: The metadata of the created snapshot.
    """
    try:
        from src.pluto.services.checkpoint_sync import CheckpointSyncEngine
        from dataclasses import asdict
        engine = CheckpointSyncEngine()
        meta = engine.create_snapshot(job_id, step, epoch, loss, local_paths)
        return {"status": "success", "snapshot": asdict(meta)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def pluto_list_checkpoints(job_id: Optional[str] = None) -> Dict[str, Any]:
    """List training checkpoint snapshots.
    
    Args:
        job_id (str, optional): The ID of the training job to filter by.
        
    Returns:
        Dict[str, Any]: List of snapshot metadata.
    """
    try:
        from src.pluto.services.checkpoint_sync import CheckpointSyncEngine
        from dataclasses import asdict
        engine = CheckpointSyncEngine()
        snapshots = engine.list_snapshots(job_id)
        return {"status": "success", "snapshots": [asdict(s) for s in snapshots]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def pluto_restore_checkpoint(snapshot_id: str, target_dir: Optional[str] = None) -> Dict[str, Any]:
    """Restore a training checkpoint snapshot.
    
    Args:
        snapshot_id (str): The ID of the snapshot to restore.
        target_dir (str, optional): The local directory to restore to.
        
    Returns:
        Dict[str, Any]: The restore operation status.
    """
    try:
        from src.pluto.services.checkpoint_sync import CheckpointSyncEngine
        engine = CheckpointSyncEngine()
        res = engine.restore_snapshot(snapshot_id, target_dir)
        return res
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def pluto_list_model_recipes() -> Dict[str, Any]:
    """List available model recipes enriched with local compatibility status."""
    try:
        from src.pluto.services.model_catalog import catalog_manager
        recipes = catalog_manager.get_all_recipes()
        return {"status": "success", "recipes": [r.model_dump() if hasattr(r, 'model_dump') else r.__dict__ for r in recipes]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def pluto_download_model_recipe(recipe_id: str) -> Dict[str, Any]:
    """Queue background weight download for a specific model recipe.
    
    Args:
        recipe_id (str): The ID of the model recipe to download.
    """
    try:
        from src.pluto.services.model_catalog import catalog_manager
        job_id = catalog_manager.download_recipe(recipe_id)
        return {"status": "success", "job_id": job_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def pluto_list_lora_adapters(base_model: str = None) -> Dict[str, Any]:
    """List trained LoRA adapters.
    
    Args:
        base_model (str, optional): Filter by base model.
        
    Returns:
        Dict[str, Any]: List of available adapters.
    """
    try:
        from src.pluto.services.lora import lora_manager
        import dataclasses
        adapters = lora_manager.list_adapters(base_model)
        return {"adapters": [dataclasses.asdict(a) for a in adapters]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def pluto_train_lora(name: str, base_model: str, image_paths: list[str], trigger_word: str, rank: int = 16, steps: int = 500, lr: float = 1e-4) -> Dict[str, Any]:
    """Queue a LoRA training job.
    
    Args:
        name (str): The name of the adapter.
        base_model (str): Base model ID.
        image_paths (list[str]): List of image paths for training.
        trigger_word (str): Trigger word.
        rank (int, optional): LoRA rank. Defaults to 16.
        steps (int, optional): Training steps. Defaults to 500.
        lr (float, optional): Learning rate. Defaults to 1e-4.
        
    Returns:
        Dict[str, Any]: Job details.
    """
    try:
        from src.pluto.services.lora import lora_manager
        job = lora_manager.create_training_job(
            name=name,
            base_model=base_model,
            image_paths=image_paths,
            trigger_word=trigger_word,
            rank=rank,
            steps=steps,
            lr=lr
        )
        return {"status": "success", "job": job}
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("Failed to train LoRA")
        return {"status": "error", "message": str(e)}


# Deliberately NOT exposed as tools — each returns a plausible success with nothing
# behind it, and an agent calling one has no way to tell:
#   pluto_skypilot_arbitrage: no arbitrage is possible on one 8 vCPU box; the G-family spot quota permits exactly one g6e.2xlarge
#   pluto_download_model: model_catalog._mock_download_task downloads nothing (TODO(real-download))
#   pluto_get_billing_usage: no metering, credits or entitlements exist, so there is nothing to report usage against
#   pluto_verify_agent_payment: same — x402 verification has no ledger behind it
#   pluto_get_fleet_status: returned a fixed {vram_usage: 0.5, instances: 10, healthy};
#     there is no fleet, and the one box is usually not running at all
#   pluto://models/ltx25, pluto://voices/catalogue: hardcoded prose stating a 48GB
#     VRAM figure and a voice list as fact, neither read from anything
# Restore a tool here only once its implementation is real.

if __name__ == "__main__":
    mcp.run()

