"""The machine identity used by SpacePilot's local and peer doors.

An identity is an Ed25519 key pair generated once per user-data directory.  It
is intentionally not derived from a hostname or hardware fingerprint: those
change, leak information, and are not credentials.  The private key is kept
in a small JSON record with restrictive filesystem permissions; the record is
created with an exclusive lock and an atomic publication so two first callers
cannot create competing identities.

The module also owns the wire-level signing convention.  JSON is encoded with
one canonical representation before signing, so a request signed by one
transport verifies identically when it arrives through another transport.
"""

from __future__ import annotations

import base64
import errno
import hashlib
import json
import os
import secrets
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.exceptions import InvalidSignature

from spacepilot.paths import identity_dir, identity_lock_path, identity_path


IDENTITY_SCHEMA = 1
KEY_ALGORITHM = "Ed25519"
KEY_ID_PREFIX = "v1:sha256:"
_LOCK_WAIT_SECONDS = 10.0
_LOCK_POLL_SECONDS = 0.01


class IdentityError(RuntimeError):
    """The local identity is absent, unsafe, corrupt, or unverifiable."""


class IdentityUnsafeError(IdentityError):
    """The identity path or its owner/permissions are unsafe."""


class IdentityCorruptError(IdentityError):
    """The identity record cannot be parsed or fails key consistency checks."""


class IdentityVerificationError(IdentityError):
    """A signed payload or envelope did not verify."""


def canonical_json(value: Any) -> bytes:
    """Return the deterministic UTF-8 JSON bytes used on the wire.

    NaN and infinities are rejected because Python's permissive JSON encoder
    would otherwise give different implementations a non-standard value to
    sign.  Mapping key order, whitespace, and Unicode representation are all
    fixed here rather than at individual call sites.
    """
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise TypeError(f"value is not canonical-JSON encodable: {exc}") from exc
    return encoded.encode("utf-8")


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str, *, field: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise IdentityCorruptError(f"identity {field} is missing")
    try:
        raw = value.encode("ascii")
        # urlsafe_b64decode silently discards non-alphabet bytes.  A signature
        # or key with discarded bytes is corruption, not a different spelling
        # of the same credential.
        if any(byte not in b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_=" for byte in raw):
            raise ValueError("invalid base64 alphabet")
        if b"=" in raw.rstrip(b"=") or len(raw.rstrip(b"=")) % 4 == 1:
            raise ValueError("invalid base64 padding")
        return base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4))
    except (UnicodeEncodeError, ValueError) as exc:
        raise IdentityCorruptError(f"identity {field} is not base64") from exc


def key_id_for_public_key(public_key: bytes) -> str:
    """Return the stable, versioned SHA-256 identifier for a public key."""
    if not isinstance(public_key, bytes) or len(public_key) != 32:
        raise ValueError("an Ed25519 public key must be exactly 32 bytes")
    return KEY_ID_PREFIX + hashlib.sha256(public_key).hexdigest()


def _current_uid() -> int | None:
    return getattr(os, "getuid", lambda: None)()


def _check_directory(path: Path, *, create: bool) -> None:
    """Create or validate an identity directory without following a symlink."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        if not create:
            raise IdentityError(f"identity does not exist: {path}")
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        # mkdir is subject to umask.  Set the exact requested mode after
        # creation, then validate it through lstat below.
        os.chmod(path, 0o700)
        info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise IdentityUnsafeError(f"identity directory is not a real directory: {path}")
    uid = _current_uid()
    if uid is not None and info.st_uid != uid:
        raise IdentityUnsafeError(f"identity directory has the wrong owner: {path}")
    if stat.S_IMODE(info.st_mode) != 0o700:
        raise IdentityUnsafeError(
            f"identity directory must have mode 0700 (got {stat.S_IMODE(info.st_mode):04o}): {path}"
        )


def _check_private_file(path: Path) -> os.stat_result:
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise IdentityError(f"identity does not exist: {path}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise IdentityUnsafeError(f"identity file is not a regular file: {path}")
    uid = _current_uid()
    if uid is not None and info.st_uid != uid:
        raise IdentityUnsafeError(f"identity file has the wrong owner: {path}")
    if stat.S_IMODE(info.st_mode) != 0o600:
        raise IdentityUnsafeError(
            f"identity file must have mode 0600 (got {stat.S_IMODE(info.st_mode):04o}): {path}"
        )
    return info


def _record_for_private_key(private: Ed25519PrivateKey) -> dict[str, Any]:
    seed = private.private_bytes_raw()
    public = private.public_key().public_bytes_raw()
    return {
        "algorithm": KEY_ALGORITHM,
        "key_id": key_id_for_public_key(public),
        "private_key": _b64encode(seed),
        "public_key": _b64encode(public),
        "version": IDENTITY_SCHEMA,
    }


def _load_record(path: Path) -> "Identity":
    _check_private_file(path)
    try:
        raw = path.read_bytes()
        if len(raw) > 16 * 1024:
            raise IdentityCorruptError("identity record is unexpectedly large")
        record = json.loads(raw.decode("utf-8"))
    except IdentityCorruptError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IdentityCorruptError(f"cannot read identity record {path}: {exc}") from exc
    if not isinstance(record, dict):
        raise IdentityCorruptError("identity record must be a JSON object")
    if record.get("version") != IDENTITY_SCHEMA:
        raise IdentityCorruptError("unsupported identity record version")
    if record.get("algorithm") != KEY_ALGORITHM:
        raise IdentityCorruptError("unsupported identity algorithm")
    seed = _b64decode(record.get("private_key"), field="private_key")
    public = _b64decode(record.get("public_key"), field="public_key")
    if len(seed) != 32 or len(public) != 32:
        raise IdentityCorruptError("identity key bytes have the wrong length")
    try:
        private = Ed25519PrivateKey.from_private_bytes(seed)
    except ValueError as exc:
        raise IdentityCorruptError("identity private key is invalid") from exc
    derived = private.public_key().public_bytes_raw()
    if not secrets.compare_digest(derived, public):
        raise IdentityCorruptError("identity public key does not match private key")
    expected_id = key_id_for_public_key(public)
    if record.get("key_id") != expected_id:
        raise IdentityCorruptError("identity key_id does not match public key")
    return Identity(private_key=private, path=path)


def _write_atomic(path: Path, record: Mapping[str, Any]) -> None:
    """Publish a new record without exposing a partial JSON document."""
    directory = path.parent
    # A random temp name avoids colliding with a stale temp left by a killed
    # process.  O_EXCL also ensures we never follow an attacker-created link.
    for _ in range(10):
        temp = directory / f".{path.name}.{secrets.token_hex(12)}.tmp"
        try:
            fd = os.open(
                temp,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            break
        except FileExistsError:
            continue
    else:  # pragma: no cover - cryptographically unlikely
        raise IdentityError("could not allocate identity temporary file")
    try:
        os.fchmod(fd, 0o600)
        payload = canonical_json(record) + b"\n"
        with os.fdopen(fd, "wb") as stream:
            fd = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # Validate the destination one final time while the creation lock is
        # held.  os.replace is atomic and never leaves a half-written record.
        try:
            path.lstat()
        except FileNotFoundError:
            pass
        else:
            raise IdentityUnsafeError(f"identity appeared during creation: {path}")
        os.replace(temp, path)
        # Durability of the directory entry matters if the machine loses power
        # immediately after first creation.
        try:
            dir_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass  # Some platforms do not permit fsync on directories.
    finally:
        if fd != -1:
            os.close(fd)
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _acquire_lock(path: Path) -> int | None:
    deadline = time.monotonic() + _LOCK_WAIT_SECONDS
    while True:
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.fchmod(fd, 0o600)
            return fd
        except FileExistsError:
            # An existing lock is itself unsafe if it is a link or owned by a
            # different user.  Never silently wait on a path we do not own.
            try:
                info = path.lstat()
            except FileNotFoundError:
                continue
            uid = _current_uid()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                raise IdentityUnsafeError(f"identity lock is not a regular file: {path}")
            if uid is not None and info.st_uid != uid:
                raise IdentityUnsafeError(f"identity lock has the wrong owner: {path}")
            if stat.S_IMODE(info.st_mode) != 0o600:
                raise IdentityUnsafeError(f"identity lock must have mode 0600: {path}")
            if time.monotonic() >= deadline:
                raise IdentityError("timed out waiting for identity creation")
            time.sleep(_LOCK_POLL_SECONDS)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise IdentityUnsafeError(f"identity lock is a symlink: {path}") from exc
            raise


def load_or_create() -> "Identity":
    """Load the machine identity, creating it once if it is absent.

    Existing paths are never rotated.  Any corruption, symlink, ownership or
    permission problem raises :class:`IdentityError` and leaves the evidence
    for the operator to repair deliberately.
    """
    directory = identity_dir()
    _check_directory(directory, create=True)
    path = identity_path()
    try:
        path.lstat()
    except FileNotFoundError:
        pass
    else:
        return _load_record(path)

    lock_path = identity_lock_path()
    lock_fd = _acquire_lock(lock_path)
    assert lock_fd is not None
    try:
        # Another process may have won while we waited for the lock.
        try:
            path.lstat()
        except FileNotFoundError:
            private = Ed25519PrivateKey.generate()
            _write_atomic(path, _record_for_private_key(private))
        return _load_record(path)
    finally:
        os.close(lock_fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


@dataclass(frozen=True)
class Identity:
    """An immutable in-process view of the persisted Ed25519 identity."""

    private_key: Ed25519PrivateKey
    path: Path

    @classmethod
    def load_or_create(cls) -> "Identity":
        return load_or_create()

    @classmethod
    def load(cls) -> "Identity":
        """Load an existing identity without creating one."""
        directory = identity_dir()
        _check_directory(directory, create=False)
        return _load_record(identity_path())

    @property
    def public_key(self) -> bytes:
        return self.private_key.public_key().public_bytes_raw()

    @property
    def public_key_b64(self) -> str:
        return _b64encode(self.public_key)

    @property
    def key_id(self) -> str:
        return key_id_for_public_key(self.public_key)

    def sign(self, message: bytes | bytearray | memoryview) -> bytes:
        return self.private_key.sign(bytes(message))

    def sign_json(self, payload: Any) -> str:
        return _b64encode(self.sign(canonical_json(payload)))

    def sign_envelope(self, payload: Any, *, kind: str = "request") -> dict[str, Any]:
        """Create a self-describing signed request/picture envelope."""
        body = {"kind": kind, "payload": payload, "version": IDENTITY_SCHEMA}
        return {
            **body,
            "key_id": self.key_id,
            "public_key": self.public_key_b64,
            "signature": self.sign_json(body),
        }

    def verify(self, message: bytes | bytearray | memoryview, signature: bytes) -> bool:
        return verify_signature(self.public_key, bytes(message), signature)

    def verify_json(self, payload: Any, signature: str | bytes) -> bool:
        return verify_json(self.public_key, payload, signature)

    def verify_envelope(self, envelope: Mapping[str, Any], *,
                        expected_kind: str | None = None) -> bool:
        return verify_envelope(
            envelope,
            public_key=self.public_key,
            expected_key_id=self.key_id,
            expected_kind=expected_kind,
        )


def verify_signature(public_key: bytes | Ed25519PublicKey,
                     message: bytes,
                     signature: bytes) -> bool:
    try:
        key = public_key if isinstance(public_key, Ed25519PublicKey) else Ed25519PublicKey.from_public_bytes(public_key)
        key.verify(signature, message)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def verify_json(public_key: bytes | Ed25519PublicKey,
                payload: Any,
                signature: str | bytes) -> bool:
    if isinstance(signature, str):
        try:
            signature = _b64decode(signature, field="signature")
        except IdentityCorruptError:
            return False
    return verify_signature(public_key, canonical_json(payload), signature)


def verify_envelope(envelope: Mapping[str, Any], *,
                    public_key: bytes | Ed25519PublicKey | None = None,
                    expected_key_id: str | None = None,
                    expected_kind: str | None = None) -> bool:
    """Verify a signed envelope without trusting its embedded key id."""
    try:
        if not isinstance(envelope, Mapping):
            return False
        if envelope.get("version") != IDENTITY_SCHEMA:
            return False
        if "payload" not in envelope:
            return False
        kind = envelope.get("kind")
        if not isinstance(kind, str) or (expected_kind is not None and kind != expected_kind):
            return False
        candidate = public_key
        if candidate is None:
            candidate = _b64decode(envelope.get("public_key"), field="public_key")
        candidate_bytes = (
            candidate.public_bytes_raw() if isinstance(candidate, Ed25519PublicKey) else candidate
        )
        actual_id = key_id_for_public_key(candidate_bytes)
        if envelope.get("key_id") != actual_id:
            return False
        if expected_key_id is not None and actual_id != expected_key_id:
            return False
        signature = _b64decode(envelope.get("signature"), field="signature")
        body = {"kind": kind, "payload": envelope.get("payload"), "version": IDENTITY_SCHEMA}
        return verify_json(candidate, body, signature)
    except (IdentityError, ValueError, TypeError):
        return False


def verified_envelope_payload(envelope: Mapping[str, Any], **kwargs: Any) -> Any:
    """Return an envelope payload or raise :class:`IdentityVerificationError`."""
    if not verify_envelope(envelope, **kwargs):
        raise IdentityVerificationError("signed envelope did not verify")
    return envelope["payload"]


def sign_request(identity: Identity, request: Any) -> dict[str, Any]:
    return identity.sign_envelope(request, kind="request")


def verify_request(envelope: Mapping[str, Any], **kwargs: Any) -> Any:
    return verified_envelope_payload(envelope, expected_kind="request", **kwargs)


def sign_picture(identity: Identity, picture: Any) -> dict[str, Any]:
    return identity.sign_envelope(picture, kind="picture")


def verify_picture(envelope: Mapping[str, Any], **kwargs: Any) -> Any:
    return verified_envelope_payload(envelope, expected_kind="picture", **kwargs)


# Explicit aliases make the intended lifecycle discoverable to callers and
# preserve a small compatibility surface for daemon code that prefers a class
# factory or a verb-style function.
load_identity = load_or_create
get_identity = load_or_create
canonicalise_json = canonical_json


__all__ = [
    "IDENTITY_SCHEMA", "KEY_ALGORITHM", "KEY_ID_PREFIX",
    "Identity", "IdentityError", "IdentityUnsafeError", "IdentityCorruptError",
    "IdentityVerificationError", "canonical_json", "canonicalise_json",
    "key_id_for_public_key", "load_or_create", "load_identity", "get_identity",
    "verify_signature", "verify_json", "verify_envelope", "verified_envelope_payload",
    "sign_request", "verify_request", "sign_picture", "verify_picture",
]
