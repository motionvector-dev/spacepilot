#!/usr/bin/env python3
"""Unit tests for SpacePilot SkyPilot Multi-Cloud Spot Orchestrator."""

import pytest
from spacepilot.skypilot_orchestrator import (
    SkyPilotOrchestrator,
    generate_skypilot_yaml,
    DEFAULT_CLOUD_CATALOG,
)


def test_skypilot_catalog_and_arbitrage():
    orch = SkyPilotOrchestrator()
    assert len(orch.catalog) >= 12

    # Verify sort by spot price
    matrix = orch.get_arbitrage_matrix(sort_by="spot_price")
    prices = [c["spot_price_usd"] for c in matrix]
    assert prices == sorted(prices)
    assert any(c["is_cheapest"] for c in matrix)

    # Verify minimum VRAM filtering
    best_high_vram = orch.get_cheapest_cloud(min_vram_gb=80)
    assert best_high_vram["vram_gb"] >= 80


def test_generate_skypilot_yaml():
    yaml_str = generate_skypilot_yaml(
        task_name="test-worker",
        accelerators="A100:1",
        cloud="oci",
        use_spot=True,
        spot_recovery="failover",
        disk_size=200,
    )
    assert "name: test-worker" in yaml_str
    assert "cloud: oci" in yaml_str
    assert "accelerators: A100:1" in yaml_str
    assert "use_spot: true" in yaml_str
    assert "spot_recovery: failover" in yaml_str
    assert "disk_size: 200" in yaml_str
    assert "r2://spacepilot-checkpoints" in yaml_str


def test_skypilot_schedule_and_preemption_failover():
    """Gated 2026-08-24: scheduling and failover fabricated cluster state (mock
    198.51.x IPs, a fixed 1.4s downtime) with no cloud call. They must raise
    NotImplementedError now, not return a fake success payload."""
    import pytest
    orch = SkyPilotOrchestrator()
    with pytest.raises(NotImplementedError):
        orch.schedule_spot_task(task_name="spacepilot-cinematic", provider="lambda")
    with pytest.raises(NotImplementedError):
        orch.trigger_preemption_failover(reason="AWS spot preemption notice")
