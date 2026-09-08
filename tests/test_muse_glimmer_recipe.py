"""Tests for Muse Glimmer CoreAI Model Recipe with K=4 DFlash Speculative Drafter."""

import pytest
from fastapi.testclient import TestClient
from spacepilot.app import create_app
from spacepilot.core.config import get_settings
from spacepilot.model_registry import load_registry
from spacepilot.services.model_catalog import catalog_manager
from spacepilot.device_probe import probe_local_device
from spacepilot.services.compatibility import assess
from spacepilot.verdict import level_for


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


def test_muse_glimmer_manifest_registry():
    """Verify muse-glimmer-coreai parses cleanly into SpacePilot's model registry."""
    reg = load_registry()
    model = reg.models.get("muse-glimmer-coreai")
    assert model is not None, "muse-glimmer-coreai not found in registry"
    assert model.name == "Muse Glimmer 30B (CoreAI)"
    assert model.kind == "text"
    assert model.family == "muse"
    assert model.license.open_source is True
    assert model.license.spdx == "Apache-2.0"

    variant = reg.variant("muse-glimmer-30b-dflash-k4")
    assert variant is not None, "Variant muse-glimmer-30b-dflash-k4 not found"
    assert variant.params == "29.6B"
    assert variant.precision == "4bit"
    assert variant.backends == ["metal"]
    assert variant.repo == "meta-models/Muse-Glimmer-30B"
    assert variant.is_pinned is True
    assert variant.revision == "a4e59da52a7bc87ae7251dd5545c0dd437c44b68"

    # Provenance facts
    assert variant.download.value >= 15 * (1024 ** 3)
    assert variant.download.source == "huggingface-api"
    assert variant.working_set.value >= 18 * (1024 ** 3)
    assert variant.working_set.source == "estimated"

    # Notes content verification
    notes = variant.notes
    assert "K=4" in notes
    assert "DFlash" in notes
    assert "64%" in notes
    assert "inject_kv" in notes
    assert "draft" in notes
    assert "Heterogeneous Dispatch" in notes
    assert "ANE" in notes
    assert "ATEM" in notes
    assert "reasoning_content" in notes


def test_muse_glimmer_catalog_manager():
    """Verify catalog manager exposes the recipe with correct metadata."""
    recipe = catalog_manager.recipes.get("muse-glimmer-30b-dflash-k4")
    assert recipe is not None
    assert recipe.recipe_id == "muse-glimmer-30b-dflash-k4"
    assert recipe.kind == "text"
    assert recipe.quantization == "4bit"
    assert recipe.backends == ["metal"]
    assert recipe.download_bytes > 0
    assert recipe.working_set_bytes > 0


def test_muse_glimmer_compatibility_assessment():
    """Verify device probe compatibility assessment for Apple Silicon memory profiles."""
    recipe = catalog_manager.recipes["muse-glimmer-30b-dflash-k4"]
    profile = probe_local_device()
    verdict = assess(recipe, profile)
    fit = level_for(verdict)
    assert fit in ("runs_well", "runs_slowly", "wont_fit")


def test_muse_glimmer_api_endpoint(client, auth_headers):
    """Verify the recipe is served over /api/compute/recipes."""
    res = client.get("/api/compute/recipes", headers=auth_headers)
    assert res.status_code == 200
    recipes = res.json()
    muse = next((r for r in recipes if r["recipe_id"] == "muse-glimmer-30b-dflash-k4"), None)
    assert muse is not None
    assert muse["name"] == "Muse Glimmer 30B (4-bit, DFlash K=4 Drafter)"
    assert muse["kind"] == "text"
    assert muse["hf_repo"] == "meta-models/Muse-Glimmer-30B"
    assert muse["backends"] == ["metal"]
