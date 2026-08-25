from __future__ import annotations

import os
import tempfile
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from spacepilot.daemon.api import FleetControl, PeerReads, create_local_app, create_peer_app
from spacepilot.daemon.identity import Identity
from spacepilot.daemon.orders import add_member, init_orders
from spacepilot.daemon.peer_auth import PEER_AUTH_HEADER, PeerAuthenticator, sign_peer_request
from spacepilot.daemon.server import bind_unix_socket
from spacepilot.daemon.tailscale import TailscaleInventory, TailscaleNode
from spacepilot.substrate import DaemonClient


class PictureOnly:
    def picture(self):
        return {"sampled_at": "2033-05-18T03:33:20+00:00"}

    def plan(self, workload):
        return {"workload": workload}

    def run(self, request):
        return {"status": "completed"}


def _short_tmpdir(prefix: str):
    """A tempdir short enough for sockaddr_un, on macOS and Linux alike.

    sockaddr_un caps the path at 103 bytes and pytest's own tmp_path names blow
    through that. This used to hardcode "/private/tmp", which is the macOS
    spelling — the path does not exist on Linux, so every daemon test errored
    in CI while passing locally. "/tmp" is short on both (on macOS it is the
    symlink to /private/tmp).
    """
    base = "/tmp" if os.path.isdir("/tmp") else tempfile.gettempdir()
    return tempfile.TemporaryDirectory(prefix=prefix, dir=base)


@pytest.fixture
def short_runtime():
    with _short_tmpdir("sp-fleet-") as directory:
        yield Path(directory)


def _identity(tmp_path, name):
    return Identity(Ed25519PrivateKey.generate(), tmp_path / f"{name}.json")


def _node(number, *, self_node=False):
    return TailscaleNode(
        f"node-stable-{number}", (f"100.64.0.{number}",),
        is_self=self_node, online=True,
    )


def _snapshot():
    return {
        "orders_version": 7,
        "rows": [{
            "member_id": "ship-1", "name": "helm", "kind": "ship",
            "state": "ready", "last_seen_at": "2033-05-18T03:33:20+00:00",
            "age_seconds": 2.0, "orders_version": 7, "errors": [],
        }],
        "errors": [],
    }


def test_local_fleet_snapshot_and_unavailable_bootstrap_are_explicit():
    fleet = FleetControl(snapshot=_snapshot)
    local = TestClient(create_local_app(PictureOnly(), fleet=fleet))
    assert local.get("/v1/fleet").json() == _snapshot()
    assert local.post("/v1/fleet/init", json={"name": "helm"}).status_code == 503
    assert local.post("/v1/fleet/add", json={"selector": "node-stable-2"}).status_code == 503
    assert local.post("/v1/fleet/join", json={
        "author_key_id": "ed25519:pin", "author_selector": "node-stable-1",
    }).status_code == 503


def test_real_temporary_uds_returns_the_injected_fleet_snapshot(short_runtime):
    app = create_local_app(PictureOnly(), fleet=FleetControl(snapshot=_snapshot))
    socket_path = short_runtime / "daemon.sock"
    with bind_unix_socket(socket_path) as bound:
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [bound.sock]}, daemon=True)
        thread.start()
        daemon = DaemonClient(socket_path, timeout=1)
        deadline = time.monotonic() + 3
        while True:
            try:
                daemon.health()
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.02)
        try:
            assert daemon._request("GET", "/v1/fleet") == _snapshot()
        finally:
            server.should_exit = True
            thread.join(timeout=3)


def test_peer_self_is_limited_and_orders_and_log_require_member_auth(tmp_path):
    author = _identity(tmp_path, "author")
    member = _identity(tmp_path, "member")
    author_node = _node(1, self_node=True)
    member_node = _node(2)
    orders = init_orders(author, author_node, name="helm")
    orders = add_member(orders, author, name="peer", public_key=member.public_key, node=member_node)
    inventory = TailscaleInventory(author_node, (author_node, member_node))
    auth = PeerAuthenticator(orders, inventory)
    log_calls = []
    reads = PeerReads(
        self_description=lambda: author.sign_envelope(
            {"tailscale_node_id": author_node.node_id}, kind="self",
        ),
        orders=orders.to_dict,
        log_records=lambda epoch, sequence, limit: (
            log_calls.append((epoch, sequence, limit)) or {"records": [{"id": "record-1"}]}
        ),
    )
    app = create_peer_app(PictureOnly(), peer_reads=reads, peer_authenticator=auth)
    client = TestClient(app, client=("100.64.0.2", 12345))

    assert client.get("/v1/self").status_code == 200
    assert client.get("/v1/orders").status_code == 401
    orders_header = sign_peer_request(member, method="GET", path="/v1/orders")
    assert client.get(
        "/v1/orders", headers={PEER_AUTH_HEADER: orders_header},
    ).json()["version"] == 2
    query = "epoch=epoch-a&limit=2&sequence=7"
    log_header = sign_peer_request(
        member, method="GET", path="/v1/log/records", query=query,
    )
    assert client.get(
        f"/v1/log/records?{query}", headers={PEER_AUTH_HEADER: log_header},
    ).json() == {"records": [{"id": "record-1"}]}
    assert log_calls == [("epoch-a", 7, 2)]

    duplicate = "limit=1&limit=2"
    duplicate_header = sign_peer_request(
        member, method="GET", path="/v1/log/records", query=duplicate,
    )
    assert client.get(
        f"/v1/log/records?{duplicate}", headers={PEER_AUTH_HEADER: duplicate_header},
    ).status_code == 400


def test_peer_app_has_no_membership_or_log_mutations(tmp_path):
    author = _identity(tmp_path, "author")
    node = _node(1, self_node=True)
    orders = init_orders(author, node, name="helm")
    auth = PeerAuthenticator(orders, TailscaleInventory(node, (node,)))
    reads = PeerReads(
        self_description=lambda: {"key_id": author.key_id},
        orders=orders.to_dict,
        log_records=lambda epoch, sequence, limit: {"records": []},
    )
    peer = TestClient(create_peer_app(PictureOnly(), peer_reads=reads, peer_authenticator=auth))
    assert peer.post("/v1/fleet/add", json={"selector": "node"}).status_code == 404
    assert peer.post("/v1/orders").status_code == 405
    assert peer.post("/v1/log/records").status_code == 405
