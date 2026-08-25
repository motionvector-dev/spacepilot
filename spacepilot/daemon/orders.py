"""Signed, single-author fleet membership (ORDERS).

YAML is only the human-readable container.  Signatures cover a strict semantic
payload encoded with canonical JSON, so comments, whitespace and mapping order
cannot change what was authorized.  The author key is permanent for schema v1.
"""

from __future__ import annotations

import base64
import os
import secrets
import stat
import uuid
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

import yaml

from spacepilot.daemon.identity import (
    Identity,
    canonical_json,
    key_id_for_public_key,
    verify_json,
)
from spacepilot.daemon.tailscale import TailscaleNode


ORDERS_SCHEMA = 2
_ORDERS_V1 = 1
SIGNATURE_ALGORITHM = "Ed25519"


class OrdersError(RuntimeError):
    """ORDERS are malformed, untrusted, or violate a version transition."""


class OrdersSignatureError(OrdersError):
    pass


class OrdersRollbackError(OrdersError):
    pass


class OrdersEquivocationError(OrdersError):
    pass


class OrdersAuthorError(OrdersError):
    pass


class OrdersBootstrapError(OrdersError):
    pass


class _NoDuplicateSafeLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader: _NoDuplicateSafeLoader, node: yaml.MappingNode,
                       deep: bool = False) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError as exc:
            raise OrdersError("YAML mapping keys must be scalar and hashable") from exc
        if duplicate:
            raise OrdersError(f"duplicate YAML key {key!r}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_NoDuplicateSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def load_yaml_strict(text: str | bytes) -> Any:
    try:
        # nosec B506 - _NoDuplicateSafeLoader subclasses yaml.SafeLoader and only
        # overrides the mapping constructor to REJECT duplicate keys. It adds no
        # constructor for any other tag, so no arbitrary object can be built.
        # Bandit's check only recognises the literal yaml.safe_load spelling.
        # test_orders_yaml_loader_cannot_construct_arbitrary_objects pins this.
        return yaml.load(text, Loader=_NoDuplicateSafeLoader)  # nosec B506
    except OrdersError:
        raise
    except yaml.YAMLError as exc:
        raise OrdersError(f"fleet YAML is invalid: {exc}") from exc


def _exact_keys(value: Mapping[str, Any], expected: set[str], where: str) -> None:
    if not all(isinstance(key, str) for key in value):
        raise OrdersError(f"{where} field names must be strings")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        detail = []
        if missing:
            detail.append(f"missing {missing}")
        if unknown:
            detail.append(f"unknown {unknown}")
        raise OrdersError(f"{where} fields are invalid: {', '.join(detail)}")


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: object, *, where: str, length: int) -> bytes:
    if not isinstance(value, str) or not value:
        raise OrdersError(f"{where} must be non-empty base64url")
    try:
        raw = value.encode("ascii")
        if any(ch not in b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for ch in raw):
            raise ValueError("non-canonical alphabet or padding")
        decoded = base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4))
    except (UnicodeEncodeError, ValueError) as exc:
        raise OrdersError(f"{where} is not canonical base64url") from exc
    if len(decoded) != length or _b64encode(decoded) != value:
        raise OrdersError(f"{where} has the wrong encoded length")
    return decoded


def _name(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise OrdersError("member name must be a non-empty trimmed string")
    if len(value) > 128 or any(ord(ch) < 32 for ch in value):
        raise OrdersError("member name is too long or contains control characters")
    return value


def _node_id(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise OrdersError("member tailscale_node_id must be a non-empty exact string")
    if any(ch.isspace() for ch in value):
        raise OrdersError("member tailscale_node_id contains whitespace")
    return value


def _slug(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise OrdersError(f"{field} must be a non-empty trimmed string")
    if len(value) > 128 or any(
        not (ch.isascii() and (ch.isalnum() or ch in "._-")) for ch in value
    ):
        raise OrdersError(f"{field} must be an ASCII slug")
    if value != value.lower():
        raise OrdersError(f"{field} must be lowercase")
    return value


def _public_label(value: object, *, field: str, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise OrdersError(f"{field} must be a non-empty trimmed string")
    if len(value) > maximum or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise OrdersError(f"{field} is too long or contains control characters")
    return value


def _rate(value: object, *, field: str) -> Decimal:
    """Parse a rate without ever converting a binary float to Decimal."""
    if isinstance(value, bool) or isinstance(value, float):
        raise OrdersError(f"{field} must be a decimal string or Decimal, not a float")
    if isinstance(value, str) and (not value or value != value.strip()):
        raise OrdersError(f"{field} must be a canonical decimal")
    try:
        parsed = Decimal(value)  # type: ignore[arg-type]
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise OrdersError(f"{field} must be a decimal") from exc
    if not parsed.is_finite() or parsed < 0:
        raise OrdersError(f"{field} must be a finite non-negative decimal")
    # Keep signed documents bounded while retaining exact decimal semantics.
    if len(parsed.as_tuple().digits) > 30 or len(format(parsed, "f")) > 64:
        raise OrdersError(f"{field} has too many digits")
    return parsed


def _rate_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _https_source(value: object) -> str:
    source = _public_label(value, field="provider.source", maximum=2048)
    parsed = urlsplit(source)
    if (
        parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password
        or parsed.query or parsed.fragment
    ):
        raise OrdersError("provider.source must be an HTTPS URL without credentials or query data")
    return source


def _checked_date(value: object) -> str:
    checked = _public_label(value, field="provider.checked", maximum=10)
    try:
        parsed = date.fromisoformat(checked)
    except ValueError as exc:
        raise OrdersError("provider.checked must be an ISO date (YYYY-MM-DD)") from exc
    if parsed.isoformat() != checked:
        raise OrdersError("provider.checked must be an ISO date (YYYY-MM-DD)")
    return checked


@dataclass(frozen=True)
class Member:
    name: str
    key_id: str
    public_key: str
    tailscale_node_id: str

    @classmethod
    def from_public_key(cls, *, name: str, public_key: bytes,
                        node: TailscaleNode) -> "Member":
        # key_id is always derived from the actual key bytes; callers never
        # supply an identifier that could disagree with the credential.
        return cls(
            name=_name(name),
            key_id=key_id_for_public_key(public_key),
            public_key=_b64encode(public_key),
            tailscale_node_id=_node_id(node.node_id),
        )

    @classmethod
    def from_dict(cls, raw: object) -> "Member":
        if not isinstance(raw, Mapping):
            raise OrdersError("member must be an object")
        _exact_keys(raw, {"name", "key_id", "public_key", "tailscale_node_id"}, "member")
        public = _b64decode(raw.get("public_key"), where="member.public_key", length=32)
        expected = key_id_for_public_key(public)
        if raw.get("key_id") != expected:
            raise OrdersError("member.key_id does not match member.public_key")
        return cls(
            name=_name(raw.get("name")),
            key_id=expected,
            public_key=_b64encode(public),
            tailscale_node_id=_node_id(raw.get("tailscale_node_id")),
        )

    @property
    def public_key_bytes(self) -> bytes:
        return _b64decode(self.public_key, where="member.public_key", length=32)

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "key_id": self.key_id,
            "public_key": self.public_key,
            "tailscale_node_id": self.tailscale_node_id,
        }


@dataclass(frozen=True)
class Author:
    key_id: str
    public_key: str

    @classmethod
    def from_identity(cls, identity: Identity) -> "Author":
        return cls(key_id=identity.key_id, public_key=identity.public_key_b64)

    @classmethod
    def from_dict(cls, raw: object) -> "Author":
        if not isinstance(raw, Mapping):
            raise OrdersError("author must be an object")
        _exact_keys(raw, {"key_id", "public_key"}, "author")
        public = _b64decode(raw.get("public_key"), where="author.public_key", length=32)
        expected = key_id_for_public_key(public)
        if raw.get("key_id") != expected:
            raise OrdersError("author.key_id does not match author.public_key")
        return cls(key_id=expected, public_key=_b64encode(public))

    @property
    def public_key_bytes(self) -> bytes:
        return _b64decode(self.public_key, where="author.public_key", length=32)

    def to_dict(self) -> dict[str, str]:
        return {"key_id": self.key_id, "public_key": self.public_key}


@dataclass(frozen=True)
class ProviderRate:
    """A signed, declared API price; it never asserts execution support."""

    provider_id: str
    variant_id: str
    provider_model: str
    input_usd_per_1m_tokens: Decimal | str | int
    output_usd_per_1m_tokens: Decimal | str | int
    source: str
    checked: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _slug(self.provider_id, field="provider.provider_id"))
        object.__setattr__(self, "variant_id", _slug(self.variant_id, field="provider.variant_id"))
        object.__setattr__(
            self, "provider_model", _public_label(self.provider_model, field="provider.provider_model"),
        )
        object.__setattr__(
            self, "input_usd_per_1m_tokens",
            _rate(self.input_usd_per_1m_tokens, field="provider.input_usd_per_1m_tokens"),
        )
        object.__setattr__(
            self, "output_usd_per_1m_tokens",
            _rate(self.output_usd_per_1m_tokens, field="provider.output_usd_per_1m_tokens"),
        )
        object.__setattr__(self, "source", _https_source(self.source))
        object.__setattr__(self, "checked", _checked_date(self.checked))

    @classmethod
    def from_dict(cls, raw: object) -> "ProviderRate":
        if not isinstance(raw, Mapping):
            raise OrdersError("provider rate must be an object")
        _exact_keys(raw, {
            "provider_id", "variant_id", "provider_model",
            "input_usd_per_1m_tokens", "output_usd_per_1m_tokens", "source", "checked",
        }, "provider")
        return cls(
            provider_id=raw.get("provider_id"),
            variant_id=raw.get("variant_id"),
            provider_model=raw.get("provider_model"),
            input_usd_per_1m_tokens=raw.get("input_usd_per_1m_tokens"),
            output_usd_per_1m_tokens=raw.get("output_usd_per_1m_tokens"),
            source=raw.get("source"),
            checked=raw.get("checked"),
        )

    @property
    def identity(self) -> tuple[str, str, str]:
        return self.provider_id, self.variant_id, self.provider_model

    def to_dict(self) -> dict[str, str]:
        # Decimal strings are deliberate: JSON/YAML numeric floats are not a
        # stable representation of a price and are rejected by from_dict.
        return {
            "provider_id": self.provider_id,
            "variant_id": self.variant_id,
            "provider_model": self.provider_model,
            "input_usd_per_1m_tokens": _rate_text(self.input_usd_per_1m_tokens),
            "output_usd_per_1m_tokens": _rate_text(self.output_usd_per_1m_tokens),
            "source": self.source,
            "checked": self.checked,
        }


@dataclass(frozen=True)
class OrdersSignature:
    key_id: str
    value: str
    algorithm: str = SIGNATURE_ALGORITHM

    @classmethod
    def from_dict(cls, raw: object) -> "OrdersSignature":
        if not isinstance(raw, Mapping):
            raise OrdersError("signature must be an object")
        _exact_keys(raw, {"algorithm", "key_id", "value"}, "signature")
        if raw.get("algorithm") != SIGNATURE_ALGORITHM:
            raise OrdersError("signature.algorithm must be Ed25519")
        key_id = raw.get("key_id")
        if not isinstance(key_id, str) or not key_id:
            raise OrdersError("signature.key_id is missing")
        value = raw.get("value")
        _b64decode(value, where="signature.value", length=64)
        return cls(key_id=key_id, value=value)

    def to_dict(self) -> dict[str, str]:
        return {"algorithm": self.algorithm, "key_id": self.key_id, "value": self.value}


@dataclass(frozen=True)
class Orders:
    fleet_id: str
    version: int
    author: Author
    members: tuple[Member, ...]
    signature: OrdersSignature
    providers: tuple[ProviderRate, ...] = ()
    schema: int = ORDERS_SCHEMA

    def __post_init__(self) -> None:
        if isinstance(self.schema, bool) or self.schema not in {_ORDERS_V1, ORDERS_SCHEMA}:
            raise OrdersError(f"unsupported ORDERS schema {self.schema!r}")
        if self.schema == _ORDERS_V1 and self.providers:
            raise OrdersError("schema v1 ORDERS cannot contain provider rates")
        providers = tuple(self.providers)
        if not all(isinstance(provider, ProviderRate) for provider in providers):
            raise OrdersError("providers must contain ProviderRate objects")
        providers = tuple(sorted(providers, key=lambda provider: provider.identity))
        if len({provider.identity for provider in providers}) != len(providers):
            raise OrdersError("provider identity must be unique")
        object.__setattr__(self, "providers", providers)
        try:
            canonical_fleet_id = str(uuid.UUID(self.fleet_id))
        except (ValueError, AttributeError, TypeError) as exc:
            raise OrdersError("fleet_id must be a canonical UUID") from exc
        if canonical_fleet_id != self.fleet_id:
            raise OrdersError("fleet_id must use canonical UUID spelling")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or not (1 <= self.version < 2**63):
            raise OrdersError("version must be a positive 63-bit integer")
        ordered = tuple(sorted(self.members, key=lambda member: member.key_id))
        object.__setattr__(self, "members", ordered)
        if not ordered:
            raise OrdersError("ORDERS must contain at least one member")
        if len({member.key_id for member in ordered}) != len(ordered):
            raise OrdersError("member key_id must be unique")
        if len({member.tailscale_node_id for member in ordered}) != len(ordered):
            raise OrdersError("member tailscale_node_id must be unique")
        author_public = _b64decode(
            self.author.public_key, where="author.public_key", length=32,
        )
        if self.author.key_id != key_id_for_public_key(author_public):
            raise OrdersAuthorError("author.key_id does not match author.public_key")
        for member in ordered:
            _name(member.name)
            _node_id(member.tailscale_node_id)
            public = _b64decode(
                member.public_key, where="member.public_key", length=32,
            )
            if member.key_id != key_id_for_public_key(public):
                raise OrdersError("member.key_id does not match member.public_key")
        if self.signature.algorithm != SIGNATURE_ALGORITHM:
            raise OrdersSignatureError("signature algorithm must be Ed25519")
        _b64decode(self.signature.value, where="signature.value", length=64)
        author_member = next((member for member in ordered if member.key_id == self.author.key_id), None)
        if author_member is None or author_member.public_key != self.author.public_key:
            raise OrdersAuthorError("the permanent author must remain an exact member")
        if self.signature.key_id != self.author.key_id:
            raise OrdersSignatureError("signature key_id is not the permanent author")

    def payload(self) -> dict[str, Any]:
        payload = {
            "schema": self.schema,
            "fleet_id": self.fleet_id,
            "version": self.version,
            "author": self.author.to_dict(),
            "members": [member.to_dict() for member in self.members],
        }
        if self.schema >= ORDERS_SCHEMA:
            payload["providers"] = [provider.to_dict() for provider in self.providers]
        return payload

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload(), "signature": self.signature.to_dict()}

    def member(self, key_id: str) -> Member | None:
        return next((member for member in self.members if member.key_id == key_id), None)

    @property
    def semantic_digest(self) -> bytes:
        import hashlib
        return hashlib.sha256(canonical_json(self.payload())).digest()


def _sign(payload: Mapping[str, Any], identity: Identity) -> OrdersSignature:
    return OrdersSignature(key_id=identity.key_id, value=identity.sign_json(payload))


def verify_orders(orders: Orders) -> Orders:
    if orders.author.key_id != key_id_for_public_key(orders.author.public_key_bytes):
        raise OrdersSignatureError("author key_id does not match public key")
    if not verify_json(orders.author.public_key_bytes, orders.payload(), orders.signature.value):
        raise OrdersSignatureError("ORDERS signature did not verify")
    return orders


def parse_orders(raw: str | bytes | Mapping[str, Any]) -> Orders:
    value = raw if isinstance(raw, Mapping) else load_yaml_strict(raw)
    if not isinstance(value, Mapping):
        raise OrdersError("fleet YAML must contain one object")
    schema = value.get("schema")
    if schema == _ORDERS_V1:
        expected = {"schema", "fleet_id", "version", "author", "members", "signature"}
    elif schema == ORDERS_SCHEMA:
        expected = {"schema", "fleet_id", "version", "author", "members", "providers", "signature"}
    else:
        raise OrdersError(f"unsupported ORDERS schema {schema!r}")
    _exact_keys(value, expected, "ORDERS")
    members_raw = value.get("members")
    if not isinstance(members_raw, list):
        raise OrdersError("members must be a list")
    providers_raw = value.get("providers", [])
    if not isinstance(providers_raw, list):
        raise OrdersError("providers must be a list")
    orders = Orders(
        schema=schema,
        fleet_id=value.get("fleet_id"),
        version=value.get("version"),
        author=Author.from_dict(value.get("author")),
        members=tuple(Member.from_dict(member) for member in members_raw),
        signature=OrdersSignature.from_dict(value.get("signature")),
        providers=tuple(ProviderRate.from_dict(provider) for provider in providers_raw),
    )
    return verify_orders(orders)


def dump_orders(orders: Orders) -> str:
    verify_orders(orders)
    return yaml.safe_dump(
        orders.to_dict(), sort_keys=False, allow_unicode=True, default_flow_style=False,
    )


def init_orders(identity: Identity, node: TailscaleNode, *, name: str,
                fleet_id: str | None = None,
                providers: tuple[ProviderRate, ...] = ()) -> Orders:
    if not node.is_self:
        raise OrdersBootstrapError("fleet init requires Tailscale Self, not a peer node")
    author = Author.from_identity(identity)
    member = Member.from_public_key(name=name, public_key=identity.public_key, node=node)
    unsigned = Orders(
        fleet_id=fleet_id or str(uuid.uuid4()),
        version=1,
        author=author,
        members=(member,),
        signature=OrdersSignature(key_id=identity.key_id, value=_b64encode(b"\0" * 64)),
        providers=providers,
    )
    return replace(unsigned, signature=_sign(unsigned.payload(), identity))


def add_member(orders: Orders, author_identity: Identity, *, name: str,
               public_key: bytes, node: TailscaleNode) -> Orders:
    verify_orders(orders)
    if author_identity.key_id != orders.author.key_id or author_identity.public_key_b64 != orders.author.public_key:
        raise OrdersAuthorError("only the permanent author can change ORDERS")
    candidate = Member.from_public_key(name=name, public_key=public_key, node=node)
    by_key = orders.member(candidate.key_id)
    by_node = next((member for member in orders.members
                    if member.tailscale_node_id == candidate.tailscale_node_id), None)
    if by_key == candidate and by_node == candidate:
        return orders
    if by_key is not None:
        raise OrdersError("member key is already bound to different member facts")
    if by_node is not None:
        raise OrdersError("Tailscale stable node ID is already bound to another key")
    members = (*orders.members, candidate)
    unsigned = Orders(
        fleet_id=orders.fleet_id,
        version=orders.version + 1,
        author=orders.author,
        members=members,
        signature=OrdersSignature(key_id=orders.author.key_id, value=_b64encode(b"\0" * 64)),
        providers=orders.providers,
        schema=orders.schema,
    )
    return replace(unsigned, signature=_sign(unsigned.payload(), author_identity))


def set_provider_rates(orders: Orders, author_identity: Identity,
                       providers: tuple[ProviderRate, ...] | list[ProviderRate]) -> Orders:
    """Replace the declared provider-rate projection as an author revision."""
    verify_orders(orders)
    if orders.schema < ORDERS_SCHEMA:
        raise OrdersError("provider rates require ORDERS schema v2")
    if author_identity.key_id != orders.author.key_id or author_identity.public_key_b64 != orders.author.public_key:
        raise OrdersAuthorError("only the permanent author can change provider rates")
    normalized = tuple(sorted(providers, key=lambda provider: provider.identity))
    candidate = Orders(
        fleet_id=orders.fleet_id,
        version=orders.version + (0 if normalized == orders.providers else 1),
        author=orders.author,
        members=orders.members,
        signature=OrdersSignature(key_id=orders.author.key_id, value=_b64encode(b"\0" * 64)),
        providers=normalized,
        schema=orders.schema,
    )
    if candidate.version == orders.version:
        return orders
    return replace(candidate, signature=_sign(candidate.payload(), author_identity))


# Keep the verb explicit for callers that model this as a publication/update.
update_provider_rates = set_provider_rates


def join_orders(raw: Orders | str | bytes | Mapping[str, Any], *,
                identity: Identity, node: TailscaleNode,
                expected_author_key_id: str,
                expected_fleet_id: str | None = None) -> Orders:
    """Validate explicit bootstrap pins and this node's prior enrollment."""
    if not expected_author_key_id:
        raise OrdersBootstrapError("joining requires an explicitly pinned author key_id")
    if not node.is_self:
        raise OrdersBootstrapError("fleet join requires Tailscale Self, not a peer node")
    orders = verify_orders(raw) if isinstance(raw, Orders) else parse_orders(raw)
    if orders.author.key_id != expected_author_key_id:
        raise OrdersBootstrapError("ORDERS author does not match the pinned author key_id")
    if expected_fleet_id is not None and orders.fleet_id != expected_fleet_id:
        raise OrdersBootstrapError("ORDERS fleet_id does not match the pinned fleet")
    member = orders.member(identity.key_id)
    if member is None:
        raise OrdersBootstrapError("this identity was not enrolled by the author")
    if member.public_key != identity.public_key_b64:
        raise OrdersBootstrapError("enrolled public key does not match this identity")
    if member.tailscale_node_id != node.node_id:
        raise OrdersBootstrapError("enrolled Tailscale stable node ID does not match this node")
    return orders


def validate_transition(current: Orders, candidate: Orders) -> Orders:
    verify_orders(current)
    verify_orders(candidate)
    if candidate.fleet_id != current.fleet_id:
        raise OrdersAuthorError("fleet_id is immutable")
    if candidate.author != current.author:
        raise OrdersAuthorError("the ORDERS author is permanent")
    if candidate.version < current.version:
        raise OrdersRollbackError(
            f"ORDERS version {candidate.version} rolls back current version {current.version}"
        )
    if candidate.version == current.version:
        if candidate.semantic_digest != current.semantic_digest:
            raise OrdersEquivocationError(
                f"different ORDERS payloads claim version {candidate.version}"
            )
        return current
    return candidate


def _safe_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = path.parent.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise OrdersError(f"ORDERS parent is not a real directory: {path.parent}")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise OrdersError(f"ORDERS parent is not owned by this user: {path.parent}")
    path.parent.chmod(0o700)


def _atomic_write(path: Path, text: str) -> None:
    _safe_parent(path)
    try:
        existing = path.lstat()
    except FileNotFoundError:
        pass
    else:
        if stat.S_ISLNK(existing.st_mode) or not stat.S_ISREG(existing.st_mode):
            raise OrdersError(f"refusing to replace unsafe ORDERS path: {path}")
        if hasattr(os, "getuid") and existing.st_uid != os.getuid():
            raise OrdersError(f"ORDERS file is not owned by this user: {path}")
    temp = path.parent / f".{path.name}.{secrets.token_hex(12)}.tmp"
    fd = -1
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.fchmod(fd, 0o600)
        payload = text.encode("utf-8")
        with os.fdopen(fd, "wb") as stream:
            fd = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        path.chmod(0o600)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
    finally:
        if fd != -1:
            os.close(fd)
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


class OrdersStore:
    """One local durable copy; callers provide the single-writer discipline."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> Orders | None:
        try:
            info = self.path.lstat()
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise OrdersError(f"refusing to read unsafe ORDERS path: {self.path}")
        if hasattr(os, "getuid") and info.st_uid != os.getuid():
            raise OrdersError(f"ORDERS file is not owned by this user: {self.path}")
        text = self.path.read_text(encoding="utf-8")
        return parse_orders(text)

    def initialize(self, identity: Identity, node: TailscaleNode, *,
                   name: str, fleet_id: str | None = None) -> Orders:
        if self.path.exists() or self.path.is_symlink():
            raise OrdersError(f"ORDERS already exist: {self.path}")
        orders = init_orders(identity, node, name=name, fleet_id=fleet_id)
        _atomic_write(self.path, dump_orders(orders))
        return orders

    def apply(self, candidate: Orders, *,
              expected_author_key_id: str | None = None) -> Orders:
        verify_orders(candidate)
        current = self.load()
        if current is None:
            if not expected_author_key_id:
                raise OrdersBootstrapError(
                    "installing first ORDERS requires an explicitly pinned author key_id"
                )
            if candidate.author.key_id != expected_author_key_id:
                raise OrdersBootstrapError("candidate author does not match bootstrap pin")
            selected = candidate
        else:
            selected = validate_transition(current, candidate)
            if selected is current:
                return current
        _atomic_write(self.path, dump_orders(selected))
        return selected

    def add(self, author_identity: Identity, *, name: str,
            public_key: bytes, node: TailscaleNode) -> Orders:
        current = self.load()
        if current is None:
            raise OrdersError("cannot add a member before fleet init")
        candidate = add_member(
            current, author_identity, name=name, public_key=public_key, node=node,
        )
        return self.apply(candidate)

    def join(self, raw: Orders | str | bytes | Mapping[str, Any], *,
             identity: Identity, node: TailscaleNode,
             expected_author_key_id: str,
             expected_fleet_id: str | None = None) -> Orders:
        candidate = join_orders(
            raw,
            identity=identity,
            node=node,
            expected_author_key_id=expected_author_key_id,
            expected_fleet_id=expected_fleet_id,
        )
        return self.apply(candidate, expected_author_key_id=expected_author_key_id)


__all__ = [
    "ORDERS_SCHEMA", "OrdersError", "OrdersSignatureError", "OrdersRollbackError",
    "OrdersEquivocationError", "OrdersAuthorError", "OrdersBootstrapError",
    "Member", "Author", "ProviderRate", "OrdersSignature", "Orders", "OrdersStore",
    "load_yaml_strict", "parse_orders", "dump_orders", "verify_orders",
    "init_orders", "add_member", "set_provider_rates", "update_provider_rates",
    "join_orders", "validate_transition",
]
