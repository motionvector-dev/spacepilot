"""Tests for MiniMax-H3 model registration and schema compliance."""

from pathlib import Path
import pytest

from spacepilot.model_registry import (
    MOVING_REFS,
    SCHEMA_VERSION,
    SOURCES,
    Registry,
    load_registry,
    parse_model,
)


def _load_registry_or_class():
    """Load registry using Registry.load() if available, else load_registry()."""
    if hasattr(Registry, "load") and callable(getattr(Registry, "load")):
        return Registry.load()
    return load_registry()


def test_minimax_h3_loads_via_registry():
    """Verify minimax-h3 is present and loaded via Registry.load() or load_registry()."""
    reg = _load_registry_or_class()
    model = reg.model("minimax-h3")
    assert model is not None, "minimax-h3 model not found in registry"
    assert model.id == "minimax-h3"
    assert model.family == "minimax"
    assert model.kind == "video"
    assert model.license.open_source is False
    assert model.license.id == "minimax-h3-community-license-agreement"
    assert len(model.license.restrictions) == 1
    assert "commercial-use" in model.license.restrictions[0]


def test_minimax_h3_variants_compliance():
    """Verify all 3 variants exist and match required schema specification."""
    reg = _load_registry_or_class()
    model = reg.model("minimax-h3")
    assert model is not None

    variant_ids = {v.id for v in model.variants}
    expected_ids = {
        "minimax-h3-fl2va-fp8",
        "minimax-h3-fl2va-bf16-offload",
        "minimax-h3-fl2va-bf16-tp4",
    }
    assert variant_ids == expected_ids, f"Variants mismatch: {variant_ids} != {expected_ids}"

    # 1. FP8 variant (~32GB working set)
    v_fp8 = reg.variant("minimax-h3-fl2va-fp8")
    assert v_fp8 is not None
    assert v_fp8.precision == "fp8"
    assert v_fp8.backends == ["cuda"]
    assert v_fp8.is_pinned is True
    assert v_fp8.revision.lower() not in MOVING_REFS
    assert len(v_fp8.revision) == 40
    assert v_fp8.working_set.value == 32 * (1024 ** 3)
    assert v_fp8.working_set.source in SOURCES
    assert "g6e.4xlarge" in v_fp8.notes and "g6e.8xlarge" in v_fp8.notes

    # 2. BF16 Offload variant (~44GB VRAM + 128GB RAM)
    v_offload = reg.variant("minimax-h3-fl2va-bf16-offload")
    assert v_offload is not None
    assert v_offload.precision == "bf16"
    assert v_offload.backends == ["cuda"]
    assert v_offload.is_pinned is True
    assert v_offload.revision.lower() not in MOVING_REFS
    assert len(v_offload.revision) == 40
    assert v_offload.working_set.value == 44 * (1024 ** 3)
    assert v_offload.working_set.source in SOURCES
    assert "g6e.8xlarge" in v_offload.notes

    # 3. BF16 TP4 variant (~64GB aggregate VRAM)
    v_tp4 = reg.variant("minimax-h3-fl2va-bf16-tp4")
    assert v_tp4 is not None
    assert v_tp4.precision == "bf16"
    assert v_tp4.backends == ["cuda"]
    assert v_tp4.is_pinned is True
    assert v_tp4.revision.lower() not in MOVING_REFS
    assert len(v_tp4.revision) == 40
    assert v_tp4.working_set.value == 64 * (1024 ** 3)
    assert v_tp4.working_set.source in SOURCES
    assert "g6e.12xlarge" in v_tp4.notes


def test_minimax_h3_yaml_direct_schema_parse():
    """Verify parsing the raw YAML file directly conforms to Schema 1."""
    import yaml
    yaml_path = Path("spacepilot/registry/models/minimax-h3.yaml")
    assert yaml_path.exists(), f"Missing yaml at {yaml_path}"

    raw = yaml.safe_load(yaml_path.read_text())
    assert raw["schema"] == SCHEMA_VERSION
    model = parse_model(raw, yaml_path.name)
    assert model.id == "minimax-h3"
    assert len(model.variants) == 3
