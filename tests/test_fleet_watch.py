from __future__ import annotations

from datetime import datetime, timedelta, timezone

from spacepilot import cli
from spacepilot.daemon.fleet import FleetRowFacts, FleetSnapshot, render_fleet_snapshot


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def test_render_recomputes_age_and_keeps_errors_versions_and_meter_in_one_fact_line():
    snapshot = FleetSnapshot(7, (
        FleetRowFacts(
            "aurora", "aurora", "ship", "asleep", (NOW - timedelta(seconds=75)).isoformat(),
            0, 7, version="daemon-1.2", meter="—", errors=("tailnet peer did not answer",),
        ),
    ))

    lines = render_fleet_snapshot(snapshot, now=NOW)

    assert lines == [
        "  ORDERS v7",
        "  aurora · asleep · last seen 1m ago · version daemon-1.2 · meter — · error: tailnet peer did not answer",
    ]
    assert snapshot.rows[0].age_seconds == 0  # rendering never mutates daemon facts


def test_each_frame_recomputes_age_from_last_seen_not_cached_age():
    snapshot = FleetSnapshot(1, (
        FleetRowFacts("aurora", "aurora", "ship", "asleep", NOW.isoformat(), 0, 1),
    ))

    first = render_fleet_snapshot(snapshot, now=NOW)[1]
    later = render_fleet_snapshot(snapshot, now=NOW + timedelta(seconds=22))[1]

    assert "last seen 0s ago" in first
    assert "last seen 22s ago" in later


def test_watch_never_leaves_a_stale_ready_picture_looking_ready():
    snapshot = FleetSnapshot(1, (
        FleetRowFacts("aurora", "aurora", "ship", "ready", NOW.isoformat(), 0, 1,
                      freshness_seconds=10),
    ))

    later = render_fleet_snapshot(snapshot, now=NOW + timedelta(seconds=11))[1]

    assert "· unknown · last seen 11s ago" in later
    assert "picture is stale; readiness is unknown" in later


class _Admin:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def list(self):
        return self.snapshot.to_wire()


def test_live_and_plain_watch_consume_identical_fact_lines(monkeypatch, capsys):
    snapshot = FleetSnapshot(4, (
        FleetRowFacts("aurora", "aurora", "ship", "asleep", (NOW - timedelta(seconds=8)).isoformat(),
                      0, 4, version="daemon-1", meter="—", errors=("unreachable",)),
    ))
    admin = _Admin(snapshot)
    monkeypatch.setattr("spacepilot.daemon.fleet.utc_now", lambda: NOW)
    sleeps = []

    cli._watch_fleet(admin, interval=2, output_mode="plain", sleep=sleeps.append, max_frames=1)
    plain = capsys.readouterr().out

    updates = []

    class FakeConsole:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def print(self, *_args):
            pass

    class FakeLive:
        def __init__(self, *_args, **kwargs):
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def update(self, rendered):
            updates.append(str(rendered))

    cli._watch_fleet(
        admin, interval=2, output_mode="live", sleep=sleeps.append, max_frames=1,
        live_factory=FakeLive, console_factory=FakeConsole,
    )

    facts = render_fleet_snapshot(snapshot, now=NOW)
    assert "\n".join(facts) in plain
    assert updates == ["\n".join(facts)]
    assert sleeps == [2, 2]


def test_live_watch_honors_no_color_without_becoming_an_alternate_screen(monkeypatch):
    snapshot = FleetSnapshot(1, ())
    admin = _Admin(snapshot)
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr("spacepilot.daemon.fleet.utc_now", lambda: NOW)
    observed = {}

    class FakeConsole:
        def __init__(self, **kwargs):
            observed["console"] = kwargs

        def print(self, *_args):
            pass

    class FakeLive:
        def __init__(self, *_args, **kwargs):
            observed["live"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def update(self, _rendered):
            pass

    cli._watch_fleet(admin, interval=2, output_mode="live", sleep=lambda _: None, max_frames=1,
                     live_factory=FakeLive, console_factory=FakeConsole)

    assert observed["console"]["no_color"] is True
    assert observed["live"]["screen"] is False


def test_live_watch_recomputes_last_seen_age_on_each_frame(monkeypatch):
    snapshot = FleetSnapshot(1, (
        FleetRowFacts("aurora", "aurora", "ship", "asleep", NOW.isoformat(), 0, 1),
    ))
    moments = iter((NOW, NOW + timedelta(seconds=9)))
    monkeypatch.setattr("spacepilot.daemon.fleet.utc_now", lambda: next(moments))
    updates = []

    class FakeLive:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def update(self, rendered):
            updates.append(str(rendered))

    class FakeConsole:
        def __init__(self, **_kwargs):
            pass

        def print(self, *_args):
            pass

    cli._watch_fleet(_Admin(snapshot), interval=2, output_mode="live", sleep=lambda _: None,
                     max_frames=2, live_factory=FakeLive, console_factory=FakeConsole)

    assert "last seen 0s ago" in updates[0]
    assert "last seen 9s ago" in updates[1]
