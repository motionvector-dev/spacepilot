"""Unit tests for user preferences and model default GPU persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spacepilot import cli
from spacepilot.services import user_preferences


def test_get_default_gpu_when_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / ".spacepilot_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    assert user_preferences.get_default_gpu("ltx-video") is None
    assert cli.get_default_gpu("ltx-video") is None


def test_set_and_get_default_gpu_persists_to_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / ".spacepilot_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    user_preferences.set_default_gpu("wan-2.1-t2v-14b", "a100-80gb")
    assert config_file.exists()

    # Verify retrieval via both module and CLI
    assert user_preferences.get_default_gpu("wan-2.1-t2v-14b") == "a100-80gb"
    assert cli.get_default_gpu("wan-2.1-t2v-14b") == "a100-80gb"

    # Verify JSON content on disk
    data = json.loads(config_file.read_text(encoding="utf-8"))
    assert data["user_preferences"]["default_gpus"]["wan-2.1-t2v-14b"] == "a100-80gb"
    assert data["default_gpus"]["wan-2.1-t2v-14b"] == "a100-80gb"


def test_set_default_gpu_does_not_clobber_existing_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / ".spacepilot_config.json"
    config_file.write_text(
        json.dumps({
            "aws_profile": "custom-prod",
            "aws_region": "us-west-2",
            "custom_secret_key": "secret-value-123",
            "user_preferences": {
                "theme": "dark",
                "default_gpus": {
                    "existing-model": "l40s"
                }
            }
        }, indent=2)
    )
    monkeypatch.setattr(cli, "CONFIG_FILE", config_file)

    # Add a new model mapping via cli wrapper
    cli.set_default_gpu("ltx-video", "g6e.2xlarge")

    data = json.loads(config_file.read_text(encoding="utf-8"))
    # Verify existing settings were preserved
    assert data["aws_profile"] == "custom-prod"
    assert data["aws_region"] == "us-west-2"
    assert data["custom_secret_key"] == "secret-value-123"
    assert data["user_preferences"]["theme"] == "dark"
    assert data["user_preferences"]["default_gpus"]["existing-model"] == "l40s"
    assert data["user_preferences"]["default_gpus"]["ltx-video"] == "g6e.2xlarge"
    assert data["default_gpus"]["ltx-video"] == "g6e.2xlarge"

    # Verify getters
    assert cli.get_default_gpu("existing-model") == "l40s"
    assert cli.get_default_gpu("ltx-video") == "g6e.2xlarge"
    assert cli.get_default_gpu("nonexistent") is None


def test_explicit_config_path_support(tmp_path: Path) -> None:
    custom_path = tmp_path / "custom_config.json"
    user_preferences.set_default_gpu("hunyuan-video", "h100", config_path=custom_path)
    assert user_preferences.get_default_gpu("hunyuan-video", config_path=custom_path) == "h100"

    data = json.loads(custom_path.read_text(encoding="utf-8"))
    assert data["user_preferences"]["default_gpus"]["hunyuan-video"] == "h100"
