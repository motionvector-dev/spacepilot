from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional

from spacepilot.services.lora import lora_manager, LoRAAdapterSpec
from spacepilot.api.deps import require_token

# Shared with the MCP tool of the same name; see spacepilot/api/contracts.py.
from spacepilot.api.contracts import TrainLoRARequest  # noqa: F401  (re-exported)

router = APIRouter(prefix="/api/lora", tags=["lora"])


@router.get("/adapters", response_model=List[LoRAAdapterSpec])
async def list_adapters(base_model: Optional[str] = None, _: None = Depends(require_token)):
    return lora_manager.list_adapters(base_model)

@router.post("/train")
async def train_lora(req: TrainLoRARequest, _: None = Depends(require_token)):
    try:
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
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))

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
