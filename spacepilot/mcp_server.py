# The SDK renamed FastMCP to MCPServer in mcp 2.0; the API is otherwise the same.
# There is deliberately no fallback stub here. The old one defined run() as `pass`,
# so a missing or moved dependency produced a server that started, served nothing,
# and exited cleanly — an agent connecting to it saw no error at all.
try:
    from mcp.server import MCPServer
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "SpacePilot MCP server needs the mcp SDK (>=2.0).\n"
        "  pip install 'mcp>=2.0'\n"
        f"import failed: {exc}"
    ) from exc

from typing import Annotated, Optional, Dict, Any, List

from pydantic import Field, ValidationError

from spacepilot import __version__ as SERVER_VERSION
from spacepilot.api import contracts

# An empty serverInfo.version told a client nothing about what it was talking
# to. It comes from the package, never from Settings: constructing Settings
# mints `.studio_token` through a default factory, and under `uv tool install`
# that writes a secret into the install tree (the bug #155 exists to fix).
# This module deliberately imports no config.
mcp = MCPServer("SpacePilot", version=SERVER_VERSION)


def _refused(exc: ValidationError) -> Dict[str, Any]:
    """The refusal an MCP caller gets for input HTTP would answer with a 422.

    Carries `error` as well as `status`/`message` so a client has one key to
    test across every refusal this server can return — unknown ids answer
    `{"error": ..., "known": [...]}`, and the two shapes were untestable
    together.
    """
    message = contracts.describe(exc)
    return {"status": "error", "error": message, "message": message}


@mcp.tool()
def spacepilot_decompose_storyboard(
    script: str,
    # Annotated so `tools/list` publishes the range too. Enforcement is the
    # shared contract below; this is what a schema-validating client reads,
    # instead of learning the bounds only from a refusal string.
    scene_count: Annotated[int, Field(
        ge=contracts.SCENE_COUNT_MIN, le=contracts.SCENE_COUNT_MAX)] = 6,
    target_duration_sec: Annotated[float, Field(
        ge=contracts.DURATION_MIN_SEC, le=contracts.DURATION_MAX_SEC)] = 60.0,
    style: str = "cinematic",
) -> Dict[str, Any]:
    """Decompose a high-level narrative script into cinematic storyboard scenes with 3D camera vectors.

    Out-of-range values are refused, not clamped: this used to answer a request
    for 50 scenes with 10 and the word "success".

    Args:
        script (str): The narrative story or high-level video prompt.
        scene_count (int, optional): Number of scenes, 4 to 10. Defaults to 6.
        target_duration_sec (float, optional): Total duration in seconds, 10 to 300. Defaults to 60.0.
        style (str, optional): Visual directing style. Defaults to "cinematic".

    Returns:
        Dict[str, Any]: Structured scenes with locked character seed and 3D camera trajectory tokens.
    """
    try:
        request = contracts.StoryboardDecomposeRequest(
            script=script,
            scene_count=scene_count,
            target_duration_sec=target_duration_sec,
            style=style,
        )
    except ValidationError as exc:
        return _refused(exc)
    try:
        from spacepilot.storyboard_decomposer import decompose_storyboard
        return decompose_storyboard(
            script=request.script,
            target_duration_sec=request.target_duration_sec,
            scene_count=request.scene_count,
            style=request.style,
        )
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def spacepilot_probe_hardware() -> Dict[str, Any]:
    """Probe host hardware capabilities and VRAM headroom for local inference.
    
    Returns:
        Dict[str, Any]: Device telemetry including backend (MPS/CUDA/CPU), total VRAM, and usable headroom.
    """
    try:
        from spacepilot.device_probe import probe_local_device
        profile = probe_local_device()
        return {"status": "success", "profile": profile.to_dict()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def spacepilot_recommend_models() -> Dict[str, Any]:
    """Recommend task-based models (TTS, Storyboard, Video Diffusion) matched to host hardware.
    
    Returns:
        Dict[str, Any]: Every registry variant graded by the shared fit verdict
        (`runs_well`, `runs_slowly`, `wont_fit`, `unknown` — the same words
        `spacepilot models` and `GET /v1/models` print), plus the older
        task-based catalogue with quantisation and local cache status.
    """
    try:
        from spacepilot.device_probe import probe_local_device
        from spacepilot.model_recommender import recommend_models_for_device
        from spacepilot.model_registry import registry
        from spacepilot.verdict import fit_verdict

        profile = probe_local_device()
        models = [
            {"model_id": v.id, "kind": v.kind, "name": v.name,
             "verdict": fit_verdict(v.id, profile)}
            for v in registry().variants
        ]
        return {"status": "success", "models": models,
                **recommend_models_for_device(profile)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def spacepilot_get_local_status() -> Dict[str, Any]:
    """Get live status of local inference workers and loaded models.
    
    Returns:
        Dict[str, Any]: Loaded model weights, current VRAM allocation, and worker availability.
    """
    try:
        from spacepilot.device_probe import probe_local_device
        from spacepilot.model_recommender import downloaded_model_ids
        profile = probe_local_device()
        downloaded = downloaded_model_ids()
        return {
            "status": "online",
            "backend": profile.backend,
            "vram_usable_gb": profile.vram_usable_gb,
            "vram_usable_known": profile.usable_memory_known,
            "loaded_models": downloaded,
            "is_local_capable": profile.is_local_capable,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}



@mcp.tool()
def spacepilot_create_checkpoint(job_id: str, step: int, epoch: int, loss: float, local_paths: List[str]) -> Dict[str, Any]:
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
        from spacepilot.services.checkpoint_sync import CheckpointSyncEngine
        from dataclasses import asdict
        engine = CheckpointSyncEngine()
        meta = engine.create_snapshot(job_id, step, epoch, loss, local_paths)
        return {"status": "success", "snapshot": asdict(meta)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def spacepilot_list_checkpoints(job_id: Optional[str] = None) -> Dict[str, Any]:
    """List training checkpoint snapshots.
    
    Args:
        job_id (str, optional): The ID of the training job to filter by.
        
    Returns:
        Dict[str, Any]: List of snapshot metadata.
    """
    try:
        from spacepilot.services.checkpoint_sync import CheckpointSyncEngine
        from dataclasses import asdict
        engine = CheckpointSyncEngine()
        snapshots = engine.list_snapshots(job_id)
        return {"status": "success", "snapshots": [asdict(s) for s in snapshots]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def spacepilot_restore_checkpoint(snapshot_id: str, target_dir: Optional[str] = None) -> Dict[str, Any]:
    """Restore a training checkpoint snapshot.
    
    Args:
        snapshot_id (str): The ID of the snapshot to restore.
        target_dir (str, optional): The local directory to restore to.
        
    Returns:
        Dict[str, Any]: The restore operation status.
    """
    try:
        from spacepilot.services.checkpoint_sync import CheckpointSyncEngine
        engine = CheckpointSyncEngine()
        res = engine.restore_snapshot(snapshot_id, target_dir)
        return res
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def spacepilot_list_model_recipes() -> Dict[str, Any]:
    """List available model recipes enriched with local compatibility status."""
    try:
        from spacepilot.services.model_catalog import catalog_manager
        recipes = catalog_manager.get_all_recipes()
        return {"status": "success", "recipes": [r.model_dump() if hasattr(r, 'model_dump') else r.__dict__ for r in recipes]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def spacepilot_download_model_recipe(recipe_id: str) -> Dict[str, Any]:
    """Queue background weight download for a specific model recipe.
    
    Args:
        recipe_id (str): The ID of the model recipe to download.
    """
    try:
        from spacepilot.services.model_catalog import catalog_manager
        job_id = catalog_manager.download_recipe(recipe_id)
        return {"status": "success", "job_id": job_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def spacepilot_list_lora_adapters(base_model: str = None) -> Dict[str, Any]:
    """List trained LoRA adapters.
    
    Args:
        base_model (str, optional): Filter by base model.
        
    Returns:
        Dict[str, Any]: List of available adapters.
    """
    try:
        from spacepilot.services.lora import lora_manager
        import dataclasses
        adapters = lora_manager.list_adapters(base_model)
        return {"adapters": [dataclasses.asdict(a) for a in adapters]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def spacepilot_train_lora(name: str, base_model: str, image_paths: list[str], trigger_word: str, rank: int = 16, steps: int = 500, lr: float = 1e-4) -> Dict[str, Any]:
    """Queue a LoRA training job.
    
    Args:
        name (str): The name of the adapter.
        base_model (str): Base model ID.
        image_paths (list[str]): List of image paths for training.
        trigger_word (str): Trigger word.
        rank (int, optional): LoRA rank; must be a positive power of 2. Defaults to 16.
        steps (int, optional): Training steps. Defaults to 500.
        lr (float, optional): Learning rate. Defaults to 1e-4.
        
    Returns:
        Dict[str, Any]: Job details.
    """
    try:
        request = contracts.TrainLoRARequest(
            name=name, base_model=base_model, image_paths=image_paths,
            trigger_word=trigger_word, rank=rank, steps=steps, lr=lr,
        )
    except ValidationError as exc:
        return _refused(exc)
    try:
        from spacepilot.services.lora import lora_manager
        job = lora_manager.create_training_job(
            name=request.name,
            base_model=request.base_model,
            image_paths=request.image_paths,
            trigger_word=request.trigger_word,
            rank=request.rank,
            steps=request.steps,
            lr=request.lr
        )
        return {"status": "success", "job": job}
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("Failed to train LoRA")
        return {"status": "error", "message": str(e)}



@mcp.tool()
def spacepilot_list_runtimes() -> dict:
    """List the packages that execute models, and whether each is installed here.

    A runtime is what runs a model — mflux for image on Apple Silicon, mlx-video
    for video, llama.cpp for GGUF text. Separate from the model registry, which
    holds weights. Having weights without a runtime gets you nothing.
    """
    from spacepilot.device_probe import probe_local_device
    from spacepilot import runtimes as rt

    profile = probe_local_device()
    out = []
    for r in rt.runtimes().values():
        st = rt.check(r)
        out.append({
            "id": r.id, "name": r.name, "serves": r.serves, "backends": r.backends,
            "installed": st.installed, "version": st.version,
            "below_minimum": st.below_minimum,
            "usable_here": bool(profile.backend and profile.backend in r.backends)
                           and st.python_compatible,
            "reason": st.reason, "python_note": st.python_note,
            "runs": r.runs, "license": r.license,
        })
    return {"backend": profile.backend, "interpreter": rt.interpreter(), "runtimes": out}


@mcp.tool()
def spacepilot_preview_runtime_install(runtime_id: str) -> dict:
    """Resolve what installing a runtime would change, without changing anything.

    Call this before spacepilot_install_runtime and show the result to the person.
    Installing into a shared environment is not additive: resolving mflux
    downgrades opencv-python from 5.0 to 4.14, which breaks whatever needed the
    newer one, later, somewhere else.
    """
    from spacepilot import runtimes as rt
    r = rt.runtimes().get(runtime_id)
    if not r:
        return {"error": f"no runtime '{runtime_id}'", "known": sorted(rt.runtimes())}
    imp = rt.preview(r)
    return {"runtime_id": runtime_id,
            "command": " ".join(rt.install_command(r)),
            "interpreter": rt.interpreter(), **imp.to_dict()}


@mcp.tool()
def spacepilot_install_runtime(runtime_id: str, allow_downgrade: bool = False) -> dict:
    """Install a runtime, then verify it by importing it.

    Ask the person first — this mutates their Python environment. Refuses when
    the resolution would downgrade something, unless allow_downgrade is set, and
    that flag should only ever be set because a human said so after seeing
    spacepilot_preview_runtime_install.
    """
    from spacepilot import runtimes as rt
    r = rt.runtimes().get(runtime_id)
    if not r:
        return {"error": f"no runtime '{runtime_id}'", "known": sorted(rt.runtimes())}

    imp = rt.preview(r)
    if imp.error:
        return {"installed": False, "error": imp.error}
    if imp.is_disruptive and not allow_downgrade:
        return {"installed": False, "refused": "would downgrade a package",
                "downgrades": imp.downgrades,
                "hint": "show these to the person; only set allow_downgrade if they agree"}

    st = rt.install(r)
    return {**st.to_dict(), "changed": imp.to_dict()}


@mcp.tool()
def spacepilot_check() -> dict:
    """Probe this machine and return its own flown corpus summaries.

    This is a read-only local check.  It never launches a worker, downloads
    weights, or turns an absent measurement into a performance claim.
    """
    from spacepilot.services.corpus import CorpusReadError, check_payload

    try:
        return check_payload()
    except CorpusReadError as exc:
        return {"error": str(exc)}


@mcp.tool()
def spacepilot_measurements(variant_id: Optional[str] = None) -> dict:
    """Return individual flown observations and their registry caveats.

    ``variant_id`` is an exact registry identifier when supplied; it is a
    filter over loaded records, never a filesystem path or a fuzzy model name.
    An unknown id is an error naming what is known — a typo and "nothing
    measured yet" are different answers, and both used to come back as [].
    """
    from spacepilot.services import corpus

    try:
        if variant_id is not None:
            known = corpus.known_variant_ids()
            if variant_id not in known:
                return {"error": f"no such variant_id '{variant_id}'", "known": known}
        payload = corpus.measurement_payload()
    except corpus.CorpusReadError as exc:
        return {"error": str(exc)}
    if variant_id is not None:
        payload["measurements"] = [
            row for row in payload["measurements"] if row["variant_id"] == variant_id
        ]
    return payload


@mcp.tool()
def spacepilot_system_summary(system_id: Optional[str] = None) -> dict:
    """Return flown two-stream summaries with associated capability caveats.

    An unknown ``system_id`` is an error naming the known ids, never an empty
    list: a caller cannot otherwise tell a typo from an unmeasured machine.
    """
    from spacepilot.services import corpus

    try:
        if system_id is not None:
            known = corpus.known_system_ids()
            if system_id not in known:
                return {"error": f"no such system_id '{system_id}'", "known": known}
        return corpus.summary_payload(system_id=system_id)
    except corpus.CorpusReadError as exc:
        return {"error": str(exc)}


# Deliberately NOT exposed as tools — each returns a plausible success with nothing
# behind it, and an agent calling one has no way to tell:
#   spacepilot_skypilot_arbitrage: no arbitrage is possible on one 8 vCPU box; the G-family spot quota permits exactly one g6e.2xlarge
#   spacepilot_download_model: model_catalog._mock_download_task downloads nothing (TODO(real-download))
#   spacepilot_get_billing_usage: no metering, credits or entitlements exist, so there is nothing to report usage against
#   spacepilot_verify_agent_payment: same — x402 verification has no ledger behind it
#   spacepilot_get_fleet_status: returned a fixed {vram_usage: 0.5, instances: 10, healthy};
#     there is no fleet, and the one box is usually not running at all
#   legacy model and voice resources: hardcoded prose stating a 48GB
#     VRAM figure and a voice list as fact, neither read from anything
#   spacepilot_generate_video_wan and spacepilot_generate_video_hunyuan: on any
#     failure both returned a
#     hardcoded job_id ("wan-12345", "hunyuan-12345") with status "processing" for a job that
#     was never queued, so the caller polled forever; the non-failing path only ever rendered
#     an ffmpeg test pattern, because both engines ignore their own mock= argument
#   spacepilot_generate_video, spacepilot_extend_video, spacepilot_generate_audio,
#     spacepilot_generate_music, spacepilot_get_render_status: one-line stubs returning
#     "vid-12345", "vid-67890", "aud-12345", "mus-12345" for jobs that were never queued.
#     get_render_status was the worst of them — it answered "completed" for ANY job id,
#     including one that never existed, so a polling agent could never learn otherwise.
#     The real work exists over HTTP (routes/generate.py, routes/audio.py); these tools
#     never called it. Restore them only by wiring them to it.
# Restore a tool here only once its implementation is real.

def main() -> None:
    """Run SpacePilot's stdio MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
