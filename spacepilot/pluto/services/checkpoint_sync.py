import datetime
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any

from fastapi import HTTPException

from spacepilot.pluto.core.utils import allocate_output, resolve_output

@dataclass
class CheckpointMetadata:
    snapshot_id: str
    job_id: str
    step: int
    epoch: int
    loss: float
    file_size_mb: float
    storage_provider: str
    remote_uri: str
    checksum_sha256: str
    timestamp: str
    mock: bool = False

class CheckpointSyncEngine:
    """Engine for syncing training checkpoints to remote storage.
    
    Manages local and remote checkpoint files, generating metadata
    and handling the transfer to block storage (S3/R2).
    """
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(CheckpointSyncEngine, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.snapshots: Dict[str, CheckpointMetadata] = {}
            self.initialized = True

    @property
    def base_dir(self) -> str:
        """Local stand-in for remote storage, under the outputs directory.

        Read from settings on every access rather than cached in __init__:
        this class is a process-wide singleton, so a cached value would
        outlive any change to PLUTO_OUTPUTS_DIR.
        """
        path = allocate_output("checkpoints")
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    def _compute_checksum(self, paths: List[str]) -> str:
        h = hashlib.sha256()
        for path in sorted(paths):
            if os.path.exists(path):
                with open(path, 'rb') as f:
                    while chunk := f.read(8192):
                        h.update(chunk)
            else:
                h.update(path.encode())
        return h.hexdigest()

    def _get_size_mb(self, paths: List[str]) -> float:
        total_bytes = 0
        for path in paths:
            if os.path.exists(path):
                total_bytes += os.path.getsize(path)
        return total_bytes / (1024 * 1024)

    def create_snapshot(self, job_id: str, step: int, epoch: int, loss: float, local_paths: List[str]) -> CheckpointMetadata:
        """Create a new checkpoint snapshot.
        
        Validates local paths, computes checksums, and syncs to remote storage.
        """
        for path in local_paths:
            p = Path(path)
            if ".." in p.parts:
                raise HTTPException(status_code=400, detail=f"Path escapes allowed directory: {path}")
            resolved = str(p.resolve())
            if resolved.startswith(("/etc", "/var", "/System", "/usr", "/bin", "/sbin", "/private/etc")):
                raise HTTPException(status_code=400, detail=f"System path not allowed: {path}")

        snapshot_id = f"snap-{uuid.uuid4().hex[:8]}"
        checksum = self._compute_checksum(local_paths)
        size_mb = self._get_size_mb(local_paths)
        
        # """Mock implementation — real R2/S3 sync requires boto3 and will be added in a follow-up PR."""
        # TODO(real-sync): implement real storage upload
        storage_provider = "Local"
        remote_uri = f"local://{self.base_dir}/{snapshot_id}"
        if os.environ.get("USE_R2"):
            storage_provider = "Cloudflare R2"
            remote_uri = f"r2://pluto-checkpoints/{job_id}/{snapshot_id}"
        elif os.environ.get("USE_S3"):
            storage_provider = "AWS S3"
            remote_uri = f"s3://pluto-checkpoints/{job_id}/{snapshot_id}"

        meta = CheckpointMetadata(
            snapshot_id=snapshot_id,
            job_id=job_id,
            step=step,
            epoch=epoch,
            loss=loss,
            file_size_mb=size_mb,
            storage_provider=storage_provider,
            remote_uri=remote_uri,
            checksum_sha256=checksum,
            timestamp=datetime.datetime.utcnow().isoformat() + "Z",
            mock=True
        )
        self.snapshots[snapshot_id] = meta
        return meta

    def list_snapshots(self, job_id: Optional[str] = None) -> List[CheckpointMetadata]:
        """List available snapshots, optionally filtered by job_id."""
        res = list(self.snapshots.values())
        if job_id:
            res = [s for s in res if s.job_id == job_id]
        return sorted(res, key=lambda x: x.timestamp, reverse=True)

    def restore_snapshot(self, snapshot_id: str, target_dir: Optional[str] = None) -> dict:
        """Restore a checkpoint snapshot to a target directory."""
        if snapshot_id not in self.snapshots:
            raise ValueError("Snapshot not found")
        meta = self.snapshots[snapshot_id]
        
        # """Mock implementation — real R2/S3 sync requires boto3 and will be added in a follow-up PR."""
        # TODO(real-sync): implement real storage download
        return {
            "status": "success",
            "snapshot_id": snapshot_id,
            "target_dir": target_dir or str(allocate_output(snapshot_id, subdir="restores")),
            "metadata": asdict(meta),
            "mock": True
        }

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot and its associated files."""
        if snapshot_id in self.snapshots:
            del self.snapshots[snapshot_id]
            return True
        return False

    def prune_snapshots(self, job_id: str, keep_best: int = 3, keep_latest: int = 2) -> dict:
        """Prune old snapshots, keeping the best by loss and the most recent ones."""
        job_snaps = [s for s in self.snapshots.values() if s.job_id == job_id]
        if not job_snaps:
            return {"deleted": 0, "kept": 0}

        # Keep best (lowest loss)
        best_snaps = sorted(job_snaps, key=lambda x: x.loss)[:keep_best]
        best_ids = {s.snapshot_id for s in best_snaps}

        # Keep latest
        latest_snaps = sorted(job_snaps, key=lambda x: x.timestamp, reverse=True)[:keep_latest]
        latest_ids = {s.snapshot_id for s in latest_snaps}

        keep_ids = best_ids.union(latest_ids)
        
        deleted_count = 0
        for s in job_snaps:
            if s.snapshot_id not in keep_ids:
                self.delete_snapshot(s.snapshot_id)
                deleted_count += 1
                
        return {"deleted": deleted_count, "kept": len(keep_ids)}
