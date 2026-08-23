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
    orch = SkyPilotOrchestrator()
    
    # 1. Schedule a spot cluster
    res = orch.schedule_spot_task(
        task_name="spacepilot-cinematic",
        provider="lambda",
        accelerator="L40S:1",
        use_spot=True,
        auto_failover=True,
    )
    assert res["status"] == "scheduled"
    assert res["provider"] == "lambda"
    
    status = orch.get_status()
    assert status["active"] is True
    assert status["provider"] == "lambda"
    assert status["preemption_failover_count"] == 0

    # 2. Trigger preemption failover
    failover_res = orch.trigger_preemption_failover(reason="AWS spot preemption notice")
    assert failover_res["status"] == "recovered"
    assert failover_res["failover"]["source_provider"] == "lambda"
    assert failover_res["failover"]["target_provider"] != "lambda"
    assert failover_res["failover"]["downtime_seconds"] <= 2.0
    assert "r2://" in failover_res["failover"]["checkpoint_restored_from"]

    # 3. Status reflects failover count
    status_after = orch.get_status()
    assert status_after["preemption_failover_count"] == 1
    assert status_after["last_failover"] is not None

    # 4. Terminate
    term = orch.terminate_cluster()
    assert term["status"] == "terminated"
    assert orch.get_status()["active"] is False
