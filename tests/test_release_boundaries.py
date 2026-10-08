"""Regression checks for the release audit; no downloads, GPU jobs or AWS writes."""
import argparse
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest


def test_cli_module_starts_without_circular_import():
    result = subprocess.run([sys.executable, "-m", "spacepilot.cli", "--version"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("backend", ["sglang", "vllm"])
def test_runtime_binds_loopback(backend):
    from spacepilot.services.runtime_manager import build_backend_command
    cmd = build_backend_command(backend, Path("/tmp/weights"), 30010)
    assert cmd[cmd.index("--host") + 1] == "127.0.0.1"


def test_runtime_rejects_arbitrary_python_module():
    from spacepilot.services.runtime_manager import build_backend_command
    with pytest.raises(ValueError, match="backend"):
        build_backend_command("arbitrary", Path("/tmp/weights"), 30010)


def test_live_launch_remains_gated_before_any_aws_call(monkeypatch):
    from spacepilot import cli
    from spacepilot.services import aws_fleet_launcher
    request = MagicMock()
    monkeypatch.setattr(aws_fleet_launcher, "request_spot_instance", request)
    args = argparse.Namespace(model="minimax-h3", gpu="g6e.4xlarge", yes=True, dry_run=False)
    assert cli.cmd_launch(args, {}) == 2
    request.assert_not_called()


def test_service_refuses_live_launch_before_identity_or_write():
    from spacepilot.services.aws_fleet_launcher import request_spot_instance
    client = MagicMock()
    with pytest.raises(ValueError, match="budget"):
        request_spot_instance("g6e.2xlarge", "key", aws_client=client, dry_run=False)
    client.run_aws_command.assert_not_called()


def test_gpu_recommendations_default_to_verified_eight_vcpus():
    from spacepilot.services.gpu_recommender import recommend_gpus
    recommendations = recommend_gpus(32 * 1024**3)
    assert recommendations
    assert all(r.instance_spec.vcpu <= 8 for r in recommendations)


@pytest.mark.parametrize("url", ["http://169.254.169.254/latest/meta-data/", "http://127.0.0.1:8080/private"])
def test_video_rejects_response_url_from_another_origin(tmp_path, url):
    from spacepilot.services.video_client import VideoClient
    with VideoClient("http://198.51.100.10:30010") as client:
        response = httpx.Response(200, json={"url": url}, request=httpx.Request("POST", client.endpoint_url))
        client._client.post = MagicMock(return_value=response)
        client._client.get = MagicMock(return_value=httpx.Response(200, content=b"unsafe", request=httpx.Request("GET", url)))
        with pytest.raises(ValueError, match="origin"):
            client.generate_video("test", "model", tmp_path / "out.mp4")
        client._client.get.assert_not_called()


def test_video_timeout_does_not_download_or_report_success(tmp_path, monkeypatch):
    from spacepilot.services.video_client import VideoClient
    monkeypatch.setattr("spacepilot.services.video_client.time.sleep", lambda _: None)
    with VideoClient("http://198.51.100.10:5000", timeout=0.5) as client:
        client._client.post = MagicMock(return_value=httpx.Response(200, json={"job_id": "job-1"}))
        client._client.get = MagicMock(side_effect=[httpx.Response(200, json={"status": "processing"}), httpx.Response(200, content=b"unsafe")])
        with pytest.raises(TimeoutError):
            client.generate_video("test", "model", tmp_path / "out.mp4")
        assert client._client.get.call_count == 1
        assert not (tmp_path / "out.mp4").exists()


@pytest.mark.parametrize("tool,args", [
    ("spacepilot_download_weights", {"model": "minimax-h3"}),
    ("spacepilot_load_runtime", {"model_id": "qwen3-8", "weights_dir": "/tmp/weights"}),
    ("spacepilot_unload_runtime", {"all_models": True}),
])
def test_mcp_mutations_require_confirmation(tool, args, monkeypatch):
    from spacepilot import mcp_server
    assert getattr(mcp_server, tool)(**args)["status"] == "error"


@pytest.mark.parametrize("escape", ["traversal", "symlink"])
def test_mcp_download_paths_cannot_escape_cache(tmp_path, monkeypatch, escape):
    from spacepilot.mcp_server import spacepilot_download_weights
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr("spacepilot.paths.model_recommender_cache_dir", lambda: cache)
    target = cache / ".." / "outside"
    if escape == "symlink":
        outside = tmp_path / "outside"
        outside.mkdir()
        (cache / "link").symlink_to(outside, target_is_directory=True)
        target = cache / "link" / "weights"
    download = MagicMock()
    monkeypatch.setattr("spacepilot.services.model_downloader.download_weights", download)
    result = spacepilot_download_weights("minimax-h3", dest=str(target), confirmed=True)
    assert result["status"] == "error"
    assert "cache" in result["message"]
    download.assert_not_called()


def test_video_rejects_download_redirect(tmp_path):
    from spacepilot.services.video_client import VideoClient
    with VideoClient("http://198.51.100.10:30010") as client:
        client._client.post = MagicMock(return_value=httpx.Response(200, json={"url": "/out.mp4"}))
        client._client.get = MagicMock(return_value=httpx.Response(302, headers={"location": "http://169.254.169.254/"}))
        with pytest.raises(ValueError, match="redirect"):
            client.generate_video("test", "model", tmp_path / "out.mp4")
        assert client._client.get.call_args.kwargs["follow_redirects"] is False
        assert not (tmp_path / "out.mp4").exists()
