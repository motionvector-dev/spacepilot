import pytest
import time
from fastapi.testclient import TestClient
from spacepilot.app import create_app
from spacepilot.core.config import get_settings
from spacepilot.services.lora import lora_manager

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
    # Gated 2026-08-24: training was a simulation (fake loss curve, no real
    # checkpoint). /train must return 501, not a fake running job.
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
    assert resp.status_code == 501

    # Listing adapters still works — it is just empty — and stays honest.
    resp = client.get("/api/lora/adapters", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

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
    from spacepilot.mcp_server import (
        spacepilot_list_lora_adapters,
        spacepilot_train_lora,
    )
    
    # Train
    job_res = spacepilot_train_lora(
        name="MCPStyle",
        base_model="ltx-video",
        image_paths=["/tmp/a.jpg"],
        trigger_word="mcpstyle"
    )
    # Gated: training raises, and the MCP tool surfaces the error, not fake success.
    assert job_res["status"] == "error"
    assert "not implemented" in job_res.get("message", "").lower()

    # List
    list_res = spacepilot_list_lora_adapters()
    assert "adapters" in list_res
