"""Tests for Model Recipes and Automated Quantized Weights Importer."""

import pytest
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


def test_list_recipes_endpoint(client):
    res = client.get("/api/compute/recipes")
    assert res.status_code == 200
    recipes = res.json()
    assert len(recipes) >= 5
    ids = [r["recipe_id"] for r in recipes]
    assert "wan-2.1-1.3b-fp8" in ids
    assert "wan-2.1-14b-fp8" in ids
    assert "hunyuan-video-gguf-q4" in ids
    assert "deepseek-r1-distill-qwen-8b-gguf" in ids


def test_download_recipe_flow(client, auth_headers):
    # 1. Trigger download
    res = client.post("/api/compute/recipes/wan-2.1-1.3b-fp8/download", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["job_id"] == "wan-2.1-1.3b-fp8"
    assert data["status"] == "pending"

    # 2. Check progress
    res = client.get("/api/compute/recipes/wan-2.1-1.3b-fp8/progress")
    assert res.status_code == 200
    prog = res.json()
    assert prog["recipe_id"] == "wan-2.1-1.3b-fp8"
    assert "progress_percent" in prog


def test_download_auth_gate(client):
    # Missing token fails closed with 401
    res = client.post("/api/compute/recipes/wan-2.1-1.3b-fp8/download")
    assert res.status_code == 401


def test_download_invalid_recipe_404(client, auth_headers):
    res = client.post("/api/compute/recipes/nonexistent-model/download", headers=auth_headers)
    assert res.status_code == 404
