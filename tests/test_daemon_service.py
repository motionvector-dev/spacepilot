"""Daemon lifecycle definitions must be safe before a supervisor sees them."""

from __future__ import annotations

import plistlib
import stat
import sys
from pathlib import Path

from spacepilot.daemon import service


def test_launchd_plist_has_exact_interpreter_argv_and_safe_restart_policy(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "daemon_log_dir", lambda: tmp_path / "logs")

    payload = service.launchd_plist()

    assert payload["ProgramArguments"] == [
        sys.executable, "-m", "spacepilot.cli", "daemon", "run",
    ]
    assert payload["RunAtLoad"] is True
    assert payload["KeepAlive"] == {"SuccessfulExit": False}
    assert Path(payload["StandardOutPath"]).is_absolute()
    assert Path(payload["StandardErrorPath"]).is_absolute()


def test_install_macos_writes_parseable_private_plist_and_uses_launchctl_argv(tmp_path, monkeypatch):
    plist_path = tmp_path / "Library" / "LaunchAgents" / "com.spacepilot.daemon.plist"
    calls: list[list[str]] = []
    monkeypatch.setattr(service, "launch_agent_path", lambda: plist_path)
    monkeypatch.setattr(service, "daemon_log_dir", lambda: tmp_path / "state" / "logs")
    monkeypatch.setattr(service, "_run_cmd", lambda: lambda argv, **_: calls.append(argv))

    assert service.install_daemon(platform="darwin") == plist_path

    payload = plistlib.loads(plist_path.read_bytes())
    assert payload["ProgramArguments"] == service.daemon_argv()
    assert calls == [["launchctl", "bootstrap", f"gui/{service.os.getuid()}", str(plist_path)]]
    assert stat.S_IMODE(plist_path.stat().st_mode) == 0o600


def test_systemd_unit_has_no_shell_and_has_runtime_safety_settings():
    unit = service.systemd_unit(argv=["/path with spaces/python", "-m", "pkg;not-a-shell", "$HOME"])

    assert 'ExecStart="/path with spaces/python" "-m" "pkg;not-a-shell" "$$HOME"' in unit
    assert "Restart=on-failure" in unit
    assert "UMask=0077" in unit
    assert "RuntimeDirectory=spacepilot" in unit
    assert "Environment=SPACEPILOT_DAEMON_RUNTIME_DIR=%t/spacepilot" in unit
    assert "sh -c" not in unit


def test_install_linux_never_enables_lingering_and_uses_systemctl_argv(tmp_path, monkeypatch):
    unit_path = tmp_path / "config" / "systemd" / "user" / service.SERVICE_NAME
    calls: list[list[str]] = []
    monkeypatch.setattr(service, "systemd_user_unit_path", lambda: unit_path)
    monkeypatch.setattr(service, "_run_cmd", lambda: lambda argv, **_: calls.append(argv))

    assert service.install_daemon(platform="linux") == unit_path

    text = unit_path.read_text()
    assert "ExecStart=" in text
    assert calls == [
        ["systemctl", "--user", "daemon-reload"],
        ["systemctl", "--user", "enable", "--now", service.SERVICE_NAME],
    ]
    assert not any(call[:2] == ["loginctl", "enable-linger"] for call in calls)
    assert stat.S_IMODE(unit_path.stat().st_mode) == 0o600


def test_linux_status_reports_lingering_without_changing_it(tmp_path, monkeypatch):
    unit_path = tmp_path / "spacepilot-daemon.service"
    unit_path.write_text("[Service]\n")
    calls: list[list[str]] = []

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        if argv[0] == "loginctl":
            return "no"
        return "active"

    monkeypatch.setattr(service, "systemd_user_unit_path", lambda: unit_path)
    monkeypatch.setattr(service, "_run_cmd", lambda: fake_run)

    status = service.daemon_status(platform="linux")

    assert status.installed and status.active and status.lingering is False
    assert calls == [
        ["loginctl", "show-user", str(service.os.getuid()), "-p", "Linger", "--value"],
        ["systemctl", "--user", "is-active", service.SERVICE_NAME],
    ]


def test_status_keeps_supervisor_facts_and_reports_live_uds_key_and_peer(tmp_path, monkeypatch):
    unit_path = tmp_path / service.SERVICE_NAME
    unit_path.write_text("[Service]\n")
    observed = "2026-08-25T12:00:00+00:00"

    class Client:
        def __init__(self, socket_path):
            assert socket_path == tmp_path / "daemon.sock"

        def health(self):
            return {"status": "ok", "peer": {
                "state": "listening", "address": "100.64.0.4", "observed_at": observed,
            }}

        def picture(self):
            return {"sampled_at": observed, "identity": {
                "state": "fresh", "observed_at": observed,
                "value": {"key_id": "ship-key-7", "algorithm": "ed25519"},
            }}

    monkeypatch.setattr(service, "systemd_user_unit_path", lambda: unit_path)
    monkeypatch.setattr(service, "daemon_socket_path", lambda: tmp_path / "daemon.sock")
    monkeypatch.setattr("spacepilot.substrate.DaemonClient", Client)
    monkeypatch.setattr(service, "_observed_age_seconds", lambda _: 8.0)
    monkeypatch.setattr(service, "_run_cmd", lambda: lambda argv, **_: "yes" if argv[0] == "loginctl" else "active")

    status = service.daemon_status(platform="linux")

    assert status.installed and status.active and status.reachable
    assert status.peer_state == "listening"
    assert status.peer_address == "100.64.0.4"
    assert status.peer_age_seconds == 8.0
    assert status.picture_age_seconds == 8.0
    assert status.key_id == "ship-key-7"
    assert status.key_age_seconds == 8.0


def test_stop_uses_uds_shutdown_for_foreground_daemon_without_a_supervisor(tmp_path, monkeypatch):
    calls: list[Path] = []

    class Client:
        def __init__(self, socket_path):
            calls.append(socket_path)

        def shutdown(self):
            return {"status": "stopping"}

    monkeypatch.setattr(service, "daemon_socket_path", lambda: tmp_path / "daemon.sock")
    monkeypatch.setattr("spacepilot.substrate.DaemonClient", Client)
    monkeypatch.setattr(service, "_run_cmd", lambda: (_ for _ in ()).throw(AssertionError("no supervisor")))

    service.stop_daemon(platform="linux")

    assert calls == [tmp_path / "daemon.sock"]


def test_stop_uses_supervisor_label_never_a_pid(tmp_path, monkeypatch):
    unit_path = tmp_path / service.SERVICE_NAME
    unit_path.touch()
    calls: list[list[str]] = []
    monkeypatch.setattr(service, "systemd_user_unit_path", lambda: unit_path)
    monkeypatch.setattr(service, "_run_cmd", lambda: lambda argv, **_: calls.append(argv))

    service.stop_daemon(platform="linux")

    assert calls == [["systemctl", "--user", "stop", service.SERVICE_NAME]]
    assert all("kill" not in " ".join(call) for call in calls)


def test_foreground_delegates_to_server_with_the_paths_socket(tmp_path, monkeypatch):
    import types

    package = types.ModuleType("spacepilot.daemon.server")
    captured: dict[str, Path] = {}

    def run_daemon(*, socket_path: Path):
        captured["socket_path"] = socket_path
        return 7

    package.run_daemon = run_daemon  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "spacepilot.daemon.server", package)
    monkeypatch.setattr(service, "daemon_runtime_dir", lambda: tmp_path / "runtime")
    monkeypatch.setattr(service, "daemon_socket_path", lambda: tmp_path / "runtime" / "daemon.sock")

    assert service.run_foreground() == 7
    assert captured["socket_path"] == tmp_path / "runtime" / "daemon.sock"
