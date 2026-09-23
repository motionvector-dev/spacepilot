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


def _runtime_rows():
    return [
        {"state": "installed (external env)", "id": "desert-ant",
         "serves": ["transcription", "audio", "text"], "backends": ["cpu", "metal"],
         "version": "0.1.1 (desert-ant-core 3.1.0)", "note": None},
        {"state": "installed", "id": "llama-cpp", "serves": ["text", "vision"],
         "backends": ["metal", "cuda", "cpu"], "version": "0.3.35", "note": None},
        {"state": "n/a here", "id": "bitnet-cpp", "serves": ["text"],
         "backends": ["cpu"], "version": None, "note": None},
    ]


def test_runtimes_table_columns_never_collide():
    """`transcription,audio,text` ran straight into `cpu,metal`.

    SERVES had a fixed 16-character width and no guard, so the table stopped
    being a table on the one row a reader most needed to read.
    """
    lines = cli._runtimes_table(_runtime_rows())
    header = lines[0]
    starts = {name: header.index(name)
              for name in ("STATE", "RUNTIME", "SERVES", "BACKENDS", "VERSION")}

    for row, line in zip(_runtime_rows(), lines[1:]):
        for name, cell in (("RUNTIME", row["id"]),
                           ("SERVES", ",".join(row["serves"])),
                           ("BACKENDS", ",".join(row["backends"])),
                           ("VERSION", row["version"] or "-")):
            assert line[starts[name]:].startswith(cell), (
                f"{name} cell {cell!r} does not begin at its header column:\n"
                f"{header}\n{line}"
            )


def test_runtimes_table_row_cells_stay_in_their_own_column():
    lines = cli._runtimes_table(_runtime_rows())
    header = lines[0]
    long_row = lines[1]
    # Nothing may be written in the gutter before the next column begins.
    assert long_row[header.index("BACKENDS") - 1] == " "
    assert long_row[header.index("VERSION") - 1] == " "


def test_runtimes_table_notes_hang_under_the_row_they_belong_to():
    rows = _runtime_rows()
    rows[2]["note"] = "needs Python >=3.10,<3.11; this interpreter is 3.11.15"
    lines = cli._runtimes_table(rows)
    assert lines[-1].strip() == rows[2]["note"]
