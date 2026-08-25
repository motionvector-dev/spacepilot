"""Phase 4 daemon contracts.  No test starts Tailscale or a model run."""

from __future__ import annotations

import datetime as dt
import json
import socket
import stat
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from spacepilot.daemon.api import create_local_app, create_peer_app
from spacepilot.daemon.picture import PictureSampler
from spacepilot.daemon.server import (
    DaemonAlreadyRunning,
    TailnetUnavailable,
    UnsafeSocketPath,
    bind_peer_socket,
    bind_unix_socket,
    discover_tailnet_ipv4,
    run_daemon,
)
from spacepilot.pluto.services.execution import RunRequest, RunResult
from spacepilot.substrate import DaemonClient, DirectLocal, SubstrateError


UTC = dt.timezone.utc


@pytest.fixture
def short_runtime():
    """macOS limits sockaddr_un paths to 103 bytes; pytest names are longer."""
    with tempfile.TemporaryDirectory(prefix="sp-daemon-", dir="/private/tmp") as directory:
        yield Path(directory)


class _System:
    def to_dict(self):
        return {"id": "test-system", "backend": "cpu"}


def _plan():
    candidate = SimpleNamespace(
        variant=SimpleNamespace(id="test-variant"),
        route=SimpleNamespace(model_alias="exact-alias"),
        verdict=SimpleNamespace(verdict="fits", reason="measured capacity fits"),
        route_state="ready",
        can_run=True,
        speed=None,
        non_safe_caveats=(),
    )
    return SimpleNamespace(
        workload="image",
        system=_System(),
        candidates=(candidate,),
        selected=candidate,
    )


def _substrate(tmp_path: Path) -> tuple[DirectLocal, MagicMock]:
    service = MagicMock()
    service.plan.return_value = _plan()
    service.execute.return_value = RunResult(
        status="completed",
        variant_id="test-variant",
        model_alias="exact-alias",
        output=tmp_path / "result.png",
        resolved_revision=None,
        wall_seconds=2.5,
        seconds_per_image=2.0,
        measurement_path=tmp_path / "measurement.yaml",
        timing_source="test-boundary",
    )
    direct = DirectLocal(
        service,
        picture_supplier=lambda: {
            "schema": 1,
            "sampled_at": "2026-08-25T00:00:00+00:00",
        },
    )
    return direct, service


class _UvicornThread:
    def __init__(self, substrate: DirectLocal, path: Path):
        self.bound_context = bind_unix_socket(path)
        self.bound = self.bound_context.__enter__()
        self.server = uvicorn.Server(uvicorn.Config(
            create_local_app(substrate), log_level="error", access_log=False,
        ))
        self.thread = threading.Thread(
            target=self.server.run,
            kwargs={"sockets": [self.bound.sock]},
            daemon=True,
        )

    def __enter__(self):
        self.thread.start()
        deadline = time.monotonic() + 3
        while not self.server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        assert self.server.started
        return self

    def __exit__(self, *exc):
        self.server.should_exit = True
        self.thread.join(timeout=3)
        self.bound_context.__exit__(*exc)
        assert not self.thread.is_alive()


def test_direct_local_equals_real_temporary_uds_daemon(tmp_path, short_runtime, monkeypatch):
    monkeypatch.setattr("spacepilot.daemon.api.allocate_output", lambda name: tmp_path / name)
    direct, service = _substrate(tmp_path)
    request = RunRequest("image", "a copper airship", tmp_path / "result.png", seed=7)
    expected_picture = direct.picture()
    expected_plan = direct.plan("image")
    expected_result = direct.run(request)

    socket_path = short_runtime / "spacepilot.sock"
    with _UvicornThread(direct, socket_path):
        daemon = DaemonClient(socket_path, output_root=tmp_path)
        assert daemon.picture() == expected_picture
        assert daemon.plan("image") == expected_plan
        assert daemon.run(request) == expected_result

    # Direct and daemon paths both delegate to the same service; the API does
    # not contain a second route selector or executor.
    assert service.execute.call_count == 2


def test_daemon_transport_failure_does_not_retry_or_fall_back(monkeypatch, tmp_path):
    calls = 0

    def fail(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("response lost after request")

    monkeypatch.setattr(httpx.Client, "request", fail)
    client = DaemonClient(tmp_path / "missing.sock", output_root=tmp_path)
    with pytest.raises(SubstrateError, match="daemon request POST /v1/run failed"):
        client.run(RunRequest("image", "prompt", tmp_path / "out.png"))
    assert calls == 1


def test_picture_failure_keeps_last_good_timestamp_and_marks_stale():
    ticks = iter([
        dt.datetime(2026, 8, 25, 1, 0, tzinfo=UTC),
        dt.datetime(2026, 8, 25, 1, 1, tzinfo=UTC),
    ])
    worker_calls = iter([{"status": "online"}, RuntimeError("probe failed")])

    def workers():
        value = next(worker_calls)
        if isinstance(value, Exception):
            raise value
        return value

    sampler = PictureSampler(
        system_probe=lambda: {"id": "test-system"},
        worker_probe=workers,
        clock=lambda: next(ticks),
    )
    first = sampler.sample()
    second = sampler.sample()
    assert first["workers"]["state"] == "fresh"
    assert second["sampled_at"] != first["sampled_at"]
    assert second["workers"]["state"] == "stale"
    assert second["workers"]["observed_at"] == first["workers"]["observed_at"]
    assert second["workers"]["value"] == {"status": "online"}
    assert "probe failed" in second["workers"]["error"]


def test_picture_first_failure_is_explicit_unknown():
    sampler = PictureSampler(
        system_probe=lambda: (_ for _ in ()).throw(OSError("probe unavailable")),
        worker_probe=lambda: {"status": "online"},
        clock=lambda: dt.datetime(2026, 8, 25, tzinfo=UTC),
    )
    picture = sampler.sample()
    assert picture["system"] == {
        "state": "unknown",
        "value": None,
        "observed_at": None,
        "error": "OSError: probe unavailable",
    }
    assert picture["workers"]["state"] == "fresh"


def test_peer_api_has_picture_but_no_plan_or_run(tmp_path, monkeypatch):
    monkeypatch.setattr("spacepilot.daemon.api.allocate_output", lambda name: tmp_path / name)
    substrate, service = _substrate(tmp_path)
    local = TestClient(create_local_app(substrate))
    peer = TestClient(create_peer_app(substrate, allow_unauthenticated=True))

    assert local.post("/v1/plan", json={"workload": "image"}).status_code == 200
    assert local.post("/v1/run", json={
        "workload": "image", "prompt": "x", "output_name": "x.png",
    }).status_code == 200
    assert peer.get("/v1/picture").status_code == 200
    assert peer.post("/v1/plan", json={"workload": "image"}).status_code == 404
    assert peer.post("/v1/run", json={
        "workload": "image", "prompt": "x", "output_name": "x.png",
    }).status_code == 404
    assert peer.get("/openapi.json").status_code == 404
    assert service.execute.call_count == 1


@pytest.mark.parametrize("unsafe", ["../escape.png", "/tmp/absolute.png", "nested/../../escape.png"])
def test_local_run_refuses_output_escape_before_execution(tmp_path, monkeypatch, unsafe):
    from fastapi import HTTPException

    substrate, service = _substrate(tmp_path)

    def checked(name):
        candidate = (tmp_path / name).resolve()
        if not candidate.is_relative_to(tmp_path.resolve()):
            raise HTTPException(status_code=400, detail="escapes the outputs directory")
        return candidate

    monkeypatch.setattr("spacepilot.daemon.api.allocate_output", checked)
    response = TestClient(create_local_app(substrate)).post("/v1/run", json={
        "workload": "image", "prompt": "x", "output_name": unsafe,
    })
    assert response.status_code == 400
    service.execute.assert_not_called()


def test_daemon_client_refuses_outside_output_without_transport(monkeypatch, tmp_path):
    request = MagicMock()
    request.workload = "image"
    request.prompt = "x"
    request.output = tmp_path.parent / "escape.png"
    request.seed = None
    transport = MagicMock()
    monkeypatch.setattr(DaemonClient, "_request", transport)
    with pytest.raises(SubstrateError, match="must be inside"):
        DaemonClient(tmp_path / "daemon.sock", output_root=tmp_path).run(request)
    transport.assert_not_called()


def test_shutdown_exists_only_on_local_api(tmp_path):
    substrate, _ = _substrate(tmp_path)
    requested = []
    local = TestClient(create_local_app(substrate, shutdown=lambda: requested.append(True)))
    peer = TestClient(create_peer_app(substrate, allow_unauthenticated=True))
    assert local.post("/v1/shutdown").json() == {"status": "stopping"}
    assert requested == [True]
    assert peer.post("/v1/shutdown").status_code == 404


def test_foreground_server_reports_peer_state_and_shuts_down_over_uds(short_runtime, tmp_path):
    substrate, service = _substrate(tmp_path)

    class Identity:
        key_id = "v1:test"
        public_key_b64 = "test-public-key"

        def sign_envelope(self, payload, *, kind):
            return {"kind": kind, "payload": payload, "key_id": self.key_id,
                    "public_key": self.public_key_b64, "signature": "test", "version": 1}

    sampler = PictureSampler(
        system_probe=lambda: {"id": "test-system"},
        worker_probe=lambda: {"status": "online"},
    )
    socket_path = short_runtime / "daemon.sock"
    thread = threading.Thread(target=run_daemon, kwargs={
        "socket_path": socket_path,
        "service": service,
        "sampler": sampler,
        "identity": Identity(),
        "discover_tailnet": False,
    }, daemon=True)
    thread.start()
    client = DaemonClient(socket_path, output_root=tmp_path, timeout=1.0)
    deadline = time.monotonic() + 3
    while True:
        try:
            health = client.health()
            break
        except SubstrateError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.02)
    assert health["status"] == "ok"
    assert health["peer"]["state"] == "disabled"
    assert health["peer"]["observed_at"]
    assert client.shutdown() == {"status": "stopping"}
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert not socket_path.exists()


def test_peer_picture_can_be_wrapped_in_a_signed_envelope(tmp_path):
    substrate, _ = _substrate(tmp_path)
    seen = []

    def signer(picture):
        seen.append(picture)
        return {"kind": "picture", "payload": picture, "signature": "test-signature"}

    peer = TestClient(create_peer_app(substrate, picture_signer=signer, allow_unauthenticated=True))
    response = peer.get("/v1/picture")
    assert response.status_code == 200
    assert response.json()["kind"] == "picture"
    assert response.json()["payload"] == seen[0]


def test_peer_picture_verifies_with_persisted_ed25519_identity(tmp_path, monkeypatch):
    from spacepilot.daemon.identity import load_or_create, sign_picture, verify_picture

    monkeypatch.setenv("SPACEPILOT_DATA_DIR", str(tmp_path / "data"))
    identity = load_or_create()
    substrate, _ = _substrate(tmp_path)
    peer = TestClient(create_peer_app(
        substrate,
        picture_signer=lambda picture: sign_picture(identity, picture),
        allow_unauthenticated=True,
    ))
    envelope = peer.get("/v1/picture").json()
    assert envelope["key_id"] == identity.key_id
    assert verify_picture(envelope, expected_key_id=identity.key_id) == substrate.picture()


def test_uds_is_private_owned_and_removed_after_exit(short_runtime):
    path = short_runtime / "too-open" / "daemon.sock"
    path.parent.mkdir(mode=0o777)
    path.parent.chmod(0o777)
    with bind_unix_socket(path):
        st = path.lstat()
        assert stat.S_ISSOCK(st.st_mode)
        assert st.st_uid == __import__("os").getuid()
        assert stat.S_IMODE(st.st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert not path.exists()


def test_stale_uds_is_cleaned_but_non_socket_is_never_replaced(short_runtime):
    path = short_runtime / "daemon.sock"
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(str(path))
    stale.close()
    assert path.exists()
    with bind_unix_socket(path):
        assert path.exists()

    path.write_text("user data")
    with pytest.raises(UnsafeSocketPath, match="non-socket"):
        with bind_unix_socket(path):
            pass
    assert path.read_text() == "user data"


def test_socket_path_symlink_is_rejected_without_touching_target(short_runtime):
    target = short_runtime / "target"
    target.write_text("keep me")
    path = short_runtime / "daemon.sock"
    path.symlink_to(target)
    with pytest.raises(UnsafeSocketPath, match="non-socket"):
        with bind_unix_socket(path):
            pass
    assert path.is_symlink()
    assert target.read_text() == "keep me"


def test_overlong_socket_path_fails_with_an_operator_facing_error(short_runtime):
    path = short_runtime / ("x" * 90) / "daemon.sock"
    with pytest.raises(UnsafeSocketPath, match="too long"):
        with bind_unix_socket(path):
            pass


def test_second_daemon_cannot_take_the_same_socket(short_runtime):
    path = short_runtime / "daemon.sock"
    with bind_unix_socket(path):
        with pytest.raises(DaemonAlreadyRunning):
            with bind_unix_socket(path):
                pass


def test_tailnet_discovery_uses_self_exact_json_and_argv():
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return json.dumps({
            "Self": {"TailscaleIPs": ["fd7a:115c:a1e0::1", "100.101.2.3"]},
            "Peer": {"wrong": {"TailscaleIPs": ["100.99.9.9"]}},
        })

    assert discover_tailnet_ipv4(run) == "100.101.2.3"
    assert calls == [([
        "tailscale", "status", "--json",
    ], {"capture": True, "timeout": 3.0})]


@pytest.mark.parametrize("payload", [
    {},
    {"Self": {"TailscaleIPs": ["127.0.0.1", "192.168.1.2"]}},
    {"Self": {"TailscaleIPs": "100.101.2.3"}},
])
def test_tailnet_discovery_never_falls_back_to_lan_loopback_or_wildcard(payload):
    with pytest.raises(TailnetUnavailable):
        discover_tailnet_ipv4(lambda *a, **k: json.dumps(payload))


def test_peer_bind_refuses_non_tailnet_addresses():
    for address in ("0.0.0.0", "127.0.0.1", "192.168.1.2"):
        with pytest.raises(TailnetUnavailable):
            with bind_peer_socket(address, 0):
                pass
