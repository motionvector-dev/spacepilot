import datetime
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any, NoReturn

from fastapi import HTTPException

from spacepilot.core.utils import allocate_output, resolve_output

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

from spacepilot.capability import absent, refuse

GATE_DATE = "2026-09-22"

# GATED 2026-09-22: none of this subsystem stored anything. `create_snapshot`
# computed a genuine sha256 and copied no bytes, leaving a `remote_uri` pointing
# at an empty directory it had just created; `restore_snapshot` reported success
# and wrote nothing; and the records lived in a dict on a process-wide
# singleton, so a snapshot vanished on restart and was invisible to the other
# transport — the HTTP server and a stdio MCP server each had their own private
# universe of snapshots. A successful snapshot_id came back "Snapshot not
# found". Real checkpoint sync (an S3/R2 upload and download) is a separate,
# unbuilt feature. Until it exists every entry point refuses rather than
# pretend, the way LoRA training and model download already do.
CHECKPOINT_SYNC = absent(
    "checkpoint_sync", GATE_DATE,
    "Checkpoint sync is not implemented. It stored nothing: snapshots were "
    "kept in one process's memory, no bytes were ever uploaded or downloaded, "
    f"and restore reported success while writing no file. Gated {GATE_DATE}.",
)


def _refuse() -> NoReturn:
    refuse(CHECKPOINT_SYNC)


class CheckpointSyncEngine:
    """Checkpoint sync, gated: every write and restore refuses.

    Kept as a class rather than deleted so the routes, the MCP tools and the
    prior work stay legible, and so the refusal is in one place when the real
    S3/R2 implementation lands.
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

        Nothing creates the directory any more: an empty `checkpoints/` made
        the `remote_uri` in every snapshot look like a real location.
        """
        return str(allocate_output("checkpoints"))

    def store_status(self) -> Dict[str, Any]:
        """Why a listing is empty — "no store" is not "this job has none"."""
        return dict(CHECKPOINT_SYNC)

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
        """Refuse: nothing was ever uploaded, and the record died with the process.

        The path validation below still runs first, so a caller passing a system
        path or a traversal still gets that 400 rather than the gate.
        """
        for path in local_paths:
            p = Path(path)
            if ".." in p.parts:
                raise HTTPException(status_code=400, detail=f"Path escapes allowed directory: {path}")
            resolved = str(p.resolve())
            if resolved.startswith(("/etc", "/var", "/System", "/usr", "/bin", "/sbin", "/private/etc")):
                raise HTTPException(status_code=400, detail=f"System path not allowed: {path}")

        _refuse()

        # Dead below the gate. Kept so the shape the real implementation has to
        # produce — and what it must actually do differently — stays readable.
        snapshot_id = f"snap-{uuid.uuid4().hex[:8]}"
        checksum = self._compute_checksum(local_paths)
        size_mb = self._get_size_mb(local_paths)

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
        """Always empty while the store is gated.

        Callers pair this with `store_status()`: an empty list on its own said
        "this job has no snapshots" when the truth is "there is no store".
        """
        res = list(self.snapshots.values())
        if job_id:
            res = [s for s in res if s.job_id == job_id]
        return sorted(res, key=lambda x: x.timestamp, reverse=True)

    def restore_snapshot(self, snapshot_id: str, target_dir: Optional[str] = None) -> dict:
        """Refuse: this reported success, created no directory, wrote no file.

        It no longer answers "Snapshot not found" first. With no store, every
        id is unknown, and "not found" would describe a store that does not
        exist — the same false-precision the gate is here to remove.
        """
        _refuse()

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Refuse: deleting from a dict that never held a real checkpoint."""
        _refuse()

    def prune_snapshots(self, job_id: str, keep_best: int = 3, keep_latest: int = 2) -> dict:
        """Refuse: retention over records that were never persisted."""
        _refuse()

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
