"""Lifecycle integration for the local SpacePilot daemon.

The daemon is a user service: no sudo, no global unit and no PID-file signal
handling.  Supervisors own the process tree, so lifecycle operations always
address the service by its supervisor label rather than guessing a PID.
"""

from __future__ import annotations

import os
import plistlib
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from spacepilot.paths import (
    daemon_log_dir,
    daemon_runtime_dir,
    daemon_socket_path,
    launch_agent_path,
    systemd_user_unit_path,
)

SERVICE_NAME = "spacepilot-daemon.service"
LAUNCHD_LABEL = "com.spacepilot.daemon"


class ServiceError(RuntimeError):
    """A lifecycle action could not be completed safely."""


@dataclass(frozen=True)
class ServiceStatus:
    """Supervisor facts and separately-observed facts from the local UDS."""

    platform: str
    definition: Path
    installed: bool
    active: bool | None
    detail: str
    lingering: bool | None = None
    reachable: bool = False
    reachability_detail: str | None = None
    peer_state: str | None = None
    peer_address: str | None = None
    peer_observed_at: str | None = None
    peer_age_seconds: float | None = None
    picture_observed_at: str | None = None
    picture_age_seconds: float | None = None
    key_id: str | None = None
    key_observed_at: str | None = None
    key_age_seconds: float | None = None


def daemon_argv() -> list[str]:
    """Use this exact interpreter, not whichever `spacepilot` is on PATH."""
    return [sys.executable, "-m", "spacepilot.cli", "daemon", "run"]


def launchd_plist(*, argv: Sequence[str] | None = None) -> dict[str, object]:
    """Return the complete per-user launchd definition."""
    log_dir = daemon_log_dir().resolve()
    return {
        "Label": LAUNCHD_LABEL,
        "ProgramArguments": list(argv or daemon_argv()),
        "RunAtLoad": True,
        # Restart failures, but allow an intentional foreground shutdown to stay down.
        "KeepAlive": {"SuccessfulExit": False},
        "StandardOutPath": str((log_dir / "daemon.out.log").resolve()),
        "StandardErrorPath": str((log_dir / "daemon.err.log").resolve()),
    }


def _systemd_exec_arg(argument: str) -> str:
    """Quote one ExecStart argument using systemd syntax, not shell syntax."""
    # systemd parses ExecStart itself.  Double quotes and backslashes are its
    # escaping mechanism; `$$` and `%%` preserve literal values through its
    # environment/specifier expansion.  Always quoting also avoids whitespace
    # becoming a second argv item when Python lives under a path with spaces.
    return '"' + (argument.replace("\\", "\\\\").replace('"', '\\"')
                    .replace("$", "$$").replace("%", "%%")) + '"'


def systemd_unit(*, argv: Sequence[str] | None = None) -> str:
    """Return a safe, shell-free systemd user unit.

    Arguments are quoted for systemd's ExecStart parser; it does not invoke a
    shell.  RuntimeDirectory gives the UDS a protected,
    session-scoped home and is mirrored into the daemon's paths helper.
    """
    command = " ".join(_systemd_exec_arg(str(arg)) for arg in (argv or daemon_argv()))
    return "\n".join((
        "[Unit]",
        "Description=SpacePilot local daemon",
        "",
        "[Service]",
        "Type=simple",
        f"ExecStart={command}",
        "Restart=on-failure",
        "RestartSec=2",
        "UMask=0077",
        "RuntimeDirectory=spacepilot",
        "Environment=SPACEPILOT_DAEMON_RUNTIME_DIR=%t/spacepilot",
        "",
        "[Install]",
        "WantedBy=default.target",
        "",
    ))


def _run_cmd() -> Callable[..., object]:
    # Import lazily: cli imports this module only from daemon command handlers.
    from spacepilot.cli import run_cmd
    return run_cmd


def _write_private(path: Path, content: bytes | str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    path.chmod(0o600)


def _platform(platform: str | None = None) -> str:
    value = platform or sys.platform
    if value == "darwin":
        return "darwin"
    if value.startswith("linux"):
        return "linux"
    raise ServiceError(f"daemon user services are not supported on {value!r}")


def install_daemon(*, platform: str | None = None) -> Path:
    """Write and load/enable the current user's daemon definition.

    An existing definition is left untouched: overwriting a service that might
    be running makes an upgrade indistinguishable from a surprise restart.
    """
    current = _platform(platform)
    if current == "darwin":
        path = launch_agent_path()
        if path.exists():
            raise ServiceError(f"daemon definition already exists: {path}; stop it before reinstalling")
        daemon_log_dir().mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = plistlib.dumps(launchd_plist(), fmt=plistlib.FMT_XML, sort_keys=False)
        _write_private(path, payload)
        _run_cmd()(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(path)])
        return path

    path = systemd_user_unit_path()
    if path.exists():
        raise ServiceError(f"daemon definition already exists: {path}; stop it before reinstalling")
    _write_private(path, systemd_unit())
    run_cmd = _run_cmd()
    run_cmd(["systemctl", "--user", "daemon-reload"])
    run_cmd(["systemctl", "--user", "enable", "--now", SERVICE_NAME])
    return path


def _command_succeeds(argv: list[str]) -> tuple[bool, str]:
    try:
        output = _run_cmd()(argv, capture=True)
    except (OSError, RuntimeError) as exc:
        return False, str(exc)
    return True, str(output)


def _lingering_status() -> bool | None:
    """Report systemd lingering, but never turn it on as an install side effect."""
    ok, output = _command_succeeds([
        "loginctl", "show-user", str(os.getuid()), "-p", "Linger", "--value",
    ])
    if not ok:
        return None
    value = output.strip().lower()
    return True if value == "yes" else False if value == "no" else None


def _observed_age_seconds(value: object) -> float | None:
    """Age an observation only when its timestamp is a real UTC instant."""
    if not isinstance(value, str) or not value:
        return None
    try:
        observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if observed.tzinfo is None:
        return None
    return max(0.0, (datetime.now(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds())


def _as_mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _daemon_observation() -> dict[str, object]:
    """Probe the local door without allowing a transport failure to look healthy."""
    from spacepilot.substrate import DaemonClient, SubstrateError

    try:
        client = DaemonClient(daemon_socket_path())
        health = client.health()
    except (OSError, SubstrateError) as exc:
        return {"reachable": False, "reachability_detail": str(exc)}

    values: dict[str, object] = {"reachable": True}
    peer = _as_mapping(health.get("peer"))
    if peer is not None:
        peer_at = peer.get("observed_at")
        values.update({
            "peer_state": peer.get("state") if isinstance(peer.get("state"), str) else None,
            "peer_address": peer.get("address") if isinstance(peer.get("address"), str) else None,
            "peer_observed_at": peer_at if isinstance(peer_at, str) else None,
            "peer_age_seconds": _observed_age_seconds(peer_at),
        })

    try:
        picture = client.picture()
    except (OSError, SubstrateError) as exc:
        values["reachability_detail"] = f"picture unavailable: {exc}"
        return values
    picture_at = picture.get("sampled_at")
    values.update({
        "picture_observed_at": picture_at if isinstance(picture_at, str) else None,
        "picture_age_seconds": _observed_age_seconds(picture_at),
    })
    identity = _as_mapping(picture.get("identity"))
    identity_value = _as_mapping(identity.get("value")) if identity is not None else None
    if identity is not None:
        key_at = identity.get("observed_at")
        values.update({
            "key_id": identity_value.get("key_id") if identity_value and isinstance(identity_value.get("key_id"), str) else None,
            "key_observed_at": key_at if isinstance(key_at, str) else None,
            "key_age_seconds": _observed_age_seconds(key_at),
        })
    return values


def daemon_status(*, platform: str | None = None) -> ServiceStatus:
    """Report supervisor state and a live UDS observation independently."""
    current = _platform(platform)
    observation = _daemon_observation()
    if current == "darwin":
        path = launch_agent_path()
        if not path.exists():
            return ServiceStatus(current, path, False, False, "not installed", **observation)
        active, detail = _command_succeeds([
            "launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}",
        ])
        return ServiceStatus(
            current, path, True, active, detail or ("active" if active else "not loaded"),
            **observation,
        )

    path = systemd_user_unit_path()
    lingering = _lingering_status()
    if not path.exists():
        return ServiceStatus(current, path, False, False, "not installed", lingering, **observation)
    active, detail = _command_succeeds(["systemctl", "--user", "is-active", SERVICE_NAME])
    return ServiceStatus(
        current, path, True, active, detail or ("active" if active else "inactive"), lingering,
        **observation,
    )


def stop_daemon(*, platform: str | None = None) -> None:
    """Ask the local door to stop first, then use a supervisor only if needed."""
    from spacepilot.substrate import DaemonClient, SubstrateError

    try:
        DaemonClient(daemon_socket_path()).shutdown()
        return
    except (OSError, SubstrateError):
        # A foreground daemon has no supervisor, and a supervisor may be
        # alive while its UDS failed early.  In either case, inspect the known
        # definition below instead of guessing a PID.
        pass
    current = _platform(platform)
    if current == "darwin":
        path = launch_agent_path()
        if not path.exists():
            raise ServiceError("daemon is not installed")
        _run_cmd()(["launchctl", "bootout", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"])
        return
    path = systemd_user_unit_path()
    if not path.exists():
        raise ServiceError("daemon is not installed")
    _run_cmd()(["systemctl", "--user", "stop", SERVICE_NAME])


def run_foreground() -> int:
    """Run the daemon server in the current terminal (the supervisor target)."""
    # This directory is only made for a user-invoked foreground process.  The
    # systemd RuntimeDirectory is created by systemd, not by us.
    daemon_runtime_dir().mkdir(mode=0o700, parents=True, exist_ok=True)
    from spacepilot.daemon.server import run_daemon
    result = run_daemon(socket_path=daemon_socket_path())
    return int(result) if result is not None else 0
