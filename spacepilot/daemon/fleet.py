"""Daemon-owned fleet liveness with explicit, honest state transitions.

The daemon is the only fleet poller and writer.  Human-facing clients receive
snapshots through its local UDS admin door; they never reach a peer, tailnet or
orders file directly.  This keeps one observation history per machine and,
more importantly, prevents a CLI refresh from turning an unreachable ship into
a fictitious fresh one.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence


class FleetError(RuntimeError):
    """The daemon could not produce a trustworthy fleet fact."""


class OrdersVerificationError(FleetError):
    """ORDERS are unsigned, invalid, or not newer than the accepted revision."""


class PictureUnreachable(FleetError):
    """A current member could not be reached; this means asleep, not gone."""


class PictureValidationError(FleetError):
    """A peer reply failed signature, clock, or schema validation."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _age_seconds(observed_at: str | None, now: datetime) -> float | None:
    observed = _parse_time(observed_at)
    if observed is None:
        return None
    return max(0.0, (now - observed).total_seconds())


@dataclass(frozen=True)
class FleetMember:
    """A member named by a signed ORDERS revision, never by a guessed IP."""

    id: str
    name: str
    key_id: str | None = None
    address: str | None = None
    tailscale_node_id: str | None = None
    public_key: str | None = None
    kind: str = "ship"

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "FleetMember":
        ident = value.get("id") or value.get("member_id") or value.get("name")
        name = value.get("name") or ident
        if not isinstance(ident, str) or not ident or not isinstance(name, str) or not name:
            raise OrdersVerificationError("ORDERS member has no stable id/name")
        return cls(
            id=ident,
            name=name,
            key_id=value.get("key_id") if isinstance(value.get("key_id"), str) else None,
            address=value.get("address") if isinstance(value.get("address"), str) else None,
            tailscale_node_id=(value.get("tailscale_node_id")
                               if isinstance(value.get("tailscale_node_id"), str) else None),
            public_key=value.get("public_key") if isinstance(value.get("public_key"), str) else None,
            kind=value.get("kind") if isinstance(value.get("kind"), str) else "ship",
        )


@dataclass(frozen=True)
class OrdersView:
    """The already-verified boundary supplied by the ORDERS subsystem."""

    version: int
    members: tuple[FleetMember, ...]
    verified: bool = True
    error: str | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "OrdersView":
        version = value.get("version")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise OrdersVerificationError("ORDERS version is not a positive integer")
        raw_members = value.get("members")
        if not isinstance(raw_members, Sequence) or isinstance(raw_members, (str, bytes)):
            raise OrdersVerificationError("ORDERS members is not a list")
        members = tuple(
            item if isinstance(item, FleetMember) else FleetMember.from_mapping(item)
            for item in raw_members
            if isinstance(item, (FleetMember, Mapping))
        )
        if len(members) != len(raw_members):
            raise OrdersVerificationError("ORDERS contains a malformed member")
        if len({member.id for member in members}) != len(members):
            raise OrdersVerificationError("ORDERS contains duplicate member identities")
        return cls(
            version=version,
            members=members,
            verified=value.get("verified", True) is True,
            error=value.get("error") if isinstance(value.get("error"), str) else None,
        )

    @classmethod
    def from_orders(cls, orders: object) -> "OrdersView":
        """Adapt the signed ORDERS model without making it a fleet dependency.

        The verification happens here, at the daemon's polling boundary, before
        membership can affect a liveness transition.  Stable Ed25519 key IDs
        become member IDs; display names and transient Tailscale addresses are
        deliberately not interchangeable identities.
        """
        from spacepilot.daemon.orders import Orders, OrdersError, verify_orders

        if not isinstance(orders, Orders):
            raise OrdersVerificationError("ORDERS adapter received an unknown document type")
        try:
            checked = verify_orders(orders)
        except OrdersError as exc:
            raise OrdersVerificationError(str(exc)) from exc
        return cls(
            version=checked.version,
            members=tuple(FleetMember(
                id=member.key_id,
                name=member.name,
                key_id=member.key_id,
                tailscale_node_id=member.tailscale_node_id,
                public_key=member.public_key,
            ) for member in checked.members),
        )


@dataclass(frozen=True)
class FleetRowFacts:
    """One row's facts; live and plain renderers both consume this exact shape."""

    member_id: str
    name: str
    kind: str
    state: str  # ready, busy, asleep, gone, unknown
    last_seen_at: str | None
    age_seconds: float | None
    orders_version: int | None
    key_id: str | None = None
    address: str | None = None
    version: str | None = None
    meter: str = "—"  # Docks supply a real running meter in Phase 6.
    errors: tuple[str, ...] = ()
    freshness_seconds: float = 10.0

    def recompute_age(self, now: datetime) -> "FleetRowFacts":
        age = _age_seconds(self.last_seen_at, now)
        if self.state in {"ready", "busy"} and (age is None or age > self.freshness_seconds):
            errors = self.errors
            stale = "picture is stale; readiness is unknown"
            if stale not in errors:
                errors = (*errors, stale)
            return replace(self, state="unknown", age_seconds=age, errors=errors)
        return replace(self, age_seconds=age)

    def to_wire(self) -> dict[str, Any]:
        return {
            "member_id": self.member_id,
            "name": self.name,
            "kind": self.kind,
            "state": self.state,
            "last_seen_at": self.last_seen_at,
            "age_seconds": self.age_seconds,
            "orders_version": self.orders_version,
            "key_id": self.key_id,
            "address": self.address,
            "version": self.version,
            "meter": self.meter,
            "errors": list(self.errors),
            "freshness_seconds": self.freshness_seconds,
        }

    @classmethod
    def from_wire(cls, value: Mapping[str, Any]) -> "FleetRowFacts":
        required = ("member_id", "name", "kind", "state")
        if not all(isinstance(value.get(key), str) and value[key] for key in required):
            raise FleetError("daemon returned a malformed fleet row")
        errors = value.get("errors", [])
        if not isinstance(errors, list) or not all(isinstance(item, str) for item in errors):
            raise FleetError("daemon returned malformed fleet errors")
        orders_version = value.get("orders_version")
        return cls(
            member_id=value["member_id"], name=value["name"], kind=value["kind"], state=value["state"],
            last_seen_at=value.get("last_seen_at") if isinstance(value.get("last_seen_at"), str) else None,
            age_seconds=value.get("age_seconds") if isinstance(value.get("age_seconds"), (float, int)) else None,
            orders_version=orders_version if isinstance(orders_version, int) and not isinstance(orders_version, bool) else None,
            key_id=value.get("key_id") if isinstance(value.get("key_id"), str) else None,
            address=value.get("address") if isinstance(value.get("address"), str) else None,
            version=value.get("version") if isinstance(value.get("version"), str) else None,
            meter=value.get("meter") if isinstance(value.get("meter"), str) else "—",
            errors=tuple(errors),
            freshness_seconds=(float(value["freshness_seconds"])
                               if isinstance(value.get("freshness_seconds"), (float, int))
                               and not isinstance(value.get("freshness_seconds"), bool) else 10.0),
        )


@dataclass(frozen=True)
class FleetSnapshot:
    orders_version: int | None
    rows: tuple[FleetRowFacts, ...]
    errors: tuple[str, ...] = ()

    def recompute_ages(self, now: datetime) -> "FleetSnapshot":
        return replace(self, rows=tuple(row.recompute_age(now) for row in self.rows))

    def to_wire(self) -> dict[str, Any]:
        return {
            "orders_version": self.orders_version,
            "rows": [row.to_wire() for row in self.rows],
            "errors": list(self.errors),
        }

    @classmethod
    def from_wire(cls, value: Mapping[str, Any]) -> "FleetSnapshot":
        rows = value.get("rows")
        if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
            raise FleetError("daemon returned no fleet rows")
        errors = value.get("errors", [])
        if not isinstance(errors, list) or not all(isinstance(item, str) for item in errors):
            raise FleetError("daemon returned malformed fleet errors")
        version = value.get("orders_version")
        return cls(
            orders_version=version if isinstance(version, int) and not isinstance(version, bool) else None,
            rows=tuple(FleetRowFacts.from_wire(row) for row in rows), errors=tuple(errors),
        )


class PictureFetcher(Protocol):
    def __call__(self, member: FleetMember) -> Mapping[str, Any]: ...


class PictureVerifier(Protocol):
    def __call__(self, member: FleetMember, picture: Mapping[str, Any]) -> Mapping[str, Any]: ...


def _missing_verifier(member: FleetMember, picture: Mapping[str, Any]) -> Mapping[str, Any]:
    """Fail closed until the daemon wires authenticated peer envelopes in."""
    raise PictureValidationError("no peer picture verifier is configured")


def verify_member_picture(member: FleetMember, envelope: Mapping[str, Any]) -> Mapping[str, Any]:
    """Verify a peer's signed PICTURE against its ORDERS-bound Ed25519 key.

    Transport/source-IP membership belongs to the injected peer client.  This
    function deliberately checks the different proof: that the reply bytes
    were authored by the current member, rather than merely reached at an IP.
    """
    if not member.key_id:
        raise PictureValidationError("ORDERS member has no Ed25519 key id")
    try:
        from spacepilot.daemon.identity import verify_picture
        picture = verify_picture(envelope, expected_key_id=member.key_id)
    except Exception as exc:
        raise PictureValidationError(f"peer picture signature did not verify: {exc}") from exc
    if not isinstance(picture, Mapping):
        raise PictureValidationError("peer picture payload is not an object")
    return picture


class FleetManager:
    """Stateful liveness reducer intended to be constructed only by the daemon."""

    def __init__(
        self,
        *,
        fetch_picture: PictureFetcher,
        verify_picture: PictureVerifier = _missing_verifier,
        clock: Callable[[], datetime] = utc_now,
        freshness_seconds: float = 10.0,
    ) -> None:
        self.fetch_picture = fetch_picture
        self.verify_picture = verify_picture
        self.clock = clock
        self.freshness_seconds = freshness_seconds
        self._orders_version: int | None = None
        self._members: dict[str, FleetMember] = {}
        self._last_seen: dict[str, datetime] = {}
        self._last_rows: dict[str, FleetRowFacts] = {}
        self._gone: dict[str, FleetRowFacts] = {}

    def _unknown_snapshot(self, error: str) -> FleetSnapshot:
        known = self._members.values() or (FleetMember("orders", "ORDERS", kind="control"),)
        rows = tuple(FleetRowFacts(
            member_id=member.id, name=member.name, kind=member.kind, state="unknown",
            last_seen_at=_iso(self._last_seen.get(member.id)), age_seconds=None,
            orders_version=self._orders_version, key_id=member.key_id, address=member.address,
            errors=(error,),
        ) for member in known)
        return FleetSnapshot(self._orders_version, rows, (error,))

    def _normalise_orders(self, orders: object) -> OrdersView:
        if isinstance(orders, OrdersView):
            result = orders
        elif isinstance(orders, Mapping):
            result = OrdersView.from_mapping(orders)
        else:
            result = OrdersView.from_orders(orders)
        if not result.verified:
            raise OrdersVerificationError(result.error or "ORDERS signature is not valid")
        return result

    def _classify(self, picture: Mapping[str, Any], now: datetime) -> tuple[str, datetime, str | None]:
        observed = _parse_time(picture.get("sampled_at"))
        if observed is None:
            raise PictureValidationError("picture has no valid sampled_at timestamp")
        age = (now - observed).total_seconds()
        if age < -1.0:
            raise PictureValidationError("picture clock is ahead of this daemon")
        if age > self.freshness_seconds:
            return "unknown", observed, f"picture is stale ({age:.0f}s old)"
        workers = picture.get("workers")
        if not isinstance(workers, Mapping) or workers.get("state") != "fresh":
            return "unknown", observed, "workers subsystem is not fresh"
        value = workers.get("value")
        worker_state = value.get("status") if isinstance(value, Mapping) else None
        if worker_state in {"busy", "processing", "loading"}:
            return "busy", observed, None
        if worker_state in {"online", "ready", "idle"}:
            return "ready", observed, None
        return "unknown", observed, "workers reported an unknown state"

    def _member_row(self, member: FleetMember, version: int, now: datetime) -> FleetRowFacts:
        try:
            raw = self.fetch_picture(member)
        except (PictureUnreachable, OSError, TimeoutError, ConnectionError) as exc:
            last = self._last_seen.get(member.id)
            return FleetRowFacts(
                member.id, member.name, member.kind, "asleep", _iso(last),
                _age_seconds(_iso(last), now), version, member.key_id, member.address,
                errors=(str(exc) or "peer is unreachable",),
            )
        except Exception as exc:
            # A fetcher failure is a transport/system failure, not evidence the
            # ship slept.  Only a declared unreachable result earns `asleep`.
            return FleetRowFacts(
                member.id, member.name, member.kind, "unknown", _iso(self._last_seen.get(member.id)),
                _age_seconds(_iso(self._last_seen.get(member.id)), now), version,
                member.key_id, member.address, errors=(f"picture fetch failed: {exc}",),
            )
        try:
            picture = self.verify_picture(member, raw)
            state, observed, error = self._classify(picture, now)
        except Exception as exc:
            return FleetRowFacts(
                member.id, member.name, member.kind, "unknown", _iso(self._last_seen.get(member.id)),
                _age_seconds(_iso(self._last_seen.get(member.id)), now), version,
                member.key_id, member.address, errors=(f"picture verification failed: {exc}",),
            )
        self._last_seen[member.id] = observed
        return FleetRowFacts(
            member.id, member.name, member.kind, state, _iso(observed),
            _age_seconds(_iso(observed), now), version, member.key_id, member.address,
            errors=(error,) if error else (), freshness_seconds=self.freshness_seconds,
        )

    def refresh(self, orders: object) -> FleetSnapshot:
        """Poll current, signed members and derive an honest snapshot.

        Removal is intentionally a versioned state transition.  A missing row
        in an invalid, replayed, or unverified document can never call a ship
        gone.
        """
        try:
            now = self.clock()
            if now.tzinfo is None:
                raise FleetError("daemon clock is not timezone-aware")
        except Exception as exc:
            return self._unknown_snapshot(f"clock failure: {exc}")
        try:
            view = self._normalise_orders(orders)
        except Exception as exc:
            return self._unknown_snapshot(f"ORDERS verification failed: {exc}")
        if self._orders_version is not None and view.version < self._orders_version:
            return self._unknown_snapshot(
                f"ORDERS version {view.version} is older than accepted {self._orders_version}"
            )

        incoming = {member.id: member for member in view.members}
        if self._orders_version is not None and view.version == self._orders_version:
            if incoming != self._members:
                return self._unknown_snapshot(
                    "ORDERS membership changed without a newer signed version"
                )
        if self._orders_version is not None and view.version > self._orders_version:
            for ident, member in self._members.items():
                if ident not in incoming:
                    last = self._last_seen.get(ident)
                    self._gone[ident] = FleetRowFacts(
                        ident, member.name, member.kind, "gone", _iso(last),
                        _age_seconds(_iso(last), now), view.version, member.key_id, member.address,
                        errors=(f"removed by signed ORDERS v{view.version}",),
                    )
        for ident in incoming:
            self._gone.pop(ident, None)
        self._orders_version = view.version
        self._members = incoming
        rows = [self._member_row(member, view.version, now) for member in incoming.values()]
        rows.extend(self._gone.values())
        rows.sort(key=lambda row: (row.name.casefold(), row.member_id))
        self._last_rows = {row.member_id: row for row in rows}
        return FleetSnapshot(view.version, tuple(rows)).recompute_ages(now)


def age_text(seconds: float | None) -> str:
    if seconds is None:
        return "last seen unknown"
    if seconds < 60:
        return f"last seen {seconds:.0f}s ago"
    if seconds < 3600:
        return f"last seen {seconds / 60:.0f}m ago"
    return f"last seen {seconds / 3600:.1f}h ago"


def render_fleet_snapshot(snapshot: FleetSnapshot, *, now: datetime) -> list[str]:
    """Render the same row facts for plain and live output modes."""
    fresh = snapshot.recompute_ages(now)
    lines = [f"  ORDERS v{fresh.orders_version}" if fresh.orders_version is not None else "  ORDERS unknown"]
    for row in fresh.rows:
        errors = f" · error: {'; '.join(row.errors)}" if row.errors else ""
        version = row.version or "unknown"
        lines.append(
            f"  {row.name} · {row.state} · {age_text(row.age_seconds)} · "
            f"version {version} · meter {row.meter}{errors}"
        )
    for error in fresh.errors:
        lines.append(f"  fleet error: {error}")
    return lines


class FleetAdmin(Protocol):
    """The future local UDS admin contract; no CLI peer/network access."""

    def init(self, name: str) -> Mapping[str, Any]: ...
    def add(self, selector: str) -> Mapping[str, Any]: ...
    def join(self, author_key_id: str, author_selector: str,
             fleet_id: str | None = None) -> Mapping[str, Any]: ...
    def list(self) -> Mapping[str, Any]: ...


class DaemonFleetAdmin:
    """Thin UDS-only adapter; server routes are added by the integration lane."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def _request(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        response = self.client._request(method, path, json=payload)  # local UDS boundary only
        if not isinstance(response, Mapping):
            raise FleetError("daemon returned a malformed fleet admin response")
        return response

    def init(self, name: str) -> Mapping[str, Any]:
        return self._request("POST", "/v1/fleet/init", {"name": name})

    def add(self, selector: str) -> Mapping[str, Any]:
        # The daemon resolves this against live Tailscale status, fetches the
        # peer's signed self-description, then derives the key/node binding.
        # Callers must never get to assert those authority-bearing fields.
        return self._request("POST", "/v1/fleet/add", {"selector": selector})

    def join(self, author_key_id: str, author_selector: str,
             fleet_id: str | None = None) -> Mapping[str, Any]:
        payload: dict[str, Any] = {
            "author_key_id": author_key_id,
            "author_selector": author_selector,
        }
        if fleet_id is not None:
            payload["fleet_id"] = fleet_id
        return self._request("POST", "/v1/fleet/join", payload)

    def list(self) -> Mapping[str, Any]:
        return self._request("GET", "/v1/fleet", None)


def local_fleet_admin() -> DaemonFleetAdmin:
    """Build the CLI's local-only client without teaching it any peer protocol."""
    from spacepilot.paths import daemon_socket_path
    from spacepilot.substrate import DaemonClient
    return DaemonFleetAdmin(DaemonClient(daemon_socket_path()))
