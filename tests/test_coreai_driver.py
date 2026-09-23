"""Core AI driver parsing and route checks. No model load."""

import os
from pathlib import Path

from spacepilot.drivers.coreai_driver import CoreAIDriver


def test_parse_reads_the_runner_summary():
    stdout = (
        " done in 0.400s\n"
        "Generating...\n"
        "Paris\n"
        "\nPerformance Summary:\n"
        "Prompt:     10.0ms, 17 tokens, 40.0 tokens/sec\n"
        "Generation: 20.0ms, 4 tokens, 50.0 tokens/sec\n"
        "Total:      0.500s\n"
    )
    result = CoreAIDriver._parse(stdout, peak_memory_gb=1.5, load_seconds=0.001)
    assert result["text"] == "Paris"
    assert result["prompt_tokens"] == 17
    assert result["generation_tokens"] == 4
    assert result["generation_tps"] == 50.0
    assert result["prompt_tps"] == 40.0
    assert result["wall_seconds"] == 0.5
    assert result["load_seconds"] == 0.4
    assert result["runtime_id"] == "coreai"


def test_route_status_needs_a_runner_and_a_bundle(tmp_path: Path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "metadata.json").write_text("{}")
    (bundle / "model.aimodel").mkdir()
    runner = tmp_path / "llm-runner"
    runner.write_text("#!/bin/sh\n")
    runner.chmod(0o755)
    driver = CoreAIDriver(
        runner_bin=str(runner), bundle_dir=str(bundle), python_bin="python3",
    )
    ready, detail = driver.route_status()
    assert ready, detail
    os.chmod(runner, 0o644)
    ready, detail = driver.route_status()
    assert not ready
    assert "llm-runner" in detail
