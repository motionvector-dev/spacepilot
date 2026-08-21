from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel

from src.pluto.services.lora import lora_manager, LoRAAdapterSpec
from src.pluto.api.deps import require_token

router = APIRouter(prefix="/api/lora", tags=["lora"])

class TrainLoRARequest(BaseModel):
    name: str
    base_model: str
    image_paths: List[str]
    trigger_word: str
    rank: int = 16
    steps: int = 500
    lr: float = 1e-4

@router.get("/adapters", response_model=List[LoRAAdapterSpec])
async def list_adapters(base_model: Optional[str] = None):
    return lora_manager.list_adapters(base_model)

@router.post("/train", dependencies=[Depends(require_token)])
async def train_lora(req: TrainLoRARequest):
    return lora_manager.create_training_job(
        name=req.name,
        base_model=req.base_model,
        image_paths=req.image_paths,
        trigger_word=req.trigger_word,
        rank=req.rank,
        steps=req.steps,
        lr=req.lr
    )

@router.get("/train/{job_id}")
async def get_training_job(job_id: str):
    job = lora_manager.get_training_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.delete("/adapters/{adapter_id}", dependencies=[Depends(require_token)])
async def delete_adapter(adapter_id: str):
    if lora_manager.delete_adapter(adapter_id):
        return {"success": True}
    raise HTTPException(status_code=404, detail="Adapter not found")
