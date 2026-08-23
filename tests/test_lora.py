import pytest
import time
from fastapi.testclient import TestClient
from spacepilot.pluto.app import create_app
from spacepilot.pluto.core.config import get_settings
from spacepilot.pluto.services.lora import lora_manager

@pytest.fixture
def test_app():
    return create_app()

@pytest.fixture
def client(test_app):
    return TestClient(test_app)

@pytest.fixture
def auth_headers():
    settings = get_settings()
    return {"X-Pluto-Token": settings.studio_token}

def test_lora_training_workflow(client, auth_headers):
    # 1. Start a training job
    req = {
        "name": "MyStyle",
        "base_model": "ltx-video",
        "image_paths": ["/tmp/img1.jpg", "/tmp/img2.jpg"],
        "trigger_word": "mystyle",
        "rank": 32,
        "alpha": 32.0,
        "steps": 10
    }
    resp = client.post("/api/lora/train", json=req, headers=auth_headers)
    assert resp.status_code == 200
    job = resp.json()
    assert job["name"] == "MyStyle"
    assert job["status"] == "training"
    assert "job_id" in job
    assert job["rank"] == 32
    assert job["alpha"] == 32.0
    job_id = job["job_id"]

    # 2. Check job progress
    # Wait for background task to advance the state a bit
    time.sleep(1.0)
    
    resp = client.get(f"/api/lora/train/{job_id}", headers=auth_headers)
    assert resp.status_code == 200
    progress = resp.json()
    assert progress["current_step"] > 0
    assert len(progress["loss_curve"]) > 0

    # Advance to completion (10 steps - wait a bit more)
    time.sleep(4.5)
    
    resp = client.get(f"/api/lora/train/{job_id}", headers=auth_headers)
    assert resp.status_code == 200
    final_job = resp.json()
    assert final_job["status"] == "completed"
    assert "adapter_id" in final_job
    adapter_id = final_job["adapter_id"]

    # 3. List adapters
    resp = client.get("/api/lora/adapters", headers=auth_headers)
    assert resp.status_code == 200
    adapters = resp.json()
    assert isinstance(adapters, list)
    assert len(adapters) > 0
    assert any(a["adapter_id"] == adapter_id for a in adapters)
    
    # Verify adapter structure
    adapter = next(a for a in adapters if a["adapter_id"] == adapter_id)
    assert adapter["name"] == "MyStyle"
    assert adapter["rank"] == 32

    # 4. Delete adapter
    resp = client.delete(f"/api/lora/adapters/{adapter_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"success": True}

    resp = client.get("/api/lora/adapters", headers=auth_headers)
    assert resp.status_code == 200
    assert not any(a["adapter_id"] == adapter_id for a in resp.json())

def test_lora_auth_gates(client):
    req = {
        "name": "MyStyle",
        "base_model": "ltx-video",
        "image_paths": ["/tmp/img1.jpg", "/tmp/img2.jpg"],
        "trigger_word": "mystyle"
    }
    # No auth
    resp = client.post("/api/lora/train", json=req)
    assert resp.status_code == 401

    resp = client.delete("/api/lora/adapters/lora-1234")
    assert resp.status_code == 401

    resp = client.get("/api/lora/adapters")
    assert resp.status_code == 401
    
    resp = client.get("/api/lora/train/job-1234")
    assert resp.status_code == 401

def test_lora_validation(client, auth_headers):
    # Test invalid rank
    req = {
        "name": "MyStyle",
        "base_model": "ltx-video",
        "image_paths": ["/tmp/img1.jpg"],
        "trigger_word": "mystyle",
        "rank": 31,  # Not power of 2
    }
    resp = client.post("/api/lora/train", json=req, headers=auth_headers)
    assert resp.status_code == 422
    
    # Test invalid alpha
    req["rank"] = 32
    req["alpha"] = -1
    resp = client.post("/api/lora/train", json=req, headers=auth_headers)
    assert resp.status_code == 422

def test_mcp_tools():
    from spacepilot.pluto_mcp_server import pluto_train_lora, pluto_list_lora_adapters
    
    # Train
    job_res = pluto_train_lora(
        name="MCPStyle",
        base_model="ltx-video",
        image_paths=["/tmp/a.jpg"],
        trigger_word="mcpstyle"
    )
    assert job_res["status"] == "success"
    
    # List
    list_res = pluto_list_lora_adapters()
    assert "adapters" in list_res
