"""The per-user Ed25519 identity is a credential, not ordinary app state."""

from __future__ import annotations

import concurrent.futures
import json
import os
import stat
from pathlib import Path

import pytest

from spacepilot import paths
from spacepilot.daemon.identity import (
    IdentityCorruptError,
    IdentityUnsafeError,
    IdentityVerificationError,
    canonical_json,
    key_id_for_public_key,
    load_or_create,
    sign_picture,
    sign_request,
    verify_envelope,
    verify_picture,
    verify_request,
)


@pytest.fixture()
def identity_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SPACEPILOT_DATA_DIR", str(tmp_path / "data"))
    return tmp_path / "data"


def test_identity_lives_in_user_data_even_in_checkout(identity_home):
    identity = load_or_create()
    assert identity.path == identity_home / "identity" / "identity.json"
    assert identity.path != Path(__file__).parents[1] / "spacepilot" / "identity.json"
    assert stat.S_IMODE(identity.path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(identity.path.stat().st_mode) == 0o600


def test_identity_is_stable_across_loads_and_key_id_is_versioned_sha256(identity_home):
    first = load_or_create()
    second = load_or_create()
    assert first.key_id == second.key_id
    assert first.public_key == second.public_key
    assert first.key_id == key_id_for_public_key(first.public_key)
    assert first.key_id.startswith("v1:sha256:")
    assert len(first.key_id.rsplit(":", 1)[-1]) == 64


def test_first_create_is_atomic_for_concurrent_callers(identity_home):
    def create():
        loaded = load_or_create()
        return loaded.key_id, loaded.public_key

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        values = list(pool.map(lambda _: create(), range(8)))
    assert len({value[0] for value in values}) == 1
    assert len({value[1] for value in values}) == 1


def test_canonical_json_and_signed_request_picture_envelopes(identity_home):
    identity = load_or_create()
    assert canonical_json({"b": 2, "a": "é"}) == '{"a":"é","b":2}'.encode()
    request = sign_request(identity, {"z": [1, 2], "a": True})
    picture = sign_picture(identity, {"observed_at": 12, "state": "ready"})
    assert verify_envelope(request)
    assert identity.verify_envelope(request, expected_kind="request")
    assert verify_request(request) == request["payload"]
    assert verify_picture(picture) == picture["payload"]
    with pytest.raises(IdentityVerificationError):
        verify_picture(request)
    request["payload"]["z"].append(3)
    with pytest.raises(IdentityVerificationError):
        verify_request(request)


def test_tampered_raw_signature_is_false(identity_home):
    identity = load_or_create()
    message = b"hello"
    signature = identity.sign(message)
    assert identity.verify(message, signature)
    assert not identity.verify(message + b"!", signature)


def test_existing_symlink_is_rejected_without_rotation(identity_home):
    directory = paths.identity_dir()
    directory.mkdir(parents=True)
    os.chmod(directory, 0o700)
    target = identity_home / "elsewhere.json"
    target.write_text("{}")
    os.symlink(target, paths.identity_path())
    with pytest.raises(IdentityUnsafeError):
        load_or_create()
    assert paths.identity_path().is_symlink()


def test_corrupt_record_is_rejected_without_rotation(identity_home):
    identity = load_or_create()
    identity.path.write_text("not-json")
    os.chmod(identity.path, 0o600)
    with pytest.raises(IdentityCorruptError):
        load_or_create()


@pytest.mark.skipif(not hasattr(os, "getuid"), reason="POSIX ownership checks")
def test_wrong_owner_is_rejected(identity_home):
    if os.getuid() == 0:
        pytest.skip("root can chown back to itself, so ownership assertion is not meaningful")
    identity = load_or_create()
    try:
        os.chown(identity.path, os.getuid() + 1, -1)
    except PermissionError:
        pytest.skip("test process cannot change file ownership")
    with pytest.raises(IdentityUnsafeError):
        load_or_create()


def test_unsafe_permissions_are_rejected(identity_home):
    identity = load_or_create()
    os.chmod(identity.path.parent, 0o755)
    with pytest.raises(IdentityUnsafeError):
        load_or_create()
    os.chmod(identity.path.parent, 0o700)
    os.chmod(identity.path, 0o644)
    with pytest.raises(IdentityUnsafeError):
        load_or_create()
