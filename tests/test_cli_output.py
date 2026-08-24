from io import StringIO
from unittest.mock import patch

import pytest

from spacepilot import cli


class _TTY(StringIO):
    def isatty(self):
        return True


def test_output_mode_precedence_and_auto_detection():
    cfg = {"output_mode": "live"}
    env = {"SPACEPILOT_OUTPUT_MODE": "plain"}
    assert cli.resolve_output_mode("live", cfg, environ=env, stdout=StringIO()) == "live"
    assert cli.resolve_output_mode(None, cfg, environ=env, stdout=_TTY()) == "plain"
    assert cli.resolve_output_mode(None, cfg, environ={}, stdout=StringIO()) == "live"
    assert cli.resolve_output_mode(None, {}, environ={}, stdout=StringIO()) == "plain"
    assert cli.resolve_output_mode(None, {}, environ={}, stdout=_TTY()) == "live"


@pytest.mark.parametrize("value", ["colourful", "", 3])
def test_invalid_output_mode_is_refused(value):
    with pytest.raises(ValueError, match="live, plain"):
        cli.resolve_output_mode(None, {"output_mode": value}, environ={}, stdout=StringIO())


def test_output_flags_work_after_a_subcommand_but_not_after_measure_separator():
    assert cli._extract_output_mode_flags(["models", "--plain"]) == (["models"], "plain")
    assert cli._extract_output_mode_flags(["--live", "models"]) == (["models"], "live")
    assert cli._extract_output_mode_flags(
        ["measure", "--model", "demo", "--metric", "x", "--", "tool", "--plain"]
    ) == (["measure", "--model", "demo", "--metric", "x", "--", "tool", "--plain"], None)
    with pytest.raises(ValueError, match="mutually exclusive"):
        cli._extract_output_mode_flags(["models", "--plain", "--live"])


def test_live_and_plain_progress_have_fact_parity():
    plain_stream = StringIO()
    live_stream = StringIO()
    facts = "[######------------------]  25.0%     4.5 MB/s"

    plain = cli.OutputRenderer("plain", stdout=plain_stream, environ={"NO_COLOR": "1"})
    live = cli.OutputRenderer("live", stdout=live_stream, environ={"NO_COLOR": "1"})
    plain.progress("Downloading", facts)
    live.progress("Downloading", facts)
    live.finish()

    assert "Downloading: " + facts in plain_stream.getvalue()
    assert "Downloading: " + facts in live_stream.getvalue()
    assert "\x1b[" not in live_stream.getvalue()


@pytest.mark.parametrize("argv", [["check", "--plain"], ["--plain", "check"]])
def test_check_alias_dispatches_to_doctor_with_resolved_output_mode(argv):
    with patch("spacepilot.cli.load_config", return_value={}), patch(
        "spacepilot.cli.cmd_doctor", return_value=0
    ) as doctor:
        assert cli.main(argv) == 0
    assert doctor.call_args.args[0].output_mode == "plain"


def test_pluto_wrapper_warns_and_preserves_main_exit_code(capsys):
    with patch("spacepilot.cli.main", return_value=7):
        assert cli.pluto_main() == 7
    assert capsys.readouterr().err.strip() == "pluto is deprecated; use spacepilot"
