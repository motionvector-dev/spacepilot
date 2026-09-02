"""Privacy-safe, signed LOG gossip records.

LOG is deliberately narrower than the local measurement corpus.  A peer gets
an allowlisted projection of systems and measurements, never arbitrary YAML
or a live picture.  Every record is signed by its original author and every
page is signed by the peer that published/relayed it.  Relaying therefore
cannot rewrite the source of a measurement.
"""

from __future__ import annotations

import base64
import binascii
import concurrent.futures
import hashlib
import json
import os
import secrets
import stat
import threading
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from spacepilot.daemon.identity import (
    IDENTITY_SCHEMA,
    Identity,
    canonical_json,
    key_id_for_public_key,
    verify_json,
)
from spacepilot.paths import daemon_log_replica_dir, daemon_log_state_path, daemon_log_store_dir


LOG_SCHEMA = 1
MAX_RECORD_BYTES = 64 * 1024
MAX_PAGE_BYTES = 1024 * 1024
MAX_RECORDS_PER_PAGE = 256

SYSTEM_FIELDS = frozenset({
    "id", "chip", "machine_model", "backend", "os_name", "os_version",
    "cpu_cores", "gpu_cores", "memory_total_bytes", "memory_limit_bytes",
    "memory_limit_source", "memory_unified", "vram_total_bytes",
    "host_fingerprint", "recorded_on",
})
MEASUREMENT_FIELDS = frozenset({
    "schema", "system_id", "model_id", "metric", "value", "contention",
    "measured_on", "variant_id", "runtime_id", "runtime_version",
    "model_revision", "quantisation", "backend", "peak_memory_bytes",
    "wall_seconds", "status",
})


class LogError(ValueError):
    """A LOG record or page is invalid, unsafe, oversized, or unverifiable."""


class LogImmutableError(LogError):
    """A verified replica already exists with different immutable bytes."""


class LogCursorError(LogError):
    """A cursor does not belong to the signed epoch/sequence stream."""


def _ensure_private_directory(path: Path) -> None:
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = path.lstat()
    except OSError as exc:
        raise LogError(f"cannot prepare LOG directory {path}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise LogError(f"LOG path is not a real directory: {path}")
    uid = getattr(os, "getuid", lambda: None)()
    if uid is not None and info.st_uid != uid:
        raise LogError(f"LOG directory has the wrong owner: {path}")
    if stat.S_IMODE(info.st_mode) != 0o700:
        raise LogError(f"LOG directory must have mode 0700: {path}")


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    converter = getattr(value, "to_dict", None)
    if callable(converter):
        converted = converter()
        if isinstance(converted, Mapping):
            return dict(converted)
    try:
        converted = asdict(value)
    except TypeError as exc:
        raise LogError(f"record is not a mapping or dataclass: {type(value).__name__}") from exc
    return dict(converted)


def _projection(raw: Mapping[str, Any], fields: frozenset[str]) -> dict[str, Any]:
    # Do not carry unknown/nested fields forward.  In particular, Measurement
    # knobs are intentionally absent: they are where prompts and local paths
    # tend to hide.
    projected = {
        key: raw[key]
        for key in fields
        if key in raw and raw[key] is not None
    }
    try:
        encoded = canonical_json(projected)
    except (TypeError, ValueError) as exc:
        raise LogError(f"projection is not canonical JSON: {exc}") from exc
    if len(encoded) > MAX_RECORD_BYTES:
        raise LogError("projection exceeds the LOG record size limit")
    return projected


def project_system(system: Any) -> dict[str, Any]:
    return _projection(_mapping(system), SYSTEM_FIELDS)


def project_measurement(measurement: Any) -> dict[str, Any]:
    return _projection(_mapping(measurement), MEASUREMENT_FIELDS)


def _record_id(kind: str, payload: Mapping[str, Any]) -> str:
    body = {"kind": kind, "payload": dict(payload), "version": LOG_SCHEMA}
    return "sha256:" + hashlib.sha256(canonical_json(body)).hexdigest()


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: Any, field: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise LogError(f"{field} is missing")
    try:
        raw = value.encode("ascii")
        unpadded = raw.rstrip(b"=")
        if any(byte not in b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_=" for byte in raw):
            raise ValueError("invalid alphabet")
        if b"=" in unpadded or len(unpadded) % 4 == 1:
            raise ValueError("invalid padding")
        return base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4))
    except (UnicodeEncodeError, ValueError, binascii.Error) as exc:
        raise LogError(f"{field} is not valid base64") from exc


def _public_key(envelope: Mapping[str, Any]) -> tuple[bytes, str]:
    public = _b64decode(envelope.get("author_public_key"), "author_public_key")
    if len(public) != 32:
        raise LogError("author public key must be 32 bytes")
    actual = key_id_for_public_key(public)
    if envelope.get("author_key_id") != actual:
        raise LogError("author key id does not match public key")
    return public, actual


def make_record(identity: Identity, kind: str, value: Any) -> dict[str, Any]:
    if kind == "system":
        payload = project_system(value)
    elif kind == "measurement":
        payload = project_measurement(value)
    else:
        raise LogError(f"LOG cannot persist kind {kind!r}")
    required = {"id"} if kind == "system" else {
        "system_id", "model_id", "metric", "value", "contention", "measured_on"
    }
    if not required.issubset(payload):
        raise LogError(f"LOG {kind} projection is missing required fields")
    record_id = _record_id(kind, payload)
    body = {
        "kind": kind,
        "payload": payload,
        "record_id": record_id,
        "version": LOG_SCHEMA,
    }
    return {
        **body,
        "author_key_id": identity.key_id,
        "author_public_key": identity.public_key_b64,
        "signature": identity.sign_json(body),
    }


def verify_record(record: Mapping[str, Any], *, expected_author_key_id: str | None = None) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise LogError("LOG record must be an object")
    required = {"version", "kind", "record_id", "payload", "author_key_id", "author_public_key", "signature"}
    if set(record) != required:
        raise LogError("LOG record has unexpected or missing fields")
    if record["version"] != LOG_SCHEMA or record["kind"] not in {"system", "measurement"}:
        raise LogError("unsupported LOG record schema or kind")
    if not isinstance(record["payload"], Mapping):
        raise LogError("LOG record payload must be an object")
    fields = SYSTEM_FIELDS if record["kind"] == "system" else MEASUREMENT_FIELDS
    payload = _projection(record["payload"], fields)
    if dict(payload) != dict(record["payload"]):
        raise LogError("LOG record payload contains fields outside its allowlist")
    expected_id = _record_id(record["kind"], payload)
    if record["record_id"] != expected_id:
        raise LogError("LOG record content hash does not match payload")
    public, author = _public_key(record)
    if expected_author_key_id is not None and author != expected_author_key_id:
        raise LogError("LOG record is authored by an unexpected key")
    signature = _b64decode(record["signature"], "signature")
    if len(signature) != 64:
        raise LogError("LOG signature must be 64 bytes")
    body = {key: record[key] for key in ("kind", "payload", "record_id", "version")}
    if not verify_json(public, body, _b64encode(signature)):
        raise LogError("LOG record signature did not verify")
    return dict(record)


def make_page(identity: Identity, records: Iterable[Mapping[str, Any]], *,
              epoch: str, sequence: int, reset: bool = False) -> dict[str, Any]:
    if not isinstance(epoch, str) or not epoch or len(epoch) > 128:
        raise LogError("epoch must be a non-empty bounded string")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
        raise LogError("sequence must be a non-negative integer")
    checked = [verify_record(record) for record in records]
    if len(checked) > MAX_RECORDS_PER_PAGE:
        raise LogError("LOG page contains too many records")
    body = {
        "author_key_id": identity.key_id,
        "cursor": {"epoch": epoch, "reset": bool(reset), "sequence": sequence},
        "epoch": epoch,
        "kind": "log_page",
        "records": checked,
        "reset": bool(reset),
        "sequence": sequence,
        "version": LOG_SCHEMA,
    }
    return {
        **body,
        "author_public_key": identity.public_key_b64,
        "signature": identity.sign_json(body),
    }


def verify_page(page: Mapping[str, Any], *, expected_author_key_id: str | None = None) -> dict[str, Any]:
    if not isinstance(page, Mapping):
        raise LogError("LOG page must be an object")
    required = {"version", "kind", "author_key_id", "author_public_key", "epoch", "sequence", "reset", "cursor", "records", "signature"}
    if set(page) != required:
        raise LogError("LOG page has unexpected or missing fields")
    if page["version"] != LOG_SCHEMA or page["kind"] != "log_page":
        raise LogError("unsupported LOG page schema")
    if not isinstance(page["epoch"], str) or not page["epoch"] or len(page["epoch"]) > 128:
        raise LogError("invalid LOG page epoch")
    if not isinstance(page["sequence"], int) or isinstance(page["sequence"], bool) or page["sequence"] < 0:
        raise LogError("invalid LOG page sequence")
    if not isinstance(page["reset"], bool) or page["cursor"] != {
        "epoch": page["epoch"], "reset": page["reset"], "sequence": page["sequence"]
    }:
        raise LogCursorError("LOG cursor does not match page epoch/sequence/reset")
    if not isinstance(page["records"], list) or len(page["records"]) > MAX_RECORDS_PER_PAGE:
        raise LogError("invalid LOG page records")
    public, author = _public_key(page)
    if expected_author_key_id is not None and author != expected_author_key_id:
        raise LogError("LOG page is authored by an unexpected key")
    for record in page["records"]:
        verify_record(record)
    signature = _b64decode(page["signature"], "signature")
    if len(signature) != 64:
        raise LogError("LOG page signature must be 64 bytes")
    body = {key: page[key] for key in (
        "author_key_id", "cursor", "epoch", "kind", "records", "reset", "sequence", "version"
    )}
    if not verify_json(public, body, _b64encode(signature)):
        raise LogError("LOG page signature did not verify")
    if len(canonical_json(page)) > MAX_PAGE_BYTES:
        raise LogError("LOG page exceeds the size limit")
    return dict(page)


def cursor_from_page(page: Mapping[str, Any]) -> dict[str, Any]:
    """Return the signed cursor state after validating its page."""
    checked = verify_page(page)
    return dict(checked["cursor"])


@dataclass(frozen=True)
class LogCursor:
    epoch: str
    sequence: int
    reset: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"epoch": self.epoch, "sequence": self.sequence, "reset": self.reset}


class LogStore:
    """Immutable verified page storage for local and remote LOG gossip."""

    def __init__(self, root: Path | None = None, *, identity: Identity | None = None) -> None:
        self.root = Path(root or daemon_log_replica_dir()).expanduser().resolve()
        self.identity = identity

    def _page_path(self, page: Mapping[str, Any]) -> Path:
        checked = verify_page(page)
        author = checked["author_key_id"]
        epoch = checked["epoch"]
        sequence = checked["sequence"]
        if any(not isinstance(value, str) or not value or "/" in value or "\\" in value or value in {".", ".."}
               for value in (author, epoch)):
            raise LogError("unsafe LOG path component")
        return self.root / author / epoch / f"{sequence:020d}.json"

    def ingest_page(self, page: Mapping[str, Any]) -> Path:
        checked = verify_page(page)
        path = self._page_path(checked)
        _ensure_private_directory(self.root)
        _ensure_private_directory(self.root / checked["author_key_id"])
        _ensure_private_directory(path.parent)
        try:
            payload = canonical_json(checked) + b"\n"
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            try:
                info = path.lstat()
            except FileNotFoundError as exc:
                raise LogImmutableError(f"LOG replica disappeared during read: {path}") from exc
            uid = getattr(os, "getuid", lambda: None)()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                raise LogImmutableError(f"existing LOG replica is not a regular file: {path}")
            if uid is not None and info.st_uid != uid:
                raise LogImmutableError(f"existing LOG replica has the wrong owner: {path}")
            if stat.S_IMODE(info.st_mode) != 0o600:
                raise LogImmutableError(f"existing LOG replica must have mode 0600: {path}")
            try:
                existing = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError) as exc:
                raise LogImmutableError(f"existing LOG replica is unreadable: {path}") from exc
            if canonical_json(existing) != canonical_json(checked):
                raise LogImmutableError(f"immutable LOG replica conflicts: {path}")
            return path
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        return path

    def pages(self, *, author_key_id: str | None = None) -> list[dict[str, Any]]:
        root = self.root / author_key_id if author_key_id else self.root
        if not root.exists():
            return []
        result = []
        for path in sorted(root.glob("*/*/*.json")) if author_key_id is None else sorted(root.glob("*/*.json")):
            try:
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                    continue
                page = json.loads(path.read_text())
                result.append(verify_page(page))
            except (OSError, json.JSONDecodeError, LogError):
                continue
        return result

    def publish(self, records: Iterable[Mapping[str, Any]], *, epoch: str, sequence: int,
                reset: bool = False) -> Path:
        if self.identity is None:
            raise LogError("publishing requires a local identity")
        page = make_page(self.identity, records, epoch=epoch, sequence=sequence, reset=reset)
        return self.ingest_page(page)


def _write_json_private(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    payload = canonical_json(value) + b"\n"
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            fd = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if fd != -1:
            os.close(fd)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


class LocalLogPublisher:
    """Publish the current corpus as a stable signed epoch/sequence stream."""

    def __init__(
        self,
        identity: Identity,
        *,
        store: LogStore | None = None,
        state_path: Path | None = None,
        page_size: int = MAX_RECORDS_PER_PAGE,
        systems_loader: Any | None = None,
        measurements_loader: Any | None = None,
    ) -> None:
        if not 1 <= page_size <= MAX_RECORDS_PER_PAGE:
            raise LogError("LOG page_size is outside the bounded range")
        self.identity = identity
        self.store = store or LogStore(daemon_log_store_dir(), identity=identity)
        self.state_path = Path(state_path or daemon_log_state_path()).expanduser().resolve()
        self.page_size = page_size
        if systems_loader is None or measurements_loader is None:
            from spacepilot import measurements as measurement_store
            systems_loader = systems_loader or measurement_store.load_systems
            measurements_loader = measurements_loader or measurement_store.load_measurements
        self.systems_loader = systems_loader
        self.measurements_loader = measurements_loader
        self._epoch, self._sequence = self._load_state()
        self._lock = threading.RLock()

    def _load_state(self) -> tuple[str, int]:
        try:
            info = self.state_path.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                raise LogError("LOG state path is not a regular file")
            if stat.S_IMODE(info.st_mode) != 0o600:
                raise LogError("LOG state path must have mode 0600")
            raw = json.loads(self.state_path.read_text())
            if (
                isinstance(raw, Mapping)
                and isinstance(raw.get("epoch"), str)
                and raw["epoch"]
                and isinstance(raw.get("sequence"), int)
                and not isinstance(raw["sequence"], bool)
                and raw["sequence"] >= -1
            ):
                return raw["epoch"], raw["sequence"]
            raise LogError("LOG state schema is invalid")
        except FileNotFoundError:
            epoch = str(uuid.uuid4())
            _write_json_private(self.state_path, {"epoch": epoch, "sequence": -1, "version": LOG_SCHEMA})
            return epoch, -1

    @property
    def epoch(self) -> str:
        return self._epoch

    @property
    def sequence(self) -> int:
        return self._sequence

    def _current_records(self) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        systems = self.systems_loader()
        system_values = systems.values() if isinstance(systems, Mapping) else systems
        for system in system_values or ():
            try:
                values.append(make_record(self.identity, "system", system))
            except (LogError, TypeError, ValueError):
                continue
        measurements = self.measurements_loader()
        for measurement in measurements or ():
            try:
                values.append(make_record(self.identity, "measurement", measurement))
            except (LogError, TypeError, ValueError):
                continue
        unique = {record["record_id"]: record for record in values}
        return [unique[key] for key in sorted(unique)]

    def _published_records(self) -> dict[str, dict[str, Any]]:
        published: dict[str, dict[str, Any]] = {}
        for page in self.store.pages(author_key_id=self.identity.key_id):
            if page["epoch"] != self.epoch:
                continue
            for record in page["records"]:
                published[record["record_id"]] = record
        return published

    def refresh(self) -> list[dict[str, Any]]:
        """Sign and persist new corpus records, returning newly made pages."""
        with self._lock:
            published = self._published_records()
            records = [record for record in self._current_records() if record["record_id"] not in published]
            pages: list[dict[str, Any]] = []
            for offset in range(0, len(records), self.page_size):
                self._sequence += 1
                page = make_page(
                    self.identity,
                    records[offset:offset + self.page_size],
                    epoch=self.epoch,
                    sequence=self.sequence,
                )
                self.store.ingest_page(page)
                _write_json_private(self.state_path, {
                    "epoch": self.epoch, "sequence": self.sequence, "version": LOG_SCHEMA,
                })
                pages.append(page)
            return pages

    def records_since(self, epoch: str | None, sequence: int = -1, limit: int = MAX_RECORDS_PER_PAGE) -> dict[str, Any]:
        """Return the next whole signed page after a cursor.

        ``limit`` is a soft response target. A stored page is never split,
        because advancing its page-level sequence after returning only part of
        it would permanently skip the remaining records.
        """
        if epoch is not None and (not isinstance(epoch, str) or not epoch):
            raise LogCursorError("cursor epoch must be non-empty text")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < -1:
            raise LogCursorError("cursor sequence must be >= -1")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= self.page_size:
            raise LogError("cursor page limit is outside the bounded range")
        with self._lock:
            self.refresh()
            pages = sorted(self.store.pages(author_key_id=self.identity.key_id), key=lambda page: page["sequence"])
            reset = epoch != self.epoch
            candidates = pages if reset else [
                page for page in pages
                if page["epoch"] == self.epoch and page["sequence"] > sequence
            ]
            if candidates:
                selected = candidates[0]
                records = list(selected["records"])
                cursor_sequence = selected["sequence"]
            else:
                records = []
                cursor_sequence = max(sequence, 0)
            return make_page(
                self.identity,
                records,
                epoch=self.epoch,
                sequence=cursor_sequence,
                reset=reset,
            )


@dataclass(frozen=True)
class GossipResult:
    pulled_pages: int
    pulled_records: int
    skipped_members: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


class GossipPuller:
    """Pull signed LOG pages from current ORDERS members with bounded fanout."""

    def __init__(
        self,
        identity: Identity,
        *,
        orders_supplier: Any,
        inventory_supplier: Any,
        peer_client: Any,
        store: LogStore | None = None,
        index_writer: Any | None = None,
        limit: int = MAX_RECORDS_PER_PAGE,
        max_workers: int = 4,
    ) -> None:
        if not 1 <= limit <= MAX_RECORDS_PER_PAGE:
            raise LogError("gossip page limit is outside the bounded range")
        if not 1 <= max_workers <= 16:
            raise LogError("gossip worker bound is outside the safe range")
        self.identity = identity
        self.orders_supplier = orders_supplier
        self.inventory_supplier = inventory_supplier
        self.peer_client = peer_client
        self.store = store or LogStore(daemon_log_replica_dir())
        self.index_writer = index_writer
        self.limit = limit
        self.max_workers = max_workers
        self._cursors: dict[str, tuple[str, int]] = {}
        self._allowed_authors: set[str] = set()

    @staticmethod
    def _field(value: Any, name: str, default: Any = None) -> Any:
        if isinstance(value, Mapping):
            return value.get(name, default)
        return getattr(value, name, default)

    def _members(self) -> tuple[list[tuple[Any, Any]], list[str]]:
        orders = self.orders_supplier()
        inventory = self.inventory_supplier()
        members = self._field(orders, "members", ())
        if not isinstance(members, Sequence) or isinstance(members, (str, bytes)):
            raise LogError("ORDERS members are not a bounded sequence")
        self._allowed_authors = {
            self._field(member, "key_id") for member in members
            if isinstance(self._field(member, "key_id"), str)
        }
        selected: list[tuple[Any, Any]] = []
        skipped: list[str] = []
        for member in members:
            key_id = self._field(member, "key_id")
            node_id = self._field(member, "tailscale_node_id")
            if not isinstance(key_id, str) or key_id == self.identity.key_id:
                continue
            try:
                lookup = getattr(inventory, "node_by_id", None)
                node = lookup(node_id) if callable(lookup) else inventory[node_id]
            except Exception:
                # Not in the current authenticated inventory means removed or
                # unavailable; never retain a stale address and dial it.
                skipped.append(key_id)
                continue
            selected.append((member, node))
        return selected, skipped

    def _pull_member(self, member_node: tuple[Any, Any]) -> tuple[str, int, int, str | None]:
        member, node = member_node
        key_id = self._field(member, "key_id")
        cursor = self._cursors.get(key_id)
        query: dict[str, str] = {"limit": str(self.limit)}
        if cursor is not None:
            query.update({"epoch": cursor[0], "sequence": str(cursor[1])})
        response = self.peer_client.get(
            node, "/v1/log/records", authenticated=True, query=query,
        )
        if not isinstance(response, Mapping):
            raise LogError("peer LOG response is not an object")
        raw_pages = response.get("pages")
        if raw_pages is None and isinstance(response.get("page"), Mapping):
            raw_pages = [response["page"]]
        if not isinstance(raw_pages, list) or len(raw_pages) > MAX_RECORDS_PER_PAGE:
            raise LogError("peer LOG response has an invalid page list")
        verified_pages = []
        for raw_page in raw_pages:
            try:
                # A peer may relay an immutable page originally signed by
                # another enrolled member.  The authenticated transport peer
                # is still checked by ORDERS above; the page author remains
                # intact and must independently be an enrolled key.
                page = verify_page(raw_page)
                if page["author_key_id"] not in self._allowed_authors:
                    raise LogError("LOG page author is not a current ORDERS member")
                verified_pages.append(page)
            except LogError:
                raise
        pages = sorted(verified_pages, key=lambda page: page["sequence"])
        pulled_pages = pulled_records = 0
        next_cursor = cursor
        for page in pages:
            if next_cursor is not None:
                if page["reset"]:
                    next_cursor = None
                elif page["epoch"] != next_cursor[0] or page["sequence"] <= next_cursor[1]:
                    continue
            self.store.ingest_page(page)
            for record in page["records"]:
                if self.index_writer is not None:
                    self.index_writer.submit(record)
            pulled_pages += 1
            pulled_records += len(page["records"])
            next_cursor = (page["epoch"], page["sequence"])
        if next_cursor is not None:
            self._cursors[key_id] = next_cursor
        elif pages:
            last = pages[-1]
            self._cursors[key_id] = (last["epoch"], last["sequence"])
        return key_id, pulled_pages, pulled_records, None

    def pull_once(self) -> GossipResult:
        selected, skipped = self._members()
        if not selected:
            return GossipResult(0, 0, tuple(skipped), ())
        pages = records = 0
        errors: list[str] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(self.max_workers, len(selected))) as pool:
            futures = [pool.submit(self._pull_member, item) for item in selected]
            for future in futures:
                try:
                    _key_id, got_pages, got_records, _ = future.result()
                    pages += got_pages
                    records += got_records
                except Exception as exc:
                    errors.append(str(exc))
        return GossipResult(pages, records, tuple(skipped), tuple(errors))

    pull = pull_once


def signed_record(identity: Identity, kind: str, value: Any) -> dict[str, Any]:
    return make_record(identity, kind, value)


def signed_page(identity: Identity, records: Iterable[Mapping[str, Any]], *,
                epoch: str, sequence: int, reset: bool = False) -> dict[str, Any]:
    return make_page(identity, records, epoch=epoch, sequence=sequence, reset=reset)


__all__ = [
    "LOG_SCHEMA", "MAX_RECORD_BYTES", "MAX_PAGE_BYTES", "MAX_RECORDS_PER_PAGE",
    "SYSTEM_FIELDS", "MEASUREMENT_FIELDS", "LogError", "LogImmutableError",
    "LogCursorError", "LogCursor", "LogStore", "project_system", "project_measurement",
    "make_record", "signed_record", "verify_record", "make_page", "signed_page",
    "verify_page", "cursor_from_page",
    "LocalLogPublisher", "GossipResult", "GossipPuller",
]
