"""Tests for Model Recipes and Automated Quantized Weights Importer."""

import pytest
from unittest import mock
from fastapi.testclient import TestClient
from src.pluto.app import create_app
from src.pluto.core.config import get_settings
from src.pluto.services.model_catalog import catalog_manager


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
    assert "wan-2.1-1.3b-fp8" in ids
    assert "wan-2.1-14b-fp8" in ids
    
    # Assert response structure
    first_recipe = recipes[0]
    expected_keys = {
        "recipe_id", "name", "family", "size_gb", "min_vram_gb",
        "quantization", "hf_repo", "download_url", "recommended_gpu", "is_local_runnable"
    }
    assert set(first_recipe.keys()) == expected_keys


@mock.patch("src.pluto.services.model_catalog.asyncio.create_task")
def test_download_recipe_flow(mock_create_task, client, auth_headers):
    # 1. Trigger download
    res = client.post("/api/compute/recipes/wan-2.1-1.3b-fp8/download", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["job_id"] == "wan-2.1-1.3b-fp8"
    assert data["status"] == "pending"
    assert data["mock"] is True
    assert mock_create_task.called

    # 2. Check progress
    res = client.get("/api/compute/recipes/wan-2.1-1.3b-fp8/progress", headers=auth_headers)
    assert res.status_code == 200
    prog = res.json()
    assert prog["recipe_id"] == "wan-2.1-1.3b-fp8"
    assert "progress_percent" in prog
    assert prog["status"] == "pending"


def test_download_auth_gate(client):
    # Missing token fails closed with 401
    res = client.post("/api/compute/recipes/wan-2.1-1.3b-fp8/download")
    assert res.status_code == 401
    
    res2 = client.get("/api/compute/recipes/wan-2.1-1.3b-fp8/progress")
    assert res2.status_code == 401


def test_download_invalid_recipe_404(client, auth_headers):
    res = client.post("/api/compute/recipes/nonexistent-model/download", headers=auth_headers)
    assert res.status_code == 404
