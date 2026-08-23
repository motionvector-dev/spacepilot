from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel, field_validator, Field

from spacepilot.pluto.services.lora import lora_manager, LoRAAdapterSpec
from spacepilot.pluto.api.deps import require_token

router = APIRouter(prefix="/api/lora", tags=["lora"])

class TrainLoRARequest(BaseModel):
    name: str
    base_model: str
    image_paths: List[str]
    trigger_word: str
    rank: int = 16
    alpha: float = 16.0
    target_modules: Optional[List[str]] = None
    steps: int = 500
    lr: float = 1e-4

    @field_validator('rank')
    @classmethod
    def validate_rank(cls, v):
        if v <= 0 or (v & (v - 1)) != 0:
            raise ValueError("rank must be > 0 and a power of 2")
        return v

    @field_validator('alpha')
    @classmethod
    def validate_alpha(cls, v):
        if v <= 0:
            raise ValueError("alpha must be > 0")
        return v

@router.get("/adapters", response_model=List[LoRAAdapterSpec])
async def list_adapters(base_model: Optional[str] = None, _: None = Depends(require_token)):
    return lora_manager.list_adapters(base_model)

@router.post("/train")
async def train_lora(req: TrainLoRARequest, _: None = Depends(require_token)):
    return lora_manager.create_training_job(
        name=req.name,
        base_model=req.base_model,
        image_paths=req.image_paths,
        trigger_word=req.trigger_word,
        rank=req.rank,
        alpha=req.alpha,
        target_modules=req.target_modules,
        steps=req.steps,
        lr=req.lr
    )

@router.get("/train/{job_id}")
async def get_training_job(job_id: str, _: None = Depends(require_token)):
    job = lora_manager.get_training_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.delete("/adapters/{adapter_id}")
async def delete_adapter(adapter_id: str, _: None = Depends(require_token)):
    if lora_manager.delete_adapter(adapter_id):
        return {"success": True}
    raise HTTPException(status_code=404, detail="Adapter not found")
