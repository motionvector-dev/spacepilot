from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from spacepilot.api.deps import require_token, update_activity
from spacepilot.services.checkpoint_sync import CheckpointSyncEngine, CheckpointMetadata

router = APIRouter(prefix="/api/checkpoints", tags=["checkpoints"])
engine = CheckpointSyncEngine()

class CreateSnapshotRequest(BaseModel):
    job_id: str
    step: int
    epoch: int
    loss: float
    local_paths: List[str]

class RestoreSnapshotRequest(BaseModel):
    target_dir: Optional[str] = None

@router.get("/snapshots")
def list_snapshots(job_id: Optional[str] = None, _: None = Depends(require_token)):
    """The listing, and why it is empty.

    A bare `[]` said "this job has no snapshots"; the truth is that there is no
    store at all, so `store` travels with every listing.
    """
    return {"snapshots": engine.list_snapshots(job_id), "store": engine.store_status()}

@router.post("/snapshot")
def create_snapshot(req: CreateSnapshotRequest, _: None = Depends(require_token)):
    update_activity()
    try:
        return engine.create_snapshot(
            job_id=req.job_id,
            step=req.step,
            epoch=req.epoch,
            loss=req.loss,
            local_paths=req.local_paths
        )
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))

@router.post("/restore/{snapshot_id}")
def restore_snapshot(snapshot_id: str, req: Optional[RestoreSnapshotRequest] = None, _: None = Depends(require_token)):
    update_activity()
    target_dir = req.target_dir if req else None
    try:
        return engine.restore_snapshot(snapshot_id, target_dir)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotImplementedError as e:
        # 501, never a green 200: restore writes nothing and must say so.
        raise HTTPException(status_code=501, detail=str(e))

@router.delete("/snapshots/{snapshot_id}")
def delete_snapshot(snapshot_id: str, _: None = Depends(require_token)):
    update_activity()
    try:
        engine.delete_snapshot(snapshot_id)
    except NotImplementedError as e:
        # Not 404: "not found" would describe a store that does not exist.
        raise HTTPException(status_code=501, detail=str(e))
    return {"status": "deleted"}
