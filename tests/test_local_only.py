"""This server hands out a token that opens a shell. These are the attacks.

Each test performs the request an attacker would, rather than asserting that a
setting has the right value — a config check passes just as happily when the
middleware was never mounted.
"""

import pytest
from fastapi.testclient import TestClient

from spacepilot.app import create_app
from spacepilot.api.security import (
    is_local_hostname, is_loopback_client, origin_allowed,
)
from spacepilot.core.config import get_settings


@pytest.fixture
def client():
    return TestClient(create_app())


# ------------------------------------------------------------ DNS rebinding

def test_a_foreign_host_header_is_refused(client):
    """The rebinding defence.

    The attack makes a browser believe an attacker's domain is this server,
    which defeats every origin check. What it cannot change is the Host header:
    it still carries their name, and this machine was never called that.
    """
    r = client.get("/api/token", headers={"Host": "evil.example.com"})
    assert r.status_code == 421
    assert "localhost" in r.json()["detail"]


def test_a_foreign_host_cannot_reach_any_route(client):
    """Not just the token — the guard is global, so nothing is reachable."""
    for path in ("/api/status", "/api/compute/local-profile", "/api/docs"):
        r = client.get(path, headers={"Host": "evil.example.com"})
        assert r.status_code == 421, f"{path} answered a rebinding host"


@pytest.mark.parametrize("host", [
    "localhost:8088", "127.0.0.1:8088", "[::1]:8088",
    "spacepilot.localhost", "pluto.localhost:8088",
])
def test_the_names_this_machine_actually_answers_to(client, host):
    r = client.get("/api/status", headers={"Host": host})
    assert r.status_code != 421, f"{host} should be accepted"


def test_a_lan_address_is_not_a_local_name():
    """Reaching the box by its LAN address is not the same as being local."""
    assert not is_local_hostname("192.168.1.14:8088")
    assert not is_local_hostname("10.0.0.5")
    assert not is_local_hostname("evil.example.com")


# ------------------------------------------------------------- the token

def test_the_token_is_issued_to_loopback_only(client):
    """It unlocks every other gate, so it never leaves this machine."""
    ok = client.get("/api/token")
    assert ok.status_code == 200 and ok.json()["token"]

    assert not is_loopback_client("192.168.1.14")
    assert not is_loopback_client(None)
    assert is_loopback_client("127.0.0.1")
    assert is_loopback_client("::1")


# --------------------------------------------------------------- websockets

def test_a_foreign_origin_is_rejected_on_a_websocket():
    """CORS does not apply to websockets, so the handler checks by hand."""
    allowed = get_settings().cors_origins
    assert not origin_allowed("https://evil.example", allowed)
    assert not origin_allowed("http://192.168.1.14:8088", allowed)
    assert origin_allowed("http://127.0.0.1:8088", allowed)
    assert origin_allowed("http://spacepilot.localhost", allowed)


def test_a_missing_origin_is_allowed():
    """The CLI, tests and MCP servers send no Origin and are not the threat.

    The attack this defends against is a page running in the user's browser,
    and browsers always send one.
    """
    assert origin_allowed(None, [])


def test_the_shell_socket_refuses_a_rebinding_host(client):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises((WebSocketDisconnect, Exception)):
        with client.websocket_connect(
            "/api/gpu/inspect/shell", headers={"Host": "evil.example.com"}
        ) as ws:
            ws.send_json({"type": "auth", "token": "anything"})
            ws.receive_text()


# ---------------------------------------------------------------- the bind

def test_the_default_bind_is_this_machine_only():
    """0.0.0.0 published the shell to whatever network the laptop joined."""
    assert get_settings().host == "127.0.0.1"


def test_serving_remotely_is_a_deliberate_opt_in(monkeypatch):
    """Widening the bind and dropping the guard move together.

    One without the other produces a server that listens on every interface and
    then refuses everything that reaches it, which reads as a bug and invites
    someone to disable the wrong half.
    """
    import spacepilot.core.config as cfg
    monkeypatch.setenv("PLUTO_ALLOW_REMOTE", "1")
    monkeypatch.setattr(cfg, "_settings_instance", None)
    assert cfg.get_settings().local_only is False

    monkeypatch.setenv("PLUTO_ALLOW_REMOTE", "")
    monkeypatch.setattr(cfg, "_settings_instance", None)
    assert cfg.get_settings().local_only is True
