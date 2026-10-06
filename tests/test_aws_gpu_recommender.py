"""Unit tests for AWS GPU recommender service."""

import pytest
from spacepilot.model_registry import Variant, License, Fact, Speed
from spacepilot.services.gpu_recommender import (
    AWS_GPU_CATALOG,
    AWSInstanceSpec,
    GPURecommendation,
    recommend_gpus,
)


def make_dummy_variant(variant_id: str, working_set_bytes: int, precision: str = "fp8") -> Variant:
    return Variant(
        id=variant_id,
        model_id="test-model",
        name="Test Model",
        kind="video",
        family="minimax",
        license=License("apache-2.0", "Apache 2.0"),
        repo="test/repo",
        files=None,
        backends=["torch"],
        download=Fact(value=10 * 1024**3, source="flown"),
        working_set=Fact(value=working_set_bytes, source="flown"),
        precision=precision,
    )


def test_catalog_entries_and_specs():
    """Verify all required instance types are present within 64 vCPU limit."""
    expected_instances = [
        "g6e.4xlarge",
        "g6e.8xlarge",
        "g6e.12xlarge",
        "g5.2xlarge",
        "g5.4xlarge",
        "g6.4xlarge",
    ]
    for inst in expected_instances:
        assert inst in AWS_GPU_CATALOG
        spec = AWS_GPU_CATALOG[inst]
        assert spec.vcpu <= 64, f"{inst} exceeds 64 vCPU quota"
        assert spec.total_vram_gb > 0
        assert spec.spot_hourly_usd > 0


def test_recommend_by_working_set_bytes_fits_24gb():
    """Model requiring ~16GB working set should fit on g5.2xlarge, g6.4xlarge, etc."""
    # 16 GB working set
    ws_bytes = 16 * 1024**3
    recs = recommend_gpus(target=ws_bytes, precision="fp8")
    assert len(recs) > 0
    types = [r.instance_type for r in recs]
    assert "g5.2xlarge" in types
    assert "g6e.4xlarge" in types

    # Best recommendation should have positive vram margin
    top = recs[0]
    assert top.fits_vram is True
    assert top.vram_margin_gb >= 0


def test_recommend_by_variant_fp8_32gb():
    """32GB working set variant (e.g. minimax-h3-fl2va-fp8) needs >= 32GB VRAM."""
    variant = make_dummy_variant("minimax-h3-fl2va-fp8", working_set_bytes=32 * 1024**3, precision="fp8")
    recs = recommend_gpus(target=variant)

    assert len(recs) > 0
    # Instances with < 32GB VRAM (like g5.2xlarge, g5.4xlarge, g6.4xlarge with 24GB) should NOT fit pure VRAM
    fitting_types = [r.instance_type for r in recs]
    assert "g6e.4xlarge" in fitting_types
    assert "g6e.8xlarge" in fitting_types
    assert "g6e.12xlarge" in fitting_types
    assert "g5.2xlarge" not in fitting_types
    assert "g6.4xlarge" not in fitting_types

    # Top recommendation should be g6e.4xlarge (lowest cost that fits 32GB pure VRAM)
    assert recs[0].instance_type == "g6e.4xlarge"
    assert recs[0].vram_margin_gb == 16.0  # 48 - 32


def test_recommend_large_model_bf16_tp4():
    """64GB aggregate VRAM variant requires multi-GPU (g6e.12xlarge with 192GB)."""
    ws_bytes = 64 * 1024**3
    recs = recommend_gpus(target=ws_bytes, precision="bf16")

    # Only g6e.12xlarge has 192GB VRAM (all others have <= 48GB)
    assert len(recs) == 1
    assert recs[0].instance_type == "g6e.12xlarge"
    assert recs[0].instance_spec.gpu_count == 4
    assert recs[0].vram_margin_gb == 128.0


def test_recommend_host_ram_offload():
    """Model requiring 44GB VRAM and 128GB host RAM offload."""
    ws_bytes = 44 * 1024**3
    host_ram_bytes = 128 * 1024**3

    recs = recommend_gpus(
        target=ws_bytes,
        precision="bf16",
        host_ram_required_bytes=host_ram_bytes,
    )
    # g6e.4xlarge only has 64GB host RAM, so only g6e.8xlarge (128GB) and g6e.12xlarge (192GB) qualify
    rec_types = [r.instance_type for r in recs]
    assert "g6e.8xlarge" in rec_types
    assert "g6e.12xlarge" in rec_types
    assert "g6e.4xlarge" not in rec_types

    # g6e.8xlarge should be ranked higher due to lower hourly cost than g6e.12xlarge
    assert recs[0].instance_type == "g6e.8xlarge"


def test_quota_filtering():
    """Instances exceeding max vCPU quota are filtered out."""
    ws_bytes = 20 * 1024**3
    # If quota is strictly 16 vCPUs, 32 and 48 vCPU instances must be excluded
    recs = recommend_gpus(target=ws_bytes, max_vcpu_quota=16)
    rec_types = [r.instance_type for r in recs]
    assert "g6e.8xlarge" not in rec_types   # 32 vCPU
    assert "g6e.12xlarge" not in rec_types  # 48 vCPU
    assert "g6e.4xlarge" in rec_types       # 16 vCPU
    assert "g5.2xlarge" in rec_types        # 8 vCPU


def test_recommendation_serialization():
    """Verify to_dict returns formatted telemetry."""
    recs = recommend_gpus(target=20 * 1024**3)
    d = recs[0].to_dict()
    assert "instance_type" in d
    assert "spot_hourly_usd" in d
    assert "vram_margin_gb" in d
    assert "generation_speed_s_per_step" in d
    assert "cost_performance_score" in d
