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
        "is_local_runnable",
    }
    assert required <= set(recipes[0].keys())


@mock.patch("src.pluto.services.model_catalog.asyncio.create_task")
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
