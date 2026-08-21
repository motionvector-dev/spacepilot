"""Compute Hardware Allocation Recipes and Automated Quantized Weights Importer."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from src.pluto.services.model_catalog import catalog_manager
from src.pluto.api.deps import require_token, update_activity

router = APIRouter(tags=["recipes"])


@router.get("/api/compute/recipes", response_model=List[Dict[str, Any]])
def list_recipes():
    """List recipes enriched with local compatibility status."""
    recipes = catalog_manager.get_all_recipes()
    return [r.__dict__ for r in recipes]


@router.post("/api/compute/recipes/{recipe_id}/download")
def download_recipe(recipe_id: str, _: None = Depends(require_token)):
    """Queue background weight download."""
    update_activity()
    try:
        job_id = catalog_manager.download_recipe(recipe_id)
        return {"job_id": job_id, "status": "pending"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/api/compute/recipes/{recipe_id}/progress")
def get_download_progress(recipe_id: str):
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
