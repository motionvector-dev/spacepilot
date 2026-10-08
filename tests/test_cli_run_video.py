import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from spacepilot import cli
from spacepilot.services.video_client import VideoGenerationResult


def test_cli_parser_run_video():
    parser = cli.build_parser()
    args = parser.parse_args([
        "run", "video",
        "--prompt", "test scene",
        "--model", "minimax-h3",
        "--box", "192.168.1.100",
        "--steps", "25",
        "--seconds", "5.0",
        "--resolution", "1280", "720",
        "--output", "/tmp/test.mp4",
        "--open",
    ])
    assert args.command == "run"
    assert args.run_workload == "video"
    assert args.prompt == "test scene"
    assert args.model == "minimax-h3"
    assert args.box == "192.168.1.100"
    assert args.steps == 25
    assert args.seconds == 5.0
    assert args.resolution == [1280, 720]
    assert args.output == "/tmp/test.mp4"
    assert args.open is True


def test_cli_run_video_execution(tmp_path, capsys):
    out_file = tmp_path / "vid.mp4"
    fake_result = VideoGenerationResult(
        output_path=out_file,
        wall_seconds=14.5,
        steps=30,
        seconds_per_step=14.5 / 30,
        model_id="minimax-h3",
    )

    args = type("Args", (), {
        "command": "run",
        "run_workload": "video",
        "prompt": "test scene",
        "model": "minimax-h3",
        "box": None,
        "steps": 30,
        "seconds": 4.0,
        "resolution": None,
        "output": str(out_file),
        "open": False,
    })()

    mock_client_instance = MagicMock()
    mock_client_instance.generate_video.return_value = fake_result

    with patch("spacepilot.cli.get_instance_info", return_value={"ip": "1.2.3.4", "state": "running"}), \
         patch("spacepilot.services.video_client.VideoClient", return_value=mock_client_instance):
        exit_code = cli.cmd_run(args, {})

    assert exit_code == 0
    mock_client_instance.generate_video.assert_called_once()
    captured = capsys.readouterr().out
    assert "prompt      test scene" in captured
    assert "endpoint    http://1.2.3.4:30010" in captured
    assert "completed   minimax-h3" in captured
    assert "wall        14.500s" in captured
    assert "step speed  0.483s/step" in captured


def test_cli_run_video_explicit_box(tmp_path, capsys):
    out_file = tmp_path / "vid2.mp4"
    fake_result = VideoGenerationResult(
        output_path=out_file,
        wall_seconds=10.0,
        steps=20,
        seconds_per_step=0.5,
        model_id="wan-2.1",
    )

    args = type("Args", (), {
        "command": "run",
        "run_workload": "video",
        "prompt": "flying eagle",
        "model": "wan-2.1",
        "box": "10.0.0.5:5000",
        "steps": 20,
        "seconds": 2.0,
        "resolution": [1280, 720],
        "output": str(out_file),
        "open": False,
    })()

    mock_client_instance = MagicMock()
    mock_client_instance.generate_video.return_value = fake_result

    with patch("spacepilot.services.video_client.VideoClient", return_value=mock_client_instance):
        exit_code = cli.cmd_run(args, {})

    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "endpoint    http://10.0.0.5:5000" in captured
    assert "resolution  1280x720" in captured
    assert "completed   wan-2.1" in captured
