"""One-header Ed25519 authentication for tailnet peer requests.

The signature binds the exact HTTP method, raw path, raw query string, body
digest, timestamp and nonce.  Acceptance additionally requires current ORDERS
membership and an exact live Tailscale source-IP → stable-node-ID match.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from spacepilot.daemon.identity import Identity, canonical_json, verify_json
from spacepilot.daemon.orders import Member, Orders, verify_orders
from spacepilot.daemon.tailscale import TailscaleError, TailscaleInventory


PEER_AUTH_HEADER = "X-SpacePilot-Peer"
PEER_AUTH_VERSION = 1


class PeerAuthError(RuntimeError):
    pass


class PeerAuthMalformed(PeerAuthError):
    pass


class PeerAuthStale(PeerAuthError):
    pass


class PeerAuthReplay(PeerAuthError):
    pass


class PeerAuthNotMember(PeerAuthError):
    pass


class PeerAuthSourceMismatch(PeerAuthError):
    pass


class PeerAuthSignatureError(PeerAuthError):
    pass


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: object, *, where: str, min_length: int = 1,
               exact_length: int | None = None) -> bytes:
    if not isinstance(value, str) or not value:
        raise PeerAuthMalformed(f"{where} must be non-empty canonical base64url")
    try:
        raw = value.encode("ascii")
        if any(ch not in b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for ch in raw):
            raise ValueError("invalid alphabet or padding")
        decoded = base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4))
    except (UnicodeEncodeError, ValueError) as exc:
        raise PeerAuthMalformed(f"{where} is not canonical base64url") from exc
    if _b64encode(decoded) != value or len(decoded) < min_length:
        raise PeerAuthMalformed(f"{where} has invalid length or spelling")
    if exact_length is not None and len(decoded) != exact_length:
        raise PeerAuthMalformed(f"{where} has the wrong length")
    return decoded


def _method(value: str) -> str:
    if not isinstance(value, str) or not value or value != value.upper():
        raise PeerAuthMalformed("HTTP method must be non-empty uppercase text")
    if any(not ("A" <= ch <= "Z" or ch == "-") for ch in value):
        raise PeerAuthMalformed("HTTP method contains invalid characters")
    return value


def _path(value: str) -> str:
    if not isinstance(value, str) or not value.startswith("/"):
        raise PeerAuthMalformed("request path must start with /")
    if "?" in value or "#" in value or "\x00" in value:
        raise PeerAuthMalformed("request path must not contain query, fragment, or NUL")
    return value


def _query(value: str) -> str:
    if not isinstance(value, str) or "#" in value or "\x00" in value:
        raise PeerAuthMalformed("raw query must be text without fragment or NUL")
    return value


def _body_bytes(value: bytes | bytearray | memoryview) -> bytes:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise PeerAuthMalformed("request body must be bytes")
    return bytes(value)


def _payload(*, key_id: str, method: str, path: str, query: str,
             body: bytes, timestamp: int, nonce: str) -> dict[str, Any]:
    if not isinstance(key_id, str) or not key_id:
        raise PeerAuthMalformed("key_id is missing")
    if isinstance(timestamp, bool) or not isinstance(timestamp, int) or timestamp < 0:
        raise PeerAuthMalformed("timestamp must be a non-negative integer Unix second")
    _b64decode(nonce, where="nonce", min_length=16)
    return {
        "version": PEER_AUTH_VERSION,
        "key_id": key_id,
        "method": _method(method),
        "path": _path(path),
        "query": _query(query),
        "body_sha256": hashlib.sha256(_body_bytes(body)).hexdigest(),
        "timestamp": timestamp,
        "nonce": nonce,
    }


def sign_peer_request(
    identity: Identity,
    *,
    method: str,
    path: str,
    query: str = "",
    body: bytes = b"",
    timestamp: int | None = None,
    nonce: str | None = None,
) -> str:
    issued = int(time.time()) if timestamp is None else timestamp
    request_nonce = nonce or _b64encode(secrets.token_bytes(18))
    payload = _payload(
        key_id=identity.key_id,
        method=method,
        path=path,
        query=query,
        body=body,
        timestamp=issued,
        nonce=request_nonce,
    )
    envelope = {"payload": payload, "signature": identity.sign_json(payload)}
    return _b64encode(canonical_json(envelope))


def _object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise PeerAuthMalformed(f"duplicate peer-auth JSON key {key!r}")
        out[key] = value
    return out


def _reject_json_constant(value: str) -> None:
    raise PeerAuthMalformed(f"non-finite JSON value {value!r}")


def decode_peer_header(header: str) -> tuple[dict[str, Any], str]:
    if not isinstance(header, str) or len(header) > 8192:
        raise PeerAuthMalformed("peer auth header is missing or too large")
    encoded = _b64decode(header, where="peer auth header")
    try:
        envelope = json.loads(
            encoded.decode("utf-8"),
            object_pairs_hook=_object_no_duplicates,
            parse_constant=_reject_json_constant,
        )
    except PeerAuthMalformed:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PeerAuthMalformed("peer auth header is not canonical JSON") from exc
    if not isinstance(envelope, Mapping) or set(envelope) != {"payload", "signature"}:
        raise PeerAuthMalformed("peer auth envelope fields are invalid")
    payload = envelope.get("payload")
    signature = envelope.get("signature")
    if not isinstance(payload, Mapping) or set(payload) != {
        "version", "key_id", "method", "path", "query", "body_sha256",
        "timestamp", "nonce",
    }:
        raise PeerAuthMalformed("peer auth payload fields are invalid")
    if payload.get("version") != PEER_AUTH_VERSION:
        raise PeerAuthMalformed("unsupported peer auth version")
    if not isinstance(signature, str):
        raise PeerAuthMalformed("peer auth signature is missing")
    _b64decode(signature, where="signature", exact_length=64)
    # Return a plain dictionary so canonical re-encoding has one predictable
    # implementation-independent shape.
    return dict(payload), signature


class NonceCache:
    """Bounded in-memory replay window; only verified requests are inserted."""

    def __init__(self, *, ttl_seconds: int = 120, max_entries: int = 10_000) -> None:
        if ttl_seconds <= 0 or max_entries <= 0:
            raise ValueError("nonce cache bounds must be positive")
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()

    def consume(self, key_id: str, nonce: str, *, now: float,
                expires_at: float | None = None) -> None:
        key = (key_id, nonce)
        with self._lock:
            expired = [item for item, expiry in self._entries.items() if expiry <= now]
            for item in expired:
                self._entries.pop(item, None)
            if key in self._entries:
                raise PeerAuthReplay("peer request nonce was already used")
            if len(self._entries) >= self.max_entries:
                # Evicting a still-live entry would make its request replayable.
                # Refuse new traffic instead; a bounded denial is safer than a
                # silent authentication downgrade.
                raise PeerAuthError("peer replay cache is at capacity")
            self._entries[key] = max(now + self.ttl_seconds, expires_at or 0.0)


@dataclass(frozen=True)
class AuthenticatedPeer:
    member: Member
    source_ip: str
    timestamp: int
    nonce: str


class PeerAuthenticator:
    def __init__(
        self,
        orders: Orders | Callable[[], Orders],
        inventory: TailscaleInventory | Callable[[], TailscaleInventory],
        *,
        max_clock_skew_seconds: int = 60,
        nonce_cache: NonceCache | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if max_clock_skew_seconds <= 0:
            raise ValueError("max_clock_skew_seconds must be positive")
        self._orders = orders
        self._inventory = inventory
        self.max_clock_skew_seconds = max_clock_skew_seconds
        self.nonce_cache = nonce_cache or NonceCache(
            ttl_seconds=max_clock_skew_seconds * 2,
        )
        self.clock = clock

    def _current_orders(self) -> Orders:
        value = self._orders() if callable(self._orders) else self._orders
        return verify_orders(value)

    def _current_inventory(self) -> TailscaleInventory:
        return self._inventory() if callable(self._inventory) else self._inventory

    def verify(
        self,
        header: str,
        *,
        method: str,
        path: str,
        query: str = "",
        body: bytes = b"",
        source_ip: str,
        now: float | None = None,
    ) -> AuthenticatedPeer:
        payload, signature = decode_peer_header(header)
        actual_now = self.clock() if now is None else now
        if isinstance(actual_now, bool) or not isinstance(actual_now, (int, float)) or not math.isfinite(actual_now):
            raise PeerAuthMalformed("verification clock must be a finite Unix timestamp")
        timestamp = payload.get("timestamp")
        if isinstance(timestamp, bool) or not isinstance(timestamp, int):
            raise PeerAuthMalformed("timestamp must be an integer Unix second")
        if abs(actual_now - timestamp) > self.max_clock_skew_seconds:
            raise PeerAuthStale("peer request timestamp is outside the freshness window")

        key_id = payload.get("key_id")
        if not isinstance(key_id, str):
            raise PeerAuthMalformed("key_id is missing")
        orders = self._current_orders()
        member = orders.member(key_id)
        if member is None:
            raise PeerAuthNotMember("signing key is not a current fleet member")

        expected = _payload(
            key_id=key_id,
            method=_method(method),
            path=_path(path),
            query=_query(query),
            body=_body_bytes(body),
            timestamp=timestamp,
            nonce=payload.get("nonce"),
        )
        if not hmac.compare_digest(
            canonical_json(payload), canonical_json(expected),
        ):
            raise PeerAuthSignatureError("signed request facts do not match the HTTP request")
        if not verify_json(member.public_key_bytes, payload, signature):
            raise PeerAuthSignatureError("peer request signature did not verify")

        # Only a cryptographically valid member request gets to trigger live
        # Tailscale inventory work. This keeps forged headers from becoming a
        # subprocess-amplification path.
        try:
            source_node = self._current_inventory().node_for_source_ip(source_ip)
        except TailscaleError as exc:
            raise PeerAuthSourceMismatch(str(exc)) from exc
        if source_node.node_id != member.tailscale_node_id:
            raise PeerAuthSourceMismatch(
                "source Tailscale stable node ID does not match the member key binding"
            )

        nonce = payload["nonce"]
        self.nonce_cache.consume(
            key_id,
            nonce,
            now=actual_now,
            expires_at=timestamp + self.max_clock_skew_seconds + 1,
        )
        return AuthenticatedPeer(
            member=member,
            source_ip=source_ip,
            timestamp=timestamp,
            nonce=nonce,
        )


__all__ = [
    "PEER_AUTH_HEADER", "PEER_AUTH_VERSION", "PeerAuthError", "PeerAuthMalformed",
    "PeerAuthStale", "PeerAuthReplay", "PeerAuthNotMember", "PeerAuthSourceMismatch",
    "PeerAuthSignatureError", "NonceCache", "AuthenticatedPeer", "PeerAuthenticator",
    "sign_peer_request", "decode_peer_header",
]
