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


# async, not sync: FastAPI runs a sync endpoint in a threadpool with no event
# loop, and download_recipe schedules the transfer with asyncio.create_task.
# As a sync route this raised "no running event loop" on every call — so this
# endpoint returned 500 long before the download itself was real.
@router.post("/api/compute/recipes/{recipe_id}/download")
async def download_recipe(recipe_id: str, _: None = Depends(require_token)):
    """Queue background weight download."""
    update_activity()
    try:
        job_id = catalog_manager.download_recipe(recipe_id)
        return {"job_id": job_id, "status": "pending"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/api/compute/recipes/{recipe_id}/progress")
def get_download_progress(recipe_id: str, _: None = Depends(require_token)):
    """Return download percentage, status, and speed."""
    job = catalog_manager.get_download_progress(recipe_id)
    if not job:
        raise HTTPException(status_code=404, detail="No active or completed download job found for this recipe.")
    
    # Return the whole job, not a hand-picked subset. The previous version
    # dropped downloaded_bytes, total_bytes, local_path and error — so a caller
    # could see a download fail but never learn why, and could not find the
    # weights after one succeeded.
    return job.model_dump()
