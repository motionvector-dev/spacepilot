"""Tests for Model Recipes and Automated Quantized Weights Importer."""

import pytest
from unittest import mock
from fastapi.testclient import TestClient
from spacepilot.app import create_app
from spacepilot.core.config import get_settings
from spacepilot.services.model_catalog import catalog_manager


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


def test_list_recipes_auth_gate(client):
    res = client.get("/api/compute/recipes")
    assert res.status_code == 401

def test_list_recipes_endpoint(client, auth_headers):
    res = client.get("/api/compute/recipes", headers=auth_headers)
    assert res.status_code == 200
    recipes = res.json()
    assert len(recipes) >= 5
    ids = [r["recipe_id"] for r in recipes]
    assert "wan-2-1-t2v-1-3b" in ids
    assert "wan-2-1-t2v-14b" in ids
    
    # Every repo id must be one that actually exists on the Hub. Six of the
    # original seven were invented and 401'd; a catalog of unfetchable models
    # fails only at download time, in front of the user.
    for r in recipes:
        assert r["hf_repo"], f"{r['recipe_id']} has no repo"
        assert r["hf_repo"].count("/") == 1, f"{r['recipe_id']}: {r['hf_repo']}"
        assert r["download_bytes"], f"{r['recipe_id']} has no measured size"

    required = {
        "recipe_id", "name", "family", "kind", "quantization", "hf_repo",
        "download_bytes", "working_set_bytes", "backends", "license",
        "is_local_runnable", "caveats",
    }
    assert required <= set(recipes[0].keys())
    distil = next(r for r in recipes if r["recipe_id"] == "distil-large-v3-ggml")
    assert distil["caveats"][0]["capability"] == "audio.transcription"
    assert distil["caveats"][0]["provenance"] == "declared"


def test_widened_fleet_recipes_are_listed(client, auth_headers):
    """deepseek-v4-flash, qwen3-6-27b and gemma4-31b must surface through the
    same recipe list every other registered model does — no second catalog."""
    res = client.get("/api/compute/recipes", headers=auth_headers)
    assert res.status_code == 200
    by_id = {r["recipe_id"]: r for r in res.json()}

    deepseek = by_id["deepseek-v4-flash-2bit-dq"]
    assert deepseek["hf_repo"] == "mlx-community/DeepSeek-V4-Flash-2bit-DQ"
    assert "metal" in deepseek["backends"]

    qwen = by_id["qwen3-6-27b-4bit"]
    assert qwen["hf_repo"] == "mlx-community/Qwen3.6-27B-4bit"
    assert qwen["license"] == "apache-2.0"

    gemma = by_id["gemma4-31b-it-4bit"]
    assert gemma["hf_repo"] == "mlx-community/gemma-4-31B-it-4bit"
    # Gemma's Apache grant incorporates a prohibited-use policy by reference,
    # so the registry carries a restriction note even though the id is apache-2.0.
    assert gemma["license_note"], "expected the prohibited-use restriction to surface"


def test_compatibility_report_carries_registry_caveats(client):
    res = client.get("/api/compute/compatibility")
    assert res.status_code == 200
    distil = next(r for r in res.json()["models"] if r["recipe_id"] == "distil-large-v3-ggml")
    assert distil["caveats"][0]["capability"] == "audio.transcription"


@mock.patch("spacepilot.services.model_catalog.asyncio.create_task")
def test_download_recipe_flow(mock_create_task, client, auth_headers):
    # 1. Trigger download
    res = client.post("/api/compute/recipes/wan-2-1-t2v-1-3b/download", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["job_id"] == "wan-2-1-t2v-1-3b"
    assert data["status"] == "pending"
    assert mock_create_task.called

    # 2. Check progress
    res = client.get("/api/compute/recipes/wan-2-1-t2v-1-3b/progress", headers=auth_headers)
    assert res.status_code == 200
    prog = res.json()
    assert prog["recipe_id"] == "wan-2-1-t2v-1-3b"
    assert "progress_percent" in prog
    assert prog["status"] == "pending"


def test_download_auth_gate(client):
    # Missing token fails closed with 401
    res = client.post("/api/compute/recipes/wan-2-1-t2v-1-3b/download")
    assert res.status_code == 401
    
    res2 = client.get("/api/compute/recipes/wan-2-1-t2v-1-3b/progress")
    assert res2.status_code == 401


def test_download_invalid_recipe_404(client, auth_headers):
    res = client.post("/api/compute/recipes/nonexistent-model/download", headers=auth_headers)
    assert res.status_code == 404
