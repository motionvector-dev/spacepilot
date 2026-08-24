from __future__ import annotations

import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from spacepilot.daemon.identity import Identity, canonical_json
from spacepilot.daemon.orders import add_member, init_orders
from spacepilot.daemon.peer_auth import (
    NonceCache,
    PeerAuthError,
    PeerAuthMalformed,
    PeerAuthNotMember,
    PeerAuthReplay,
    PeerAuthSignatureError,
    PeerAuthSourceMismatch,
    PeerAuthStale,
    PeerAuthenticator,
    decode_peer_header,
    sign_peer_request,
)
from spacepilot.daemon.tailscale import TailscaleInventory, TailscaleNode


NOW = 2_000_000_000
NONCE = base64.urlsafe_b64encode(b"0123456789abcdef01").rstrip(b"=").decode()


def _identity(tmp_path, name):
    return Identity(Ed25519PrivateKey.generate(), tmp_path / f"{name}.json")


def _node(number, *, self_node=False):
    return TailscaleNode(
        node_id=f"node-stable-{number}", addresses=(f"100.64.0.{number}",),
        is_self=self_node, online=True,
    )


def _context(tmp_path):
    author = _identity(tmp_path, "author")
    peer = _identity(tmp_path, "peer")
    author_node = _node(1, self_node=True)
    peer_node = _node(2)
    orders = init_orders(
        author, author_node, name="helm",
        fleet_id="33333333-3333-4333-8333-333333333333",
    )
    orders = add_member(
        orders, author, name="peer", public_key=peer.public_key, node=peer_node,
    )
    inventory = TailscaleInventory(
        self_node=author_node, nodes=(author_node, peer_node),
    )
    auth = PeerAuthenticator(orders, inventory, clock=lambda: NOW)
    return author, peer, orders, inventory, auth


def _header(peer, **overrides):
    values = {
        "method": "POST",
        "path": "/v1/log/records",
        "query": "since=epoch%3A7&limit=20",
        "body": b'{"records":[]}',
        "timestamp": NOW,
        "nonce": NONCE,
    }
    values.update(overrides)
    return sign_peer_request(peer, **values)


def _verify(auth, header, **overrides):
    values = {
        "method": "POST",
        "path": "/v1/log/records",
        "query": "since=epoch%3A7&limit=20",
        "body": b'{"records":[]}',
        "source_ip": "100.64.0.2",
        "now": NOW,
    }
    values.update(overrides)
    return auth.verify(header, **values)


def test_valid_request_binds_every_http_fact_member_and_source_node(tmp_path):
    _, peer, _, _, auth = _context(tmp_path)
    accepted = _verify(auth, _header(peer))
    assert accepted.member.key_id == peer.key_id
    assert accepted.member.tailscale_node_id == "node-stable-2"
    assert accepted.source_ip == "100.64.0.2"
    assert accepted.timestamp == NOW
    assert accepted.nonce == NONCE


@pytest.mark.parametrize(("field", "changed"), [
    ("method", "PUT"),
    ("path", "/v1/log/other"),
    ("query", "limit=20&since=epoch%3A7"),
    ("body", b'{"records":[1]}'),
])
def test_method_path_raw_query_and_body_are_all_signed(tmp_path, field, changed):
    _, peer, _, _, auth = _context(tmp_path)
    with pytest.raises(PeerAuthSignatureError, match="facts do not match"):
        _verify(auth, _header(peer), **{field: changed})


def test_signature_tampering_fails_before_live_inventory_lookup(tmp_path):
    _, peer, orders, inventory, _ = _context(tmp_path)
    calls = []
    auth = PeerAuthenticator(orders, lambda: calls.append(True) or inventory, clock=lambda: NOW)
    envelope = _decode_outer(_header(peer))
    signature = bytearray(base64.urlsafe_b64decode(
        envelope["signature"] + "=" * (-len(envelope["signature"]) % 4)
    ))
    signature[0] ^= 1
    envelope["signature"] = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    with pytest.raises(PeerAuthSignatureError, match="did not verify"):
        _verify(auth, _encode_outer(envelope))
    assert calls == []


@pytest.mark.parametrize("timestamp", [NOW - 61, NOW + 61])
def test_old_and_future_requests_outside_window_are_rejected(tmp_path, timestamp):
    _, peer, _, _, auth = _context(tmp_path)
    with pytest.raises(PeerAuthStale):
        _verify(auth, _header(peer, timestamp=timestamp))


@pytest.mark.parametrize("now", [float("nan"), float("inf"), True])
def test_verifier_refuses_a_non_finite_or_boolean_clock(tmp_path, now):
    _, peer, _, _, auth = _context(tmp_path)
    with pytest.raises(PeerAuthMalformed, match="clock"):
        _verify(auth, _header(peer), now=now)


def test_nonce_replay_is_rejected_until_request_can_no_longer_be_fresh(tmp_path):
    _, peer, orders, inventory, _ = _context(tmp_path)
    cache = NonceCache(ttl_seconds=1)
    auth = PeerAuthenticator(orders, inventory, nonce_cache=cache, clock=lambda: NOW)
    header = _header(peer, timestamp=NOW + 60)
    _verify(auth, header)
    with pytest.raises(PeerAuthReplay):
        _verify(auth, header, now=NOW + 120)


def test_replay_cache_never_evicts_a_live_nonce_at_capacity(tmp_path):
    _, peer, orders, inventory, _ = _context(tmp_path)
    auth = PeerAuthenticator(
        orders, inventory, nonce_cache=NonceCache(ttl_seconds=120, max_entries=1),
        clock=lambda: NOW,
    )
    _verify(auth, _header(peer))
    other_nonce = base64.urlsafe_b64encode(b"abcdefghijklmnopqr").rstrip(b"=").decode()
    with pytest.raises(PeerAuthError, match="capacity"):
        _verify(auth, _header(peer, nonce=other_nonce))
    with pytest.raises(PeerAuthReplay):
        _verify(auth, _header(peer))


def test_removed_or_unknown_member_is_rejected_from_current_orders(tmp_path):
    author, peer, orders, inventory, _ = _context(tmp_path)
    current = [orders]
    auth = PeerAuthenticator(lambda: current[0], inventory, clock=lambda: NOW)
    header = _header(peer)
    # A current signed manifest without the peer models removal. The author is
    # permanent and remains enrolled.
    current[0] = init_orders(
        author, _node(1, self_node=True), name="helm", fleet_id=orders.fleet_id,
    )
    with pytest.raises(PeerAuthNotMember):
        _verify(auth, header)


def test_source_ip_must_map_to_the_member_bound_stable_node(tmp_path):
    _, peer, _, _, auth = _context(tmp_path)
    header = _header(peer)
    with pytest.raises(PeerAuthSourceMismatch, match="does not match"):
        _verify(auth, header, source_ip="100.64.0.1")
    with pytest.raises(PeerAuthSourceMismatch):
        _verify(auth, header, source_ip="peer.example.ts.net")
    with pytest.raises(PeerAuthSourceMismatch):
        _verify(auth, header, source_ip="192.168.1.2")


def test_forged_invalid_request_does_not_poison_nonce_cache(tmp_path):
    _, peer, orders, inventory, _ = _context(tmp_path)
    auth = PeerAuthenticator(orders, inventory, clock=lambda: NOW)
    valid = _header(peer)
    envelope = _decode_outer(valid)
    envelope["signature"] = "A" * len(envelope["signature"])
    with pytest.raises(PeerAuthSignatureError):
        _verify(auth, _encode_outer(envelope))
    assert _verify(auth, valid).member.key_id == peer.key_id


def test_header_rejects_duplicate_json_keys_unknown_fields_and_bad_nonce(tmp_path):
    _, peer, _, _, _ = _context(tmp_path)
    valid = _decode_outer(_header(peer))
    duplicate_json = (
        '{"payload":' + json.dumps(valid["payload"], separators=(",", ":"))
        + ',"signature":"' + valid["signature"] + '","signature":"again"}'
    ).encode()
    duplicate_header = base64.urlsafe_b64encode(duplicate_json).rstrip(b"=").decode()
    with pytest.raises(PeerAuthMalformed, match="duplicate"):
        decode_peer_header(duplicate_header)

    valid["payload"]["extra"] = True
    with pytest.raises(PeerAuthMalformed, match="fields"):
        decode_peer_header(_encode_outer(valid))

    with pytest.raises(PeerAuthMalformed, match="nonce"):
        sign_peer_request(
            peer, method="GET", path="/v1/picture", timestamp=NOW, nonce="short",
        )


def test_signer_refuses_ambiguous_method_path_query_or_body_types(tmp_path):
    _, peer, _, _, _ = _context(tmp_path)
    with pytest.raises(PeerAuthMalformed):
        sign_peer_request(peer, method="get", path="/v1/picture", timestamp=NOW)
    with pytest.raises(PeerAuthMalformed):
        sign_peer_request(peer, method="GET", path="/v1/picture?x=1", timestamp=NOW)
    with pytest.raises(PeerAuthMalformed):
        sign_peer_request(peer, method="GET", path="/v1/picture", query="x=1#frag", timestamp=NOW)
    with pytest.raises(PeerAuthMalformed):
        sign_peer_request(peer, method="GET", path="/v1/picture", body="not bytes", timestamp=NOW)  # type: ignore[arg-type]


def _decode_outer(header):
    raw = base64.urlsafe_b64decode(header + "=" * (-len(header) % 4))
    return json.loads(raw)


def _encode_outer(value):
    return base64.urlsafe_b64encode(canonical_json(value)).rstrip(b"=").decode()
