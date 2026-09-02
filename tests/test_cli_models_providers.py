"""Provider rates in `models` are signed declarations, not local capability facts."""

from __future__ import annotations

import argparse

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from spacepilot.device_probe import GIB, DeviceProfile
from spacepilot.daemon.identity import Identity
from spacepilot.daemon.orders import OrdersStore, ProviderRate, init_orders, set_provider_rates
from spacepilot.daemon.tailscale import TailscaleNode


def _profile():
    return DeviceProfile(
        os_name="macOS", chip="Apple M1 Max", backend="metal",
        memory_total_bytes=32 * GIB, memory_free_bytes=20 * GIB,
        memory_limit_bytes=25 * GIB, memory_limit_source="metal",
        memory_unified=True, disk_free_bytes=100 * GIB,
    )


def _orders(path):
    identity = Identity(Ed25519PrivateKey.generate(), path.parent / "identity.json")
    node = TailscaleNode(
        node_id="node-stable-1", addresses=("100.64.0.1",),
        is_self=True, online=True,
    )
    orders = init_orders(
        identity, node, name="helm", fleet_id="11111111-1111-4111-8111-111111111111",
    )
    orders = set_provider_rates(orders, identity, [ProviderRate(
        provider_id="acme", variant_id="voice-v1", provider_model="public-model",
        input_usd_per_1m_tokens="0.4", output_usd_per_1m_tokens="1.6",
        source="https://acme.example/pricing", checked="2026-08-25",
    )])
    OrdersStore(path).apply(orders, expected_author_key_id=identity.key_id)


def test_models_renders_provider_rates_as_a_separate_on_paper_section(monkeypatch, tmp_path, capsys):
    import spacepilot.cli as cli
    from spacepilot import measurements as ms

    orders_path = tmp_path / "fleet.yaml"
    _orders(orders_path)
    monkeypatch.setattr(cli, "fleet_orders_path", lambda: orders_path)
    monkeypatch.setattr("spacepilot.device_probe.probe_local_device", _profile)
    monkeypatch.setattr(ms, "load_measurements", lambda: [])

    assert cli.cmd_models(argparse.Namespace(model_id=None)) == 0
    out = capsys.readouterr().out

    assert "PROVIDERS — on paper only" in out
    assert "INPUT USD/1M TOKENS" in out
    assert "OUTPUT USD/1M TOKENS" in out
    assert "acme / voice-v1 / public-model" in out
    assert "0.4" in out and "1.6" in out
    assert "https://acme.example/pricing · checked 2026-08-25" in out
    assert "no local fit verdict" in out
    assert "no flown/unflown speed axis" in out
    assert "no execution support is implied" in out


def test_models_does_not_fabricate_provider_rows_without_orders_or_network(monkeypatch, tmp_path, capsys):
    import spacepilot.cli as cli
    from spacepilot import measurements as ms

    monkeypatch.setattr(cli, "fleet_orders_path", lambda: tmp_path / "missing-fleet.yaml")
    monkeypatch.setattr("spacepilot.device_probe.probe_local_device", _profile)
    monkeypatch.setattr(ms, "load_measurements", lambda: [])
    monkeypatch.setattr(cli.httpx, "get", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("models must not use the network"),
    ))

    assert cli.cmd_models(argparse.Namespace(model_id=None)) == 0
    out = capsys.readouterr().out
    assert "PROVIDERS — on paper only" not in out
    assert "acme / voice-v1 / public-model" not in out
