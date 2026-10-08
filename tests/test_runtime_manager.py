"""Unit tests for SpacePilot runtime manager."""

import os
import signal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from spacepilot.services import runtime_manager


class FakeProcess:
    def __init__(self, pid: int = 12345):
        self.pid = pid


def test_build_backend_command_sglang():
    cmd = runtime_manager.build_backend_command("sglang", Path("/tmp/weights"), port=30010, tp=1)
    assert "sglang.launch_server" in " ".join(cmd)
    assert "--model-path" in cmd
    assert "/tmp/weights" in cmd
    assert "--port" in cmd
    assert "30010" in cmd
    assert "--tp" in cmd
    assert "1" in cmd


def test_build_backend_command_vllm():
    cmd = runtime_manager.build_backend_command("vllm", Path("/tmp/weights"), port=8000, tp=2)
    assert "vllm.entrypoints.openai.api_server" in " ".join(cmd)
    assert "--model" in cmd
    assert "--tensor-parallel-size" in cmd
    assert "2" in cmd


def test_load_and_get_resident_models(tmp_path, monkeypatch):
    state_file = tmp_path / "resident.json"
    fake_pid = 42424

    # Mock pid alive
    monkeypatch.setattr(runtime_manager, "_is_pid_alive", lambda pid: True)

    fake_runner = MagicMock(return_value=FakeProcess(pid=fake_pid))

    res = runtime_manager.load_model(
        model_id="qwen3-8",
        weights_dir=Path("/data/weights/qwen3-8"),
        backend="sglang",
        port=30010,
        tp=1,
        state_path=state_file,
        runner=fake_runner,
        skip_healthcheck=True,
    )

    assert res["model_id"] == "qwen3-8"
    assert res["port"] == 30010
    assert res["pid"] == fake_pid
    assert res["healthy"] is None
    assert fake_runner.called

    # Verify resident.json content
    residents = runtime_manager.get_resident_models(state_path=state_file)
    assert len(residents) == 1
    assert residents[0]["model_id"] == "qwen3-8"
    assert residents[0]["port"] == 30010


def test_load_model_conflict(tmp_path, monkeypatch):
    state_file = tmp_path / "resident.json"
    monkeypatch.setattr(runtime_manager, "_is_pid_alive", lambda pid: True)

    fake_runner = MagicMock(return_value=FakeProcess(pid=100))

    runtime_manager.load_model(
        model_id="model-a",
        weights_dir=Path("/data/a"),
        port=30010,
        state_path=state_file,
        runner=fake_runner,
        skip_healthcheck=True,
    )

    # Attempt same port with different model
    with pytest.raises(RuntimeError, match="Port 30010 is already in use"):
        runtime_manager.load_model(
            model_id="model-b",
            weights_dir=Path("/data/b"),
            port=30010,
            state_path=state_file,
            runner=fake_runner,
            skip_healthcheck=True,
        )

    # Attempt same model with different port
    with pytest.raises(RuntimeError, match="Model model-a is already resident"):
        runtime_manager.load_model(
            model_id="model-a",
            weights_dir=Path("/data/a"),
            port=30011,
            state_path=state_file,
            runner=fake_runner,
            skip_healthcheck=True,
        )


def test_healthcheck_timeout_kills_process(tmp_path, monkeypatch):
    state_file = tmp_path / "resident.json"
    killed_signals = []

    monkeypatch.setattr(runtime_manager, "_is_pid_alive", lambda pid: True)
    monkeypatch.setattr(os, "kill", lambda pid, sig: killed_signals.append((pid, sig)))

    fake_runner = MagicMock(return_value=FakeProcess(pid=9999))
    fake_checker = MagicMock(return_value=False)

    with pytest.raises(TimeoutError, match="Healthcheck timed out"):
        runtime_manager.load_model(
            model_id="failing-model",
            weights_dir=Path("/data/model"),
            port=30020,
            state_path=state_file,
            runner=fake_runner,
            health_timeout=0.2,
            health_checker=fake_checker,
        )

    assert (9999, signal.SIGTERM) in killed_signals
    # Model was cleaned up and not saved to residents
    assert len(runtime_manager.get_resident_models(state_path=state_file)) == 0


def test_unload_by_model_id(tmp_path, monkeypatch):
    state_file = tmp_path / "resident.json"
    killed_signals = []

    monkeypatch.setattr(runtime_manager, "_is_pid_alive", lambda pid: True)
    monkeypatch.setattr(os, "kill", lambda pid, sig: killed_signals.append((pid, sig)))

    runtime_manager.load_model(
        model_id="m1",
        weights_dir=Path("/data/m1"),
        port=30001,
        state_path=state_file,
        runner=lambda cmd: FakeProcess(pid=1001),
        skip_healthcheck=True,
    )
    runtime_manager.load_model(
        model_id="m2",
        weights_dir=Path("/data/m2"),
        port=30002,
        state_path=state_file,
        runner=lambda cmd: FakeProcess(pid=1002),
        skip_healthcheck=True,
    )

    assert len(runtime_manager.get_resident_models(state_path=state_file)) == 2

    # Unload m1
    res = runtime_manager.unload_model(model_id="m1", state_path=state_file)
    assert res["unloaded_count"] == 1
    assert res["remaining_count"] == 1
    assert (1001, signal.SIGTERM) in killed_signals

    remaining = runtime_manager.get_resident_models(state_path=state_file)
    assert len(remaining) == 1
    assert remaining[0]["model_id"] == "m2"


def test_unload_all_models(tmp_path, monkeypatch):
    state_file = tmp_path / "resident.json"
    killed_signals = []

    monkeypatch.setattr(runtime_manager, "_is_pid_alive", lambda pid: True)
    monkeypatch.setattr(os, "kill", lambda pid, sig: killed_signals.append((pid, sig)))

    runtime_manager.load_model(
        model_id="m1",
        weights_dir=Path("/data/m1"),
        port=30001,
        state_path=state_file,
        runner=lambda cmd: FakeProcess(pid=2001),
        skip_healthcheck=True,
    )
    runtime_manager.load_model(
        model_id="m2",
        weights_dir=Path("/data/m2"),
        port=30002,
        state_path=state_file,
        runner=lambda cmd: FakeProcess(pid=2002),
        skip_healthcheck=True,
    )

    res = runtime_manager.unload_model(all_models=True, state_path=state_file)
    assert res["unloaded_count"] == 2
    assert res["remaining_count"] == 0
    assert (2001, signal.SIGTERM) in killed_signals
    assert (2002, signal.SIGTERM) in killed_signals

    assert len(runtime_manager.get_resident_models(state_path=state_file)) == 0


def test_get_resident_models_prunes_dead_processes(tmp_path, monkeypatch):
    state_file = tmp_path / "resident.json"

    # Initially mock both alive
    alive_pids = {3001, 3002}
    monkeypatch.setattr(runtime_manager, "_is_pid_alive", lambda pid: pid in alive_pids)

    runtime_manager.load_model(
        model_id="m1",
        weights_dir=Path("/data/m1"),
        port=30001,
        state_path=state_file,
        runner=lambda cmd: FakeProcess(pid=3001),
        skip_healthcheck=True,
    )
    runtime_manager.load_model(
        model_id="m2",
        weights_dir=Path("/data/m2"),
        port=30002,
        state_path=state_file,
        runner=lambda cmd: FakeProcess(pid=3002),
        skip_healthcheck=True,
    )

    assert len(runtime_manager.get_resident_models(state_path=state_file)) == 2

    # Simulate process 3001 dying
    alive_pids.remove(3001)

    # Query with verify_alive=True
    active = runtime_manager.get_resident_models(state_path=state_file, verify_alive=True)
    assert len(active) == 1
    assert active[0]["model_id"] == "m2"

    # Verify persisted state file was pruned
    persisted = runtime_manager.get_resident_models(state_path=state_file, verify_alive=False)
    assert len(persisted) == 1
    assert persisted[0]["model_id"] == "m2"
