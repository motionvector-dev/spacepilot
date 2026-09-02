"""Compute profiling and model management routes."""

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException

from spacepilot.api.deps import require_token

router = APIRouter(prefix="/api/compute", tags=["compute"])


class ModelDownloadRequest(BaseModel):
    model_id: str


@router.get("/local-profile")
def get_local_compute_profile():
    """Probe host hardware capabilities and VRAM headroom for local inference."""
    try:
        from spacepilot.device_probe import probe_local_device
        return probe_local_device().to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to probe local hardware: {str(e)}")


@router.get("/models/recommended")
def get_recommended_models():
    """Get task-based model recommendations matched to probed hardware."""
    try:
        from spacepilot.model_recommender import recommend_models_for_device
        return recommend_models_for_device()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate model recommendations: {str(e)}")


@router.post("/models/download", dependencies=[Depends(require_token)])
def download_local_model(req: ModelDownloadRequest):
    """Download a model to the local cache directory."""
    try:
        from spacepilot.model_recommender import download_model_mock
        res = download_model_mock(req.model_id)
        if not res.get("success"):
            raise HTTPException(status_code=400, detail=res.get("error", "Download failed"))
        return res
    except HTTPException:
        raise
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download model: {str(e)}")


@router.get("/local-status")
def get_local_compute_status():
    """Get live status of local inference cache and loaded weights."""
    try:
        from spacepilot.device_probe import probe_local_device
        from spacepilot.model_recommender import MODELS_CACHE
        profile = probe_local_device()
        downloaded = []
        if MODELS_CACHE.exists():
            downloaded = [f.name for f in MODELS_CACHE.iterdir() if f.is_file()]
        return {
            "status": "online",
            "backend": profile.backend,
            "device_name": profile.device_name,
            "vram_usable_gb": profile.vram_usable_gb,
            "vram_usable_known": profile.usable_memory_known,
            "loaded_models": downloaded,
            "is_local_capable": profile.is_local_capable,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve local status: {str(e)}")


@router.get("/compatibility")
def get_compatibility_report():
    """The probed machine, every model's verdict against it, and what to lead with."""
    from spacepilot.services.model_catalog import catalog_manager
    return catalog_manager.compatibility_report()
