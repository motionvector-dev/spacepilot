from __future__ import annotations

from datetime import datetime, timezone

from spacepilot import cli
from spacepilot.daemon.fleet import DaemonFleetAdmin, FleetRowFacts, FleetSnapshot


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


class FakeAdmin:
    def __init__(self):
        self.calls = []

    def init(self, name):
        self.calls.append(("init", name))
        return {"orders_version": 1}

    def add(self, selector):
        self.calls.append(("add", selector))
        return {"orders_version": 2}

    def join(self, author_key_id, author_selector, fleet_id=None):
        self.calls.append(("join", author_key_id, author_selector, fleet_id))
        return {"orders_version": 3}

    def list(self):
        self.calls.append(("list",))
        return FleetSnapshot(3, (
            FleetRowFacts("aurora", "aurora", "ship", "ready", NOW.isoformat(), 0, 3),
        )).to_wire()


def test_fleet_commands_use_local_admin_adapter_not_peer_network(monkeypatch, capsys):
    admin = FakeAdmin()
    monkeypatch.setattr(cli, "_fleet_admin_client", lambda: admin)
    monkeypatch.setattr("spacepilot.daemon.fleet.utc_now", lambda: NOW)

    assert cli.main(["fleet", "init", "home-ship"]) == 0
    assert cli.main(["fleet", "add", "aurora-tailnet"]) == 0
    assert cli.main(["fleet", "join", "--author-key-id", "author-1", "--author-selector", "author-tailnet"]) == 0
    assert cli.main(["fleet", "list"]) == 0

    assert admin.calls == [
        ("init", "home-ship"),
        ("add", "aurora-tailnet"),
        ("join", "author-1", "author-tailnet", None),
        ("list",),
    ]
    output = capsys.readouterr().out
    assert "aurora · ready" in output


def test_fleet_watch_shortcut_and_list_watch_use_the_same_watch_function(monkeypatch):
    admin = FakeAdmin()
    calls = []
    monkeypatch.setattr(cli, "_fleet_admin_client", lambda: admin)
    monkeypatch.setattr(
        cli, "_watch_fleet",
        lambda client, *, interval, output_mode: calls.append((client, interval, output_mode)) or 0,
    )

    assert cli.main(["fleet", "--watch", "--interval", "3"]) == 0
    assert cli.main(["fleet", "list", "--watch", "--interval", "4"]) == 0
    assert calls == [(admin, 3.0, "plain"), (admin, 4.0, "plain")]


def test_fleet_watch_rejects_non_positive_interval(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_fleet_admin_client", FakeAdmin)
    assert cli.main(["fleet", "list", "--watch", "--interval", "0"]) == 2
    assert "greater than zero" in capsys.readouterr().out


def test_fleet_admin_sends_only_selectors_over_the_mocked_local_uds_client():
    calls = []

    class MockDaemonClient:
        def _request(self, method, path, *, json=None):
            calls.append((method, path, json))
            return {"orders_version": 2}

    admin = DaemonFleetAdmin(MockDaemonClient())
    admin.add("aurora-tailnet")
    admin.join("v1:sha256:author", "author-tailnet", "fleet-uuid")

    assert calls == [
        ("POST", "/v1/fleet/add", {"selector": "aurora-tailnet"}),
        ("POST", "/v1/fleet/join", {
            "author_key_id": "v1:sha256:author",
            "author_selector": "author-tailnet",
            "fleet_id": "fleet-uuid",
        }),
    ]


def test_a_missing_daemon_socket_is_named_as_such_not_as_errno_2(tmp_path):
    """`[Errno 2] No such file or directory` never said which file, or what to do."""
    import pytest

    from spacepilot.substrate import DaemonClient, SubstrateError

    client = DaemonClient(tmp_path / "never-created.sock")
    with pytest.raises(SubstrateError) as caught:
        client.health()
    message = str(caught.value)
    assert "daemon is not running" in message
    assert "spacepilot daemon install" in message
    assert str(tmp_path / "never-created.sock") in message


def test_fleet_list_against_an_absent_daemon_exits_non_zero_with_that_message(
    monkeypatch, capsys, tmp_path
):
    """A failed command that exits 0 is undetectable from a script or a CI step."""
    socket_path = tmp_path / "absent.sock"
    monkeypatch.setattr("spacepilot.paths.daemon_socket_path", lambda: socket_path)

    assert cli.main(["fleet", "list"]) == 1
    out = capsys.readouterr().out
    assert "daemon is not running" in out
    assert "spacepilot daemon install" in out
    assert "Errno 2" not in out


def test_every_daemon_backed_fleet_action_exits_non_zero_when_the_daemon_is_absent(
    monkeypatch, tmp_path
):
    socket_path = tmp_path / "absent.sock"
    monkeypatch.setattr("spacepilot.paths.daemon_socket_path", lambda: socket_path)

    assert cli.main(["fleet", "init", "home-ship"]) == 1
    assert cli.main(["fleet", "add", "aurora-tailnet"]) == 1
    assert cli.main(["fleet", "list", "--json"]) == 1
    assert cli.main([
        "fleet", "join", "--author-key-id", "a", "--author-selector", "b",
    ]) == 1
