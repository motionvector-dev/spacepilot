"""Canonical CLI config migration is deliberately read-compatible only."""

from __future__ import annotations

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
