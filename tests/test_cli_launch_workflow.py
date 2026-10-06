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
        gpu="g6e.4xlarge",
        on_demand=False,
        dry_run=True,
        yes=True,
    )
    cfg = {"key_name": "test-key", "key_file": "/path/to/key.pem"}

    exit_code = cli.cmd_launch(args, cfg)

    assert exit_code == 0
    assert len(mock_aws_fleet) == 1
    assert mock_aws_fleet[0]["instance_type"] == "g6e.4xlarge"
    assert mock_aws_fleet[0]["market_type"] == "spot"
    assert mock_aws_fleet[0]["dry_run"] is True


def test_cmd_launch_interactive_flow_with_custom_gpu_and_save_default(mock_aws_fleet, tmp_path, monkeypatch):
    """Interactive flow prompts for model, shows recommendations, accepts custom GPU, and saves preference."""
    config_file = tmp_path / ".spacepilot_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    # 1. Model selection prompt -> choose "minimax-h3" (or substring)
    # 2. GPU prompt -> select "g6e.8xlarge"
    # 3. Save default prompt -> "y"
    user_inputs = iter(["minimax-h3", "g6e.8xlarge", "y"])

    monkeypatch.setattr("builtins.input", lambda prompt="": next(user_inputs))

    args = argparse.Namespace(
        model=None,
        gpu=None,
        on_demand=False,
        dry_run=False,
        yes=False,
    )
    cfg = {"key_name": "test-key", "key_file": "/path/to/key.pem"}

    exit_code = cli.cmd_launch(args, cfg)

    assert exit_code == 0
    assert len(mock_aws_fleet) == 1
    assert mock_aws_fleet[0]["instance_type"] == "g6e.8xlarge"
    assert mock_aws_fleet[0]["market_type"] == "spot"

    # Verify default GPU was saved to config
    saved_gpu = cli.get_default_gpu("minimax-h3")
    assert saved_gpu == "g6e.8xlarge"


def test_cmd_launch_interactive_uses_persisted_default_when_empty_input(mock_aws_fleet, tmp_path, monkeypatch):
    """Interactive flow recommends persisted default GPU and accepts pressing Enter."""
    config_file = tmp_path / ".spacepilot_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)
    cli.set_default_gpu("minimax-h3", "g6e.8xlarge")

    # 1. Model selection -> select "minimax-h3"
    # 2. GPU selection -> select default (Enter -> "")
    # 3. Save preference -> "n"
    user_inputs = iter(["minimax-h3", "", "n"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(user_inputs))

    args = argparse.Namespace(
        model=None,
        gpu=None,
        on_demand=False,
        dry_run=False,
        yes=False,
    )
    cfg = {"key_name": "test-key"}

    exit_code = cli.cmd_launch(args, cfg)

    assert exit_code == 0
    assert len(mock_aws_fleet) == 1
    assert mock_aws_fleet[0]["instance_type"] == "g6e.8xlarge"


def test_cmd_launch_on_demand_flag(mock_aws_fleet, tmp_path, monkeypatch):
    """Passing --on-demand requests on-demand market type."""
    config_file = tmp_path / ".spacepilot_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    args = argparse.Namespace(
        model="minimax-h3-fl2va-fp8",
        gpu="g6e.4xlarge",
        on_demand=True,
        dry_run=False,
        yes=True,
    )
    cfg = {}

    exit_code = cli.cmd_launch(args, cfg)

    assert exit_code == 0
    assert len(mock_aws_fleet) == 1
    assert mock_aws_fleet[0]["instance_type"] == "g6e.4xlarge"
    assert mock_aws_fleet[0]["market_type"] == "ondemand"


def test_cmd_launch_unknown_model_returns_error(mock_aws_fleet, tmp_path, monkeypatch, capsys):
    """Specifying a non-existent model prints error and exits code 1."""
    config_file = tmp_path / ".spacepilot_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    args = argparse.Namespace(
        model="non-existent-fantasy-model",
        gpu=None,
        on_demand=False,
        dry_run=False,
        yes=False,
    )
    cfg = {}

    exit_code = cli.cmd_launch(args, cfg)
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "not found in registry" in captured.out
    assert len(mock_aws_fleet) == 0
