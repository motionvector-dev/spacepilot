import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import httpx

from spacepilot.services.video_client import (
    VideoClient,
    VideoGenerationResult,
)


def test_video_client_init():
    client = VideoClient(endpoint_url="http://1.2.3.4:30010", timeout=120.0)
    assert client.endpoint_url == "http://1.2.3.4:30010"
    assert client.timeout == 120.0


def test_video_client_endpoint_url_strips_trailing_slash():
    client = VideoClient(endpoint_url="http://1.2.3.4:30010/")
    assert client.endpoint_url == "http://1.2.3.4:30010"


def test_generate_video_success_binary_stream(tmp_path):
    output_path = tmp_path / "output.mp4"
    fake_video_bytes = b"\x00\x00\x00\x18ftypmp42" + b"x" * 1024

    progress_events = []

    def progress_cb(step, total):
        progress_events.append((step, total))

    # Mock response returning binary video directly
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {
        "content-type": "video/mp4",
        "x-inference-wall-seconds": "15.0",
        "x-inference-steps": "30",
    }
    mock_response.content = fake_video_bytes
    mock_response.iter_bytes.return_value = [fake_video_bytes]

    client = VideoClient(endpoint_url="http://1.2.3.4:30010")

    with patch.object(client._client, "post", return_value=mock_response) as mock_post:
        result = client.generate_video(
            prompt="A cinematic drone shot of mountains",
            model_id="minimax-h3",
            output_path=output_path,
            steps=30,
            seconds=4.0,
            resolution=(1024, 576),
            seed=42,
            progress_callback=progress_cb,
        )

        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["prompt"] == "A cinematic drone shot of mountains"
        assert call_kwargs["json"]["model"] == "minimax-h3"
        assert call_kwargs["json"]["steps"] == 30
        assert call_kwargs["json"]["seconds"] == 4.0
        assert call_kwargs["json"]["width"] == 1024
        assert call_kwargs["json"]["height"] == 576
        assert call_kwargs["json"]["seed"] == 42

    assert isinstance(result, VideoGenerationResult)
    assert result.output_path == output_path
    assert output_path.exists()
    assert output_path.read_bytes() == fake_video_bytes
    assert result.steps == 30
    assert result.wall_seconds > 0
    assert result.seconds_per_step == pytest.approx(result.wall_seconds / 30, rel=1e-2)
    assert result.model_id == "minimax-h3"


def test_generate_video_success_json_b64_or_url(tmp_path):
    output_path = tmp_path / "output_json.mp4"
    import base64
    fake_video_bytes = b"\x00\x00\x00\x18ftypmp42" + b"b64test"
    b64_str = base64.b64encode(fake_video_bytes).decode("ascii")

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {
        "status": "completed",
        "video_base64": b64_str,
        "wall_seconds": 12.0,
        "steps": 25,
    }

    client = VideoClient(endpoint_url="http://1.2.3.4:30010")

    with patch.object(client._client, "post", return_value=mock_response):
        result = client.generate_video(
            prompt="A cat jumping",
            model_id="wan-2.1-t2v-14b",
            output_path=output_path,
            steps=25,
        )

    assert result.output_path == output_path
    assert output_path.read_bytes() == fake_video_bytes
    assert result.steps == 25
    assert result.wall_seconds == 12.0
    assert result.seconds_per_step == pytest.approx(12.0 / 25, rel=1e-3)
    assert result.model_id == "wan-2.1-t2v-14b"


def test_generate_video_worker_poll_and_download(tmp_path):
    output_path = tmp_path / "output_worker.mp4"
    fake_video_bytes = b"\x00\x00\x00\x18ftypmp42" + b"workerbytes"

    # Simulates remote worker protocol: POST /generate returns {job_id: "xyz"},
    # GET /status/xyz returns progress then completed,
    # GET /download/xyz returns binary mp4.
    mock_post_resp = MagicMock(spec=httpx.Response)
    mock_post_resp.status_code = 200
    mock_post_resp.headers = {"content-type": "application/json"}
    mock_post_resp.json.return_value = {"job_id": "job-123", "status": "queued"}

    mock_status_prog = MagicMock(spec=httpx.Response)
    mock_status_prog.status_code = 200
    mock_status_prog.json.return_value = {"status": "processing", "step": 10, "total_steps": 30}

    mock_status_done = MagicMock(spec=httpx.Response)
    mock_status_done.status_code = 200
    mock_status_done.json.return_value = {
        "status": "completed",
        "step": 30,
        "total_steps": 30,
        "wall_seconds": 18.0,
    }

    mock_download = MagicMock(spec=httpx.Response)
    mock_download.status_code = 200
    mock_download.headers = {"content-type": "video/mp4"}
    mock_download.content = fake_video_bytes

    client = VideoClient(endpoint_url="http://1.2.3.4:5000")

    progress_log = []
    def on_progress(step, total):
        progress_log.append((step, total))

    with patch.object(client._client, "post", return_value=mock_post_resp) as mock_post, \
         patch.object(client._client, "get", side_effect=[mock_status_prog, mock_status_done, mock_download]) as mock_get:
        result = client.generate_video(
            prompt="A running river",
            model_id="ltx-video",
            output_path=output_path,
            steps=30,
            progress_callback=on_progress,
        )

    assert result.output_path.read_bytes() == fake_video_bytes
    assert (10, 30) in progress_log
    assert result.wall_seconds == 18.0
    assert result.steps == 30
    assert result.seconds_per_step == pytest.approx(18.0 / 30, rel=1e-3)


def test_generate_video_handles_http_error(tmp_path):
    output_path = tmp_path / "output_fail.mp4"
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error: CUDA OOM"
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError("OOM", request=MagicMock(), response=mock_response)

    client = VideoClient(endpoint_url="http://1.2.3.4:30010")

    with patch.object(client._client, "post", return_value=mock_response):
        with pytest.raises(RuntimeError) as exc_info:
            client.generate_video(
                prompt="fail prompt",
                model_id="minimax-h3",
                output_path=output_path,
            )
        assert "Generation failed" in str(exc_info.value)
