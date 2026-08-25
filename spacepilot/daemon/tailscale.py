"""Exact Tailscale node identity and address discovery.

DNS names and status-map keys are display data, not authority.  This module
accepts only the stable node ``ID`` and Tailscale-assigned IPs reported for
``Self`` and ``Peer`` by ``tailscale status --json``.
"""

from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping


class TailscaleError(RuntimeError):
    """Tailscale status is unavailable, malformed, or internally ambiguous."""


_TAILSCALE_V4 = ipaddress.ip_network("100.64.0.0/10")
_TAILSCALE_V6 = ipaddress.ip_network("fd7a:115c:a1e0::/48")


def _tailscale_ip(value: object) -> str:
    if not isinstance(value, str):
        raise TailscaleError("TailscaleIPs entries must be strings")
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise TailscaleError(f"invalid Tailscale IP {value!r}") from exc
    if address not in (_TAILSCALE_V4 if address.version == 4 else _TAILSCALE_V6):
        raise TailscaleError(f"address is not in a Tailscale-assigned range: {value}")
    return str(address)


@dataclass(frozen=True)
class TailscaleNode:
    node_id: str
    addresses: tuple[str, ...]
    is_self: bool = False
    online: bool | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, str) or not self.node_id.strip():
            raise TailscaleError("node ID is missing")
        if self.node_id != self.node_id.strip() or any(ch.isspace() for ch in self.node_id):
            raise TailscaleError("node ID contains whitespace")
        canonical = tuple(sorted({_tailscale_ip(value) for value in self.addresses}))
        if not canonical:
            raise TailscaleError(f"node {self.node_id!r} has no Tailscale IPs")
        object.__setattr__(self, "addresses", canonical)


@dataclass(frozen=True)
class TailscaleInventory:
    self_node: TailscaleNode
    nodes: tuple[TailscaleNode, ...]

    def __post_init__(self) -> None:
        by_id: dict[str, TailscaleNode] = {}
        by_ip: dict[str, TailscaleNode] = {}
        self_count = 0
        for node in self.nodes:
            if node.node_id in by_id:
                raise TailscaleError(f"duplicate stable node ID {node.node_id!r}")
            by_id[node.node_id] = node
            self_count += int(node.is_self)
            for address in node.addresses:
                if address in by_ip:
                    raise TailscaleError(
                        f"Tailscale IP {address} belongs to more than one stable node ID"
                    )
                by_ip[address] = node
        if self_count != 1 or by_id.get(self.self_node.node_id) != self.self_node:
            raise TailscaleError("inventory must contain exactly its declared Self node")
        object.__setattr__(self, "_by_id", by_id)
        object.__setattr__(self, "_by_ip", by_ip)

    def node_by_id(self, node_id: str) -> TailscaleNode:
        try:
            return self._by_id[node_id]  # type: ignore[attr-defined]
        except KeyError as exc:
            raise TailscaleError(f"stable node ID is not present in live status: {node_id}") from exc

    def node_for_source_ip(self, source_ip: str) -> TailscaleNode:
        """Map only a literal live Tailscale IP; never resolve a name."""
        canonical = _tailscale_ip(source_ip)
        try:
            return self._by_ip[canonical]  # type: ignore[attr-defined]
        except KeyError as exc:
            raise TailscaleError(f"source IP is not present in live Tailscale status: {canonical}") from exc

    def addresses_for_node_id(self, node_id: str) -> tuple[str, ...]:
        return self.node_by_id(node_id).addresses

    def resolve_selector(self, selector: str) -> TailscaleNode:
        """Resolve only an exact stable ID or literal Tailscale IP.

        CLI-friendly names may be rendered elsewhere, but DNSName/HostName are
        never accepted as membership authority.
        """
        if selector in self._by_id:  # type: ignore[attr-defined]
            return self.node_by_id(selector)
        return self.node_for_source_ip(selector)


def _node(raw: object, *, is_self: bool) -> TailscaleNode:
    if not isinstance(raw, Mapping):
        raise TailscaleError("Tailscale node status must be an object")
    node_id = raw.get("ID")
    addresses = raw.get("TailscaleIPs")
    if not isinstance(node_id, str) or not node_id:
        raise TailscaleError("Tailscale node status has no stable ID")
    if not isinstance(addresses, list):
        raise TailscaleError(f"Tailscale node {node_id!r} has no TailscaleIPs list")
    online_value = raw.get("Online")
    online = online_value if isinstance(online_value, bool) else None
    return TailscaleNode(
        node_id=node_id,
        addresses=tuple(addresses),
        is_self=is_self,
        online=online,
    )


def parse_status(raw: str | bytes | Mapping[str, Any]) -> TailscaleInventory:
    if isinstance(raw, Mapping):
        payload: object = raw
    else:
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
            raise TailscaleError(f"tailscale status is not JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise TailscaleError("tailscale status JSON must be an object")
    self_node = _node(payload.get("Self"), is_self=True)
    peers_raw = payload.get("Peer", {})
    if not isinstance(peers_raw, Mapping):
        raise TailscaleError("tailscale status Peer must be an object")
    # Mapping keys, DNSName and HostName are deliberately ignored: none is the
    # stable node identity asserted by the local tailscaled.
    peers = tuple(_node(value, is_self=False) for value in peers_raw.values())
    return TailscaleInventory(self_node=self_node, nodes=(self_node, *peers))


def status(run: Callable[..., Any] | None = None) -> TailscaleInventory:
    if run is None:
        from spacepilot.cli import run_cmd
        run = run_cmd
    try:
        raw = run(
            ["tailscale", "status", "--json"],
            capture=True,
            timeout=3.0,
        )
    except Exception as exc:
        raise TailscaleError(f"tailscale status unavailable: {exc}") from exc
    return parse_status(raw)


__all__ = [
    "TailscaleError", "TailscaleNode", "TailscaleInventory",
    "parse_status", "status",
]
