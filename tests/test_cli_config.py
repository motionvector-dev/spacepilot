"""Canonical CLI config migration is deliberately read-compatible only."""

from __future__ import annotations

import pytest

import json
import stat

from spacepilot import cli


def test_canonical_config_wins_over_legacy_when_both_exist(tmp_path, monkeypatch):
    canonical = tmp_path / ".spacepilot_config.json"
    legacy = tmp_path / ".pluto_config.json"
    canonical.write_text(json.dumps({"aws_profile": "canonical-profile"}))
    legacy.write_text(json.dumps({"aws_profile": "legacy-profile"}))
    monkeypatch.setattr(cli, "CONFIG_FILE", canonical)
    monkeypatch.setattr(cli, "LEGACY_CONFIG_FILE", legacy)

    assert cli.load_config()["aws_profile"] == "canonical-profile"


def test_legacy_config_is_read_only_when_canonical_is_absent(tmp_path, monkeypatch):
    canonical = tmp_path / ".spacepilot_config.json"
    legacy = tmp_path / ".pluto_config.json"
    legacy.write_text(json.dumps({"aws_profile": "legacy-profile"}))
    monkeypatch.setattr(cli, "CONFIG_FILE", canonical)
    monkeypatch.setattr(cli, "LEGACY_CONFIG_FILE", legacy)

    assert cli.load_config()["aws_profile"] == "legacy-profile"
    cli.save_config({"aws_profile": "canonical-profile"})

    assert json.loads(canonical.read_text())["aws_profile"] == "canonical-profile"
    assert json.loads(legacy.read_text())["aws_profile"] == "legacy-profile"


def test_malformed_canonical_config_does_not_fall_back_to_legacy(tmp_path, monkeypatch):
    canonical = tmp_path / ".spacepilot_config.json"
    legacy = tmp_path / ".pluto_config.json"
    canonical.write_text("not json")
    legacy.write_text(json.dumps({"aws_profile": "legacy-profile"}))
    monkeypatch.setattr(cli, "CONFIG_FILE", canonical)
    monkeypatch.setattr(cli, "LEGACY_CONFIG_FILE", legacy)

    assert cli.load_config()["aws_profile"] == cli.DEFAULT_CONFIG["aws_profile"]


def test_save_config_is_atomic_private_and_leaves_no_temporary_file(tmp_path, monkeypatch):
    canonical = tmp_path / ".spacepilot_config.json"
    monkeypatch.setattr(cli, "CONFIG_FILE", canonical)

    cli.save_config({"output_mode": "plain"})

    assert json.loads(canonical.read_text()) == {"output_mode": "plain"}
    assert stat.S_IMODE(canonical.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".spacepilot_config.json.*.tmp"))


def test_a_tampered_orders_file_speaks_instead_of_vanishing(tmp_path, monkeypatch, capsys):
    """A failed signature is the design working. It must not render as absence.

    _load_declared_provider_rates used to swallow every exception into an empty
    tuple and log at DEBUG, so `spacepilot models` printed output identical to
    "this machine has no fleet" — the detection fired and the screen said
    nothing.
    """
    import spacepilot.cli as cli

    bad = tmp_path / "ORDERS.yaml"
    bad.write_text("schema: 1\nthis: is not a signed orders file\n")
    monkeypatch.setattr(cli, "fleet_orders_path", lambda: bad)

    providers, failure = cli._load_declared_provider_rates()
    assert providers == ()
    assert failure, "a tampered ORDERS must report why, not return a bare empty tuple"

    cli._print_provider_rates(providers, failure)
    out = capsys.readouterr().out
    assert "PROVIDERS — unavailable" in out
    assert "did not verify" in out
    assert "not an absence" in out


def test_a_genuinely_absent_orders_file_stays_quiet(tmp_path, monkeypatch, capsys):
    """No fleet is not an error, and must not grow a scary banner."""
    import spacepilot.cli as cli

    monkeypatch.setattr(cli, "fleet_orders_path", lambda: tmp_path / "nothing.yaml")
    providers, failure = cli._load_declared_provider_rates()
    assert providers == ()
    assert failure is None

    cli._print_provider_rates(providers, failure)
    assert capsys.readouterr().out == ""


def _parsed(argv):
    """Capture the Namespace `main` builds, without running a command."""
    import argparse
    import spacepilot.cli as cli
    from unittest import mock

    real = argparse.ArgumentParser.parse_args
    box = {}

    def spy(self, *a, **k):
        box["ns"] = real(self, *a, **k)
        raise SystemExit(0)

    with mock.patch.object(argparse.ArgumentParser, "parse_args", spy):
        with pytest.raises(SystemExit):
            cli.main(argv)
    return box["ns"]


def test_fleet_watch_flags_survive_being_given_before_the_subcommand():
    """`fleet --watch --interval 5 list` used to become a single 2s snapshot.

    argparse writes a subparser's default over whatever the parent already
    parsed, so both flags were dropped without a word. A silently ignored flag
    is the CLI telling you it did something it did not do.
    """
    before = _parsed(["fleet", "--watch", "--interval", "5", "list"])
    after = _parsed(["fleet", "list", "--watch", "--interval", "5"])

    for ns in (before, after):
        assert ns.fleet_action == "list"
        assert ns.watch is True
        assert ns.interval == 5.0

    plain = _parsed(["fleet", "list"])
    assert plain.watch is False
    assert plain.interval == 2.0
