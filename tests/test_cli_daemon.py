from __future__ import annotations

from pathlib import Path

from spacepilot import cli
from spacepilot.daemon.service import ServiceStatus


def test_daemon_parser_dispatches_status_without_starting_a_service(monkeypatch, capsys, tmp_path):
    calls: list[str] = []

    def fake_status():
        calls.append("status")
        return ServiceStatus("linux", tmp_path / "spacepilot-daemon.service", True, True, "active", False)

    monkeypatch.setattr("spacepilot.daemon.service.daemon_status", fake_status)
    assert cli.main(["daemon", "status"]) == 0
    assert calls == ["status"]
    output = capsys.readouterr().out
    assert "installed   yes" in output
    assert "state       active" in output
    assert "lingering   off" in output


def test_daemon_run_delegates_to_foreground_server(monkeypatch):
    monkeypatch.setattr("spacepilot.daemon.service.run_foreground", lambda: 4)
    assert cli.main(["daemon", "run"]) == 4


def test_daemon_stop_is_explicit_and_does_not_fall_back_to_pid_killing(monkeypatch, capsys):
    calls: list[str] = []
    monkeypatch.setattr("spacepilot.daemon.service.stop_daemon", lambda: calls.append("stop"))

    assert cli.main(["daemon", "stop"]) == 0
    assert calls == ["stop"]
    assert "daemon stopped" in capsys.readouterr().out


def test_daemon_status_renders_uds_peer_and_key_ages(monkeypatch, capsys, tmp_path):
    state = ServiceStatus(
        "linux", tmp_path / "spacepilot-daemon.service", False, False, "not installed",
        reachable=True, picture_age_seconds=8,
        peer_state="waiting", peer_address="100.64.0.5", peer_age_seconds=8,
        key_id="ship-key-7", key_age_seconds=65,
    )
    monkeypatch.setattr("spacepilot.daemon.service.daemon_status", lambda: state)

    assert cli.main(["daemon", "status"]) == 0
    output = capsys.readouterr().out
    assert "local door  reachable" in output
    assert "picture     checked 8s ago" in output
    assert "peer        waiting (100.64.0.5) · checked 8s ago" in output
    assert "key         ship-key-7 · checked 1m ago" in output
