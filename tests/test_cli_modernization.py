"""Unit tests for SpacePilot CLI hierarchy modernization."""

from __future__ import annotations

import pytest
from spacepilot import __version__, cli


def test_cli_version_flag(capsys):
    """spacepilot --version prints package version."""
    parser = cli.build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert f"spacepilot {__version__}" in out


def test_cli_subparsers_list():
    """Verify clean top-level verb list matches the production architecture."""
    parser = cli.build_parser()
    actions = [a for a in parser._actions if a.dest == "command"]
    assert len(actions) == 1
    subparsers_action = actions[0]
    registered = set(subparsers_action.choices.keys())

    # Deprecated verbs must not be present
    assert "recipes" in registered
    assert "lora" not in registered
    assert "check" in registered
    assert "generate" not in registered
    assert "sync" not in registered
    assert "deploy" not in registered

    # Essential orchestrator verbs must be present
    expected_core = {
        "doctor",
        "probe",
        "serve",
        "status",
        "launch",
        "run",
        "download",
        "load",
        "unload",
        "models",
        "terminate",
        "bench",
    }
    for verb in expected_core:
        assert verb in registered, f"Expected '{verb}' in CLI subparsers"


def test_cli_bench_subcommands():
    """spacepilot bench provides measure, sweep, and silicon subcommands."""
    parser = cli.build_parser()
    args_measure = parser.parse_args(["bench", "measure", "--model", "flux", "--metric", "seconds_per_image"])
    assert args_measure.command == "bench"
    assert args_measure.bench_action == "measure"

    args_silicon = parser.parse_args(["bench", "silicon"])
    assert args_silicon.command == "bench"
    assert args_silicon.bench_action == "silicon"
