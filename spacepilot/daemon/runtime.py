"""Production composition for fleet control, peer reads, and liveness.

All authority-bearing inputs stay injectable: live Tailscale inventory and the
HTTP transport.  The default daemon constructs this object without performing
network or Tailscale work; calls resolve those facts at the moment of use.
"""

from __future__ import annotations

import base64
import binascii
import ipaddress
import socket
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import quote, urlencode

import httpx

from spacepilot.daemon.api import FleetControl, PeerReads
from spacepilot.daemon.fleet import FleetManager, FleetSnapshot, verify_member_picture
from spacepilot.daemon.identity import Identity, IdentityError, verified_envelope_payload
from spacepilot.daemon.index import IndexWriter
from spacepilot.daemon.log import GossipPuller, LocalLogPublisher, LogStore
from spacepilot.daemon.orders import Orders, OrdersError, OrdersStore
from spacepilot.daemon.peer_auth import PEER_AUTH_HEADER, PeerAuthenticator, sign_peer_request
from spacepilot.daemon.tailscale import TailscaleInventory, TailscaleNode, status
from spacepilot.paths import fleet_orders_path


class FleetRuntimeError(RuntimeError):
    pass


class HttpxPeerClient:
    """One-shot GETs to an exact Tailscale address; never DNS or wildcard."""

    def __init__(self, identity: Identity, *, port: int, timeout: float = 5.0,
                 transport: httpx.BaseTransport | None = None) -> None:
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError("peer port must be in 1..65535")
        if timeout <= 0:
            raise ValueError("peer timeout must be positive")
        self.identity = identity
        self.port = port
        self.timeout = timeout
        self.transport = transport

    def get(self, node: TailscaleNode, path: str, *, authenticated: bool,
            query: Mapping[str, str] | None = None) -> dict[str, Any]:
        if not path.startswith("/") or "?" in path or "#" in path:
            raise FleetRuntimeError("peer path must be absolute and contain no query or fragment")
        if not node.addresses:
            raise FleetRuntimeError("selected Tailscale node has no live address")
        address = str(ipaddress.ip_address(node.addresses[0]))
        host = f"[{address}]" if ":" in address else address
        query_values = dict(query or {})
        if any(not isinstance(key, str) or not isinstance(value, str)
               for key, value in query_values.items()):
            raise FleetRuntimeError("peer query keys and values must be strings")
        raw_query = urlencode(sorted(query_values.items()), quote_via=quote, safe="")
        headers = {}
        if authenticated:
            headers[PEER_AUTH_HEADER] = sign_peer_request(
                self.identity, method="GET", path=path, query=raw_query,
            )
        try:
            with httpx.Client(transport=self.transport, timeout=self.timeout) as client:
                target = f"http://{host}:{self.port}{path}" + (f"?{raw_query}" if raw_query else "")
                response = client.get(target, headers=headers)
                response.raise_for_status()
                value = response.json()
        except (httpx.HTTPError, OSError, ValueError) as exc:
            raise FleetRuntimeError(f"peer GET {path} failed: {exc}") from exc
        if not isinstance(value, dict):
            raise FleetRuntimeError(f"peer GET {path} returned a non-object")
        return value


class FleetBackgroundLoop:
    """Non-blocking local publication and gossip refresh lifecycle."""

    def __init__(self, publisher: LocalLogPublisher, puller: GossipPuller, *,
                 index_writer: IndexWriter | None = None,
                 interval_seconds: float = 2.0,
                 clock: Callable[[], float] = time.time) -> None:
        if interval_seconds <= 0:
            raise ValueError("fleet background interval must be positive")
        self.publisher = publisher
        self.puller = puller
        self.index_writer = index_writer
        self.interval_seconds = interval_seconds
        self.clock = clock
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._rebuilt = False
        self._status: dict[str, Any] = {
            "state": "stopped", "observed_at": None, "errors": [],
            "local_pages": 0, "pulled_pages": 0, "pulled_records": 0,
        }

    def tick(self) -> dict[str, Any]:
        errors: list[str] = []
        local_pages = pulled_pages = pulled_records = 0
        if self.index_writer is not None and not self._rebuilt:
            try:
                replica_root = getattr(getattr(self.puller, "store", None), "root", None)
                if replica_root is not None:
                    self.index_writer.rebuild(log_root=replica_root)
                self._rebuilt = True
            except Exception as exc:
                errors.append(f"fleet index rebuild failed: {exc}")
        try:
            pages = self.publisher.refresh()
            local_pages = len(pages)
            if self.index_writer is not None:
                for page in pages:
                    for record in page["records"]:
                        self.index_writer.submit(record)
        except Exception as exc:
            errors.append(f"local LOG refresh failed: {exc}")
        try:
            result = self.puller.pull_once()
            pulled_pages = result.pulled_pages
            pulled_records = result.pulled_records
            errors.extend(result.errors)
        except Exception as exc:
            errors.append(f"LOG gossip pull failed: {exc}")
        with self._lock:
            self._status = {
                "state": "degraded" if errors else "ok",
                "observed_at": self.clock(),
                "errors": errors,
                "local_pages": local_pages,
                "pulled_pages": pulled_pages,
                "pulled_records": pulled_records,
            }
            return dict(self._status)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {**self._status, "errors": list(self._status["errors"])}

    def _run(self) -> None:
        while not self._stop.is_set():
            self.tick()
            self._stop.wait(self.interval_seconds)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="spacepilot-fleet-background", daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(10.0, self.interval_seconds + 0.5))
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                self._status["errors"] = [
                    *self._status["errors"], "background worker did not stop within its bounded timeout",
                ]
                self._status["state"] = "degraded"
            if self._status["state"] not in {"degraded"}:
                self._status["state"] = "stopped"


@dataclass
class FleetRuntime:
    identity: Identity
    store: OrdersStore
    inventory_supplier: Callable[[], TailscaleInventory]
    peer_client: HttpxPeerClient
    manager: FleetManager
    log_store: LogStore
    ship_name_supplier: Callable[[], str]
    local_publisher: LocalLogPublisher | None = None
    gossip_puller: GossipPuller | None = None
    background: FleetBackgroundLoop | None = None
    index_writer: IndexWriter | None = None

    def __post_init__(self) -> None:
        self._mutation_lock = threading.Lock()

    def _orders(self) -> Orders:
        orders = self.store.load()
        if orders is None:
            raise OrdersError("fleet is not initialized")
        return orders

    @staticmethod
    def _ship_name(value: object) -> str:
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise FleetRuntimeError("signed ship name must be a non-empty trimmed string")
        if len(value) > 128 or any(ord(character) < 32 for character in value):
            raise FleetRuntimeError("signed ship name is too long or contains control characters")
        return value

    @staticmethod
    def _verified_self(envelope: Mapping[str, Any], node: TailscaleNode,
                       *, expected_key_id: str | None = None) -> tuple[bytes, str]:
        try:
            payload = verified_envelope_payload(
                envelope, expected_kind="self", expected_key_id=expected_key_id,
            )
        except IdentityError as exc:
            raise FleetRuntimeError("peer self-description signature did not verify") from exc
        if not isinstance(payload, Mapping) or set(payload) != {
            "schema", "key_id", "name", "tailscale_node_id",
        }:
            raise FleetRuntimeError("peer self-description fields are invalid")
        if payload.get("schema") != 1 or payload.get("key_id") != envelope.get("key_id"):
            raise FleetRuntimeError("peer self-description identity binding is invalid")
        if payload.get("tailscale_node_id") != node.node_id:
            raise FleetRuntimeError("peer self-description does not match the selected stable node ID")
        name = FleetRuntime._ship_name(payload.get("name"))
        encoded = envelope.get("public_key")
        if not isinstance(encoded, str):
            raise FleetRuntimeError("peer self-description has no Ed25519 public key")
        try:
            public_key = base64.b64decode(
                encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True,
            )
        except (binascii.Error, ValueError) as exc:
            raise FleetRuntimeError("peer self-description public key is malformed") from exc
        canonical = base64.urlsafe_b64encode(public_key).rstrip(b"=").decode()
        if len(public_key) != 32 or canonical != encoded:
            raise FleetRuntimeError("peer self-description public key is not canonical Ed25519")
        return public_key, name

    def self_description(self) -> dict[str, Any]:
        node = self.inventory_supplier().self_node
        return self.identity.sign_envelope({
            "schema": 1,
            "key_id": self.identity.key_id,
            "name": self._ship_name(self.ship_name_supplier()),
            "tailscale_node_id": node.node_id,
        }, kind="self")

    def init(self, name: str) -> dict[str, Any]:
        with self._mutation_lock:
            orders = self.store.initialize(
                self.identity, self.inventory_supplier().self_node, name=name,
            )
        return {"fleet_id": orders.fleet_id, "orders_version": orders.version}

    def add(self, selector: str) -> dict[str, Any]:
        node = self.inventory_supplier().resolve_selector(selector)
        if node.is_self:
            raise FleetRuntimeError("cannot add Tailscale Self as a remote member")
        envelope = self.peer_client.get(node, "/v1/self", authenticated=False)
        public_key, name = self._verified_self(envelope, node)
        with self._mutation_lock:
            orders = self.store.add(
                self.identity, name=name, public_key=public_key, node=node,
            )
        return {"fleet_id": orders.fleet_id, "orders_version": orders.version}

    def join(self, author_key_id: str, author_selector: str,
             fleet_id: str | None = None) -> dict[str, Any]:
        inventory = self.inventory_supplier()
        author_node = inventory.resolve_selector(author_selector)
        if author_node.is_self:
            raise FleetRuntimeError("author selector must identify a remote Tailscale node")
        author_self = self.peer_client.get(author_node, "/v1/self", authenticated=False)
        self._verified_self(author_self, author_node, expected_key_id=author_key_id)
        # The author must already have enrolled this identity: /v1/orders is a
        # normal authenticated member read, not a bootstrap authentication bypass.
        raw_orders = self.peer_client.get(author_node, "/v1/orders", authenticated=True)
        with self._mutation_lock:
            orders = self.store.join(
                raw_orders,
                identity=self.identity,
                node=inventory.self_node,
                expected_author_key_id=author_key_id,
                expected_fleet_id=fleet_id,
            )
        return {"fleet_id": orders.fleet_id, "orders_version": orders.version}

    def snapshot(self) -> dict[str, Any]:
        current = self.store.load()
        if current is None:
            return FleetSnapshot(None, (), ("fleet is not initialized",)).to_wire()
        return self.manager.refresh(current).to_wire()

    def orders_read(self) -> dict[str, Any]:
        return self._orders().to_dict()

    def log_records_read(self, epoch: str | None, sequence: int,
                         limit: int) -> dict[str, Any]:
        if self.local_publisher is None:
            raise FleetRuntimeError("local LOG publisher is unavailable")
        page = self.local_publisher.records_since(epoch, sequence, limit)
        # An empty page carries no new cursor value worth ingesting and could
        # conflict with a future first non-empty page at the same sequence.
        return {"pages": [page] if page["records"] else []}

    def controls(self) -> FleetControl:
        return FleetControl(
            snapshot=self.snapshot,
            init_handler=self.init,
            add_handler=self.add,
            join_handler=self.join,
        )

    def peer_reads(self) -> PeerReads:
        return PeerReads(
            self_description=self.self_description,
            orders=self.orders_read,
            log_records=self.log_records_read,
        )

    def peer_authenticator(self) -> PeerAuthenticator:
        return PeerAuthenticator(self._orders, self.inventory_supplier)

    def lifecycle_components(self) -> tuple[Any, ...]:
        values = (self.index_writer, self.background)
        return tuple(value for value in values if value is not None)

    def status(self) -> dict[str, Any]:
        return {
            "background": self.background.snapshot() if self.background is not None else {
                "state": "disabled", "errors": [], "observed_at": None,
            },
        }


def build_runtime(identity: Identity, *, peer_port: int,
                  inventory_supplier: Callable[[], TailscaleInventory] = status,
                  peer_client: HttpxPeerClient | None = None,
                  store: OrdersStore | None = None,
                  log_store: LogStore | None = None,
                  ship_name_supplier: Callable[[], str] = socket.gethostname,
                  index_writer: IndexWriter | None = None,
                  background_interval_seconds: float = 2.0,
                  publisher: LocalLogPublisher | None = None,
                  gossip_puller: GossipPuller | None = None) -> FleetRuntime:
    client = peer_client or HttpxPeerClient(identity, port=peer_port)

    def fetch_picture(member: Any) -> Mapping[str, Any]:
        node = inventory_supplier().node_by_id(member.tailscale_node_id)
        return client.get(node, "/v1/picture", authenticated=True)

    manager = FleetManager(
        fetch_picture=fetch_picture,
        verify_picture=verify_member_picture,
    )
    orders_store = store or OrdersStore(fleet_orders_path())
    replica_store = log_store or LogStore()
    if publisher is not None:
        local_publisher = publisher
    elif log_store is not None:
        local_publisher = LocalLogPublisher(
            identity,
            store=LogStore(log_store.root / "local", identity=identity),
            state_path=log_store.root / "publisher-state.json",
        )
    else:
        local_publisher = LocalLogPublisher(identity)
    def current_orders() -> Orders:
        current = orders_store.load()
        if current is None:
            raise OrdersError("fleet is not initialized")
        return current

    puller = gossip_puller or GossipPuller(
        identity,
        orders_supplier=current_orders,
        inventory_supplier=inventory_supplier,
        peer_client=client,
        store=replica_store,
        index_writer=index_writer,
    )
    background = FleetBackgroundLoop(
        local_publisher, puller, index_writer=index_writer,
        interval_seconds=background_interval_seconds,
    )
    runtime = FleetRuntime(
        identity=identity,
        store=orders_store,
        inventory_supplier=inventory_supplier,
        peer_client=client,
        manager=manager,
        log_store=replica_store,
        ship_name_supplier=ship_name_supplier,
        local_publisher=local_publisher,
        gossip_puller=puller,
        background=background,
        index_writer=index_writer,
    )
    return runtime


__all__ = [
    "FleetRuntimeError", "HttpxPeerClient", "FleetBackgroundLoop",
    "FleetRuntime", "build_runtime",
]
