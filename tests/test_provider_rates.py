from __future__ import annotations

from decimal import Decimal

import pytest

from spacepilot.daemon.identity import Identity
from spacepilot.daemon.orders import (
    OrdersError,
    OrdersSignatureError,
    ProviderRate,
    add_member,
    init_orders,
    parse_orders,
    set_provider_rates,
)
from spacepilot.daemon.tailscale import TailscaleNode
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _identity(tmp_path, name):
    return Identity(Ed25519PrivateKey.generate(), tmp_path / f"{name}.json")


def _node(number, *, self_node=False):
    return TailscaleNode(
        node_id=f"node-stable-{number}", addresses=(f"100.64.0.{number}",),
        is_self=self_node, online=True,
    )


def _fleet(tmp_path):
    author = _identity(tmp_path, "author")
    return author, init_orders(
        author, _node(1, self_node=True), name="helm",
        fleet_id="11111111-1111-4111-8111-111111111111",
    )


def _rate(provider="acme", variant="voice-v1", model="public-model", *, value="0.4000"):
    return ProviderRate(
        provider_id=provider, variant_id=variant, provider_model=model,
        input_usd_per_1m_tokens=value, output_usd_per_1m_tokens="1.600",
        source="https://acme.example/pricing", checked="2026-08-25",
    )


def test_provider_rates_are_decimal_strings_and_sort_by_stable_identity(tmp_path):
    author, orders = _fleet(tmp_path)
    rates = set_provider_rates(orders, author, [_rate("zeta"), _rate("acme")])
    assert rates.version == 2
    assert [rate.provider_id for rate in rates.providers] == ["acme", "zeta"]
    wire = rates.to_dict()
    assert wire["providers"][0]["input_usd_per_1m_tokens"] == "0.4"
    assert wire["providers"][0]["output_usd_per_1m_tokens"] == "1.6"
    assert parse_orders(wire) == rates
    assert rates.providers[0].input_usd_per_1m_tokens == Decimal("0.4")


def test_provider_rate_revision_is_author_only_and_noop_is_stable(tmp_path):
    author, orders = _fleet(tmp_path)
    impostor = _identity(tmp_path, "impostor")
    rate = _rate()
    with pytest.raises(OrdersError, match="only the permanent author"):
        set_provider_rates(orders, impostor, [rate])
    revised = set_provider_rates(orders, author, [rate])
    assert set_provider_rates(revised, author, [rate]) is revised
    changed = set_provider_rates(revised, author, [
        ProviderRate(
            provider_id=rate.provider_id, variant_id=rate.variant_id,
            provider_model=rate.provider_model, input_usd_per_1m_tokens="0.5",
            output_usd_per_1m_tokens=rate.output_usd_per_1m_tokens,
            source=rate.source, checked=rate.checked,
        ),
    ])
    assert changed.version == 3


def test_member_revision_preserves_provider_rates(tmp_path):
    author, orders = _fleet(tmp_path)
    orders = set_provider_rates(orders, author, [_rate()])
    peer = _identity(tmp_path, "peer")
    revised = add_member(orders, author, name="peer", public_key=peer.public_key, node=_node(2))
    assert revised.providers == orders.providers
    assert revised.version == orders.version + 1


def test_v1_documents_remain_readable_without_provider_projection(tmp_path):
    author, current = _fleet(tmp_path)
    payload = {
        "schema": 1, "fleet_id": current.fleet_id, "version": 1,
        "author": current.author.to_dict(),
        "members": [member.to_dict() for member in current.members],
    }
    raw = {**payload, "signature": {
        "algorithm": "Ed25519", "key_id": author.key_id,
        "value": author.sign_json(payload),
    }}
    parsed = parse_orders(raw)
    assert parsed.schema == 1
    assert parsed.providers == ()
    assert parsed.payload() == payload


@pytest.mark.parametrize(("field", "value", "message"), [
    ("input_usd_per_1m_tokens", 0.4, "not a float"),
    ("output_usd_per_1m_tokens", "-1", "non-negative"),
    ("source", "http://acme.example/pricing", "HTTPS"),
    ("checked", "2026-2-5", "ISO date"),
    ("provider_id", "Acme Cloud", "ASCII slug"),
])
def test_provider_rate_validation_rejects_ambiguous_or_unsafe_values(field, value, message):
    kwargs = {
        "provider_id": "acme", "variant_id": "voice-v1", "provider_model": "public-model",
        "input_usd_per_1m_tokens": "0.4", "output_usd_per_1m_tokens": "1.6",
        "source": "https://acme.example/pricing", "checked": "2026-08-25",
    }
    kwargs[field] = value
    with pytest.raises(OrdersError, match=message):
        ProviderRate(**kwargs)


def test_duplicate_provider_identity_and_tampering_are_rejected(tmp_path):
    author, orders = _fleet(tmp_path)
    rate = _rate()
    with pytest.raises(OrdersError, match="identity must be unique"):
        set_provider_rates(orders, author, [rate, rate])
    signed = set_provider_rates(orders, author, [rate]).to_dict()
    signed["providers"][0]["input_usd_per_1m_tokens"] = "0.5"
    with pytest.raises(OrdersSignatureError, match="did not verify"):
        parse_orders(signed)
