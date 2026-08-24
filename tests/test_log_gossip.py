"""LOG is a signed, privacy-safe projection and immutable replica format."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from spacepilot.daemon.identity import load_or_create
from spacepilot.daemon.log import (
    MAX_PAGE_BYTES,
    LogError,
    LogImmutableError,
    LogStore,
    make_page,
    make_record,
    GossipPuller,
    LocalLogPublisher,
    verify_page,
    verify_record,
)


@pytest.fixture()
def identity(tmp_path, monkeypatch):
    monkeypatch.setenv("SPACEPILOT_DATA_DIR", str(tmp_path / "data"))
    return load_or_create()


def test_projection_allowlist_redacts_private_measurement_fields(identity):
    measurement = {
        "schema": 1,
        "system_id": "box",
        "model_id": "demo",
        "metric": "seconds_per_image",
        "value": 4.0,
        "contention": "solo",
        "measured_on": "2026-08-25T00:00:00+00:00",
        "interpreter": "/Users/alice/.venv/bin/python",
        "note": "private note",
        "error": "secret error",
        "knobs": {"prompt": "hide this", "path": "/tmp/secret"},
        "output_path": "/tmp/output.png",
    }
    record = make_record(identity, "measurement", measurement)
    payload = record["payload"]
    assert payload["model_id"] == "demo"
    for private in ("interpreter", "note", "error", "knobs", "output_path"):
        assert private not in payload
    assert verify_record(record)["record_id"] == record["record_id"]


def test_records_are_content_hashed_and_tampering_fails(identity):
    record = make_record(identity, "system", {"id": "box", "backend": "cpu", "prompt": "omit"})
    assert record["record_id"].startswith("sha256:")
    record["payload"]["backend"] = "gpu"
    with pytest.raises(LogError):
        verify_record(record)


def test_page_signature_binds_epoch_sequence_reset_and_records(identity):
    record = make_record(identity, "system", {"id": "box"})
    page = make_page(identity, [record], epoch="epoch-a", sequence=4, reset=False)
    assert verify_page(page)["cursor"] == {"epoch": "epoch-a", "sequence": 4, "reset": False}
    page["sequence"] = 5
    with pytest.raises(LogError):
        verify_page(page)


def test_remote_replica_is_verified_immutable_and_keeps_original_author(identity, tmp_path, monkeypatch):
    monkeypatch_data = tmp_path / "data"
    monkeypatch.setenv("SPACEPILOT_DATA_DIR", str(monkeypatch_data))
    original = identity
    monkeypatch.setenv("SPACEPILOT_DATA_DIR", str(monkeypatch_data))
    relay = load_or_create()
    record = make_record(original, "system", {"id": "original"})
    page = make_page(relay, [record], epoch="e", sequence=0)
    store = LogStore(tmp_path / "replicas")
    path = store.ingest_page(page)
    assert path.exists()
    assert json.loads(path.read_text())["records"][0]["author_key_id"] == original.key_id
    assert store.ingest_page(page) == path
    conflicting = dict(page)
    conflicting["records"] = []
    with pytest.raises(LogError):
        store.ingest_page(conflicting)


def test_oversized_page_is_rejected(identity):
    record = make_record(identity, "system", {"id": "box"})
    page = make_page(identity, [record], epoch="e", sequence=0)
    page["payload_padding"] = "x" * MAX_PAGE_BYTES
    with pytest.raises(LogError):
        verify_page(page)


def test_local_publisher_has_stable_epoch_sequence_and_reset_paging(identity, tmp_path):
    systems = [{"id": "box-a", "backend": "cpu"}]
    store = LogStore(tmp_path / "local-log", identity=identity)
    publisher = LocalLogPublisher(
        identity,
        store=store,
        state_path=tmp_path / "state.json",
        page_size=1,
        systems_loader=lambda: systems,
        measurements_loader=lambda: [],
    )
    first = publisher.records_since(None, -1, 1)
    assert first["reset"] is True
    assert first["epoch"] == publisher.epoch
    assert first["sequence"] == 0
    old_epoch = publisher.epoch
    systems.append({"id": "box-b", "backend": "cpu"})
    second = publisher.records_since(old_epoch, 0, 1)
    assert second["reset"] is False
    assert second["sequence"] == 1
    restarted = LocalLogPublisher(
        identity,
        store=store,
        state_path=tmp_path / "state.json",
        page_size=1,
        systems_loader=lambda: systems,
        measurements_loader=lambda: [],
    )
    assert restarted.epoch == old_epoch
    assert restarted.sequence == 1
    reset = restarted.records_since("stale-epoch", 999, 1)
    assert reset["reset"] is True
    assert reset["epoch"] == old_epoch


def test_limit_smaller_than_stored_page_never_skips_its_remaining_records(identity, tmp_path):
    systems = [{"id": f"box-{number}"} for number in range(3)]
    publisher = LocalLogPublisher(
        identity,
        store=LogStore(tmp_path / "local-log", identity=identity),
        state_path=tmp_path / "state.json",
        page_size=3,
        systems_loader=lambda: systems,
        measurements_loader=lambda: [],
    )
    first = publisher.records_since(None, -1, 1)
    # The limit is soft when the next immutable page is larger. Returning one
    # record while advancing sequence 0 would skip the other two forever.
    assert len(first["records"]) == 3
    assert first["sequence"] == 0
    after = publisher.records_since(first["epoch"], first["sequence"], 1)
    assert after["records"] == []


@dataclass(frozen=True)
class _Node:
    node_id: str


@dataclass(frozen=True)
class _Member:
    key_id: str
    tailscale_node_id: str


class _Inventory:
    def __init__(self, nodes):
        self.nodes = dict(nodes)

    def node_by_id(self, node_id):
        if node_id not in self.nodes:
            raise KeyError(node_id)
        return self.nodes[node_id]


class _Orders:
    def __init__(self, members):
        self.members = tuple(members)


class _Peer:
    def __init__(self, page):
        self.page = page
        self.calls = []

    def get(self, node, path, *, authenticated, query):
        self.calls.append((node, path, authenticated, query))
        return {"pages": [self.page]}


def test_gossip_puller_authenticates_current_member_and_preserves_relayed_author(identity, tmp_path):
    original = identity
    relay_data = tmp_path / "relay-data"
    os.environ["SPACEPILOT_DATA_DIR"] = str(relay_data)
    relay = load_or_create()
    os.environ["SPACEPILOT_DATA_DIR"] = str(tmp_path / "puller-data")
    puller_identity = load_or_create()
    original_record = make_record(original, "system", {"id": "original-box"})
    page = make_page(relay, [original_record], epoch="relay-epoch", sequence=0)
    member = _Member(relay.key_id, "relay-node")
    peer = _Peer(page)
    from spacepilot.daemon.index import IndexWriter, FleetIndex
    writer = IndexWriter(tmp_path / "index.sqlite3")
    try:
        puller = GossipPuller(
            puller_identity,
            orders_supplier=lambda: _Orders([member]),
            inventory_supplier=lambda: _Inventory({"relay-node": _Node("relay-node")}),
            peer_client=peer,
            store=LogStore(tmp_path / "replicas"),
            index_writer=writer,
        )
        result = puller.pull_once()
    finally:
        writer.close()
    assert result.pulled_pages == 1
    assert result.pulled_records == 1
    assert not result.errors
    assert peer.calls[0][1:] == ("/v1/log/records", True, {"limit": "256"})
    assert FleetIndex(tmp_path / "index.sqlite3").systems()[0]["author_key_id"] == original.key_id


def test_gossip_puller_skips_member_removed_from_live_inventory(identity, tmp_path):
    member = _Member(identity.key_id + "-remote", "removed-node")
    puller = GossipPuller(
        identity,
        orders_supplier=lambda: _Orders([member]),
        inventory_supplier=lambda: _Inventory({}),
        peer_client=_Peer(make_page(identity, [], epoch="e", sequence=0)),
        store=LogStore(tmp_path / "replicas"),
    )
    result = puller.pull_once()
    assert result.pulled_pages == 0
    assert result.skipped_members == (member.key_id,)
