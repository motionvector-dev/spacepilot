"""The CLI must work run as a file, not only as a module.

`python spacepilot/cli.py runtimes check mflux` raised ModuleNotFoundError: No module
named 'spacepilot' — running a script inside the package puts that directory on
sys.path rather than the repo root, so the seven `from spacepilot.…` imports in
cli.py cannot resolve. The
`python -m spacepilot.cli` form always worked, which is why the break went unnoticed.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "argv",
    [
        [sys.executable, "spacepilot/cli.py", "runtimes", "list"],
        [sys.executable, "-m", "spacepilot.cli", "runtimes", "list"],
    ],
    ids=["as-a-file", "as-a-module"],
)
def test_runtimes_list_runs_both_ways(argv):
    proc = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "No module named 'spacepilot'" not in proc.stderr


def test_measure_refuses_to_record_a_failed_run(tmp_path):
    """A command that exited non-zero measured nothing; recording it would poison
    the store with the duration of a crash."""
    proc = subprocess.run(
        [sys.executable, "spacepilot/cli.py", "measure", "--model", "flux",
         "--metric", "seconds_per_image", "--", "/bin/sh", "-c", "exit 3"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 3
    assert "nothing recorded" in proc.stdout


def test_measure_needs_a_command():
    proc = subprocess.run(
        [sys.executable, "spacepilot/cli.py", "measure", "--model", "flux",
         "--metric", "seconds_per_image"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 1
    assert "Nothing to measure" in proc.stdout


def test_a_failed_measure_leaves_no_system_record(monkeypatch):
    """"nothing recorded" has to mean nothing.

    The system record was written before the command ran, so every failed
    measure still stamped the host into registry/systems/. On CI that put the
    runner's own Xeon into the shipped registry and broke the export test.
    """
    import argparse

    sys.path.insert(0, str(ROOT))
    import spacepilot.cli as cli
    from spacepilot.pluto import measurements as ms

    written = []
    monkeypatch.setattr(ms, "write_system", lambda s, root=None: written.append(s))

    args = argparse.Namespace(
        model="flux", metric="seconds_per_image",
        command_argv=["--", "/bin/sh", "-c", "exit 3"],
    )
    assert cli.cmd_measure(args) == 3
    assert written == []


def _measure(*extra, expect=0):
    proc = subprocess.run(
        [sys.executable, "spacepilot/cli.py", "measure", *extra],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == expect, proc.stdout + proc.stderr[-2000:]
    return proc.stdout


def test_realtime_factor_records_units_over_wall():
    """A rate metric is not wall/units. Recorded the other way round, the
    machine-written records were the reciprocal of the hand-written ones and
    nothing could average or rank the two together."""
    out = _measure("--model", "kokoro", "--metric", "realtime_factor",
                   "--units", "12.5", "--", "/bin/sh", "-c", "sleep 2.5")
    line = next(l for l in out.splitlines() if "realtime factor" in l)
    assert 4.0 < float(line.split()[-1]) < 6.0, line


def test_a_rate_metric_without_units_is_refused_before_the_run():
    out = _measure("--model", "kokoro", "--metric", "realtime_factor",
                   "--", "/bin/sh", "-c", "sleep 30", expect=1)
    assert "cannot produce it" in out


def test_an_unknown_metric_is_caught_before_the_command_runs():
    """Catching it at record time threw away a run that had already happened."""
    out = _measure("--model", "kokoro", "--metric", "rt_factor", "--units", "1",
                   "--", "/bin/sh", "-c", "sleep 30", expect=1)
    assert "Unknown metric" in out


def test_a_model_the_registry_never_heard_of_is_refused():
    """--model whisper-base-en used to file an orphan directory in silence."""
    out = _measure("--model", "whisper-base-en", "--metric", "realtime_factor",
                   "--units", "180", "--", "/bin/true", expect=1)
    assert "whisper-base-en" in out and "--allow-unknown-model" in out
