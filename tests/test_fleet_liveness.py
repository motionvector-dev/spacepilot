from __future__ import annotations

from datetime import datetime, timedelta, timezone

from spacepilot.daemon.fleet import (
    FleetManager,
    PictureUnreachable,
    PictureValidationError,
)


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def picture(at: datetime, state: str = "online"):
    return {
        "sampled_at": at.isoformat(),
        "workers": {"state": "fresh", "value": {"status": state}},
    }


def orders(version: int, *names: str, verified: bool = True):
    return {
        "version": version,
        "verified": verified,
        "members": [{"id": name, "name": name} for name in names],
    }


def test_fresh_valid_picture_is_ready_or_busy_and_keeps_placeholder_meter():
    replies = {"aurora": picture(NOW, "online"), "borealis": picture(NOW, "busy")}
    manager = FleetManager(fetch_picture=lambda member: replies[member.id],
                           verify_picture=lambda _member, value: value, clock=lambda: NOW)

    snapshot = manager.refresh(orders(1, "aurora", "borealis"))
    rows = {row.member_id: row for row in snapshot.rows}

    assert rows["aurora"].state == "ready"
    assert rows["borealis"].state == "busy"
    assert rows["aurora"].meter == "—"
    assert all(row.age_seconds == 0 for row in rows.values())


def test_unreachable_current_member_is_asleep_with_last_seen_age_not_gone():
    calls = 0

    def fetch(_member):
        nonlocal calls
        calls += 1
        if calls == 1:
            return picture(NOW)
        raise PictureUnreachable("tailnet peer did not answer")

    clock = iter((NOW, NOW + timedelta(seconds=18)))
    manager = FleetManager(fetch_picture=fetch, verify_picture=lambda _member, value: value,
                           clock=lambda: next(clock))
    manager.refresh(orders(1, "aurora"))
    row = manager.refresh(orders(1, "aurora")).rows[0]

    assert row.state == "asleep"
    assert row.last_seen_at == NOW.isoformat(timespec="seconds")
    assert row.age_seconds == 18
    assert "did not answer" in row.errors[0]


def test_gone_requires_a_newer_verified_orders_removal_transition():
    manager = FleetManager(fetch_picture=lambda _member: picture(NOW),
                           verify_picture=lambda _member, value: value, clock=lambda: NOW)
    manager.refresh(orders(1, "aurora", "borealis"))

    same_revision = manager.refresh(orders(1, "aurora"))
    assert {row.state for row in same_revision.rows} == {"unknown"}
    assert "without a newer" in same_revision.errors[0]

    removed = manager.refresh(orders(2, "aurora"))
    rows = {row.member_id: row for row in removed.rows}
    assert rows["aurora"].state == "ready"
    assert rows["borealis"].state == "gone"
    assert "signed ORDERS v2" in rows["borealis"].errors[0]


def test_signature_and_clock_failures_are_unknown_never_asleep_or_gone():
    manager = FleetManager(
        fetch_picture=lambda _member: picture(NOW),
        verify_picture=lambda _member, _picture: (_ for _ in ()).throw(PictureValidationError("bad signature")),
        clock=lambda: NOW,
    )
    row = manager.refresh(orders(1, "aurora")).rows[0]
    assert row.state == "unknown"
    assert "verification failed" in row.errors[0]

    bad_orders = manager.refresh(orders(2, "aurora", verified=False))
    assert all(row.state == "unknown" for row in bad_orders.rows)
    assert "ORDERS verification failed" in bad_orders.errors[0]

    broken_clock = FleetManager(fetch_picture=lambda _member: picture(NOW),
                                verify_picture=lambda _member, value: value,
                                clock=lambda: (_ for _ in ()).throw(OSError("clock unavailable")))
    clock_row = broken_clock.refresh(orders(1, "aurora")).rows[0]
    assert clock_row.state == "unknown"
    assert "clock failure" in clock_row.errors[0]


def test_missing_peer_auth_verifier_fails_closed_to_unknown():
    manager = FleetManager(fetch_picture=lambda _member: picture(NOW), clock=lambda: NOW)

    row = manager.refresh(orders(1, "aurora")).rows[0]

    assert row.state == "unknown"
    assert "no peer picture verifier" in row.errors[0]
