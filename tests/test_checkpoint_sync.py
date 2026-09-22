"""The checkpoint subsystem is theatre, and now it says so.

Verified against v2.8.0 on 2026-09-22, on both transports:

* `create_snapshot` copied no bytes. It computed a genuine sha256 of the source
  paths — which made it read as more real than it was — stored a record in a
  plain dict, and returned a `remote_uri` pointing at a directory it created
  and left empty.
* `restore_snapshot` returned `{"status": "success"}` with the caller's
  `target_dir` echoed back, created nothing, and hid `mock: true` in the
  payload. Agents read the status.
* The record store was a process-local dict on a process-wide singleton, so a
  snapshot survived neither a restart nor a hop between the HTTP server and a
  stdio MCP server. A successful snapshot_id became "Snapshot not found".

So every entry point refuses, naming the date it was gated, the way
`spacepilot_train_lora` does. These tests pin the refusals and, just as
importantly, pin that a refusal writes nothing.
"""

import os

import pytest
from fastapi.testclient import TestClient

from spacepilot.app import create_app
from spacepilot.mcp_server import (
    spacepilot_create_checkpoint,
    spacepilot_list_checkpoints,
    spacepilot_restore_checkpoint,
)
from spacepilot.services.checkpoint_sync import CheckpointSyncEngine

GATE_DATE = "2026-09-22"


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


# ------------------------------------------------------------------ engine


def test_engine_create_refuses_and_stores_nothing(reset_engine):
    with pytest.raises(NotImplementedError) as exc:
        reset_engine.create_snapshot("job-1", 100, 1, 0.5, ["/nonexistent/path.pt"])
    assert GATE_DATE in str(exc.value), "a gate states the date it was gated"
    assert reset_engine.snapshots == {}


def test_engine_restore_refuses_and_creates_nothing(reset_engine, tmp_path):
    target = tmp_path / "restored"
    with pytest.raises(NotImplementedError) as exc:
        reset_engine.restore_snapshot("snap-anything", str(target))
    assert GATE_DATE in str(exc.value)
    assert not target.exists(), "a refusal creates nothing"


def test_engine_delete_and_prune_refuse(reset_engine):
    with pytest.raises(NotImplementedError):
        reset_engine.delete_snapshot("snap-anything")
    with pytest.raises(NotImplementedError):
        reset_engine.prune_snapshots("job-1")


def test_engine_list_says_there_is_no_store_rather_than_no_snapshots(reset_engine):
    """`[]` read as "this job has no snapshots". There is no store at all."""
    status = reset_engine.store_status()
    assert status["implemented"] is False
    assert GATE_DATE in status["detail"]
    assert reset_engine.list_snapshots("job-1") == []


# -------------------------------------------------------------------- HTTP


def _headers():
    from spacepilot.core.config import get_settings
    return {"X-Pluto-Token": get_settings().studio_token}


def test_http_create_and_restore_are_501_not_a_green_200(client):
    resp = client.post("/api/checkpoints/snapshot", json={
        "job_id": "api-job", "step": 10, "epoch": 1, "loss": 0.1, "local_paths": [],
    }, headers=_headers())
    assert resp.status_code == 501
    assert "not implemented" in resp.json()["detail"].lower()

    resp = client.post("/api/checkpoints/restore/snap-123",
                       json={"target_dir": "/tmp/test"}, headers=_headers())
    assert resp.status_code == 501

    resp = client.delete("/api/checkpoints/snapshots/snap-123", headers=_headers())
    assert resp.status_code == 501


def test_a_system_path_is_still_rejected_before_the_gate(client):
    """The gate must not swallow the path checks: /etc/passwd is still a 400."""
    resp = client.post("/api/checkpoints/snapshot", json={
        "job_id": "api-job", "step": 10, "epoch": 1, "loss": 0.1,
        "local_paths": ["/etc/passwd"],
    }, headers=_headers())
    assert resp.status_code == 400


def test_http_list_reports_the_missing_store(client):
    resp = client.get("/api/checkpoints/snapshots?job_id=api-job", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["snapshots"] == []
    assert body["store"]["implemented"] is False
    assert GATE_DATE in body["store"]["detail"]


@pytest.mark.parametrize("method,endpoint,payload", [
    ("POST", "/api/checkpoints/snapshot", {"job_id": "api-job", "step": 10, "epoch": 1, "loss": 0.1, "local_paths": []}),
    ("GET", "/api/checkpoints/snapshots", None),
    ("POST", "/api/checkpoints/restore/snap-123", {"target_dir": "/tmp/test"}),
    ("DELETE", "/api/checkpoints/snapshots/snap-123", None),
])
def test_api_auth_gate(client, method, endpoint, payload):
    """The token check runs before the gate; a bad token is still 401."""
    if method == "GET":
        resp = client.get(endpoint, headers={"X-Pluto-Token": "badtoken"})
    elif method == "POST":
        resp = client.post(endpoint, json=payload, headers={"X-Pluto-Token": "badtoken"})
    elif method == "DELETE":
        resp = client.delete(endpoint, headers={"X-Pluto-Token": "badtoken"})

    assert resp.status_code == 401


# --------------------------------------------------------------------- MCP


def test_mcp_tools_report_the_gate_as_an_error(reset_engine):
    res_create = spacepilot_create_checkpoint("mcp-job", 50, 1, 0.2, [])
    assert res_create["status"] == "error"
    assert "not implemented" in res_create["message"].lower()

    target = "/tmp/spacepilot-restore-that-never-happens"
    res_restore = spacepilot_restore_checkpoint("snap-123", target)
    assert res_restore["status"] == "error"
    assert "not implemented" in res_restore["message"].lower()
    assert not os.path.exists(target)

    res_list = spacepilot_list_checkpoints("mcp-job")
    assert res_list["snapshots"] == []
    assert res_list["store"]["implemented"] is False


def test_the_two_transports_answer_the_same_way(client):
    """A snapshot could never cross from stdio MCP to HTTP; now neither claims one."""
    mcp = spacepilot_list_checkpoints("shared-job")
    http = client.get("/api/checkpoints/snapshots?job_id=shared-job", headers=_headers()).json()
    assert mcp["snapshots"] == http["snapshots"] == []
    assert mcp["store"] == http["store"]
