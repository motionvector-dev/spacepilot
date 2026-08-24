from __future__ import annotations

import datetime as dt
import time

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from spacepilot.daemon.fleet import FleetManager, verify_member_picture
from spacepilot.daemon.identity import Identity, sign_picture
from spacepilot.daemon.index import FleetIndex, IndexWriter
from spacepilot.daemon.log import GossipResult, LogStore, make_page, make_record
from spacepilot.daemon.orders import OrdersStore, add_member, init_orders
from spacepilot.daemon.peer_auth import PEER_AUTH_HEADER, decode_peer_header
from spacepilot.daemon.runtime import (
    FleetBackgroundLoop,
    FleetRuntime,
    FleetRuntimeError,
    HttpxPeerClient,
    build_runtime,
)
from spacepilot.daemon.tailscale import TailscaleInventory, TailscaleNode


def _identity(tmp_path, name):
    return Identity(Ed25519PrivateKey.generate(), tmp_path / f"{name}.json")


def _node(number, *, self_node=False):
    return TailscaleNode(
        f"node-stable-{number}", (f"100.64.0.{number}",),
        is_self=self_node, online=True,
    )


class FakePeerClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, node, path, *, authenticated):
        self.calls.append((node.node_id, path, authenticated))
        return self.responses[path]


def _runtime(tmp_path, who, inventory, peer):
    manager = FleetManager(
        fetch_picture=lambda member: (_ for _ in ()).throw(ConnectionError("offline")),
        verify_picture=verify_member_picture,
    )
    return FleetRuntime(
        identity=who,
        store=OrdersStore(tmp_path / "fleet" / "fleet.yaml"),
        inventory_supplier=lambda: inventory,
        peer_client=peer,
        manager=manager,
        log_store=LogStore(tmp_path / "log"),
        ship_name_supplier=lambda: "local-ship",
    )


def test_init_and_add_bind_signed_self_to_exact_live_node(tmp_path):
    author = _identity(tmp_path, "author")
    recruit = _identity(tmp_path, "recruit")
    author_node = _node(1, self_node=True)
    recruit_node = _node(2)
    inventory = TailscaleInventory(author_node, (author_node, recruit_node))
    peer = FakePeerClient({
        "/v1/self": recruit.sign_envelope(
            {"schema": 1, "key_id": recruit.key_id,
             "name": "borealis",
             "tailscale_node_id": recruit_node.node_id}, kind="self",
        ),
    })
    runtime = _runtime(tmp_path, author, inventory, peer)

    assert runtime.init("helm")["orders_version"] == 1
    assert runtime.add("100.64.0.2")["orders_version"] == 2
    saved = runtime.store.load()
    assert saved.member(recruit.key_id).tailscale_node_id == recruit_node.node_id
    assert saved.member(recruit.key_id).name == "borealis"
    assert peer.calls == [(recruit_node.node_id, "/v1/self", False)]


def test_add_rejects_signed_self_for_a_different_stable_node(tmp_path):
    author = _identity(tmp_path, "author")
    recruit = _identity(tmp_path, "recruit")
    author_node = _node(1, self_node=True)
    recruit_node = _node(2)
    inventory = TailscaleInventory(author_node, (author_node, recruit_node))
    peer = FakePeerClient({
        "/v1/self": recruit.sign_envelope(
            {"schema": 1, "key_id": recruit.key_id, "name": "borealis",
             "tailscale_node_id": "node-stable-9"}, kind="self",
        ),
    })
    runtime = _runtime(tmp_path, author, inventory, peer)
    runtime.init("helm")
    with pytest.raises(FleetRuntimeError, match="stable node ID"):
        runtime.add(recruit_node.node_id)
    assert runtime.store.load().version == 1


@pytest.mark.parametrize("bad_name", ["", " padded ", "bad\nname", "x" * 129])
def test_add_rejects_invalid_signed_ship_name(tmp_path, bad_name):
    author = _identity(tmp_path, "author")
    recruit = _identity(tmp_path, "recruit")
    author_node = _node(1, self_node=True)
    recruit_node = _node(2)
    inventory = TailscaleInventory(author_node, (author_node, recruit_node))
    peer = FakePeerClient({
        "/v1/self": recruit.sign_envelope({
            "schema": 1, "key_id": recruit.key_id, "name": bad_name,
            "tailscale_node_id": recruit_node.node_id,
        }, kind="self"),
    })
    runtime = _runtime(tmp_path, author, inventory, peer)
    runtime.init("helm")
    with pytest.raises(FleetRuntimeError, match="ship name"):
        runtime.add(recruit_node.node_id)
    assert runtime.store.load().version == 1


def test_join_pins_author_then_uses_authenticated_orders_read(tmp_path):
    author = _identity(tmp_path, "author")
    joiner = _identity(tmp_path, "joiner")
    authored_node = _node(1, self_node=True)
    joining_node = _node(2)
    orders = init_orders(author, authored_node, name="helm")
    orders = add_member(
        orders, author, name="joiner", public_key=joiner.public_key, node=joining_node,
    )
    local_joining = TailscaleNode(
        joining_node.node_id, joining_node.addresses, is_self=True, online=True,
    )
    remote_author = TailscaleNode(
        authored_node.node_id, authored_node.addresses, is_self=False, online=True,
    )
    inventory = TailscaleInventory(local_joining, (local_joining, remote_author))
    peer = FakePeerClient({
        "/v1/self": author.sign_envelope(
            {"schema": 1, "key_id": author.key_id, "name": "helm",
             "tailscale_node_id": remote_author.node_id}, kind="self",
        ),
        "/v1/orders": orders.to_dict(),
    })
    runtime = _runtime(tmp_path, joiner, inventory, peer)

    joined = runtime.join(author.key_id, remote_author.node_id, orders.fleet_id)
    assert joined["orders_version"] == 2
    assert peer.calls == [
        (remote_author.node_id, "/v1/self", False),
        (remote_author.node_id, "/v1/orders", True),
    ]


def test_self_description_is_only_signed_identity_and_node_binding(tmp_path):
    author = _identity(tmp_path, "author")
    author_node = _node(1, self_node=True)
    inventory = TailscaleInventory(author_node, (author_node,))
    runtime = _runtime(tmp_path, author, inventory, FakePeerClient({}))
    runtime.init("helm")

    envelope = runtime.self_description()
    assert set(envelope["payload"]) == {"schema", "key_id", "name", "tailscale_node_id"}
    assert envelope["payload"]["name"] == "local-ship"
    assert "orders" not in envelope["payload"]


def test_uninitialized_snapshot_is_explicit_not_fake_success(tmp_path):
    author = _identity(tmp_path, "author")
    author_node = _node(1, self_node=True)
    runtime = _runtime(
        tmp_path, author, TailscaleInventory(author_node, (author_node,)), FakePeerClient({}),
    )
    snapshot = runtime.snapshot()
    assert snapshot["orders_version"] is None
    assert snapshot["rows"] == []
    assert snapshot["errors"] == ["fleet is not initialized"]


def test_picture_poll_signs_request_and_verifies_member_envelope(tmp_path):
    author = _identity(tmp_path, "author")
    author_node = _node(1, self_node=True)
    inventory = TailscaleInventory(author_node, (author_node,))
    now = dt.datetime.now(dt.timezone.utc)
    picture = {
        "sampled_at": now.isoformat(),
        "workers": {"state": "fresh", "value": {"status": "ready"}},
    }
    peer = FakePeerClient({"/v1/picture": sign_picture(author, picture)})
    store = OrdersStore(tmp_path / "fleet.yaml")
    store.initialize(author, author_node, name="helm")
    runtime = build_runtime(
        author, peer_port=8765, inventory_supplier=lambda: inventory,
        peer_client=peer, store=store, log_store=LogStore(tmp_path / "log"),
    )
    snapshot = runtime.snapshot()
    assert snapshot["rows"][0]["state"] == "ready"
    assert peer.calls == [(author_node.node_id, "/v1/picture", True)]


def test_httpx_peer_client_uses_literal_address_and_auth_header(tmp_path):
    who = _identity(tmp_path, "member")
    node = _node(2)
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    client = HttpxPeerClient(
        who, port=9999, transport=httpx.MockTransport(handler),
    )
    assert client.get(node, "/v1/self", authenticated=False) == {"ok": True}
    assert client.get(node, "/v1/orders", authenticated=True, query={
        "sequence": "7", "epoch": "a b", "limit": "2",
    }) == {"ok": True}
    assert str(seen[0].url) == "http://100.64.0.2:9999/v1/self"
    assert PEER_AUTH_HEADER not in seen[0].headers
    assert str(seen[1].url) == "http://100.64.0.2:9999/v1/orders?epoch=a%20b&limit=2&sequence=7"
    header = seen[1].headers.get(PEER_AUTH_HEADER)
    assert header
    payload, _ = decode_peer_header(header)
    assert payload["query"] == "epoch=a%20b&limit=2&sequence=7"


def test_background_tick_indexes_local_records_and_retains_gossip_errors(tmp_path):
    who = _identity(tmp_path, "author")
    record = make_record(who, "system", {"id": "local-box"})
    page = make_page(who, [record], epoch="epoch-a", sequence=0)

    class Publisher:
        def refresh(self):
            return [page]

    class Puller:
        def pull_once(self):
            return GossipResult(0, 0, errors=("peer asleep",))

    writer = IndexWriter(tmp_path / "fleet.sqlite3")
    try:
        loop = FleetBackgroundLoop(
            Publisher(), Puller(), index_writer=writer, interval_seconds=0.01,
            clock=lambda: 123.0,
        )
        status = loop.tick()
        assert status["state"] == "degraded"
        assert status["errors"] == ["peer asleep"]
        assert status["observed_at"] == 123.0
        rows = FleetIndex(tmp_path / "fleet.sqlite3").systems()
        assert len(rows) == 1
        assert "local-box" in rows[0]["payload_json"]
    finally:
        writer.close()


def test_background_lifecycle_is_non_blocking_and_stops_cleanly():
    calls = []

    class Publisher:
        def refresh(self):
            calls.append("publish")
            return []

    class Puller:
        def pull_once(self):
            calls.append("pull")
            return GossipResult(0, 0)

    loop = FleetBackgroundLoop(Publisher(), Puller(), interval_seconds=0.01)
    loop.start()
    deadline = time.monotonic() + 1
    while len(calls) < 2 and time.monotonic() < deadline:
        time.sleep(0.005)
    loop.stop()
    assert calls[:2] == ["publish", "pull"]
    assert loop.snapshot()["state"] == "stopped"
