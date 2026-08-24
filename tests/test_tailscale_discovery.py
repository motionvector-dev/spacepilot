from __future__ import annotations

import json

import pytest

from spacepilot.daemon.tailscale import (
    TailscaleError,
    parse_status,
    status,
)


def _payload():
    return {
        "Self": {
            "ID": "node-self-stable",
            "HostName": "not-authority",
            "DNSName": "self.example.ts.net.",
            "TailscaleIPs": ["100.64.0.10", "fd7a:115c:a1e0::10"],
            "Online": True,
        },
        "Peer": {
            "nodekey:map-key-is-not-id": {
                "ID": "node-peer-stable",
                "HostName": "peer-label",
                "DNSName": "peer.example.ts.net.",
                "TailscaleIPs": ["100.64.0.20", "fd7a:115c:a1e0::20"],
                "Online": False,
            },
        },
    }


def test_status_uses_exact_argv_and_stable_ids_not_dns_or_map_keys():
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return json.dumps(_payload())

    inventory = status(run)

    assert calls == [
        (["tailscale", "status", "--json"], {"capture": True, "timeout": 3.0}),
    ]
    assert inventory.self_node.node_id == "node-self-stable"
    assert inventory.node_by_id("node-peer-stable").addresses == (
        "100.64.0.20", "fd7a:115c:a1e0::20",
    )
    with pytest.raises(TailscaleError):
        inventory.node_by_id("nodekey:map-key-is-not-id")
    with pytest.raises(TailscaleError):
        inventory.node_by_id("peer.example.ts.net.")


def test_source_ip_maps_exactly_to_one_stable_node_id():
    inventory = parse_status(_payload())
    assert inventory.node_for_source_ip("100.64.0.20").node_id == "node-peer-stable"
    assert inventory.node_for_source_ip("fd7a:115c:a1e0::20").node_id == "node-peer-stable"
    assert inventory.resolve_selector("node-peer-stable").node_id == "node-peer-stable"
    assert inventory.resolve_selector("100.64.0.20").node_id == "node-peer-stable"
    assert inventory.addresses_for_node_id("node-self-stable") == (
        "100.64.0.10", "fd7a:115c:a1e0::10",
    )


@pytest.mark.parametrize("source", [
    "peer.example.ts.net", "0.0.0.0", "127.0.0.1", "192.168.1.9", "::1",
])
def test_source_mapping_never_accepts_dns_wildcard_loopback_or_lan(source):
    with pytest.raises(TailscaleError):
        parse_status(_payload()).node_for_source_ip(source)


def test_missing_stable_id_is_not_recovered_from_peer_map_key():
    payload = _payload()
    del payload["Peer"]["nodekey:map-key-is-not-id"]["ID"]
    with pytest.raises(TailscaleError, match="no stable ID"):
        parse_status(payload)


@pytest.mark.parametrize("address", ["192.168.1.2", "127.0.0.1", "0.0.0.0"])
def test_status_rejects_non_tailscale_addresses(address):
    payload = _payload()
    payload["Peer"]["nodekey:map-key-is-not-id"]["TailscaleIPs"] = [address]
    with pytest.raises(TailscaleError, match="not in a Tailscale-assigned range"):
        parse_status(payload)


def test_duplicate_stable_id_or_address_is_ambiguous_and_rejected():
    duplicate_id = _payload()
    duplicate_id["Peer"]["nodekey:map-key-is-not-id"]["ID"] = "node-self-stable"
    with pytest.raises(TailscaleError, match="duplicate stable node ID"):
        parse_status(duplicate_id)

    duplicate_ip = _payload()
    duplicate_ip["Peer"]["nodekey:map-key-is-not-id"]["TailscaleIPs"] = ["100.64.0.10"]
    with pytest.raises(TailscaleError, match="more than one stable node ID"):
        parse_status(duplicate_ip)


def test_command_or_json_failure_is_explicit():
    with pytest.raises(TailscaleError, match="unavailable"):
        status(lambda *a, **k: (_ for _ in ()).throw(RuntimeError("tailscaled down")))
    with pytest.raises(TailscaleError, match="not JSON"):
        parse_status("not json")
