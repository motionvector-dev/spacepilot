"""End-to-end unit tests for SpacePilot CLI launch workflow."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

import pytest

from spacepilot import cli
from spacepilot.services import aws_fleet_launcher


@pytest.fixture
def mock_aws_fleet(monkeypatch):
    """Mock AWS request_spot_instance to avoid real AWS EC2 calls."""
    calls = []

    def fake_request_spot_instance(
        instance_type: str,
        key_name: str,
        *,
        key_file: str | None = None,
        market_type: str = "spot",
        dry_run: bool = False,
        **kwargs: Any,
    ):
        telemetry = aws_fleet_launcher.InstanceConnectionTelemetry(
            instance_id="i-test12345678",
            state="running" if not dry_run else "dry_run",
            public_ip="198.51.100.42",
            instance_type=instance_type,
            ssh_user="ubuntu",
            ssh_command=f"ssh -i {key_file} ubuntu@198.51.100.42" if key_file else "ssh ubuntu@198.51.100.42",
            tunnel_command=f"ssh -i {key_file} -L 5000:localhost:5000 ubuntu@198.51.100.42" if key_file else "ssh -L 5000:localhost:5000 ubuntu@198.51.100.42",
            dry_run=dry_run,
        )
        calls.append({
            "instance_type": instance_type,
            "key_name": key_name,
            "key_file": key_file,
            "market_type": market_type,
            "dry_run": dry_run,
            "telemetry": telemetry,
        })
        return telemetry

    monkeypatch.setattr(aws_fleet_launcher, "request_spot_instance", fake_request_spot_instance)
    return calls


def test_cmd_launch_non_interactive_bypasses_prompts(mock_aws_fleet, tmp_path, monkeypatch):
    """Passing --model and --gpu directly bypasses all input prompts and launches."""
    config_file = tmp_path / ".spacepilot_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    def fail_on_input(prompt=""):
        pytest.fail(f"Unexpected interactive input requested: {prompt}")

    monkeypatch.setattr("builtins.input", fail_on_input)

    args = argparse.Namespace(
        model="minimax-h3",
        gpu="g6e.2xlarge",
        on_demand=False,
        dry_run=True,
        yes=True,
    )
    cfg = {"key_name": "test-key", "key_file": "/path/to/key.pem"}

    exit_code = cli.cmd_launch(args, cfg)

    assert exit_code == 0
    assert len(mock_aws_fleet) == 1
    assert mock_aws_fleet[0]["instance_type"] == "g6e.2xlarge"
    assert mock_aws_fleet[0]["market_type"] == "spot"
    assert mock_aws_fleet[0]["dry_run"] is True


@pytest.mark.parametrize("gpu", ["g6e.4xlarge", "unknown"])
def test_explicit_gpu_cannot_bypass_quota(mock_aws_fleet, gpu):
    args = argparse.Namespace(model="minimax-h3", gpu=gpu, dry_run=True, yes=True, on_demand=False)
    assert cli.cmd_launch(args, {}) == 1
    assert mock_aws_fleet == []


def test_live_launch_refuses_even_with_yes(mock_aws_fleet):
    args = argparse.Namespace(model="minimax-h3", gpu="g6e.2xlarge", dry_run=False, yes=True)
    assert cli.cmd_launch(args, {}) == 2
    assert mock_aws_fleet == []


def test_cmd_launch_unknown_model_returns_error(mock_aws_fleet, tmp_path, monkeypatch, capsys):
    """Specifying a non-existent model prints error and exits code 1."""
    config_file = tmp_path / ".spacepilot_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    args = argparse.Namespace(
        model="non-existent-fantasy-model",
        gpu=None,
        on_demand=False,
        dry_run=True,
        yes=False,
    )
    cfg = {}

    exit_code = cli.cmd_launch(args, cfg)
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "not found in registry" in captured.out
    assert len(mock_aws_fleet) == 0
