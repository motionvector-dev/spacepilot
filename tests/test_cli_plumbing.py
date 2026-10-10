"""Unit tests for SpacePilot CLI plumbing commands: download, load, unload."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from spacepilot import cli


def test_cmd_download_calls_model_downloader(tmp_path):
    """spacepilot download --model minimax-h3-fl2va-fp8 --stage stage1 --dest /tmp/test calls download_weights."""
    args = argparse.Namespace(
        model="minimax-h3-fl2va-fp8",
        stage="stage1",
        dest=str(tmp_path / "test"),
        concurrency=8,
    )
    cfg = {}

    with patch("spacepilot.services.model_downloader.download_weights") as mock_download:
        mock_download.return_value = tmp_path / "test"
        rc = cli.cmd_download(args, cfg)

        assert rc == 0
        mock_download.assert_called_once_with(
            variant="minimax-h3-fl2va-fp8",
            dest_dir=Path(tmp_path / "test"),
            stage="stage1",
            concurrency=8,
        )


def test_cmd_load_calls_runtime_manager(tmp_path):
    """spacepilot load --model minimax-h3-fl2va-fp8 --backend sglang --port 30010 calls load_model."""
    weights_path = tmp_path / "weights"
    weights_path.mkdir(parents=True, exist_ok=True)

    args = argparse.Namespace(
        model="minimax-h3-fl2va-fp8",
        weights_dir=str(weights_path),
        backend="sglang",
        port=30010,
        tp=1,
        skip_healthcheck=True,
    )
    cfg = {}

    with patch("spacepilot.services.runtime_manager.load_model") as mock_load:
        mock_load.return_value = {
            "model_id": "minimax-h3-fl2va-fp8",
            "weights_dir": str(weights_path),
            "backend": "sglang",
            "port": 30010,
            "pid": 99999,
            "healthy": True,
        }
        rc = cli.cmd_load(args, cfg)

        assert rc == 0
        mock_load.assert_called_once_with(
            model_id="minimax-h3-fl2va-fp8",
            weights_dir=Path(weights_path),
            backend="sglang",
            port=30010,
            tp=1,
            skip_healthcheck=True,
        )


def test_cmd_unload_specific_model():
    """spacepilot unload --model minimax-h3-fl2va-fp8 calls unload_model with model_id."""
    args = argparse.Namespace(
        model="minimax-h3-fl2va-fp8",
        port=None,
        all=False,
    )
    cfg = {}

    with patch("spacepilot.services.runtime_manager.unload_model") as mock_unload:
        mock_unload.return_value = {
            "status": "ok",
            "unloaded_count": 1,
            "unloaded": [{"model_id": "minimax-h3-fl2va-fp8", "pid": 1234}],
        }
        rc = cli.cmd_unload(args, cfg)

        assert rc == 0
        mock_unload.assert_called_once_with(
            model_id="minimax-h3-fl2va-fp8",
            port=None,
            all_models=False,
        )


def test_cmd_unload_all():
    """spacepilot unload --all calls unload_model with all_models=True."""
    args = argparse.Namespace(
        model=None,
        port=None,
        all=True,
    )
    cfg = {}

    with patch("spacepilot.services.runtime_manager.unload_model") as mock_unload:
        mock_unload.return_value = {
            "status": "ok",
            "unloaded_count": 3,
            "unloaded": [],
        }
        rc = cli.cmd_unload(args, cfg)

        assert rc == 0
        mock_unload.assert_called_once_with(
            model_id=None,
            port=None,
            all_models=True,
        )
