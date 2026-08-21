import pytest
from fastapi.testclient import TestClient
from src.pluto.app import create_app
from src.pluto.core.config import get_settings
from src.pluto.services.lora import lora_manager

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
        "steps": 10
    }
    resp = client.post("/api/lora/train", json=req, headers=auth_headers)
    assert resp.status_code == 200
    job = resp.json()
    assert job["name"] == "MyStyle"
    assert job["status"] == "training"
    job_id = job["job_id"]

    # 2. Check job progress
    resp = client.get(f"/api/lora/train/{job_id}")
    assert resp.status_code == 200
    progress = resp.json()
    assert progress["current_step"] > 0
    assert len(progress["loss_curve"]) > 0

    # Advance to completion (10 steps)
    for _ in range(15):
        resp = client.get(f"/api/lora/train/{job_id}")
    
    final_job = resp.json()
    assert final_job["status"] == "completed"
    adapter_id = final_job["adapter_id"]

    # 3. List adapters
    resp = client.get("/api/lora/adapters")
    assert resp.status_code == 200
    adapters = resp.json()
    assert len(adapters) > 0
    assert any(a["adapter_id"] == adapter_id for a in adapters)

    # 4. Delete adapter
    resp = client.delete(f"/api/lora/adapters/{adapter_id}", headers=auth_headers)
    assert resp.status_code == 200

    resp = client.get("/api/lora/adapters")
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

def test_mcp_tools():
    from src.pluto_mcp_server import pluto_train_lora, pluto_list_lora_adapters
    
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
    
