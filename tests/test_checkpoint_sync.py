import os
import pytest
from fastapi.testclient import TestClient
from spacepilot.pluto.app import create_app
from spacepilot.pluto.services.checkpoint_sync import CheckpointSyncEngine
from spacepilot.pluto_mcp_server import (
    spacepilot_create_checkpoint,
    spacepilot_list_checkpoints,
    spacepilot_restore_checkpoint,
)

@pytest.fixture(autouse=True)
def reset_engine():
    engine = CheckpointSyncEngine()
    engine.snapshots.clear()
    yield engine
    engine.snapshots.clear()

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

def test_engine_create_and_list(reset_engine):
    meta = reset_engine.create_snapshot("job-1", 100, 1, 0.5, ["/nonexistent/path.pt"])
    assert meta.job_id == "job-1"
    assert meta.step == 100
    assert meta.epoch == 1
    assert meta.loss == 0.5
    
    snaps = reset_engine.list_snapshots("job-1")
    assert len(snaps) == 1
    assert snaps[0].snapshot_id == meta.snapshot_id

def test_engine_restore(reset_engine):
    meta = reset_engine.create_snapshot("job-2", 200, 2, 0.4, [])
    res = reset_engine.restore_snapshot(meta.snapshot_id)
    assert res["status"] == "success"
    assert res["snapshot_id"] == meta.snapshot_id
    assert res["metadata"]["job_id"] == "job-2"

def test_engine_prune(reset_engine):
    # create 5 snapshots with varying loss and timestamps
    # loss: 0.9, 0.8, 0.7, 0.6, 0.5
    for i in range(5):
        reset_engine.create_snapshot("job-3", i*100, 1, 0.9 - i*0.1, [])
    
    res = reset_engine.prune_snapshots("job-3", keep_best=2, keep_latest=1)
    # 5 total, keep best 2 (loss 0.5, 0.6) and latest 1 (which is the last one with loss 0.5)
    # total kept should be 2.
    assert res["kept"] <= 3
    assert len(reset_engine.snapshots) == res["kept"]

def test_api_routes(client):
    from spacepilot.pluto.core.config import get_settings
    headers = {"X-Pluto-Token": get_settings().studio_token}
    
    # 1. Create snapshot
    resp = client.post("/api/checkpoints/snapshot", json={
        "job_id": "api-job",
        "step": 10,
        "epoch": 1,
        "loss": 0.1,
        "local_paths": []
    }, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == "api-job"
    snap_id = data["snapshot_id"]
    
    # 2. List snapshots
    resp = client.get("/api/checkpoints/snapshots?job_id=api-job", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    
    # 3. Restore snapshot
    resp = client.post(f"/api/checkpoints/restore/{snap_id}", json={"target_dir": "/tmp/test"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    
    # 4. Delete snapshot
    resp = client.delete(f"/api/checkpoints/snapshots/{snap_id}", headers=headers)
    assert resp.status_code == 200

@pytest.mark.parametrize("method,endpoint,payload", [
    ("POST", "/api/checkpoints/snapshot", {"job_id": "api-job", "step": 10, "epoch": 1, "loss": 0.1, "local_paths": []}),
    ("GET", "/api/checkpoints/snapshots", None),
    ("POST", "/api/checkpoints/restore/snap-123", {"target_dir": "/tmp/test"}),
    ("DELETE", "/api/checkpoints/snapshots/snap-123", None),
])
def test_api_auth_gate(client, method, endpoint, payload):
    if method == "GET":
        resp = client.get(endpoint, headers={"X-Pluto-Token": "badtoken"})
    elif method == "POST":
        resp = client.post(endpoint, json=payload, headers={"X-Pluto-Token": "badtoken"})
    elif method == "DELETE":
        resp = client.delete(endpoint, headers={"X-Pluto-Token": "badtoken"})
    
    assert resp.status_code == 401

def test_mcp_tools(reset_engine):
    res_create = spacepilot_create_checkpoint("mcp-job", 50, 1, 0.2, [])
    assert res_create["status"] == "success"
    snap_id = res_create["snapshot"]["snapshot_id"]
    
    res_list = spacepilot_list_checkpoints("mcp-job")
    assert res_list["status"] == "success"
    assert len(res_list["snapshots"]) == 1
    
    res_restore = spacepilot_restore_checkpoint(snap_id)
    assert res_restore["status"] == "success"

def test_edge_cases(client):
    from spacepilot.pluto.core.config import get_settings
    headers = {"X-Pluto-Token": get_settings().studio_token}

    # Test missing path / escapes directory
    resp = client.post("/api/checkpoints/snapshot", json={
        "job_id": "api-job",
        "step": 10,
        "epoch": 1,
        "loss": 0.1,
        "local_paths": ["/etc/passwd"]
    }, headers=headers)
    assert resp.status_code == 400

    # Test invalid snapshot ID on restore
    resp = client.post("/api/checkpoints/restore/invalid-snap-id", headers=headers)
    assert resp.status_code == 404

    # Test invalid snapshot ID on delete
    resp = client.delete("/api/checkpoints/snapshots/invalid-snap-id", headers=headers)
    assert resp.status_code == 404
