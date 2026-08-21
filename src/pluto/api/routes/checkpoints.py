from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from src.pluto.services.checkpoint_sync import CheckpointSyncEngine, CheckpointMetadata

router = APIRouter(prefix="/api/checkpoints", tags=["checkpoints"])
engine = CheckpointSyncEngine()

from src.pluto.api.deps import require_token, update_activity

class CreateSnapshotRequest(BaseModel):
    job_id: str
    step: int
    epoch: int
    loss: float
    local_paths: List[str]

class RestoreSnapshotRequest(BaseModel):
    target_dir: Optional[str] = None

@router.get("/snapshots")
def list_snapshots(job_id: Optional[str] = None):
    return engine.list_snapshots(job_id)

@router.post("/snapshot")
def create_snapshot(req: CreateSnapshotRequest, _: None = Depends(require_token)):
    update_activity()
    meta = engine.create_snapshot(
        job_id=req.job_id,
        step=req.step,
        epoch=req.epoch,
        loss=req.loss,
        local_paths=req.local_paths
    )
    return meta

@router.post("/restore/{snapshot_id}")
def restore_snapshot(snapshot_id: str, req: Optional[RestoreSnapshotRequest] = None, _: None = Depends(require_token)):
    update_activity()
    target_dir = req.target_dir if req else None
    try:
        return engine.restore_snapshot(snapshot_id, target_dir)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/snapshots/{snapshot_id}")
def delete_snapshot(snapshot_id: str, _: None = Depends(require_token)):
    update_activity()
    success = engine.delete_snapshot(snapshot_id)
    if not success:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return {"status": "deleted"}
