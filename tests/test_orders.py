from __future__ import annotations

import os
import stat
from dataclasses import replace

import pytest
import yaml
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from spacepilot.daemon.identity import Identity
from spacepilot.daemon.orders import (
    OrdersAuthorError,
    OrdersBootstrapError,
    OrdersEquivocationError,
    OrdersError,
    OrdersRollbackError,
    OrdersSignatureError,
    OrdersStore,
    add_member,
    dump_orders,
    init_orders,
    join_orders,
    load_yaml_strict,
    parse_orders,
    validate_transition,
)
from spacepilot.daemon.tailscale import TailscaleNode


def _identity(tmp_path, name):
    return Identity(Ed25519PrivateKey.generate(), tmp_path / f"{name}.json")


def _node(number, *, self_node=False):
    return TailscaleNode(
        node_id=f"node-stable-{number}",
        addresses=(f"100.64.0.{number}",),
        is_self=self_node,
        online=True,
    )


def _fleet(tmp_path):
    author = _identity(tmp_path, "author")
    orders = init_orders(
        author, _node(1, self_node=True), name="helm",
        fleet_id="11111111-1111-4111-8111-111111111111",
    )
    return author, orders


def test_semantic_signature_survives_yaml_format_mapping_and_member_order(tmp_path):
    author, first = _fleet(tmp_path)
    peer = _identity(tmp_path, "peer")
    orders = add_member(first, author, name="peer", public_key=peer.public_key, node=_node(2))
    raw = orders.to_dict()
    raw["members"] = list(reversed(raw["members"]))
    reordered = {
        "signature": raw["signature"], "members": raw["members"],
        "author": raw["author"], "version": raw["version"],
        "fleet_id": raw["fleet_id"], "schema": raw["schema"],
        "providers": raw["providers"],
    }
    text = "# comments and YAML order are not signed\n" + yaml.safe_dump(reordered, sort_keys=False)
    parsed = parse_orders(text)
    assert parsed.semantic_digest == orders.semantic_digest
    assert [member.key_id for member in parsed.members] == sorted(
        member.key_id for member in orders.members
    )


@pytest.mark.parametrize("text", [
    "schema: 1\nschema: 1\n",
    "author:\n  key_id: one\n  key_id: two\n",
    "base: &base\n  name: one\nmember:\n  <<: *base\n  name: two\n",
])
def test_duplicate_yaml_keys_are_rejected_at_every_level(text):
    with pytest.raises(OrdersError, match="duplicate YAML key"):
        load_yaml_strict(text)


def test_tampering_any_signed_fact_fails_verification(tmp_path):
    _, orders = _fleet(tmp_path)
    raw = orders.to_dict()
    raw["version"] = 2
    with pytest.raises(OrdersSignatureError, match="did not verify"):
        parse_orders(raw)

    raw = orders.to_dict()
    raw["members"][0]["name"] = "renamed without author"
    with pytest.raises(OrdersSignatureError, match="did not verify"):
        parse_orders(raw)


def test_member_key_id_is_derived_and_node_binding_is_unique(tmp_path):
    author, first = _fleet(tmp_path)
    peer = _identity(tmp_path, "peer")
    second = add_member(first, author, name="peer", public_key=peer.public_key, node=_node(2))
    member = second.member(peer.key_id)
    assert member is not None
    assert member.key_id == peer.key_id
    assert member.tailscale_node_id == "node-stable-2"
    assert second.version == 2
    assert add_member(second, author, name="peer", public_key=peer.public_key, node=_node(2)) is second

    another = _identity(tmp_path, "another")
    with pytest.raises(OrdersError, match="already bound"):
        add_member(second, author, name="another", public_key=another.public_key, node=_node(2))


def test_only_permanent_author_can_add_and_author_never_changes(tmp_path):
    author, current = _fleet(tmp_path)
    impostor = _identity(tmp_path, "impostor")
    with pytest.raises(OrdersAuthorError, match="only the permanent author"):
        add_member(current, impostor, name="peer", public_key=impostor.public_key, node=_node(2))

    other_v1 = init_orders(
        impostor, _node(2, self_node=True), name="new helm", fleet_id=current.fleet_id,
    )
    other_fleet = add_member(
        other_v1, impostor, name="other", public_key=author.public_key, node=_node(3),
    )
    # A valid signature by another key still cannot rotate the permanent author.
    with pytest.raises(OrdersAuthorError, match="permanent"):
        validate_transition(current, other_fleet)


def test_rollback_and_same_version_equivocation_are_rejected(tmp_path):
    author, v1 = _fleet(tmp_path)
    left = _identity(tmp_path, "left")
    right = _identity(tmp_path, "right")
    v2_left = add_member(v1, author, name="left", public_key=left.public_key, node=_node(2))
    v2_right = add_member(v1, author, name="right", public_key=right.public_key, node=_node(3))

    with pytest.raises(OrdersRollbackError):
        validate_transition(v2_left, v1)
    with pytest.raises(OrdersEquivocationError):
        validate_transition(v2_left, v2_right)
    assert validate_transition(v2_left, parse_orders(dump_orders(v2_left))) is v2_left


def test_join_requires_pinned_author_prior_enrollment_and_exact_self_node(tmp_path):
    author, v1 = _fleet(tmp_path)
    joiner = _identity(tmp_path, "joiner")
    enrolled = add_member(
        v1, author, name="joiner", public_key=joiner.public_key, node=_node(2),
    )
    local_node = _node(2, self_node=True)
    assert join_orders(
        dump_orders(enrolled), identity=joiner, node=local_node,
        expected_author_key_id=author.key_id, expected_fleet_id=enrolled.fleet_id,
    ) == enrolled

    with pytest.raises(OrdersBootstrapError, match="pinned author"):
        join_orders(enrolled, identity=joiner, node=local_node, expected_author_key_id="wrong")
    with pytest.raises(OrdersBootstrapError, match="stable node ID"):
        join_orders(
            enrolled, identity=joiner, node=_node(3, self_node=True),
            expected_author_key_id=author.key_id,
        )
    stranger = _identity(tmp_path, "stranger")
    with pytest.raises(OrdersBootstrapError, match="not enrolled"):
        join_orders(
            enrolled, identity=stranger, node=_node(3, self_node=True),
            expected_author_key_id=author.key_id,
        )
    with pytest.raises(OrdersBootstrapError, match="Tailscale Self"):
        join_orders(
            enrolled, identity=joiner, node=_node(2),
            expected_author_key_id=author.key_id,
        )


def test_init_requires_tailscale_self(tmp_path):
    with pytest.raises(OrdersBootstrapError, match="Tailscale Self"):
        init_orders(_identity(tmp_path, "author"), _node(1), name="helm")


def test_store_requires_bootstrap_pin_and_checks_transitions(tmp_path):
    author, v1 = _fleet(tmp_path)
    store = OrdersStore(tmp_path / "joined" / "fleet.yaml")
    with pytest.raises(OrdersBootstrapError, match="pinned"):
        store.apply(v1)
    with pytest.raises(OrdersBootstrapError, match="bootstrap pin"):
        store.apply(v1, expected_author_key_id="wrong")
    assert store.apply(v1, expected_author_key_id=author.key_id) == v1

    peer = _identity(tmp_path, "peer")
    v2 = add_member(v1, author, name="peer", public_key=peer.public_key, node=_node(2))
    assert store.apply(v2) == v2
    with pytest.raises(OrdersRollbackError):
        store.apply(v1)


def test_store_initialize_and_join_are_atomic_private_and_fsynced(tmp_path, monkeypatch):
    calls = []
    real_fsync = os.fsync

    def fsync(fd):
        calls.append(fd)
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", fsync)
    author = _identity(tmp_path, "author")
    store = OrdersStore(tmp_path / "state" / "fleet.yaml")
    orders = store.initialize(
        author, _node(1, self_node=True), name="helm",
        fleet_id="22222222-2222-4222-8222-222222222222",
    )
    assert store.load() == orders
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(store.path.parent.stat().st_mode) == 0o700
    assert len(calls) >= 2  # file content and containing directory
    assert not list(store.path.parent.glob(".*.tmp"))


def test_store_never_replaces_a_symlink(tmp_path):
    author, orders = _fleet(tmp_path)
    target = tmp_path / "target"
    target.write_text("keep")
    path = tmp_path / "fleet.yaml"
    path.symlink_to(target)
    store = OrdersStore(path)
    with pytest.raises(OrdersError):
        store.initialize(author, _node(1, self_node=True), name="helm")
    assert path.is_symlink()
    assert target.read_text() == "keep"
