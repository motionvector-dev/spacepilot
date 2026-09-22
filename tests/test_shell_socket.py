"""The shell websocket: its gates, and what it says when AWS fails.

`/api/gpu/inspect/shell` hands out an interactive shell on a billing GPU box,
so every gate in front of it is load-bearing and none of them had a test.

The failure this file was written for: with a valid token and no running
instance, the handler means to send `{"type":"error"}` and close 1011. It
asked AWS first, `get_instance_info` raised out of `run_cmd`, the exception
escaped the handler, and the client got a bare 1006 with no message — every
AWS failure (missing profile, expired credentials, no network) looked like an
unexplained drop.
"""

import json
import logging

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import spacepilot.web_api as web_api

SHELL = "/api/gpu/inspect/shell"

CFG = {
    "aws_profile": "test-profile",
    "aws_region": "us-east-1",
    "instance_type": "g6e.2xlarge",
    "key_file": "/nonexistent/key.pem",
}


@pytest.fixture
def client():
    return TestClient(web_api.app)


@pytest.fixture
def token():
    return web_api.STUDIO_TOKEN


@pytest.fixture(autouse=True)
def never_reach_aws_or_ssh(monkeypatch):
    """No test here may shell out. Each one overrides what it needs."""
    monkeypatch.setattr(web_api, "load_config", lambda: dict(CFG), raising=False)
    monkeypatch.setattr(web_api, "get_instance_info", lambda cfg: None, raising=False)


# ------------------------------------------------------------- the gates

def test_a_foreign_origin_never_reaches_the_auth_frame(client):
    """CORS does not apply to websockets; the handler checks Origin by hand."""
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            SHELL, headers={"Origin": "https://evil.example"}
        ) as ws:
            ws.receive()


def test_a_rebinding_host_never_reaches_the_auth_frame(client):
    """A re-resolved attacker domain still carries its own name in Host."""
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            SHELL, headers={"Host": "evil.example.com"}
        ) as ws:
            ws.receive()


def test_a_wrong_token_is_closed_1008(client):
    with client.websocket_connect(SHELL) as ws:
        ws.send_json({"type": "auth", "token": "not-the-token"})
        assert ws.receive() == {"type": "websocket.close", "code": 1008, "reason": ""}


def test_an_empty_token_is_closed_1008(client):
    with client.websocket_connect(SHELL) as ws:
        ws.send_json({"type": "auth", "token": ""})
        assert ws.receive()["code"] == 1008


def test_a_frame_that_is_not_an_auth_frame_is_closed_1008(client, token):
    """The right token in the wrong frame is still not an authentication."""
    with client.websocket_connect(SHELL) as ws:
        ws.send_json({"type": "resize", "token": token, "cols": 80})
        assert ws.receive()["code"] == 1008


def test_a_frame_that_is_not_json_is_closed_1008(client):
    with client.websocket_connect(SHELL) as ws:
        ws.send_text("not json at all")
        assert ws.receive()["code"] == 1008


def test_a_client_that_never_authenticates_is_closed_1008(client):
    """The 3s window: an accepted socket that stays silent is not left open."""
    with client.websocket_connect(SHELL) as ws:
        assert ws.receive()["code"] == 1008


def test_an_auth_frame_sent_after_the_window_buys_nothing(client, token, monkeypatch):
    """Saying the right thing late does not reopen the window.

    Asserted by what the handler does next rather than by what comes back:
    past the close there is nothing to receive and a second read would hang.
    If the late frame had been honoured, the handler would go on to ask AWS
    for the instance — so a lookup that records its calls proves it did not.
    """
    calls = []
    monkeypatch.setattr(
        web_api, "get_instance_info", lambda cfg: calls.append(cfg), raising=False
    )
    with client.websocket_connect(SHELL) as ws:
        assert ws.receive()["code"] == 1008
        ws.send_json({"type": "auth", "token": token})
    assert calls == [], "a late auth frame reopened the authenticated path"


def test_cross_origin_reads_of_the_token_route_are_not_allowed(client):
    """The token unlocks this socket, so a foreign page must not read it."""
    r = client.get("/api/token", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


# ------------------------------------------------- what it says when it fails

def test_no_running_instance_is_reported_and_closed_1011(client, token):
    with client.websocket_connect(SHELL) as ws:
        ws.send_json({"type": "auth", "token": token})
        msg = json.loads(ws.receive_text())
        assert msg == {"type": "error", "message": "Instance not running"}
        assert ws.receive()["code"] == 1011


def test_an_aws_failure_is_reported_instead_of_crashing(client, token, monkeypatch, caplog):
    """The bug: this raised out of the handler and the client saw a bare 1006."""
    def boom(cfg):
        raise RuntimeError(
            "Command failed (255): aws ec2 describe-instances\n"
            "The config profile (new-profile) could not be found"
        )

    monkeypatch.setattr(web_api, "get_instance_info", boom, raising=False)
    with caplog.at_level(logging.ERROR, logger="spacepilot.api.routes.gpu"):
        with client.websocket_connect(SHELL) as ws:
            ws.send_json({"type": "auth", "token": token})
            msg = json.loads(ws.receive_text())
            assert msg["type"] == "error"
            assert "could not be found" in msg["message"]
            assert ws.receive()["code"] == 1011

    # The catch is total, so the trace has to land somewhere a developer looks.
    assert any(r.exc_info for r in caplog.records), "the failure was swallowed silently"


def test_a_long_failure_message_is_bounded_on_the_socket(client, token, monkeypatch):
    """aws stderr can be long; the socket gets a bounded slice of it."""
    def boom(cfg):
        raise RuntimeError("x" * 5000)

    monkeypatch.setattr(web_api, "get_instance_info", boom, raising=False)
    with client.websocket_connect(SHELL) as ws:
        ws.send_json({"type": "auth", "token": token})
        msg = json.loads(ws.receive_text())
        assert 0 < len(msg["message"]) <= 500
        assert ws.receive()["code"] == 1011


def test_an_error_with_no_message_still_names_itself(client, token, monkeypatch):
    """`str(exc)` is empty for a bare raise; an empty error frame says nothing."""
    def boom(cfg):
        raise TimeoutError()

    monkeypatch.setattr(web_api, "get_instance_info", boom, raising=False)
    with client.websocket_connect(SHELL) as ws:
        ws.send_json({"type": "auth", "token": token})
        msg = json.loads(ws.receive_text())
        assert msg["message"] == "TimeoutError"
        assert ws.receive()["code"] == 1011


def test_an_unreadable_config_is_reported_instead_of_crashing(client, token, monkeypatch):
    """load_config is inside the same guard; it reads a file that may be broken."""
    def boom():
        raise RuntimeError("config unreadable")

    monkeypatch.setattr(web_api, "load_config", boom, raising=False)
    with client.websocket_connect(SHELL) as ws:
        ws.send_json({"type": "auth", "token": token})
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "error"
        assert ws.receive()["code"] == 1011
