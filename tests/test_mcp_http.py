"""The stable Studio process also hosts the versioned MCP transport."""

import pytest
from fastapi.testclient import TestClient

from spacepilot.app import MCP_HTTP_PATH, create_app


@pytest.fixture
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


def test_human_docs_are_available_at_the_canonical_route(client):
    response = client.get("/docs", headers={"Host": "spacepilot.localhost:8088"})
    assert response.status_code == 200
    assert "SpacePilot" in response.text


def test_mcp_v1_accepts_an_initialize_request(client):
    response = client.post(
        MCP_HTTP_PATH,
        headers={
            "Host": "spacepilot.localhost:8088",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "spacepilot-test", "version": "1"},
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["serverInfo"]["name"] == "SpacePilot"


def test_initialize_reports_the_package_version_not_an_empty_string(client):
    """A blank version tells a client nothing about what it is talking to."""
    from spacepilot.core.config import get_settings

    response = client.post(
        MCP_HTTP_PATH,
        headers={
            "Host": "spacepilot.localhost:8088",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "spacepilot-test", "version": "1"},
            },
        },
    )
    assert response.status_code == 200
    reported = response.json()["result"]["serverInfo"]["version"]
    assert reported, "serverInfo.version was empty"
    assert reported == get_settings().version


def test_mcp_transport_is_covered_by_the_host_guard(client):
    response = client.post(
        MCP_HTTP_PATH,
        headers={
            "Host": "evil.example",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
    )
    assert response.status_code == 421


def test_mvec_port_is_used_when_spacepilot_port_is_absent(monkeypatch):
    from spacepilot import web_api

    monkeypatch.delenv("SPACEPILOT_STUDIO_PORT", raising=False)
    monkeypatch.delenv("PLUTO_STUDIO_PORT", raising=False)
    monkeypatch.setenv("PORT", "18088")
    assert web_api.studio_port() == 18088


def test_spacepilot_port_wins_over_mvec_port(monkeypatch):
    from spacepilot import web_api

    monkeypatch.setenv("SPACEPILOT_STUDIO_PORT", "28088")
    monkeypatch.setenv("PORT", "18088")
    assert web_api.studio_port() == 28088


def test_ambient_host_cannot_widen_the_loopback_bind(monkeypatch):
    from spacepilot import web_api

    monkeypatch.delenv("SPACEPILOT_STUDIO_HOST", raising=False)
    monkeypatch.delenv("PLUTO_STUDIO_HOST", raising=False)
    monkeypatch.setenv("HOST", "0.0.0.0")
    assert web_api.studio_host() == "127.0.0.1"
