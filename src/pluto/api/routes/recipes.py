"""Compute Hardware Allocation Recipes and Automated Quantized Weights Importer."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from pydantic import BaseModel
from src.pluto.services.model_catalog import catalog_manager
from src.pluto.api.deps import require_token, update_activity

router = APIRouter(tags=["recipes"])

class RecipeResponse(BaseModel):
    recipe_id: str
    name: str
    family: str
    size_gb: float
    min_vram_gb: float
    quantization: str
    hf_repo: str
    download_url: str
    recommended_gpu: str
    is_local_runnable: bool

@router.get("/api/compute/recipes", response_model=List[RecipeResponse])
def list_recipes(_: None = Depends(require_token)):
    """List recipes enriched with local compatibility status."""
    recipes = catalog_manager.get_all_recipes()
    return recipes


@router.post("/api/compute/recipes/{recipe_id}/download")
def download_recipe(recipe_id: str, _: None = Depends(require_token)):
    """Queue background weight download."""
    update_activity()
    try:
        job_id = catalog_manager.download_recipe(recipe_id)
        # TODO(real-download): Remove mock flag when actual download is implemented
        return {"job_id": job_id, "status": "pending", "mock": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/api/compute/recipes/{recipe_id}/progress")
def get_download_progress(recipe_id: str, _: None = Depends(require_token)):
    """Return download percentage, status, and speed."""
    job = catalog_manager.get_download_progress(recipe_id)
    if not job:
        raise HTTPException(status_code=404, detail="No active or completed download job found for this recipe.")
    
    return {
        "job_id": job.job_id,
        "recipe_id": job.recipe_id,
        "status": job.status,
        "progress_percent": job.progress_percent,
        "speed_mb_s": job.speed_mb_s,
    }
